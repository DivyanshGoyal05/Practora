"""Phase 3 Slice C — Intake Forms backend tests.

Covers:
- PUT/GET /api/me/services/{id}/intake-form (auth)
- Public GET /api/p/{slug}/services/{id}/intake-form
- Validation: dropdown without options, >20 questions, unsupported type
- Booking with required intake answers, invalid email, invalid url
- Snapshot persistence on booking + booking_intake_answers analytics row
- Snapshot unaffected by later question edits
- Activity log metadata intake_count
- [EMAIL:CONSOLE] subject 'New booking' fallback
- Clearing intake form (questions=[]) skips intake on subsequent bookings
"""
import os
import re
import time
import uuid
import subprocess
from datetime import date, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
API = f"{BASE_URL}/api"

PRO_EMAIL = "anjali@practora.in"
PRO_PASSWORD = "demo123"
PRO_SLUG = "dr-anjali"

MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']


# ---------- helpers ----------
def _next_weekday(target_wd: int, min_days_out: int = 7) -> str:
    d = date.today()
    for off in range(min_days_out, 60):
        nd = d + timedelta(days=off)
        if nd.weekday() == target_wd:
            return nd.isoformat()
    raise RuntimeError("no date found")


@pytest.fixture(scope="session")
def mongo_db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture(scope="module", autouse=True)
def _clear_intake_forms_after_module():
    """Ensure all seeded services are left without intake forms so other
    test files (e.g. Phase 2 lifecycle) don't break."""
    yield
    # Teardown
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    s.post(f"{API}/auth/login", json={"email": PRO_EMAIL, "password": PRO_PASSWORD})
    svcs = s.get(f"{API}/me/services").json()
    for svc in svcs:
        s.put(f"{API}/me/services/{svc['id']}/intake-form", json={"questions": []})


@pytest.fixture(scope="session")
def pro_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": PRO_EMAIL, "password": PRO_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def services(pro_session):
    r = pro_session.get(f"{API}/me/services")
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="session")
def initial_service(services):
    for svc in services:
        if "initial" in svc.get("name", "").lower():
            return svc
    return services[0]


@pytest.fixture(scope="session")
def therapy_service(services):
    for svc in services:
        if "therapy" in svc.get("name", "").lower():
            return svc
    return services[-1]


@pytest.fixture(scope="session")
def future_monday():
    return _next_weekday(0, min_days_out=7)


@pytest.fixture(scope="session")
def future_tuesday():
    return _next_weekday(1, min_days_out=7)


def _get_slot(date_str, service_id):
    r = requests.get(f"{API}/p/{PRO_SLUG}/slots", params={"date": date_str, "service_id": service_id})
    assert r.status_code == 200, r.text
    slots = r.json()["slots"]
    assert slots, "no slots available"
    return slots


