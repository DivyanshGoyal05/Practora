from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import re
import uuid
import asyncio
import secrets
import logging
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, Query
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr

from email_service import (
    send_email,
    render_booking_confirmed_customer,
    render_booking_confirmed_pro,
    render_booking_rescheduled,
    render_booking_cancelled,
)
from scheduler import run_scheduler, parse_booking_dt, IST
from razorpay_service import (
    get_settings as rp_get_settings,
    ensure_plan as rp_ensure_plan,
    create_subscription_for_user as rp_create_subscription,
    cancel_subscription as rp_cancel_subscription,
    verify_webhook_signature as rp_verify_webhook,
    handle_webhook_event as rp_handle_webhook,
    user_has_platform_access as rp_has_access,
    is_configured as rp_is_configured,
    TRIAL_DAYS,
    DEFAULT_SUBSCRIPTION_AMOUNT_INR,
)

# --- Setup -----------------------------------------------------------
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALG = "HS256"
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")

app = FastAPI(title="Practora API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("practora")

CATEGORIES = ["Astrologer", "Doctor", "Therapist", "Dietician", "Coach", "Yoga Teacher", "Tutor", "Consultant"]

# --- Constants -------------------------------------------------------
class Status:
    CONFIRMED = "CONFIRMED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"

ACTIVE_STATUSES = [Status.CONFIRMED, Status.RESCHEDULED]
TERMINAL_STATUSES = [Status.CANCELLED, Status.COMPLETED, Status.NO_SHOW]

class Action:
    BOOKING_CREATED = "BOOKING_CREATED"
    BOOKING_CONFIRMED = "BOOKING_CONFIRMED"
    BOOKING_RESCHEDULED = "BOOKING_RESCHEDULED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"
    BOOKING_COMPLETED = "BOOKING_COMPLETED"
    BOOKING_NO_SHOW = "BOOKING_NO_SHOW"
    REMINDER_SENT_24H = "REMINDER_SENT_24H"
    REMINDER_SENT_1H = "REMINDER_SENT_1H"
    MEETING_UPDATED = "MEETING_UPDATED"

# --- Helpers ---------------------------------------------------------
def now_utc():
    return datetime.now(timezone.utc)

def now_iso():
    return now_utc().isoformat()

def slugify(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")

def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def create_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email, "exp": now_utc() + timedelta(days=7), "type": "access"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def serialize_user(u: dict) -> dict:
    return {
        "id": u["id"], "email": u["email"], "name": u["name"], "role": u.get("role", "professional"),
        "slug": u.get("slug"), "bio": u.get("bio", ""), "category": u.get("category", ""),
        "photo_url": u.get("photo_url", ""), "experience": u.get("experience", ""),
        "languages": u.get("languages", []), "whatsapp": u.get("whatsapp", ""),
        "instagram": u.get("instagram", ""), "website": u.get("website", ""),
        "meet_link": u.get("meet_link", ""),
        "policies": u.get("policies", default_policies()),
        "subscription_status": u.get("subscription_status", "none"),
        "subscription_id": u.get("subscription_id"),
        "subscription_amount_inr": u.get("subscription_amount_inr"),
        "subscription_current_end": u.get("subscription_current_end"),
        "subscription_charge_at": u.get("subscription_charge_at"),
        "subscription_last_payment_at": u.get("subscription_last_payment_at"),
        "subscription_cancel_at_cycle_end": u.get("subscription_cancel_at_cycle_end", False),
        "trial_ends_at": u.get("trial_ends_at"),
        "created_at": u.get("created_at"),
    }

def default_policies() -> dict:
    return {
        "reschedule_window_hours": 12,
        "cancel_window_hours": 24,
        "reschedule_limit": 2,
    }

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"id": payload["sub"]})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    user.pop("password_hash", None)
    user.pop("_id", None)
    return user

async def log_activity(booking_id: str, action_type: str, actor_type: str, actor_id: Optional[str] = None, metadata: Optional[dict] = None):
    """Append an immutable audit entry."""
    await db.booking_activities.insert_one({
        "id": str(uuid.uuid4()),
        "booking_id": booking_id,
        "action_type": action_type,
        "actor_type": actor_type,  # customer | professional | system | admin
        "actor_id": actor_id,
        "metadata": metadata or {},
        "created_at": now_iso(),
    })

def booking_manage_url(booking: dict) -> str:
    base = FRONTEND_URL or ""
    return f"{base}/booking/{booking['id']}/manage?token={booking.get('customer_access_token', '')}"

def booking_pro_url(booking: dict) -> str:
    base = FRONTEND_URL or ""
    return f"{base}/dashboard/bookings/{booking['id']}"

def compute_end_time(start_time: str, duration_min: int) -> str:
    sh, sm = map(int, start_time.split(":"))
    total = sh * 60 + sm + duration_min
    return f"{total // 60:02d}:{total % 60:02d}"

def booking_start_dt(b: dict) -> datetime:
    return parse_booking_dt(b["date"], b["start_time"])

# --- Pydantic models -------------------------------------------------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=2)
    slug: str = Field(min_length=3, max_length=40)
    category: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    category: Optional[str] = None
    photo_url: Optional[str] = None
    experience: Optional[str] = None
    languages: Optional[List[str]] = None
    whatsapp: Optional[str] = None
    instagram: Optional[str] = None
    website: Optional[str] = None
    meet_link: Optional[str] = None

class PoliciesIn(BaseModel):
    reschedule_window_hours: int = Field(ge=0, le=720)
    cancel_window_hours: int = Field(ge=0, le=720)
    reschedule_limit: int = Field(ge=0, le=20)

class ServiceIn(BaseModel):
    name: str
    description: str = ""
    duration_min: int = Field(ge=5, le=480)
    price: float = Field(ge=0)
    cover_image: str = ""
    meeting_mode: str = Field(default="video", pattern="^(video|in_person|phone)$")
    meeting_details: str = ""  # default video link OR clinic address OR phone number

class ScheduleDay(BaseModel):
    enabled: bool = False
    start: str = "09:00"
    end: str = "18:00"

class ScheduleIn(BaseModel):
    days: Dict[str, ScheduleDay]
    buffer_min: int = Field(ge=0, le=120, default=15)
    blocked_dates: List[str] = []

