"""Razorpay Subscriptions integration for Practora.

Handles:
- Platform-level settings (subscription amount in DB; creates a new Razorpay Plan when amount changes)
- Subscription creation per professional
- Subscription cancellation
- Webhook verification + state sync
- Trial period tracking (7 days from signup by default)
"""
import os
import hmac
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger("practora.razorpay")

# --- Constants -------------------------------------------------------
TRIAL_DAYS = int(os.environ.get("TRIAL_DAYS", "7"))
DEFAULT_SUBSCRIPTION_AMOUNT_INR = int(os.environ.get("DEFAULT_SUBSCRIPTION_AMOUNT_INR", "500"))
PLATFORM_SETTINGS_ID = "platform"

# Razorpay subscription states (per Razorpay docs)
SUB_STATE_CREATED = "created"
SUB_STATE_AUTHENTICATED = "authenticated"
SUB_STATE_ACTIVE = "active"
SUB_STATE_PENDING = "pending"
SUB_STATE_HALTED = "halted"
SUB_STATE_CANCELLED = "cancelled"
SUB_STATE_COMPLETED = "completed"
SUB_STATE_EXPIRED = "expired"
SUB_STATE_PAUSED = "paused"

# States considered "grants access to platform"
ACTIVE_SUBSCRIPTION_STATES = {
    SUB_STATE_AUTHENTICATED,
    SUB_STATE_ACTIVE,
    SUB_STATE_PENDING,   # payment retry period, still active
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


def is_configured() -> bool:
    return bool(
        os.environ.get("RAZORPAY_KEY_ID", "").strip()
        and os.environ.get("RAZORPAY_KEY_SECRET", "").strip()
    )


def get_client():
    """Returns a razorpay.Client or None if not configured."""
    if not is_configured():
        return None
    import razorpay
    return razorpay.Client(
        auth=(os.environ["RAZORPAY_KEY_ID"], os.environ["RAZORPAY_KEY_SECRET"])
    )


# --- Settings helpers -------------------------------------------------
async def get_settings(db) -> dict:
    """Get platform settings, creating defaults if missing."""
    doc = await db.settings.find_one({"id": PLATFORM_SETTINGS_ID}, {"_id": 0})
    if not doc:
        doc = {
            "id": PLATFORM_SETTINGS_ID,
            "subscription_amount_inr": DEFAULT_SUBSCRIPTION_AMOUNT_INR,
            "trial_days": TRIAL_DAYS,
            "current_plan_id": None,
            "current_plan_amount_paise": DEFAULT_SUBSCRIPTION_AMOUNT_INR * 100,
            "updated_at": now_iso(),
        }
        await db.settings.insert_one(doc)
    return doc


async def ensure_plan(db, amount_inr: int) -> Optional[str]:
    """Ensure a Razorpay Plan exists for the given amount. Returns plan_id.

    If no plan exists at this amount, creates one and updates settings.
    """
    client = get_client()
    if not client:
        logger.warning("Razorpay not configured; skipping plan creation")
        return None

    settings = await get_settings(db)
    amount_paise = amount_inr * 100

    # If current plan matches, reuse
    if settings.get("current_plan_id") and settings.get("current_plan_amount_paise") == amount_paise:
        return settings["current_plan_id"]

    # Create a new plan
    try:
        plan = client.plan.create({
            "period": "monthly",
            "interval": 1,
            "item": {
                "name": f"Practora Professional Plan (₹{amount_inr}/mo)",
                "amount": amount_paise,
                "currency": "INR",
                "description": "Monthly subscription for Practora professional booking page",
            },
            "notes": {"created_by": "practora", "amount_inr": str(amount_inr)},
        })
        plan_id = plan["id"]
        await db.settings.update_one(
            {"id": PLATFORM_SETTINGS_ID},
            {"$set": {
                "current_plan_id": plan_id,
                "current_plan_amount_paise": amount_paise,
                "subscription_amount_inr": amount_inr,
                "updated_at": now_iso(),
            }},
            upsert=True,
        )
        logger.info("Created new Razorpay plan %s for ₹%s", plan_id, amount_inr)
        return plan_id
    except Exception:
        logger.exception("Failed to create Razorpay plan for amount %s", amount_inr)
        return None


# --- Subscription lifecycle ------------------------------------------
async def create_subscription_for_user(db, user: dict) -> dict:
    """Create a Razorpay Subscription for a professional. Returns
    {subscription_id, key_id, plan_id, amount_inr, short_url}.

    Raises ValueError on any misconfiguration.
    """
    client = get_client()
    if not client:
        raise ValueError("Razorpay is not configured. Please set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.")

    settings = await get_settings(db)
    amount_inr = settings["subscription_amount_inr"]
    plan_id = await ensure_plan(db, amount_inr)
    if not plan_id:
        raise ValueError("Failed to prepare subscription plan.")

    # total_count = 120 months = ~10 years of monthly billing (Razorpay requires a finite total_count)
    try:
        sub = client.subscription.create({
            "plan_id": plan_id,
            "customer_notify": 1,
            "quantity": 1,
            "total_count": 120,
            "notes": {
                "user_id": user["id"],
                "email": user["email"],
                "name": user.get("name", ""),
            },
        })
    except Exception as e:
        logger.exception("Razorpay subscription.create failed")
        raise ValueError(f"Razorpay error: {e}")

    # Save subscription reference
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "subscription_id": sub["id"],
            "subscription_plan_id": plan_id,
            "subscription_amount_inr": amount_inr,
            "subscription_status": sub.get("status", SUB_STATE_CREATED),
            "subscription_updated_at": now_iso(),
        }},
    )
    await db.subscription_events.insert_one({
        "id": f"evt_local_{sub['id']}_create",
        "user_id": user["id"],
        "subscription_id": sub["id"],
        "event_type": "local.subscription.created",
        "payload": {"plan_id": plan_id, "amount_inr": amount_inr},
        "created_at": now_iso(),
    })

    return {
        "subscription_id": sub["id"],
        "key_id": os.environ["RAZORPAY_KEY_ID"],
        "plan_id": plan_id,
        "amount_inr": amount_inr,
        "short_url": sub.get("short_url", ""),
        "status": sub.get("status"),
    }