# ---------- PUT /intake-form validation ----------
class TestIntakeFormCRUD:
    def test_put_intake_form_assigns_uuids(self, pro_session, initial_service):
        payload = {"questions": [
            {"text": "What brings you here today?", "type": "short_text", "required": True},
            {"text": "How did you hear about us?", "type": "dropdown", "required": False,
             "options": ["Google", "Friend", "Instagram"]},
            {"text": "Best contact email?", "type": "email", "required": True},
        ]}
        r = pro_session.put(f"{API}/me/services/{initial_service['id']}/intake-form", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        qs = data["questions"]
        assert len(qs) == 3
        for q in qs:
            assert q["id"] and len(q["id"]) > 0
            # UUID-shaped
            assert re.match(r"^[a-f0-9-]{36}$", q["id"])
        assert qs[0]["required"] is True
        assert qs[1]["type"] == "dropdown"
        assert qs[1]["options"] == ["Google", "Friend", "Instagram"]
        assert qs[2]["type"] == "email"

    def test_get_intake_form_persists(self, pro_session, initial_service):
        r = pro_session.get(f"{API}/me/services/{initial_service['id']}/intake-form")
        assert r.status_code == 200
        qs = r.json()["questions"]
        assert len(qs) == 3
        assert qs[0]["text"] == "What brings you here today?"

    def test_public_get_intake_form_no_auth(self, initial_service):
        r = requests.get(f"{API}/p/{PRO_SLUG}/services/{initial_service['id']}/intake-form")
        assert r.status_code == 200
        qs = r.json()["questions"]
        assert len(qs) == 3

    def test_put_dropdown_without_options_400(self, pro_session, initial_service):
        payload = {"questions": [
            {"text": "Pick one", "type": "dropdown", "required": True, "options": []}
        ]}
        r = pro_session.put(f"{API}/me/services/{initial_service['id']}/intake-form", json=payload)
        assert r.status_code == 400
        assert "option" in r.text.lower()

    def test_put_more_than_20_questions_400(self, pro_session, initial_service):
        payload = {"questions": [{"text": f"Q{i}", "type": "short_text"} for i in range(21)]}
        r = pro_session.put(f"{API}/me/services/{initial_service['id']}/intake-form", json=payload)
        assert r.status_code == 400
        assert "20" in r.text

    def test_put_unsupported_type_400(self, pro_session, initial_service):
        payload = {"questions": [{"text": "weird", "type": "random_type"}]}
        r = pro_session.put(f"{API}/me/services/{initial_service['id']}/intake-form", json=payload)
        assert r.status_code == 400
        assert "random_type" in r.text or "Unsupported" in r.text

    def test_restore_initial_form(self, pro_session, initial_service):
        """Re-apply the standard 3-question form for downstream tests."""
        payload = {"questions": [
            {"text": "What brings you here today?", "type": "short_text", "required": True},
            {"text": "How did you hear about us?", "type": "dropdown", "required": False,
             "options": ["Google", "Friend", "Instagram"]},
            {"text": "Best contact email?", "type": "email", "required": True},
        ]}
        r = pro_session.put(f"{API}/me/services/{initial_service['id']}/intake-form", json=payload)
        assert r.status_code == 200


# ---------- Booking with intake validation ----------
class TestBookingIntakeValidation:
    def _base_payload(self, service_id, date_str, start, email_suffix="x"):
        return {
            "service_id": service_id, "date": date_str, "start_time": start,
            "customer_name": "TEST_IntakeCust",
            "customer_email": f"TEST_intake_{email_suffix}_{uuid.uuid4().hex[:6]}@example.com",
            "customer_phone": "9876543210", "notes": "",
        }

    def test_missing_required_intake_400(self, future_monday, initial_service):
        slots = _get_slot(future_monday, initial_service["id"])
        body = self._base_payload(initial_service["id"], future_monday, slots[0])
        body["intake_answers"] = []
        r = requests.post(f"{API}/p/{PRO_SLUG}/book", json=body)
        assert r.status_code == 400, r.text
        assert "What brings you here today?" in r.text or "required" in r.text.lower()

    def test_invalid_email_in_intake_400(self, future_monday, initial_service, pro_session):
        # get current question ids
        qs = pro_session.get(f"{API}/me/services/{initial_service['id']}/intake-form").json()["questions"]
        q_short = next(q for q in qs if q["type"] == "short_text")
        q_email = next(q for q in qs if q["type"] == "email")
        slots = _get_slot(future_monday, initial_service["id"])
        body = self._base_payload(initial_service["id"], future_monday, slots[0], email_suffix="bademail")
        body["intake_answers"] = [
            {"question_id": q_short["id"], "answer": "Stress"},
            {"question_id": q_email["id"], "answer": "not-an-email"},
        ]
        r = requests.post(f"{API}/p/{PRO_SLUG}/book", json=body)
        assert r.status_code == 400
        assert "Invalid email" in r.text

    def test_invalid_url_in_intake_400(self, pro_session, future_tuesday, therapy_service):
        # put a url question on therapy_service
        url_q_payload = {"questions": [
            {"text": "Your website", "type": "url", "required": True}
        ]}
        r = pro_session.put(f"{API}/me/services/{therapy_service['id']}/intake-form", json=url_q_payload)
        assert r.status_code == 200
        q_id = r.json()["questions"][0]["id"]
        slots = _get_slot(future_tuesday, therapy_service["id"])
        body = {
            "service_id": therapy_service["id"], "date": future_tuesday, "start_time": slots[0],
            "customer_name": "TEST_UrlCust", "customer_email": f"TEST_url_{uuid.uuid4().hex[:6]}@example.com",
            "customer_phone": "9876543210", "notes": "",
            "intake_answers": [{"question_id": q_id, "answer": "google.com"}],
        }
        r2 = requests.post(f"{API}/p/{PRO_SLUG}/book", json=body)
        assert r2.status_code == 400
        assert "URL" in r2.text or "http" in r2.text


# ---------- Successful booking + snapshot + analytics ----------
@pytest.fixture(scope="session")
def successful_booking(pro_session, initial_service, future_monday, mongo_db):
    qs = pro_session.get(f"{API}/me/services/{initial_service['id']}/intake-form").json()["questions"]
    q_short = next(q for q in qs if q["type"] == "short_text")
    q_drop = next(q for q in qs if q["type"] == "dropdown")
    q_email = next(q for q in qs if q["type"] == "email")
    slots = _get_slot(future_monday, initial_service["id"])
    start = slots[1] if len(slots) > 1 else slots[0]
    body = {
        "service_id": initial_service["id"], "date": future_monday, "start_time": start,
        "customer_name": "TEST_GoodCust",
        "customer_email": f"TEST_good_{uuid.uuid4().hex[:6]}@example.com",
        "customer_phone": "9876543210", "notes": "",
        "intake_answers": [
            {"question_id": q_short["id"], "answer": "Burnout and anxiety"},
            {"question_id": q_drop["id"], "answer": "Google"},
            {"question_id": q_email["id"], "answer": "contact@example.com"},
        ],
    }
    r = requests.post(f"{API}/p/{PRO_SLUG}/book", json=body)
    assert r.status_code == 200, r.text
    return r.json(), qs


class TestBookingSnapshot:
    def test_intake_answers_in_booking(self, successful_booking):
        booking, qs = successful_booking
        snap = booking["intake_answers"]
        assert len(snap) == len(qs)
        # every question has question_text/id/type/answer
        for row in snap:
            assert "question_id" in row and "question_text" in row
            assert "question_type" in row and "answer" in row
        texts = {row["question_text"]: row["answer"] for row in snap}
        assert texts["What brings you here today?"] == "Burnout and anxiety"
        assert texts["How did you hear about us?"] == "Google"
        assert texts["Best contact email?"] == "contact@example.com"

    def test_booking_intake_answers_collection(self, successful_booking, mongo_db):
        booking, _ = successful_booking
        rows = list(mongo_db.booking_intake_answers.find({"booking_id": booking["id"]}, {"_id": 0}))
        # one row per non-empty answer (all 3 non-empty)
        assert len(rows) == 3
        # answer_lower exists & lowercased
        for r in rows:
            assert "answer_lower" in r
            assert r["answer_lower"] == r["answer"].lower()
        assert any(r["answer_lower"] == "burnout and anxiety" for r in rows)

    def test_me_bookings_returns_intake_answers(self, pro_session, successful_booking):
        booking, _ = successful_booking
        r = pro_session.get(f"{API}/me/bookings/{booking['id']}")
        assert r.status_code == 200
        data = r.json()
        assert "intake_answers" in data["booking"]
        assert len(data["booking"]["intake_answers"]) >= 1

    def test_activity_log_includes_intake_count(self, pro_session, successful_booking):
        booking, _ = successful_booking
        r = pro_session.get(f"{API}/me/bookings/{booking['id']}")
        acts = r.json()["activities"]
        created = [a for a in acts if a["action_type"] == "BOOKING_CREATED"]
        assert created
        assert created[0]["metadata"].get("intake_count") == 3


# ---------- Snapshot immutability when pro edits form ----------
class TestSnapshotImmutable:
    def test_old_booking_unaffected_by_form_edit(self, pro_session, initial_service, successful_booking):
        booking, _ = successful_booking
        # Replace intake form completely (no shared question ids)
        new_payload = {"questions": [
            {"text": "Brand new question only", "type": "short_text", "required": False}
        ]}
        r = pro_session.put(f"{API}/me/services/{initial_service['id']}/intake-form", json=new_payload)
        assert r.status_code == 200
        # Old booking still has original snapshot
        r2 = pro_session.get(f"{API}/me/bookings/{booking['id']}")
        snap = r2.json()["booking"]["intake_answers"]
        texts = [row["question_text"] for row in snap]
        assert "What brings you here today?" in texts
        assert "Best contact email?" in texts
        # Restore the original form
        restore = {"questions": [
            {"text": "What brings you here today?", "type": "short_text", "required": True},
            {"text": "How did you hear about us?", "type": "dropdown", "required": False,
             "options": ["Google", "Friend", "Instagram"]},
            {"text": "Best contact email?", "type": "email", "required": True},
        ]}
        pro_session.put(f"{API}/me/services/{initial_service['id']}/intake-form", json=restore)


# ---------- Clearing intake form ----------
class TestClearIntake:
    def test_empty_form_skips_intake_requirement(self, pro_session, therapy_service, future_tuesday):
        # Clear therapy_service intake form
        r = pro_session.put(f"{API}/me/services/{therapy_service['id']}/intake-form",
                            json={"questions": []})
        assert r.status_code == 200
        assert r.json()["questions"] == []
        # Book without intake_answers — should succeed
        slots = _get_slot(future_tuesday, therapy_service["id"])
        # Use last slot to avoid conflict
        start = slots[-1]
        body = {
            "service_id": therapy_service["id"], "date": future_tuesday, "start_time": start,
            "customer_name": "TEST_NoIntakeCust",
            "customer_email": f"TEST_nointake_{uuid.uuid4().hex[:6]}@example.com",
            "customer_phone": "9876543210", "notes": "", "intake_answers": [],
        }
        r2 = requests.post(f"{API}/p/{PRO_SLUG}/book", json=body)
        assert r2.status_code == 200, r2.text
        assert r2.json()["intake_answers"] == []


# ---------- [EMAIL:CONSOLE] log emission ----------
class TestEmailConsole:
    def test_console_email_log_present(self):
        # tail recent backend.err.log entries
        try:
            out = subprocess.check_output(
                ["tail", "-n", "500", "/var/log/supervisor/backend.err.log"],
                stderr=subprocess.STDOUT, timeout=5,
            ).decode("utf-8", errors="ignore")
        except Exception as e:
            pytest.skip(f"cannot read supervisor log: {e}")
        assert "[EMAIL:CONSOLE]" in out, "expected [EMAIL:CONSOLE] fallback log entries"
        assert "New booking" in out, "expected 'New booking' subject in console email log"
