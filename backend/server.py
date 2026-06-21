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

class RescheduleIn(BaseModel):
    date: str
    start_time: str
    reason: str = ""

class CancelIn(BaseModel):
    reason: str = ""

class NoShowIn(BaseModel):
    reason: str = ""

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
    user_doc = {
        "id": user_id, "email": email, "password_hash": hash_password(body.password),
        "name": body.name.strip(), "role": "professional", "slug": slug, "category": body.category,
        "bio": "", "photo_url": "", "experience": "", "languages": [],
        "whatsapp": "", "instagram": "", "website": "", "meet_link": "",
        "policies": default_policies(),
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
    return {"professional": serialize_user(user), "services": services}

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
    service = await db.services.find_one({"id": body.service_id, "pro_id": user["id"]}, {"_id": 0})
    if not service:
        raise HTTPException(404, "Service not found")
    conflict = await db.bookings.find_one({
        "pro_id": user["id"], "date": body.date, "start_time": body.start_time,
        "status": {"$nin": [Status.CANCELLED]},
    })
    if conflict:
        raise HTTPException(409, "This slot is no longer available")

    end_time = compute_end_time(body.start_time, service["duration_min"])
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
        "meet_link": user.get("meet_link", ""),
        "status": Status.CONFIRMED,
        "customer_access_token": secrets.token_urlsafe(24),
        "reminder_24h_sent": False,
        "reminder_1h_sent": False,
        "reschedule_count": 0,
        "cancel_reason": "",
        "reschedule_reason": "",
        "completed_at": None,
        # payment placeholder (decoupled from lifecycle)
        "payment_status": "unpaid",
        "payment_id": None,
        "created_at": now_iso(),
    }
    await db.bookings.insert_one(booking)
    booking.pop("_id", None)

    await log_activity(booking["id"], Action.BOOKING_CREATED, "customer", None,
                       {"service_id": service["id"], "date": body.date, "start_time": body.start_time})
    await log_activity(booking["id"], Action.BOOKING_CONFIRMED, "system", None, {})

    # send confirmations (fire and forget — but we await briefly for log clarity)
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
    """Idempotent migrations: uppercase statuses, backfill tokens & reminder flags & policies."""
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
        if updates:
            await db.bookings.update_one({"id": b["id"]}, {"$set": updates})

    # Default policies for users missing them
    await db.users.update_many({"policies": {"$exists": False}}, {"$set": {"policies": default_policies()}})


_scheduler_task: Optional[asyncio.Task] = None

@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("slug", unique=True, sparse=True)
    await db.services.create_index("pro_id")
    await db.bookings.create_index([("pro_id", 1), ("date", 1)])
    await db.bookings.create_index("customer_access_token")
    await db.booking_activities.create_index([("booking_id", 1), ("created_at", -1)])
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