class BookingIn(BaseModel):
    service_id: str
    date: str
    start_time: str
    customer_name: str = Field(min_length=2)
    customer_email: EmailStr
    customer_phone: str = ""
    notes: str = ""
    intake_answers: List[Dict[str, str]] = []  # [{question_id, answer}]

class RescheduleIn(BaseModel):
    date: str
    start_time: str
    reason: str = ""

class CancelIn(BaseModel):
    reason: str = ""

class NoShowIn(BaseModel):
    reason: str = ""

# --- Intake form ----------------------------------------------------
ALLOWED_QUESTION_TYPES = {
    "short_text", "long_text", "dropdown", "email", "phone", "url",
    # Reserved for future: "file", "checkbox", "multi_choice", "date", "signature", "rating"
}

class IntakeQuestion(BaseModel):
    id: Optional[str] = None  # generated if missing
    text: str = Field(min_length=1, max_length=500)
    type: str = "short_text"
    required: bool = False
    options: List[str] = []  # only used for dropdown / multi_choice

class IntakeFormIn(BaseModel):
    questions: List[IntakeQuestion] = []

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def validate_intake_answer(q_type: str, answer: str) -> Optional[str]:
    """Returns error string if invalid, else None."""
    if q_type == "email" and not EMAIL_RE.match(answer):
        return "Invalid email address"
    if q_type == "url" and not URL_RE.match(answer):
        return "Must be a URL starting with http:// or https://"
    if q_type == "phone" and len(re.sub(r"\D", "", answer)) < 6:
        return "Invalid phone number"
    return None

# --- Auth ------------------------------------------------------------
@api.post("/auth/register")
async def register(body: RegisterIn, response: Response):
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    slug = slugify(body.slug)
    if not slug:
        raise HTTPException(400, "Invalid slug")
    if await db.users.find_one({"slug": slug}):
        raise HTTPException(400, "This URL is already taken")

    user_id = str(uuid.uuid4())
    trial_ends = (now_utc() + timedelta(days=TRIAL_DAYS)).isoformat()
    user_doc = {
        "id": user_id, "email": email, "password_hash": hash_password(body.password),
        "name": body.name.strip(), "role": "professional", "slug": slug, "category": body.category,
        "bio": "", "photo_url": "", "experience": "", "languages": [],
        "whatsapp": "", "instagram": "", "website": "", "meet_link": "",
        "policies": default_policies(),
        "subscription_status": "trial",
        "subscription_id": None,
        "subscription_amount_inr": None,
        "trial_ends_at": trial_ends,
        "created_at": now_iso(),
    }
    await db.users.insert_one(user_doc)
    await db.schedules.insert_one({
        "pro_id": user_id,
        "days": {
            "mon": {"enabled": True, "start": "09:00", "end": "18:00"},
            "tue": {"enabled": True, "start": "09:00", "end": "18:00"},
            "wed": {"enabled": True, "start": "09:00", "end": "18:00"},
            "thu": {"enabled": True, "start": "09:00", "end": "18:00"},
            "fri": {"enabled": True, "start": "09:00", "end": "18:00"},
            "sat": {"enabled": False, "start": "10:00", "end": "14:00"},
            "sun": {"enabled": False, "start": "10:00", "end": "14:00"},
        },
        "buffer_min": 15, "blocked_dates": [],
    })
    token = create_token(user_id, email)
    response.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 7, path="/")
    return {"user": serialize_user(user_doc), "token": token}

@api.post("/auth/login")
async def login(body: LoginIn, response: Response):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    token = create_token(user["id"], email)
    response.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 7, path="/")
    return {"user": serialize_user(user), "token": token}

@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}

@api.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return serialize_user(user)

