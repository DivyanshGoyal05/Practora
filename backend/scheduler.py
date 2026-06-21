"""Background scheduler for reminders + auto-completion. Runs every 60s as asyncio task."""
import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta

from email_service import (
    send_email,
    render_reminder,
    render_booking_cancelled,  # noqa: F401 (kept for parity)
)

logger = logging.getLogger("practora.scheduler")
IST = timezone(timedelta(hours=5, minutes=30))


def parse_booking_dt(date_str: str, time_str: str) -> datetime:
    """Treat booking date+time as IST."""
    dt = datetime.fromisoformat(f"{date_str}T{time_str}:00")
    return dt.replace(tzinfo=IST)


def now_ist() -> datetime:
    return datetime.now(IST)


async def _frontend_url() -> str:
    return os.environ.get("FRONTEND_URL", "").rstrip("/")


async def _send_reminder(db, booking: dict, hours: int):
    """Send 24h or 1h reminder to both customer and pro. Marks idempotent flag."""
    flag = "reminder_24h_sent" if hours == 24 else "reminder_1h_sent"
    if booking.get(flag):
        return
    pro = await db.users.find_one({"id": booking["pro_id"]})
    if not pro:
        return
    fe = await _frontend_url()
    manage_url = f"{fe}/booking/{booking['id']}/manage?token={booking.get('customer_access_token','')}"
    pro_url = f"{fe}/dashboard/bookings/{booking['id']}"

    # customer
    tpl = render_reminder(booking, pro["name"], "customer", hours, manage_url)
    send_email(booking["customer_email"], tpl["subject"], tpl["html"], tpl["text"])
    # professional
    tpl_pro = render_reminder(booking, pro["name"], "professional", hours, pro_url)
    send_email(pro["email"], tpl_pro["subject"], tpl_pro["html"], tpl_pro["text"])

    await db.bookings.update_one({"id": booking["id"]}, {"$set": {flag: True}})
    action = "REMINDER_SENT_24H" if hours == 24 else "REMINDER_SENT_1H"
    await db.booking_activities.insert_one({
        "id": f"act_{booking['id']}_{hours}h",
        "booking_id": booking["id"],
        "action_type": action,
        "actor_type": "system",
        "actor_id": None,
        "metadata": {"hours_before": hours},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    logger.info("Reminder %sh sent for booking %s", hours, booking["id"])


async def tick(db):
    """Single iteration: send reminders + auto-complete."""
    now = now_ist()
    active_statuses = ["CONFIRMED", "RESCHEDULED"]

    # 24h reminders
    cursor = db.bookings.find({
        "status": {"$in": active_statuses},
        "reminder_24h_sent": {"$ne": True},
    })
    async for b in cursor:
        try:
            start = parse_booking_dt(b["date"], b["start_time"])
            delta = (start - now).total_seconds()
            if 0 < delta <= 24 * 3600:
                await _send_reminder(db, b, 24)
        except Exception:
            logger.exception("24h reminder error for %s", b.get("id"))

    # 1h reminders
    cursor = db.bookings.find({
        "status": {"$in": active_statuses},
        "reminder_1h_sent": {"$ne": True},
    })
    async for b in cursor:
        try:
            start = parse_booking_dt(b["date"], b["start_time"])
            delta = (start - now).total_seconds()
            if 0 < delta <= 3600:
                await _send_reminder(db, b, 1)
        except Exception:
            logger.exception("1h reminder error for %s", b.get("id"))

    # Auto-complete: 30 min after end_time
    cursor = db.bookings.find({"status": {"$in": active_statuses}})
    async for b in cursor:
        try:
            end = parse_booking_dt(b["date"], b["end_time"])
            if (now - end).total_seconds() >= 30 * 60:
                await db.bookings.update_one(
                    {"id": b["id"]},
                    {"$set": {"status": "COMPLETED", "completed_at": datetime.now(timezone.utc).isoformat()}},
                )
                await db.booking_activities.insert_one({
                    "id": f"act_{b['id']}_complete_{int(now.timestamp())}",
                    "booking_id": b["id"],
                    "action_type": "BOOKING_COMPLETED",
                    "actor_type": "system",
                    "actor_id": None,
                    "metadata": {"auto": True},
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                logger.info("Auto-completed booking %s", b["id"])
        except Exception:
            logger.exception("Auto-complete error for %s", b.get("id"))


async def run_scheduler(db, interval_seconds: int = 60):
    """Forever loop. Cancellable on shutdown."""
    logger.info("Scheduler started (interval=%ss)", interval_seconds)
    while True:
        try:
            await tick(db)
        except Exception:
            logger.exception("Scheduler tick error")
        await asyncio.sleep(interval_seconds)