async def cancel_subscription(db, user: dict, cancel_at_cycle_end: bool = True) -> dict:
    """Cancel a user's Razorpay subscription."""
    sub_id = user.get("subscription_id")
    if not sub_id:
        raise ValueError("No active subscription to cancel.")

    client = get_client()
    if not client:
        raise ValueError("Razorpay is not configured.")

    try:
        cancelled = client.subscription.cancel(sub_id, {"cancel_at_cycle_end": 1 if cancel_at_cycle_end else 0})
    except Exception as e:
        logger.exception("Razorpay subscription.cancel failed")
        raise ValueError(f"Razorpay error: {e}")

    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "subscription_status": cancelled.get("status", SUB_STATE_CANCELLED),
            "subscription_updated_at": now_iso(),
            "subscription_cancel_at_cycle_end": cancel_at_cycle_end,
        }},
    )
    await db.subscription_events.insert_one({
        "id": f"evt_local_{sub_id}_cancel",
        "user_id": user["id"],
        "subscription_id": sub_id,
        "event_type": "local.subscription.cancelled",
        "payload": {"cancel_at_cycle_end": cancel_at_cycle_end},
        "created_at": now_iso(),
    })
    return {"status": cancelled.get("status"), "cancel_at_cycle_end": cancel_at_cycle_end}


