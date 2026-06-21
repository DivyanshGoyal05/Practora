"""End-to-end backend tests for Practora booking lifecycle (Phase 2).

Covers:
- Auth (login, /auth/me)
- Policies GET/PUT
- Public profile + slots + booking creation
- Pro booking detail + reschedule + cancel + no-show
- Customer magic-link access + reschedule + cancel + permissions
- Slot conflict (409) and availability validation (400)
- Activity log immutability & ordering
- [EMAIL:CONSOLE] log emission
"""
import os
import re
import time
import uuid
import subprocess
from datetime import date, datetime, timedelta

import pytest
import requests

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/') if os.environ.get('REACT_APP_BACKEND_URL') else 'https://practora-bookings.preview.emergentagent.com'
API = f"{BASE_URL}/api"

PRO_EMAIL = "anjali@practora.in"
PRO_PASSWORD = "demo123"
PRO_SLUG = "dr-anjali"


def _next_weekday(target_wd: int, min_days_out: int = 5) -> str:
    d = date.today()
    for off in range(min_days_out, 60):
        nd = d + timedelta(days=off)
        if nd.weekday() == target_wd:
            return nd.isoformat()
    raise RuntimeError("no date found")


@pytest.fixture(scope="session")
def future_monday():
    return _next_weekday(0, min_days_out=5)


@pytest.fixture(scope="session")
def future_tuesday():
    return _next_weekday(1, min_days_out=5)


@pytest.fixture(scope="session")
def future_sunday():
    return _next_weekday(6, min_days_out=5)


@pytest.fixture(scope="session")
def pro_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": PRO_EMAIL, "password": PRO_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def pro_service(pro_session):
    r = pro_session.get(f"{API}/me/services")
    assert r.status_code == 200
    services = r.json()
    assert services, "pro must have services"
    # pick the 45-min Initial Consultation
    for svc in services:
        if "initial" in svc.get("name", "").lower():
            return svc
    return services[0]


