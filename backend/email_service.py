"""Email delivery via Resend. Fails soft when RESEND_API_KEY is unset (logs to stdout)."""
import os
import logging
import requests

logger = logging.getLogger("practora.email")

RESEND_ENDPOINT = "https://api.resend.com/emails"


def _is_configured() -> bool:
    return bool(os.environ.get("RESEND_API_KEY", "").strip())


def send_email(to: str, subject: str, html: str, text: str = "") -> dict:
    """Send an email via Resend. Returns dict {sent: bool, mode: 'live'|'sandbox'|'console', detail}."""
    from_addr = os.environ.get("RESEND_FROM_EMAIL", "Practora <onboarding@resend.dev>")

    if not _is_configured():
        logger.info("[EMAIL:CONSOLE] to=%s subject=%s\n%s", to, subject, text or html[:300])
        return {"sent": True, "mode": "console", "to": to, "subject": subject}

    try:
        resp = requests.post(
            RESEND_ENDPOINT,
            headers={
                "Authorization": f"Bearer {os.environ['RESEND_API_KEY']}",
                "Content-Type": "application/json",
            },
            json={
                "from": from_addr,
                "to": [to],
                "subject": subject,
                "html": html,
                "text": text or "",
            },
            timeout=10,
        )
        if resp.status_code >= 400:
            logger.warning("[EMAIL:FAIL] %s %s", resp.status_code, resp.text)
            return {"sent": False, "mode": "live", "error": resp.text}
        return {"sent": True, "mode": "live", "detail": resp.json()}
    except Exception as e:
        logger.exception("Resend send failed: %s", e)
        return {"sent": False, "mode": "live", "error": str(e)}


# --- Templates -------------------------------------------------------
_BASE_STYLE = """
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #FDFBF7; color: #2C1E16; max-width: 560px; margin: 0 auto;
  padding: 32px 24px; line-height: 1.55;
"""


def _wrap(inner_html: str) -> str:
    return f"""
    <div style="background:#F5F0E6;padding:32px 16px;">
      <div style="{_BASE_STYLE} background:#fff;border:1px solid #E8DED1;border-radius:12px;">
        <div style="font-family:'Cormorant Garamond',Georgia,serif;font-size:28px;color:#C86B53;margin-bottom:18px;">
          Practora
        </div>
        {inner_html}
        <div style="margin-top:28px;padding-top:18px;border-top:1px solid #E8DED1;font-size:12px;color:#7A685D;">
          Practora — booking platform for independent professionals.
        </div>
      </div>
    </div>
    """


def _meeting_html(b: dict) -> str:
    """Renders the meeting info block for emails based on meeting_mode + meeting_details."""
    mode = (b.get("meeting_mode") or "video").lower()
    details = (b.get("meeting_details") or b.get("meet_link") or "").strip()
    if mode == "in_person":
        if not details:
            return ""
        # HTML-escape for safety on user-entered address
        safe = details.replace("<", "&lt;").replace(">", "&gt;")
        return (
            '<div style="margin:12px 0;padding:12px 14px;background:#F5EFE6;border-radius:10px;font-size:14px;">'
            '<p style="margin:0 0 4px 0;font-size:11px;text-transform:uppercase;letter-spacing:0.15em;color:#7A685D;">In-person meeting</p>'
            f'<p style="margin:0;white-space:pre-wrap;">{safe}</p></div>'
        )
    if mode == "phone":
        if not details:
            return ""
        return (
            '<div style="margin:12px 0;padding:12px 14px;background:#F5EFE6;border-radius:10px;font-size:14px;">'
            '<p style="margin:0 0 4px 0;font-size:11px;text-transform:uppercase;letter-spacing:0.15em;color:#7A685D;">Phone call</p>'
            f'<p style="margin:0;">The professional will call you on <strong>{details}</strong>.</p></div>'
        )
    # default: video
    if not details:
        return (
            '<div style="margin:12px 0;padding:12px 14px;background:#FFF7EE;border-radius:10px;font-size:13px;color:#8A6B33;">'
            'The video meeting link will be shared before the session.</div>'
        )
    return (
        '<div style="margin:12px 0;padding:12px 14px;background:#F5EFE6;border-radius:10px;font-size:14px;">'
        '<p style="margin:0 0 4px 0;font-size:11px;text-transform:uppercase;letter-spacing:0.15em;color:#7A685D;">Video meeting</p>'
        f'<p style="margin:0;"><a href="{details}" style="color:#C86B53;">{details}</a></p></div>'
    )


def _meeting_text(b: dict) -> str:
    mode = (b.get("meeting_mode") or "video").lower()
    details = (b.get("meeting_details") or b.get("meet_link") or "").strip()
    if mode == "in_person":
        return f"\nIn-person location: {details}" if details else ""
    if mode == "phone":
        return f"\nPhone: the professional will call you on {details}" if details else ""
    return f"\nMeeting link: {details}" if details else "\nMeeting link will be shared before the session."


def _btn(href: str, label: str, color: str = "#C86B53") -> str:
    return (
        f'<a href="{href}" style="display:inline-block;background:{color};color:#fff;'
        f'text-decoration:none;padding:11px 22px;border-radius:999px;font-weight:600;">{label}</a>'
    )


def _summary(b: dict, pro_name: str) -> str:
    return f"""
    <table style="width:100%;font-size:14px;margin:18px 0;border-collapse:collapse;">
      <tr><td style="padding:6px 0;color:#7A685D;">Service</td><td style="padding:6px 0;text-align:right;">{b['service_name']}</td></tr>
      <tr><td style="padding:6px 0;color:#7A685D;">Date</td><td style="padding:6px 0;text-align:right;">{b['date']}</td></tr>
      <tr><td style="padding:6px 0;color:#7A685D;">Time</td><td style="padding:6px 0;text-align:right;">{b['start_time']} – {b['end_time']}</td></tr>
      <tr><td style="padding:6px 0;color:#7A685D;">With</td><td style="padding:6px 0;text-align:right;">{pro_name}</td></tr>
      <tr><td style="padding:6px 0;color:#7A685D;">Amount</td><td style="padding:6px 0;text-align:right;">₹{b['price']}</td></tr>
    </table>
    """