# --- Webhook handling ------------------------------------------------
def verify_webhook_signature(payload_body: bytes, signature: str) -> bool:
    """Verify Razorpay webhook X-Razorpay-Signature header (HMAC-SHA256).

    payload_body: raw request body bytes
    signature: value of X-Razorpay-Signature header
    """
    secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "").strip()
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode("utf-8"), payload_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def handle_webhook_event(db, event_json: dict) -> dict:
    """Process a Razorpay webhook event and update local subscription state.

    Handles: subscription.activated, subscription.charged, subscription.completed,
    subscription.updated, subscription.pending, subscription.halted,
    subscription.cancelled, subscription.paused, subscription.resumed
    """
    event_type = event_json.get("event", "")
    payload = event_json.get("payload", {}) or {}
    sub_entity = (payload.get("subscription") or {}).get("entity", {}) or {}
    payment_entity = (payload.get("payment") or {}).get("entity", {}) or {}

    sub_id = sub_entity.get("id") or payment_entity.get("subscription_id")

    # Persist raw event (idempotent by razorpay event id if present)
    razor_event_id = event_json.get("id") or f"evt_{event_type}_{sub_id or 'unknown'}_{int(now_utc().timestamp())}"
    existing = await db.subscription_events.find_one({"razorpay_event_id": razor_event_id})
    if existing:
        return {"ok": True, "duplicate": True, "event_type": event_type}

    await db.subscription_events.insert_one({
        "id": razor_event_id,
        "razorpay_event_id": razor_event_id,
        "subscription_id": sub_id,
        "event_type": event_type,
        "payload": event_json,
        "created_at": now_iso(),
    })

    if not sub_id:
        return {"ok": True, "event_type": event_type, "note": "no subscription id"}

    user = await db.users.find_one({"subscription_id": sub_id})
    if not user:
        return {"ok": True, "event_type": event_type, "note": "user not found"}

    updates: dict = {"subscription_updated_at": now_iso()}

    # Map event -> local status
    event_status_map = {
        "subscription.activated": SUB_STATE_ACTIVE,
        "subscription.charged": SUB_STATE_ACTIVE,
        "subscription.authenticated": SUB_STATE_AUTHENTICATED,
        "subscription.completed": SUB_STATE_COMPLETED,
        "subscription.pending": SUB_STATE_PENDING,
        "subscription.halted": SUB_STATE_HALTED,
        "subscription.cancelled": SUB_STATE_CANCELLED,
        "subscription.paused": SUB_STATE_PAUSED,
        "subscription.resumed": SUB_STATE_ACTIVE,
        "subscription.updated": sub_entity.get("status"),
    }
    if event_type in event_status_map:
        new_status = event_status_map[event_type]
        if new_status:
            updates["subscription_status"] = new_status

    # Record current period end (from Razorpay's current_end unix ts)
    current_end = sub_entity.get("current_end")
    if current_end:
        try:
            updates["subscription_current_end"] = datetime.fromtimestamp(int(current_end), timezone.utc).isoformat()
        except Exception:
            pass

    charge_at = sub_entity.get("charge_at")
    if charge_at:
        try:
            updates["subscription_charge_at"] = datetime.fromtimestamp(int(charge_at), timezone.utc).isoformat()
        except Exception:
            pass

    # For payment.captured / subscription.charged, record last successful payment
    if event_type == "subscription.charged":
        updates["subscription_last_payment_at"] = now_iso()
        if payment_entity.get("amount"):
            updates["subscription_last_payment_amount_paise"] = payment_entity["amount"]

    if updates:
        await db.users.update_one({"id": user["id"]}, {"$set": updates})

    logger.info("Handled Razorpay event %s for user %s -> %s", event_type, user["id"], updates.get("subscription_status"))
    return {"ok": True, "event_type": event_type, "user_id": user["id"], "status": updates.get("subscription_status")}


# --- Access-gate helper ---------------------------------------------
def user_has_platform_access(user: dict, settings: Optional[dict] = None) -> tuple[bool, str]:
    """Return (allowed, reason). Considers trial + subscription status."""
    # Trial check
    trial_ends_at = user.get("trial_ends_at")
    if trial_ends_at:
        try:
            end = datetime.fromisoformat(trial_ends_at.replace("Z", "+00:00")) if isinstance(trial_ends_at, str) else trial_ends_at
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            if end > now_utc():
                return True, "trial"
        except Exception:
            pass

    status = (user.get("subscription_status") or "").lower()
    if status in ACTIVE_SUBSCRIPTION_STATES:
        return True, status

    if status == SUB_STATE_CANCELLED:
        # If cancel_at_cycle_end and current_end still in the future, still allow
        current_end = user.get("subscription_current_end")
        if current_end:
            try:
                end_dt = datetime.fromisoformat(current_end.replace("Z", "+00:00"))
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=timezone.utc)
                if end_dt > now_utc():
                    return True, "cancelled_until_period_end"
            except Exception:
                pass

    return False, status or "no_subscription"