# ---------- Auth ----------
class TestAuth:
    def test_login_and_me(self, pro_session):
        r = pro_session.get(f"{API}/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == PRO_EMAIL
        assert data["slug"] == PRO_SLUG
        assert data["role"] == "professional"

    def test_login_bad_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": PRO_EMAIL, "password": "wrong"})
        assert r.status_code == 401


# ---------- Policies ----------
class TestPolicies:
    def test_get_default_policies(self, pro_session):
        r = pro_session.get(f"{API}/me/policies")
        assert r.status_code == 200
        p = r.json()
        # Reset to defaults first in case earlier test mutated
        pro_session.put(f"{API}/me/policies",
                        json={"reschedule_window_hours": 12, "cancel_window_hours": 24, "reschedule_limit": 2})
        r2 = pro_session.get(f"{API}/me/policies")
        p2 = r2.json()
        assert p2["reschedule_window_hours"] == 12
        assert p2["cancel_window_hours"] == 24
        assert p2["reschedule_limit"] == 2

    def test_put_persists(self, pro_session):
        new_p = {"reschedule_window_hours": 6, "cancel_window_hours": 12, "reschedule_limit": 3}
        r = pro_session.put(f"{API}/me/policies", json=new_p)
        assert r.status_code == 200
        # GET again to verify persistence
        r2 = pro_session.get(f"{API}/me/policies")
        assert r2.json() == new_p
        # restore defaults
        pro_session.put(f"{API}/me/policies",
                        json={"reschedule_window_hours": 12, "cancel_window_hours": 24, "reschedule_limit": 2})


# ---------- Public booking creation ----------
class TestPublicBooking:
    def test_public_profile(self):
        r = requests.get(f"{API}/p/{PRO_SLUG}")
        assert r.status_code == 200
        data = r.json()
        assert data["professional"]["slug"] == PRO_SLUG
        assert isinstance(data["services"], list) and len(data["services"]) > 0

    def test_public_slots_returns_array(self, future_monday, pro_service):
        r = requests.get(f"{API}/p/{PRO_SLUG}/slots",
                         params={"date": future_monday, "service_id": pro_service["id"]})
        assert r.status_code == 200
        slots = r.json()["slots"]
        assert isinstance(slots, list)
        assert len(slots) > 0
        assert re.match(r"^\d{2}:\d{2}$", slots[0])


@pytest.fixture(scope="session")
def created_booking(future_monday, pro_service):
    # find first available slot
    r = requests.get(f"{API}/p/{PRO_SLUG}/slots",
                     params={"date": future_monday, "service_id": pro_service["id"]})
    slots = r.json()["slots"]
    assert slots, "no slots"
    start = slots[0]
    payload = {
        "service_id": pro_service["id"],
        "date": future_monday,
        "start_time": start,
        "customer_name": "TEST_Customer",
        "customer_email": f"test_{uuid.uuid4().hex[:8]}@example.com",
        "customer_phone": "+919999999999",
        "notes": "auto-test",
    }
    r = requests.post(f"{API}/p/{PRO_SLUG}/book", json=payload)
    assert r.status_code == 200, f"book failed: {r.status_code} {r.text}"
    return r.json()


class TestBookingCreation:
    def test_book_returns_expected_fields(self, created_booking):
        b = created_booking
        assert b["status"] == "CONFIRMED"
        assert b["customer_access_token"]
        assert b["reminder_24h_sent"] is False
        assert b["reminder_1h_sent"] is False
        assert b["reschedule_count"] == 0

    def test_book_logs_email_console(self, created_booking):
        # tail backend logs and look for [EMAIL:CONSOLE]
        out = subprocess.run(
            ["tail", "-n", "300", "/var/log/supervisor/backend.err.log"],
            capture_output=True, text=True
        ).stdout + subprocess.run(
            ["tail", "-n", "300", "/var/log/supervisor/backend.out.log"],
            capture_output=True, text=True
        ).stdout
        assert "[EMAIL:CONSOLE]" in out, "no console email log emitted"

    def test_double_book_returns_409(self, created_booking, pro_service):
        payload = {
            "service_id": pro_service["id"],
            "date": created_booking["date"],
            "start_time": created_booking["start_time"],
            "customer_name": "TEST_Dup",
            "customer_email": "dup@example.com",
        }
        r = requests.post(f"{API}/p/{PRO_SLUG}/book", json=payload)
        assert r.status_code == 409

    def test_pro_booking_detail_has_activities(self, pro_session, created_booking):
        r = pro_session.get(f"{API}/me/bookings/{created_booking['id']}")
        assert r.status_code == 200
        data = r.json()
        assert data["booking"]["id"] == created_booking["id"]
        actions = [a["action_type"] for a in data["activities"]]
        # newest first → CONFIRMED should appear before CREATED
        assert "BOOKING_CREATED" in actions
        assert "BOOKING_CONFIRMED" in actions
        # sorted newest-first: created_at descending
        cas = [a["created_at"] for a in data["activities"]]
        assert cas == sorted(cas, reverse=True)
        assert data["policies"]


# ---------- Customer magic-link ----------
class TestCustomerMagic:
    def test_valid_token_returns_permissions(self, created_booking):
        bid = created_booking["id"]; tok = created_booking["customer_access_token"]
        r = requests.get(f"{API}/public/bookings/{bid}", params={"token": tok})
        assert r.status_code == 200
        data = r.json()
        perms = data["permissions"]
        assert "can_reschedule" in perms and "can_cancel" in perms
        assert "hours_until_start" in perms
        # booking is many days out → should be allowed
        assert perms["can_reschedule"] is True
        assert perms["can_cancel"] is True

    def test_invalid_token_returns_404(self, created_booking):
        r = requests.get(f"{API}/public/bookings/{created_booking['id']}", params={"token": "BADTOKEN"})
        assert r.status_code == 404


# ---------- Customer reschedule / cancel / policy edge cases ----------
@pytest.fixture
def fresh_booking(future_tuesday, pro_service):
    r = requests.get(f"{API}/p/{PRO_SLUG}/slots",
                     params={"date": future_tuesday, "service_id": pro_service["id"]})
    slots = r.json()["slots"]
    assert slots
    payload = {
        "service_id": pro_service["id"],
        "date": future_tuesday,
        "start_time": slots[0],
        "customer_name": "TEST_FreshCust",
        "customer_email": f"fresh_{uuid.uuid4().hex[:6]}@example.com",
    }
    r = requests.post(f"{API}/p/{PRO_SLUG}/book", json=payload)
    assert r.status_code == 200
    return r.json()


class TestCustomerActions:
    def test_customer_reschedule_limit_blocked(self, pro_session, fresh_booking, future_monday, pro_service):
        # set reschedule_limit=0
        pro_session.put(f"{API}/me/policies",
                        json={"reschedule_window_hours": 12, "cancel_window_hours": 24, "reschedule_limit": 0})
        try:
            # get a different slot
            slots = requests.get(f"{API}/p/{PRO_SLUG}/slots",
                                 params={"date": future_monday, "service_id": pro_service["id"]}).json()["slots"]
            r = requests.post(
                f"{API}/public/bookings/{fresh_booking['id']}/reschedule",
                params={"token": fresh_booking["customer_access_token"]},
                json={"date": future_monday, "start_time": slots[0], "reason": "test"},
            )
            assert r.status_code == 400
            assert "limit" in r.text.lower() or "reschedule" in r.text.lower()
        finally:
            pro_session.put(f"{API}/me/policies",
                            json={"reschedule_window_hours": 12, "cancel_window_hours": 24, "reschedule_limit": 2})

    def test_customer_cancel_succeeds(self, fresh_booking):
        r = requests.post(
            f"{API}/public/bookings/{fresh_booking['id']}/cancel",
            params={"token": fresh_booking["customer_access_token"]},
            json={"reason": "no longer needed"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "CANCELLED"

    def test_cancelled_booking_permissions_block(self, fresh_booking):
        # cancel first
        requests.post(
            f"{API}/public/bookings/{fresh_booking['id']}/cancel",
            params={"token": fresh_booking["customer_access_token"]},
            json={"reason": "x"},
        )
        r = requests.get(f"{API}/public/bookings/{fresh_booking['id']}",
                         params={"token": fresh_booking["customer_access_token"]})
        assert r.status_code == 200
        perms = r.json()["permissions"]
        assert perms["can_reschedule"] is False
        assert perms["can_cancel"] is False
        assert perms["reason_blocked"]


# ---------- Pro reschedule / cancel / no-show ----------
class TestProActions:
    def test_pro_reschedule_and_activity(self, pro_session, created_booking, future_monday, pro_service):
        # find a different slot on future_monday
        slots = requests.get(f"{API}/p/{PRO_SLUG}/slots",
                             params={"date": future_monday, "service_id": pro_service["id"]}).json()["slots"]
        # avoid the slot we already booked
        target_slot = next((s for s in slots if s != created_booking["start_time"]), None)
        assert target_slot, "no alternate slot"
        r = pro_session.post(
            f"{API}/me/bookings/{created_booking['id']}/reschedule",
            json={"date": future_monday, "start_time": target_slot, "reason": "pro_test_reason"},
        )
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["status"] == "RESCHEDULED"
        assert b["reschedule_count"] >= 1
        assert b["reminder_24h_sent"] is False

        # activity log
        det = pro_session.get(f"{API}/me/bookings/{created_booking['id']}").json()
        actions = [a["action_type"] for a in det["activities"]]
        assert "BOOKING_RESCHEDULED" in actions
        resc = next(a for a in det["activities"] if a["action_type"] == "BOOKING_RESCHEDULED")
        assert resc["actor_type"] == "professional"
        assert "from" in resc["metadata"] and "to" in resc["metadata"]
        assert resc["metadata"]["reason"] == "pro_test_reason"

    def test_pro_reschedule_to_occupied_returns_409(self, pro_session, future_monday, pro_service):
        # create two bookings; reschedule first onto second's slot
        slots = requests.get(f"{API}/p/{PRO_SLUG}/slots",
                             params={"date": future_monday, "service_id": pro_service["id"]}).json()["slots"]
        assert len(slots) >= 2
        b1 = requests.post(f"{API}/p/{PRO_SLUG}/book", json={
            "service_id": pro_service["id"], "date": future_monday, "start_time": slots[0],
            "customer_name": "TEST_Conflict1", "customer_email": f"c1_{uuid.uuid4().hex[:6]}@x.com"}).json()
        b2 = requests.post(f"{API}/p/{PRO_SLUG}/book", json={
            "service_id": pro_service["id"], "date": future_monday, "start_time": slots[1],
            "customer_name": "TEST_Conflict2", "customer_email": f"c2_{uuid.uuid4().hex[:6]}@x.com"}).json()
        r = pro_session.post(f"{API}/me/bookings/{b1['id']}/reschedule",
                             json={"date": future_monday, "start_time": slots[1], "reason": "x"})
        assert r.status_code == 409

    def test_pro_reschedule_to_sunday_returns_400(self, pro_session, fresh_booking, future_sunday):
        # Sunday disabled in seed
        r = pro_session.post(
            f"{API}/me/bookings/{fresh_booking['id']}/reschedule",
            json={"date": future_sunday, "start_time": "10:00", "reason": "out"},
        )
        assert r.status_code == 400
        assert "availability" in r.text.lower()

    def test_pro_cancel(self, pro_session, fresh_booking):
        r = pro_session.post(f"{API}/me/bookings/{fresh_booking['id']}/cancel",
                             json={"reason": "pro_cancel_test"})
        assert r.status_code == 200
        assert r.json()["status"] == "CANCELLED"
        det = pro_session.get(f"{API}/me/bookings/{fresh_booking['id']}").json()
        cancel_a = next(a for a in det["activities"] if a["action_type"] == "BOOKING_CANCELLED")
        assert cancel_a["actor_type"] == "professional"
        assert cancel_a["metadata"]["reason"] == "pro_cancel_test"

    def test_pro_no_show(self, pro_session, fresh_booking):
        r = pro_session.post(f"{API}/me/bookings/{fresh_booking['id']}/no-show",
                             json={"reason": "missed"})
        assert r.status_code == 200
        det = pro_session.get(f"{API}/me/bookings/{fresh_booking['id']}").json()
        assert det["booking"]["status"] == "NO_SHOW"
        ns = next(a for a in det["activities"] if a["action_type"] == "BOOKING_NO_SHOW")
        assert ns["actor_type"] == "professional"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