def render_booking_confirmed_customer(b: dict, pro_name: str, manage_url: str) -> dict:
    body = f"""
      <h2 style="font-family:'Cormorant Garamond',Georgia,serif;font-size:28px;margin:0 0 6px 0;">You're booked, {b['customer_name'].split(' ')[0]}.</h2>
      <p style="color:#7A685D;margin:0 0 8px 0;">Your session is confirmed.</p>
      {_summary(b, pro_name)}
      {_meeting_html(b)}
      <p style="margin-top:18px;">{_btn(manage_url, 'Manage booking')}</p>
      <p style="font-size:12px;color:#7A685D;">Need to reschedule or cancel? Use the button above.</p>
    """
    text = f"Your booking is confirmed.\n{b['service_name']} with {pro_name}\n{b['date']} at {b['start_time']}{_meeting_text(b)}\nManage: {manage_url}"
    return {"subject": f"Booking confirmed — {b['date']} at {b['start_time']}", "html": _wrap(body), "text": text}


def render_booking_confirmed_pro(b: dict, pro_name: str, detail_url: str) -> dict:
    intake_html = ""
    if b.get("intake_answers"):
        rows = "".join(
            f"<tr><td style='padding:6px 0;color:#7A685D;width:42%;vertical-align:top;'>{a['question_text']}</td>"
            f"<td style='padding:6px 0;'>{a['answer'] or '—'}</td></tr>"
            for a in b["intake_answers"]
        )
        intake_html = (
            '<div style="margin-top:18px;border-top:1px solid #E8DED1;padding-top:14px;">'
            '<p style="font-size:11px;text-transform:uppercase;letter-spacing:0.15em;color:#7A685D;margin:0 0 8px 0;">Intake answers</p>'
            f'<table style="width:100%;font-size:13px;border-collapse:collapse;">{rows}</table></div>'
        )
    body = f"""
      <h2 style="font-family:'Cormorant Garamond',Georgia,serif;font-size:26px;margin:0 0 6px 0;">New booking</h2>
      <p style="color:#7A685D;margin:0 0 8px 0;">{b['customer_name']} just booked you.</p>
      {_summary(b, pro_name)}
      <p style="font-size:14px;"><strong>Email:</strong> {b['customer_email']}<br/><strong>Phone:</strong> {b.get('customer_phone') or '—'}</p>
      {('<p style="font-size:14px;"><strong>Note from client:</strong> ' + b['notes'] + '</p>') if b.get('notes') else ''}
      {intake_html}
      <p style="margin-top:18px;">{_btn(detail_url, 'View in dashboard')}</p>
    """
    text = f"New booking from {b['customer_name']} on {b['date']} at {b['start_time']}."
    return {"subject": f"New booking — {b['customer_name']} on {b['date']}", "html": _wrap(body), "text": text}


def render_booking_rescheduled(b: dict, pro_name: str, recipient: str, manage_url: str, by: str) -> dict:
    headline = "Your session was rescheduled" if recipient == "customer" else "Booking rescheduled"
    by_label = "by you" if (by == recipient) else f"by the {'professional' if by == 'professional' else 'customer'}"
    body = f"""
      <h2 style="font-family:'Cormorant Garamond',Georgia,serif;font-size:26px;margin:0 0 6px 0;">{headline}</h2>
      <p style="color:#7A685D;margin:0 0 8px 0;">This booking has been moved {by_label}.</p>
      {_summary(b, pro_name)}
      <p style="margin-top:18px;">{_btn(manage_url, 'View booking')}</p>
    """
    text = f"Booking rescheduled to {b['date']} at {b['start_time']}."
    return {"subject": f"Rescheduled — {b['date']} at {b['start_time']}", "html": _wrap(body), "text": text}


def render_booking_cancelled(b: dict, pro_name: str, recipient: str, by: str, reason: str = "") -> dict:
    headline = "Your session was cancelled"
    body = f"""
      <h2 style="font-family:'Cormorant Garamond',Georgia,serif;font-size:26px;margin:0 0 6px 0;">{headline}</h2>
      <p style="color:#7A685D;margin:0 0 8px 0;">Cancelled by the {by}.</p>
      {_summary(b, pro_name)}
      {('<p style="font-size:14px;"><strong>Reason:</strong> ' + reason + '</p>') if reason else ''}
    """
    text = f"Booking cancelled (was {b['date']} {b['start_time']})."
    return {"subject": f"Cancelled — {b['date']} {b['start_time']}", "html": _wrap(body), "text": text}


def render_reminder(b: dict, pro_name: str, recipient: str, hours: int, manage_url: str) -> dict:
    headline = "Your session starts soon" if hours == 1 else "Your session is tomorrow"
    body = f"""
      <h2 style="font-family:'Cormorant Garamond',Georgia,serif;font-size:26px;margin:0 0 6px 0;">{headline}</h2>
      <p style="color:#7A685D;margin:0 0 8px 0;">A friendly reminder.</p>
      {_summary(b, pro_name)}
      {_meeting_html(b)}
      <p style="margin-top:18px;">{_btn(manage_url, 'View booking')}</p>
    """
    text = f"Reminder: {b['service_name']} on {b['date']} at {b['start_time']}.{_meeting_text(b)}"
    return {"subject": f"Reminder — {b['date']} at {b['start_time']}", "html": _wrap(body), "text": text}