# --- Profile ---------------------------------------------------------
@api.put("/me/profile")
async def update_profile(body: ProfileUpdate, user=Depends(get_current_user)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if updates:
        await db.users.update_one({"id": user["id"]}, {"$set": updates})
    fresh = await db.users.find_one({"id": user["id"]})
    return serialize_user(fresh)

@api.get("/me/slug-available")
async def slug_available(slug: str = Query(...)):
    s = slugify(slug)
    if not s or len(s) < 3:
        return {"available": False, "slug": s}
    existing = await db.users.find_one({"slug": s})
    return {"available": existing is None, "slug": s}

@api.get("/me/policies")
async def get_policies(user=Depends(get_current_user)):
    return user.get("policies", default_policies())

@api.put("/me/policies")
async def update_policies(body: PoliciesIn, user=Depends(get_current_user)):
    await db.users.update_one({"id": user["id"]}, {"$set": {"policies": body.model_dump()}})
    return body.model_dump()

# --- Services --------------------------------------------------------
@api.get("/me/services")
async def list_my_services(user=Depends(get_current_user)):
    return await db.services.find({"pro_id": user["id"]}, {"_id": 0}).to_list(500)

@api.post("/me/services")
async def create_service(body: ServiceIn, user=Depends(get_current_user)):
    doc = {"id": str(uuid.uuid4()), "pro_id": user["id"], **body.model_dump(), "created_at": now_iso()}
    await db.services.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.put("/me/services/{service_id}")
async def update_service(service_id: str, body: ServiceIn, user=Depends(get_current_user)):
    res = await db.services.update_one({"id": service_id, "pro_id": user["id"]}, {"$set": body.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(404, "Service not found")
    return await db.services.find_one({"id": service_id}, {"_id": 0})

@api.delete("/me/services/{service_id}")
async def delete_service(service_id: str, user=Depends(get_current_user)):
    await db.services.delete_one({"id": service_id, "pro_id": user["id"]})
    return {"ok": True}

# --- Intake form (per service) --------------------------------------
@api.get("/me/services/{service_id}/intake-form")
async def get_intake_form(service_id: str, user=Depends(get_current_user)):
    svc = await db.services.find_one({"id": service_id, "pro_id": user["id"]}, {"_id": 0})
    if not svc:
        raise HTTPException(404, "Service not found")
    return {"questions": svc.get("intake_questions", [])}

@api.put("/me/services/{service_id}/intake-form")
async def update_intake_form(service_id: str, body: IntakeFormIn, user=Depends(get_current_user)):
    if len(body.questions) > 20:
        raise HTTPException(400, "Maximum 20 questions per service")
    cleaned = []
    for q in body.questions:
        if q.type not in ALLOWED_QUESTION_TYPES:
            raise HTTPException(400, f"Unsupported question type: {q.type}")
        if q.type == "dropdown" and not q.options:
            raise HTTPException(400, f"Dropdown '{q.text}' must have at least one option")
        cleaned.append({
            "id": q.id or str(uuid.uuid4()),
            "text": q.text.strip(),
            "type": q.type,
            "required": q.required,
            "options": [o.strip() for o in q.options if o.strip()] if q.type == "dropdown" else [],
        })
    res = await db.services.update_one(
        {"id": service_id, "pro_id": user["id"]},
        {"$set": {"intake_questions": cleaned}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Service not found")
    return {"questions": cleaned}

# Public read of intake form (used during booking flow)
@api.get("/p/{slug}/services/{service_id}/intake-form")
async def public_intake_form(slug: str, service_id: str):
    pro = await db.users.find_one({"slug": slug.lower()})
    if not pro:
        raise HTTPException(404, "Profile not found")
    svc = await db.services.find_one({"id": service_id, "pro_id": pro["id"]}, {"_id": 0})
    if not svc:
        raise HTTPException(404, "Service not found")
    return {"questions": svc.get("intake_questions", [])}

# --- Schedule --------------------------------------------------------
@api.get("/me/schedule")
async def get_my_schedule(user=Depends(get_current_user)):
    return await db.schedules.find_one({"pro_id": user["id"]}, {"_id": 0})

@api.put("/me/schedule")
async def update_my_schedule(body: ScheduleIn, user=Depends(get_current_user)):
    await db.schedules.update_one(
        {"pro_id": user["id"]},
        {"$set": {**body.model_dump(), "pro_id": user["id"]}},
        upsert=True,
    )
    return await db.schedules.find_one({"pro_id": user["id"]}, {"_id": 0})

# --- Pro: bookings list & detail ------------------------------------
async def _enrich_booking(b: dict) -> dict:
    svc = await db.services.find_one({"id": b["service_id"]}, {"_id": 0})
    b["service"] = svc or {}
    return b

@api.get("/me/bookings")
async def my_bookings(user=Depends(get_current_user)):
    docs = await db.bookings.find({"pro_id": user["id"]}, {"_id": 0}).sort("date", -1).to_list(500)
    for d in docs:
        await _enrich_booking(d)
    return docs

@api.get("/me/bookings/{booking_id}/reschedule-slots")
async def my_booking_reschedule_slots(booking_id: str, date: str = Query(...), user=Depends(get_current_user)):
    b = await db.bookings.find_one({"id": booking_id, "pro_id": user["id"]}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Booking not found")
    return {"slots": await _available_slots(user["id"], date, b["duration_min"], exclude_booking_id=b["id"])}

@api.get("/me/bookings/{booking_id}")
async def my_booking_detail(booking_id: str, user=Depends(get_current_user)):
    b = await db.bookings.find_one({"id": booking_id, "pro_id": user["id"]}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Booking not found")
    await _enrich_booking(b)
    activities = await db.booking_activities.find(
        {"booking_id": booking_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    return {"booking": b, "activities": activities, "policies": user.get("policies", default_policies())}

@api.get("/me/stats")
async def my_stats(user=Depends(get_current_user)):
    bookings_all = await db.bookings.find({"pro_id": user["id"]}, {"_id": 0}).to_list(2000)
    today = now_utc().date().isoformat()
    revenue = sum(b.get("price", 0) for b in bookings_all if b.get("status") != Status.CANCELLED)
    upcoming = sum(1 for b in bookings_all if b.get("date", "") >= today and b.get("status") in ACTIVE_STATUSES)
    total = len([b for b in bookings_all if b.get("status") != Status.CANCELLED])
    emails = [b.get("customer_email") for b in bookings_all]
    seen, dup = set(), 0
    for e in emails:
        if e in seen:
            dup += 1
        else:
            seen.add(e)
    return {"total_revenue": round(revenue, 2), "upcoming_sessions": upcoming,
            "total_bookings": total, "repeat_customers": dup}

# --- Slot generation --------------------------------------------------
def _gen_day_slots(start: str, end: str, duration: int, buffer_: int) -> List[str]:
    sh, sm = map(int, start.split(":"))
    eh, em = map(int, end.split(":"))
    cur, end_min = sh * 60 + sm, eh * 60 + em
    step = duration + buffer_
    out = []
    while cur + duration <= end_min:
        out.append(f"{cur // 60:02d}:{cur % 60:02d}")
        cur += step
    return out

async def _available_slots(pro_id: str, date: str, duration_min: int, exclude_booking_id: Optional[str] = None) -> List[str]:
    schedule = await db.schedules.find_one({"pro_id": pro_id}, {"_id": 0}) or {}
    try:
        d = datetime.fromisoformat(date).date()
    except Exception:
        raise HTTPException(400, "Invalid date")
    if date in schedule.get("blocked_dates", []):
        return []
    day_key = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][d.weekday()]
    day_cfg = schedule.get("days", {}).get(day_key, {})
    if not day_cfg.get("enabled"):
        return []
    all_slots = _gen_day_slots(day_cfg.get("start", "09:00"), day_cfg.get("end", "18:00"),
                               duration_min, schedule.get("buffer_min", 15))
    q = {"pro_id": pro_id, "date": date, "status": {"$nin": [Status.CANCELLED]}}
    if exclude_booking_id:
        q["id"] = {"$ne": exclude_booking_id}
    booked_docs = await db.bookings.find(q, {"_id": 0}).to_list(500)
    booked = {b["start_time"] for b in booked_docs}

    today_iso = now_utc().date().isoformat()
    if date == today_iso:
        now_min = now_utc().hour * 60 + now_utc().minute
        all_slots = [s for s in all_slots if (int(s[:2]) * 60 + int(s[3:])) > now_min]
    return [s for s in all_slots if s not in booked]

# --- Public profile + booking creation ------------------------------
@api.get("/p/{slug}")
async def public_profile(slug: str):
    user = await db.users.find_one({"slug": slug.lower()})
    if not user:
        raise HTTPException(404, "Profile not found")
    services = await db.services.find({"pro_id": user["id"]}, {"_id": 0}).to_list(200)
    has_access, _reason = rp_has_access(user)
    return {
        "professional": serialize_user(user),
        "services": services,
        "booking_enabled": has_access,
    }

@api.get("/p/{slug}/slots")
async def public_slots(slug: str, date: str = Query(...), service_id: str = Query(...)):
    user = await db.users.find_one({"slug": slug.lower()})
    if not user:
        raise HTTPException(404, "Profile not found")
    service = await db.services.find_one({"id": service_id, "pro_id": user["id"]}, {"_id": 0})
    if not service:
        raise HTTPException(404, "Service not found")
    return {"slots": await _available_slots(user["id"], date, service["duration_min"])}

@api.post("/p/{slug}/book")
async def public_book(slug: str, body: BookingIn):
    user = await db.users.find_one({"slug": slug.lower()})
    if not user:
        raise HTTPException(404, "Profile not found")
    # Access gate — trial OR active subscription
    allowed, _reason = rp_has_access(user)
    if not allowed:
        raise HTTPException(402, "This professional is not accepting bookings right now.")
    service = await db.services.find_one({"id": body.service_id, "pro_id": user["id"]}, {"_id": 0})
    if not service:
        raise HTTPException(404, "Service not found")
    conflict = await db.bookings.find_one({
        "pro_id": user["id"], "date": body.date, "start_time": body.start_time,
        "status": {"$nin": [Status.CANCELLED]},
    })
    if conflict:
        raise HTTPException(409, "This slot is no longer available")

    # --- Intake form validation + snapshot ---
    questions = service.get("intake_questions", []) or []
    answer_map = {a.get("question_id"): (a.get("answer") or "").strip() for a in body.intake_answers}
    snapshot = []
    for q in questions:
        ans = answer_map.get(q["id"], "")
        if q.get("required") and not ans:
            raise HTTPException(400, f"'{q['text']}' is required")
        if ans:
            if q["type"] == "dropdown":
                allowed = q.get("options", []) or []
                if ans not in allowed:
                    raise HTTPException(400, f"'{q['text']}': invalid option")
            else:
                err = validate_intake_answer(q["type"], ans)
                if err:
                    raise HTTPException(400, f"{q['text']}: {err}")
        snapshot.append({
            "question_id": q["id"],
            "question_text": q["text"],
            "question_type": q["type"],
            "answer": ans,
        })

    end_time = compute_end_time(body.start_time, service["duration_min"])
    svc_mode = service.get("meeting_mode") or "video"
    svc_details = service.get("meeting_details") or ""
    # If service has no default and pro has a legacy static meet_link, use it (video mode only)
    if svc_mode == "video" and not svc_details:
        svc_details = user.get("meet_link", "") or ""
    booking = {
        "id": str(uuid.uuid4()),
        "pro_id": user["id"],
        "service_id": service["id"],
        "service_name": service["name"],
        "date": body.date,
        "start_time": body.start_time,
        "end_time": end_time,
        "duration_min": service["duration_min"],
        "price": service["price"],
        "customer_name": body.customer_name,
        "customer_email": body.customer_email.lower(),
        "customer_phone": body.customer_phone,
        "notes": body.notes,
        "meeting_mode": svc_mode,
        "meeting_details": svc_details,
        "meet_link": svc_details if svc_mode == "video" else "",  # kept for backward-compat
        "status": Status.CONFIRMED,
        "customer_access_token": secrets.token_urlsafe(24),
        "reminder_24h_sent": False,
        "reminder_1h_sent": False,
        "reschedule_count": 0,
        "cancel_reason": "",
        "reschedule_reason": "",
        "completed_at": None,
        "intake_answers": snapshot,
        # payment placeholder (decoupled from lifecycle)
        "payment_status": "unpaid",
        "payment_id": None,
        "created_at": now_iso(),
    }
    await db.bookings.insert_one(booking)
    booking.pop("_id", None)

    # Analytics-ready: one row per answer for future search/filter
    for a in snapshot:
        if not a["answer"]:
            continue
        await db.booking_intake_answers.insert_one({
            "id": str(uuid.uuid4()),
            "booking_id": booking["id"],
            "pro_id": user["id"],
            "service_id": service["id"],
            "question_id": a["question_id"],
            "question_text": a["question_text"],
            "question_type": a["question_type"],
            "answer": a["answer"],
            "answer_lower": a["answer"].lower(),
            "created_at": now_iso(),
        })

    await log_activity(booking["id"], Action.BOOKING_CREATED, "customer", None,
                       {"service_id": service["id"], "date": body.date, "start_time": body.start_time,
                        "intake_count": len([a for a in snapshot if a["answer"]])})
    await log_activity(booking["id"], Action.BOOKING_CONFIRMED, "system", None, {})

    try:
        manage_url = booking_manage_url(booking)
        cust_tpl = render_booking_confirmed_customer(booking, user["name"], manage_url)
        send_email(booking["customer_email"], cust_tpl["subject"], cust_tpl["html"], cust_tpl["text"])
        pro_tpl = render_booking_confirmed_pro(booking, user["name"], booking_pro_url(booking))
        send_email(user["email"], pro_tpl["subject"], pro_tpl["html"], pro_tpl["text"])
    except Exception:
        logger.exception("Email send failed for booking %s", booking["id"])

    return booking

@api.get("/bookings/{booking_id}")
async def get_booking(booking_id: str):
    """Public-by-id booking view (used by the confirmation page). No mutations."""
    b = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Booking not found")
    pro = await db.users.find_one({"id": b["pro_id"]})
    b["professional"] = {
        "name": pro["name"] if pro else "",
        "slug": pro.get("slug", "") if pro else "",
        "category": pro.get("category", "") if pro else "",
        "photo_url": pro.get("photo_url", "") if pro else "",
        "meet_link": pro.get("meet_link", "") if pro else "",
    }
    return b

@api.get("/categories")
async def categories():
    return CATEGORIES

# --- Customer-side token-protected endpoints ------------------------
async def _get_booking_for_customer(booking_id: str, token: str) -> dict:
    if not token:
        raise HTTPException(401, "Missing access token")
    b = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
    if not b or b.get("customer_access_token") != token:
        raise HTTPException(404, "Booking not found")
    return b

def _is_before_start(b: dict) -> bool:
    return booking_start_dt(b) > datetime.now(IST)

def _hours_until_start(b: dict) -> float:
    return (booking_start_dt(b) - datetime.now(IST)).total_seconds() / 3600

@api.get("/public/bookings/{booking_id}")
async def public_booking_detail(booking_id: str, token: str = Query(...)):
    b = await _get_booking_for_customer(booking_id, token)
    pro = await db.users.find_one({"id": b["pro_id"]})
    policies = (pro or {}).get("policies", default_policies())
    hours_left = _hours_until_start(b)
    can_reschedule = (
        b["status"] in ACTIVE_STATUSES
        and hours_left > policies["reschedule_window_hours"]
        and b.get("reschedule_count", 0) < policies["reschedule_limit"]
    )
    can_cancel = (
        b["status"] in ACTIVE_STATUSES
        and hours_left > policies["cancel_window_hours"]
    )
    return {
        "booking": b,
        "professional": {
            "name": pro["name"] if pro else "",
            "slug": pro.get("slug", "") if pro else "",
            "category": pro.get("category", "") if pro else "",
            "photo_url": pro.get("photo_url", "") if pro else "",
        },
        "policies": policies,
        "permissions": {
            "can_reschedule": can_reschedule,
            "can_cancel": can_cancel,
            "hours_until_start": round(hours_left, 2),
            "reason_blocked": _blocked_reason(b, policies, hours_left, can_reschedule, can_cancel),
        },
    }

def _blocked_reason(b, policies, hours_left, can_reschedule, can_cancel) -> Optional[str]:
    if b["status"] == Status.CANCELLED:
        return "This booking is cancelled."
    if b["status"] == Status.COMPLETED:
        return "This session has already taken place."
    if b["status"] == Status.NO_SHOW:
        return "This session was marked as no-show."
    if hours_left <= 0:
        return "The session has already started."
    if not can_reschedule and not can_cancel:
        if b.get("reschedule_count", 0) >= policies["reschedule_limit"]:
            return "Reschedule limit reached. Please contact the professional."
        return f"Changes must be made at least {policies['cancel_window_hours']}h in advance."
    return None

@api.get("/public/bookings/{booking_id}/slots")
async def public_booking_slots(booking_id: str, token: str = Query(...), date: str = Query(...)):
    b = await _get_booking_for_customer(booking_id, token)
    return {"slots": await _available_slots(b["pro_id"], date, b["duration_min"], exclude_booking_id=b["id"])}

@api.post("/public/bookings/{booking_id}/reschedule")
async def public_reschedule(booking_id: str, body: RescheduleIn, token: str = Query(...)):
    b = await _get_booking_for_customer(booking_id, token)
    if b["status"] not in ACTIVE_STATUSES:
        raise HTTPException(400, "This booking cannot be rescheduled")
    pro = await db.users.find_one({"id": b["pro_id"]})
    policies = (pro or {}).get("policies", default_policies())
    if _hours_until_start(b) <= policies["reschedule_window_hours"]:
        raise HTTPException(400, f"Reschedule must be at least {policies['reschedule_window_hours']}h before start")
    if b.get("reschedule_count", 0) >= policies["reschedule_limit"]:
        raise HTTPException(400, "Reschedule limit reached. Please contact the professional.")
    return await _do_reschedule(b, pro, body.date, body.start_time, body.reason, actor_type="customer", actor_id=None)

@api.post("/public/bookings/{booking_id}/cancel")
async def public_cancel(booking_id: str, body: CancelIn, token: str = Query(...)):
    b = await _get_booking_for_customer(booking_id, token)
    if b["status"] not in ACTIVE_STATUSES:
        raise HTTPException(400, "This booking cannot be cancelled")
    pro = await db.users.find_one({"id": b["pro_id"]})
    policies = (pro or {}).get("policies", default_policies())
    if _hours_until_start(b) <= policies["cancel_window_hours"]:
        raise HTTPException(400, f"Cancellation must be at least {policies['cancel_window_hours']}h before start")
    return await _do_cancel(b, pro, body.reason, actor_type="customer", actor_id=None)

# --- Pro-side reschedule / cancel / no-show -------------------------
@api.post("/me/bookings/{booking_id}/reschedule")
async def pro_reschedule(booking_id: str, body: RescheduleIn, user=Depends(get_current_user)):
    b = await db.bookings.find_one({"id": booking_id, "pro_id": user["id"]}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Booking not found")
    if b["status"] not in ACTIVE_STATUSES:
        raise HTTPException(400, "This booking cannot be rescheduled")
    return await _do_reschedule(b, user, body.date, body.start_time, body.reason, actor_type="professional", actor_id=user["id"])

@api.post("/me/bookings/{booking_id}/cancel")
async def pro_cancel(booking_id: str, body: CancelIn, user=Depends(get_current_user)):
    b = await db.bookings.find_one({"id": booking_id, "pro_id": user["id"]}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Booking not found")
    if b["status"] not in ACTIVE_STATUSES:
        raise HTTPException(400, "This booking cannot be cancelled")
    return await _do_cancel(b, user, body.reason, actor_type="professional", actor_id=user["id"])

@api.post("/me/bookings/{booking_id}/no-show")
async def pro_no_show(booking_id: str, body: NoShowIn, user=Depends(get_current_user)):
    b = await db.bookings.find_one({"id": booking_id, "pro_id": user["id"]}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Booking not found")
    if b["status"] not in ACTIVE_STATUSES:
        raise HTTPException(400, "This booking is not active")
    await db.bookings.update_one({"id": b["id"]},
        {"$set": {"status": Status.NO_SHOW, "completed_at": now_iso()}})
    await log_activity(b["id"], Action.BOOKING_NO_SHOW, "professional", user["id"], {"reason": body.reason})
    return {"ok": True}

class MeetingUpdateIn(BaseModel):
    meeting_mode: Optional[str] = Field(default=None, pattern="^(video|in_person|phone)$")
    meeting_details: Optional[str] = None

@api.patch("/me/bookings/{booking_id}/meeting")
async def pro_update_meeting(booking_id: str, body: MeetingUpdateIn, user=Depends(get_current_user)):
    b = await db.bookings.find_one({"id": booking_id, "pro_id": user["id"]}, {"_id": 0})
    if not b:
        raise HTTPException(404, "Booking not found")
    updates: dict = {}
    if body.meeting_mode is not None:
        updates["meeting_mode"] = body.meeting_mode
    if body.meeting_details is not None:
        updates["meeting_details"] = body.meeting_details.strip()
        # keep backward-compat meet_link field mirrored when mode is video (or unset)
        effective_mode = body.meeting_mode or b.get("meeting_mode", "video")
        if effective_mode == "video":
            updates["meet_link"] = body.meeting_details.strip()
    if not updates:
        return b
    updates["meeting_updated_at"] = now_iso()
    await db.bookings.update_one({"id": b["id"]}, {"$set": updates})
    await log_activity(b["id"], Action.MEETING_UPDATED, "professional", user["id"], updates)
    fresh = await db.bookings.find_one({"id": b["id"]}, {"_id": 0})
    return fresh

# --- Shared mutation helpers ----------------------------------------
async def _do_reschedule(b: dict, pro: dict, new_date: str, new_start: str, reason: str, actor_type: str, actor_id: Optional[str]):
    prev_date = b["date"]
    prev_time = b["start_time"]

    # Conflict check (excluding current booking)
    conflict = await db.bookings.find_one({
        "pro_id": b["pro_id"], "date": new_date, "start_time": new_start,
        "id": {"$ne": b["id"]}, "status": {"$nin": [Status.CANCELLED]},
    })
    if conflict:
        raise HTTPException(409, "That slot is not available")
    # Validate against schedule by checking if slot is in available list
    available = await _available_slots(b["pro_id"], new_date, b["duration_min"], exclude_booking_id=b["id"])
    if new_start not in available:
        raise HTTPException(400, "That slot is outside availability")

    new_end = compute_end_time(new_start, b["duration_min"])
    update = {
        "date": new_date, "start_time": new_start, "end_time": new_end,
        "status": Status.RESCHEDULED,
        "reschedule_count": b.get("reschedule_count", 0) + 1,
        "reschedule_reason": reason or b.get("reschedule_reason", ""),
        # reset reminder flags since timing changed
        "reminder_24h_sent": False,
        "reminder_1h_sent": False,
    }
    await db.bookings.update_one({"id": b["id"]}, {"$set": update})
    b.update(update)

    await log_activity(b["id"], Action.BOOKING_RESCHEDULED, actor_type, actor_id,
                       {"from": {"date": prev_date, "start_time": prev_time},
                        "to": {"date": new_date, "start_time": new_start},
                        "reason": reason})

    # Emails
    try:
        pro_name = pro["name"]
        manage_url = booking_manage_url(b)
        pro_url = booking_pro_url(b)
        tpl = render_booking_rescheduled(b, pro_name, "customer", manage_url, actor_type)
        send_email(b["customer_email"], tpl["subject"], tpl["html"], tpl["text"])
        tpl2 = render_booking_rescheduled(b, pro_name, "professional", pro_url, actor_type)
        send_email(pro["email"], tpl2["subject"], tpl2["html"], tpl2["text"])
    except Exception:
        logger.exception("Reschedule email failed for booking %s", b["id"])

    return b

async def _do_cancel(b: dict, pro: dict, reason: str, actor_type: str, actor_id: Optional[str]):
    await db.bookings.update_one({"id": b["id"]},
        {"$set": {"status": Status.CANCELLED, "cancel_reason": reason, "cancelled_at": now_iso()}})
    b["status"] = Status.CANCELLED
    b["cancel_reason"] = reason

    await log_activity(b["id"], Action.BOOKING_CANCELLED, actor_type, actor_id, {"reason": reason})

    try:
        tpl = render_booking_cancelled(b, pro["name"], "customer", actor_type, reason)
        send_email(b["customer_email"], tpl["subject"], tpl["html"], tpl["text"])
        tpl2 = render_booking_cancelled(b, pro["name"], "professional", actor_type, reason)
        send_email(pro["email"], tpl2["subject"], tpl2["html"], tpl2["text"])
    except Exception:
        logger.exception("Cancel email failed for booking %s", b["id"])

    return b

@api.get("/")
async def root():
    return {"app": "Practora", "status": "ok"}

# --- Public settings (subscription price, trial days) --------------
@api.get("/settings/public")
async def public_settings():
    s = await rp_get_settings(db)
    return {
        "subscription_amount_inr": s["subscription_amount_inr"],
        "trial_days": s.get("trial_days", TRIAL_DAYS),
        "razorpay_configured": rp_is_configured(),
    }

# --- Pro subscription endpoints -------------------------------------
def _access_snapshot(user: dict) -> dict:
    allowed, reason = rp_has_access(user)
    return {
        "has_access": allowed,
        "reason": reason,
        "subscription_status": user.get("subscription_status", "none"),
        "subscription_amount_inr": user.get("subscription_amount_inr"),
        "trial_ends_at": user.get("trial_ends_at"),
        "subscription_current_end": user.get("subscription_current_end"),
        "subscription_charge_at": user.get("subscription_charge_at"),
        "subscription_last_payment_at": user.get("subscription_last_payment_at"),
        "subscription_id": user.get("subscription_id"),
        "cancel_at_cycle_end": user.get("subscription_cancel_at_cycle_end", False),
    }

@api.get("/me/subscription")
async def get_my_subscription(user=Depends(get_current_user)):
    settings = await rp_get_settings(db)
    fresh = await db.users.find_one({"id": user["id"]})
    snap = _access_snapshot(fresh or user)
    snap["platform_amount_inr"] = settings["subscription_amount_inr"]
    snap["razorpay_configured"] = rp_is_configured()
    # last 20 subscription events for this user
    events = await db.subscription_events.find(
        {"user_id": user["id"]}, {"_id": 0, "payload": 0}
    ).sort("created_at", -1).to_list(20)
    snap["recent_events"] = events
    return snap

@api.post("/me/subscription/create")
async def create_my_subscription(user=Depends(get_current_user)):
    if not rp_is_configured():
        raise HTTPException(503, "Payments are not configured yet. Please contact support.")
    # If already active, prevent duplicate
    fresh = await db.users.find_one({"id": user["id"]})
    status = (fresh or {}).get("subscription_status", "")
    if status in {"active", "authenticated", "pending"}:
        raise HTTPException(400, "You already have an active subscription.")
    try:
        result = await rp_create_subscription(db, fresh or user)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return result

@api.post("/me/subscription/cancel")
async def cancel_my_subscription(user=Depends(get_current_user)):
    fresh = await db.users.find_one({"id": user["id"]})
    if not fresh or not fresh.get("subscription_id"):
        raise HTTPException(400, "No active subscription found.")
    try:
        result = await rp_cancel_subscription(db, fresh, cancel_at_cycle_end=True)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return result

# --- Razorpay webhook -----------------------------------------------
@api.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request):
    raw = await request.body()
    sig = request.headers.get("X-Razorpay-Signature", "")
    if not rp_verify_webhook(raw, sig):
        logger.warning("Razorpay webhook signature verification FAILED")
        raise HTTPException(400, "Invalid signature")
    try:
        import json as _json
        event = _json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    return await rp_handle_webhook(db, event)

# --- Admin endpoints -------------------------------------------------
async def get_admin_user(user=Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    return user

class AdminSettingsIn(BaseModel):
    subscription_amount_inr: int = Field(ge=1, le=100000)
    trial_days: int = Field(ge=0, le=90, default=7)

@api.get("/admin/settings")
async def admin_get_settings(_=Depends(get_admin_user)):
    s = await rp_get_settings(db)
    s["razorpay_configured"] = rp_is_configured()
    return s

@api.put("/admin/settings")
async def admin_update_settings(body: AdminSettingsIn, _=Depends(get_admin_user)):
    current = await rp_get_settings(db)
    updates = {
        "subscription_amount_inr": body.subscription_amount_inr,
        "trial_days": body.trial_days,
        "updated_at": now_iso(),
    }
    # If amount changed, create a new Razorpay plan (if configured)
    if body.subscription_amount_inr != current.get("subscription_amount_inr"):
        if rp_is_configured():
            new_plan_id = await rp_ensure_plan(db, body.subscription_amount_inr)
            if not new_plan_id:
                raise HTTPException(500, "Failed to create a new Razorpay plan for the new amount.")
        else:
            # Just store, plan will be created lazily when Razorpay is configured
            updates["current_plan_id"] = None
            updates["current_plan_amount_paise"] = body.subscription_amount_inr * 100
    await db.settings.update_one(
        {"id": "platform"},
        {"$set": updates},
        upsert=True,
    )
    fresh = await rp_get_settings(db)
    fresh["razorpay_configured"] = rp_is_configured()
    return fresh

@api.get("/admin/subscriptions")
async def admin_list_subscriptions(_=Depends(get_admin_user)):
    users = await db.users.find(
        {"role": "professional"}, {"_id": 0, "password_hash": 0}
    ).sort("created_at", -1).to_list(1000)
    return [{
        "id": u["id"],
        "name": u.get("name"),
        "email": u.get("email"),
        "slug": u.get("slug"),
        "category": u.get("category"),
        "subscription_status": u.get("subscription_status", "none"),
        "subscription_id": u.get("subscription_id"),
        "subscription_amount_inr": u.get("subscription_amount_inr"),
        "trial_ends_at": u.get("trial_ends_at"),
        "subscription_current_end": u.get("subscription_current_end"),
        "subscription_last_payment_at": u.get("subscription_last_payment_at"),
        "created_at": u.get("created_at"),
    } for u in users]

# --- Razorpay Standard Checkout (one-time orders) -----------------
import hmac as _hmac
import hashlib as _hashlib

class CreateOrderIn(BaseModel):
    amount: int = Field(ge=100, description="Amount in paise; minimum 100 (₹1)")
    currency: str = Field(default="INR", min_length=3, max_length=3)
    receipt: Optional[str] = None
    notes: Optional[dict] = None

@api.post("/create-order")
async def create_order(body: CreateOrderIn):
    """Create a Razorpay Order for Standard Checkout (one-time payment)."""
    if not rp_is_configured():
        raise HTTPException(503, "Payments are not configured on the server.")
    try:
        import razorpay
        client = razorpay.Client(auth=(os.environ["RAZORPAY_KEY_ID"], os.environ["RAZORPAY_KEY_SECRET"]))
        order = client.order.create({
            "amount": body.amount,
            "currency": body.currency,
            "receipt": body.receipt or f"rcpt_{int(now_utc().timestamp())}",
            "notes": body.notes or {},
            "payment_capture": 1,
        })
    except Exception as e:
        logger.exception("Razorpay order.create failed")
        raise HTTPException(500, f"Failed to create order: {e}")
    # Record order for audit
    await db.orders.insert_one({
        "id": order["id"],
        "amount": order["amount"],
        "currency": order["currency"],
        "receipt": order.get("receipt"),
        "status": order.get("status"),
        "notes": order.get("notes", {}),
        "created_at": now_iso(),
    })
    return {
        "order_id": order["id"],
        "amount": order["amount"],
        "currency": order["currency"],
        "key_id": os.environ["RAZORPAY_KEY_ID"],
        "receipt": order.get("receipt"),
    }


class VerifyPaymentIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

@api.post("/verify-payment")
async def verify_payment(body: VerifyPaymentIn):
    """Verify Razorpay payment signature (HMAC-SHA256 of order_id|payment_id)."""
    secret = os.environ.get("RAZORPAY_KEY_SECRET", "").strip()
    if not secret:
        raise HTTPException(503, "Payments are not configured on the server.")
    if not (body.razorpay_order_id and body.razorpay_payment_id and body.razorpay_signature):
        raise HTTPException(400, "Missing required fields.")

    payload = f"{body.razorpay_order_id}|{body.razorpay_payment_id}".encode("utf-8")
    expected = _hmac.new(secret.encode("utf-8"), payload, _hashlib.sha256).hexdigest()
    if not _hmac.compare_digest(expected, body.razorpay_signature):
        # Record the failed verification
        await db.orders.update_one(
            {"id": body.razorpay_order_id},
            {"$set": {"last_verification_status": "failed", "last_verified_at": now_iso()}},
        )
        raise HTTPException(400, "Signature verification failed.")

    await db.orders.update_one(
        {"id": body.razorpay_order_id},
        {"$set": {
            "status": "paid",
            "razorpay_payment_id": body.razorpay_payment_id,
            "razorpay_signature": body.razorpay_signature,
            "last_verification_status": "success",
            "last_verified_at": now_iso(),
        }},
    )
    return {
        "verified": True,
        "razorpay_order_id": body.razorpay_order_id,
        "razorpay_payment_id": body.razorpay_payment_id,
    }


# --- App init --------------------------------------------------------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

async def seed_admin():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@practora.in")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    if not await db.users.find_one({"email": admin_email}):
        await db.users.insert_one({
            "id": str(uuid.uuid4()), "email": admin_email,
            "password_hash": hash_password(admin_password),
            "name": "Practora Admin", "role": "admin", "slug": None,
            "policies": default_policies(),
            "created_at": now_iso(),
        })

async def seed_demo():
    demos = [
        {"email": "anjali@practora.in", "password": "demo123", "name": "Dr. Anjali Mehta",
         "slug": "dr-anjali", "category": "Therapist",
         "bio": "Licensed clinical psychologist with 8+ years of experience helping clients navigate anxiety, burnout, and life transitions.",
         "photo_url": "https://images.pexels.com/photos/4100671/pexels-photo-4100671.jpeg",
         "experience": "8 years", "languages": ["English", "Hindi"],
         "whatsapp": "+91 98765 43210", "instagram": "https://instagram.com/dranjali",
         "website": "", "meet_link": "https://meet.google.com/abc-defg-hij",
         "services": [
             {"name": "Initial Consultation", "description": "A 45-minute first-time session to understand your concerns and align on a plan.", "duration_min": 45, "price": 1500, "cover_image": ""},
             {"name": "Therapy Session", "description": "Standard 1-on-1 therapy session for ongoing care.", "duration_min": 60, "price": 2200, "cover_image": ""},
         ]},
        {"email": "raj@practora.in", "password": "demo123", "name": "Astro Raj",
         "slug": "astro-raj", "category": "Astrologer",
         "bio": "Vedic astrologer guiding clients on career, relationships, and life direction through detailed chart readings.",
         "photo_url": "https://images.pexels.com/photos/8152402/pexels-photo-8152402.jpeg",
         "experience": "12 years", "languages": ["English", "Hindi", "Marathi"],
         "whatsapp": "+91 91234 56789", "instagram": "https://instagram.com/astroraj",
         "website": "", "meet_link": "https://meet.google.com/xyz-uvwx-pqr",
         "services": [
             {"name": "Birth Chart Reading", "description": "Full Vedic birth chart analysis covering career, relationships, and life path.", "duration_min": 60, "price": 1999, "cover_image": ""},
             {"name": "Quick Question Session", "description": "30-minute focused session for a specific question or decision.", "duration_min": 30, "price": 999, "cover_image": ""},
         ]},
    ]
    for demo in demos:
        if await db.users.find_one({"email": demo["email"]}):
            continue
        uid = str(uuid.uuid4())
        services = demo.pop("services")
        pw = demo.pop("password")
        await db.users.insert_one({
            "id": uid, "password_hash": hash_password(pw), "role": "professional",
            "policies": default_policies(), "created_at": now_iso(), **demo,
        })
        await db.schedules.insert_one({
            "pro_id": uid,
            "days": {
                "mon": {"enabled": True, "start": "10:00", "end": "18:00"},
                "tue": {"enabled": True, "start": "10:00", "end": "18:00"},
                "wed": {"enabled": True, "start": "10:00", "end": "18:00"},
                "thu": {"enabled": True, "start": "10:00", "end": "18:00"},
                "fri": {"enabled": True, "start": "10:00", "end": "18:00"},
                "sat": {"enabled": True, "start": "10:00", "end": "14:00"},
                "sun": {"enabled": False, "start": "10:00", "end": "14:00"},
            },
            "buffer_min": 15, "blocked_dates": [],
        })
        for s in services:
            await db.services.insert_one({"id": str(uuid.uuid4()), "pro_id": uid, "created_at": now_iso(), **s})

async def migrate():
    """Idempotent migrations: uppercase statuses, backfill tokens & reminder flags & policies & intake."""
    async for b in db.bookings.find({}):
        updates = {}
        s = (b.get("status") or "").upper()
        if s and s != b.get("status"):
            updates["status"] = s
        if not b.get("customer_access_token"):
            updates["customer_access_token"] = secrets.token_urlsafe(24)
        if "reminder_24h_sent" not in b:
            updates["reminder_24h_sent"] = False
        if "reminder_1h_sent" not in b:
            updates["reminder_1h_sent"] = False
        if "reschedule_count" not in b:
            updates["reschedule_count"] = 0
        if "intake_answers" not in b:
            updates["intake_answers"] = []
        if updates:
            await db.bookings.update_one({"id": b["id"]}, {"$set": updates})

    # services without intake_questions
    await db.services.update_many(
        {"intake_questions": {"$exists": False}},
        {"$set": {"intake_questions": []}},
    )

    # Services without meeting_mode → default 'video' with empty details
    await db.services.update_many(
        {"meeting_mode": {"$exists": False}},
        {"$set": {"meeting_mode": "video", "meeting_details": ""}},
    )

    # Bookings without meeting_mode → backfill from service/user
    async for b in db.bookings.find({"meeting_mode": {"$exists": False}}, {"_id": 0, "id": 1, "meet_link": 1, "service_id": 1}):
        svc = await db.services.find_one({"id": b.get("service_id")}, {"_id": 0}) or {}
        mode = svc.get("meeting_mode") or "video"
        details = svc.get("meeting_details") or b.get("meet_link", "")
        await db.bookings.update_one({"id": b["id"]}, {"$set": {"meeting_mode": mode, "meeting_details": details}})

    # Default policies for users missing them
    await db.users.update_many({"policies": {"$exists": False}}, {"$set": {"policies": default_policies()}})

    # Backfill trial_ends_at + subscription_status for existing pros (30-day generous trial for legacy users)
    from datetime import timedelta as _td
    legacy_trial_end = (now_utc() + _td(days=30)).isoformat()
    await db.users.update_many(
        {"role": "professional", "subscription_status": {"$exists": False}},
        {"$set": {"subscription_status": "trial", "trial_ends_at": legacy_trial_end}},
    )
    # Ensure platform settings exist
    await rp_get_settings(db)


_scheduler_task: Optional[asyncio.Task] = None

@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("slug", unique=True, sparse=True)
    await db.services.create_index("pro_id")
    await db.bookings.create_index([("pro_id", 1), ("date", 1)])
    await db.bookings.create_index("customer_access_token")
    await db.booking_activities.create_index([("booking_id", 1), ("created_at", -1)])
    await db.booking_intake_answers.create_index([("pro_id", 1), ("question_id", 1), ("answer_lower", 1)])
    await db.booking_intake_answers.create_index([("booking_id", 1)])
    await db.subscription_events.create_index([("user_id", 1), ("created_at", -1)])
    await db.subscription_events.create_index("razorpay_event_id")
    await db.users.create_index("subscription_id", sparse=True)
    await seed_admin()
    await seed_demo()
    await migrate()
    global _scheduler_task
    _scheduler_task = asyncio.create_task(run_scheduler(db, interval_seconds=60))
    logger.info("Practora startup complete")

@app.on_event("shutdown")
async def shutdown():
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
    client.close()
