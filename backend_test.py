#!/usr/bin/env python3
"""
Comprehensive backend test suite for Practora Razorpay subscription monetization (Phase 3).
Tests all critical scenarios without requiring live Razorpay configuration.
"""
import requests
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Backend URL
BASE_URL = "http://localhost:8001/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_CREDS = {"email": "admin@practora.in", "password": "admin123"}
PRO_ANJALI_CREDS = {"email": "anjali@practora.in", "password": "demo123"}
PRO_RAJ_CREDS = {"email": "raj@practora.in", "password": "demo123"}

# Color codes for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures = []
    
    def add_pass(self, test_name: str):
        self.passed += 1
        print(f"{GREEN}✓{RESET} {test_name}")
    
    def add_fail(self, test_name: str, reason: str, details: Optional[Dict] = None):
        self.failed += 1
        self.failures.append({"test": test_name, "reason": reason, "details": details})
        print(f"{RED}✗{RESET} {test_name}")
        print(f"  {RED}Reason:{RESET} {reason}")
        if details:
            print(f"  {RED}Details:{RESET} {json.dumps(details, indent=2)}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"{BLUE}TEST SUMMARY{RESET}")
        print(f"{'='*60}")
        print(f"Total: {total} | {GREEN}Passed: {self.passed}{RESET} | {RED}Failed: {self.failed}{RESET}")
        
        if self.failures:
            print(f"\n{RED}FAILED TESTS:{RESET}")
            for i, failure in enumerate(self.failures, 1):
                print(f"\n{i}. {failure['test']}")
                print(f"   Reason: {failure['reason']}")
                if failure.get('details'):
                    print(f"   Details: {json.dumps(failure['details'], indent=6)}")
        
        return self.failed == 0

result = TestResult()

def login(creds: Dict[str, str]) -> Optional[str]:
    """Login and return access token (from cookie or response)."""
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json=creds)
        if resp.status_code == 200:
            # Try to get token from cookie first
            token = resp.cookies.get("access_token")
            if token:
                return token
            # Fallback to response body
            data = resp.json()
            return data.get("token")
        return None
    except Exception as e:
        print(f"{RED}Login failed: {e}{RESET}")
        return None

def make_request(method: str, endpoint: str, token: Optional[str] = None, 
                 json_data: Optional[Dict] = None, headers: Optional[Dict] = None) -> requests.Response:
    """Make an authenticated request."""
    url = f"{BASE_URL}{endpoint}"
    req_headers = headers or {}
    
    if token:
        req_headers["Authorization"] = f"Bearer {token}"
    
    if method == "GET":
        return requests.get(url, headers=req_headers)
    elif method == "POST":
        return requests.post(url, json=json_data, headers=req_headers)
    elif method == "PUT":
        return requests.put(url, json=json_data, headers=req_headers)
    elif method == "DELETE":
        return requests.delete(url, headers=req_headers)
    else:
        raise ValueError(f"Unsupported method: {method}")

print(f"\n{BLUE}{'='*60}{RESET}")
print(f"{BLUE}Practora Phase 3: Razorpay Subscription Backend Tests{RESET}")
print(f"{BLUE}{'='*60}{RESET}\n")

# ============================================================================
# TEST 1: GET /api/settings/public (no auth required)
# ============================================================================
print(f"\n{YELLOW}[TEST 1] Public Settings Endpoint{RESET}")
try:
    resp = requests.get(f"{BASE_URL}/settings/public")
    if resp.status_code == 200:
        data = resp.json()
        if (data.get("subscription_amount_inr") == 500 and 
            data.get("trial_days") == 7 and 
            data.get("razorpay_configured") == False):
            result.add_pass("GET /api/settings/public returns correct defaults")
        else:
            result.add_fail("GET /api/settings/public", 
                          "Incorrect response values", 
                          {"expected": {"subscription_amount_inr": 500, "trial_days": 7, "razorpay_configured": False},
                           "actual": data})
    else:
        result.add_fail("GET /api/settings/public", 
                      f"Expected 200, got {resp.status_code}", 
                      {"response": resp.text})
except Exception as e:
    result.add_fail("GET /api/settings/public", f"Exception: {str(e)}")

# ============================================================================
# TEST 2: Auth flow as pro (anjali)
# ============================================================================
print(f"\n{YELLOW}[TEST 2] Auth Flow (Pro User - Anjali){RESET}")
anjali_token = login(PRO_ANJALI_CREDS)
if anjali_token:
    result.add_pass("POST /api/auth/login (anjali) - login successful")
    
    # Check /api/auth/me
    try:
        resp = make_request("GET", "/auth/me", token=anjali_token)
        if resp.status_code == 200:
            user_data = resp.json()
            if (user_data.get("subscription_status") == "trial" and 
                user_data.get("trial_ends_at")):
                # Verify trial_ends_at is in the future
                trial_ends = datetime.fromisoformat(user_data["trial_ends_at"].replace("Z", "+00:00"))
                if trial_ends > datetime.now(trial_ends.tzinfo):
                    result.add_pass("GET /api/auth/me - returns trial status with future trial_ends_at")
                else:
                    result.add_fail("GET /api/auth/me", 
                                  "trial_ends_at is not in the future", 
                                  {"trial_ends_at": user_data["trial_ends_at"]})
            else:
                result.add_fail("GET /api/auth/me", 
                              "Missing or incorrect subscription_status/trial_ends_at", 
                              {"user_data": user_data})
        else:
            result.add_fail("GET /api/auth/me", 
                          f"Expected 200, got {resp.status_code}", 
                          {"response": resp.text})
    except Exception as e:
        result.add_fail("GET /api/auth/me", f"Exception: {str(e)}")
else:
    result.add_fail("POST /api/auth/login (anjali)", "Login failed - no token returned")

# ============================================================================
# TEST 3: GET /api/me/subscription (authenticated as pro)
# ============================================================================
print(f"\n{YELLOW}[TEST 3] Pro Subscription Status{RESET}")
if anjali_token:
    try:
        resp = make_request("GET", "/me/subscription", token=anjali_token)
        if resp.status_code == 200:
            data = resp.json()
            if (data.get("has_access") == True and 
                data.get("reason") == "trial" and 
                data.get("subscription_status") == "trial" and
                data.get("platform_amount_inr") == 500 and
                data.get("razorpay_configured") == False and
                isinstance(data.get("recent_events"), list)):
                result.add_pass("GET /api/me/subscription - returns correct trial status")
            else:
                result.add_fail("GET /api/me/subscription", 
                              "Incorrect response structure or values", 
                              {"expected": {"has_access": True, "reason": "trial", "subscription_status": "trial", 
                                          "platform_amount_inr": 500, "razorpay_configured": False},
                               "actual": data})
        else:
            result.add_fail("GET /api/me/subscription", 
                          f"Expected 200, got {resp.status_code}", 
                          {"response": resp.text})
    except Exception as e:
        result.add_fail("GET /api/me/subscription", f"Exception: {str(e)}")

# ============================================================================
# TEST 4: POST /api/me/subscription/create (Razorpay NOT configured)
# ============================================================================
print(f"\n{YELLOW}[TEST 4] Create Subscription (Razorpay NOT configured){RESET}")
if anjali_token:
    try:
        resp = make_request("POST", "/me/subscription/create", token=anjali_token)
        if resp.status_code == 503:
            data = resp.json()
            if "Payments are not configured yet" in data.get("detail", ""):
                result.add_pass("POST /api/me/subscription/create - returns 503 when Razorpay not configured")
            else:
                result.add_fail("POST /api/me/subscription/create", 
                              "Expected 'Payments are not configured yet' message", 
                              {"response": data})
        else:
            result.add_fail("POST /api/me/subscription/create", 
                          f"Expected 503, got {resp.status_code}", 
                          {"response": resp.text})
    except Exception as e:
        result.add_fail("POST /api/me/subscription/create", f"Exception: {str(e)}")

# ============================================================================
# TEST 5: POST /api/me/subscription/cancel (no subscription_id)
# ============================================================================
print(f"\n{YELLOW}[TEST 5] Cancel Subscription (no active subscription){RESET}")
if anjali_token:
    try:
        resp = make_request("POST", "/me/subscription/cancel", token=anjali_token)
        if resp.status_code == 400:
            data = resp.json()
            if "No active subscription found" in data.get("detail", ""):
                result.add_pass("POST /api/me/subscription/cancel - returns 400 when no subscription")
            else:
                result.add_fail("POST /api/me/subscription/cancel", 
                              "Expected 'No active subscription found' message", 
                              {"response": data})
        else:
            result.add_fail("POST /api/me/subscription/cancel", 
                          f"Expected 400, got {resp.status_code}", 
                          {"response": resp.text})
    except Exception as e:
        result.add_fail("POST /api/me/subscription/cancel", f"Exception: {str(e)}")

# ============================================================================
# TEST 6: Admin flow
# ============================================================================
print(f"\n{YELLOW}[TEST 6] Admin Endpoints{RESET}")

# 6a. Admin login
admin_token = login(ADMIN_CREDS)
if admin_token:
    result.add_pass("POST /api/auth/login (admin) - login successful")
    
    # Verify admin role
    try:
        resp = make_request("GET", "/auth/me", token=admin_token)
        if resp.status_code == 200:
            admin_data = resp.json()
            if admin_data.get("role") == "admin":
                result.add_pass("GET /api/auth/me (admin) - role is 'admin'")
            else:
                result.add_fail("GET /api/auth/me (admin)", 
                              f"Expected role 'admin', got '{admin_data.get('role')}'", 
                              {"user_data": admin_data})
        else:
            result.add_fail("GET /api/auth/me (admin)", 
                          f"Expected 200, got {resp.status_code}")
    except Exception as e:
        result.add_fail("GET /api/auth/me (admin)", f"Exception: {str(e)}")
    
    # 6b. GET /api/admin/settings
    try:
        resp = make_request("GET", "/admin/settings", token=admin_token)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("razorpay_configured") == False:
                result.add_pass("GET /api/admin/settings - returns settings with razorpay_configured=false")
            else:
                result.add_fail("GET /api/admin/settings", 
                              "Expected razorpay_configured=false", 
                              {"response": data})
        else:
            result.add_fail("GET /api/admin/settings", 
                          f"Expected 200, got {resp.status_code}", 
                          {"response": resp.text})
    except Exception as e:
        result.add_fail("GET /api/admin/settings", f"Exception: {str(e)}")
    
    # 6c. PUT /api/admin/settings (change to 749/10)
    try:
        resp = make_request("PUT", "/admin/settings", token=admin_token, 
                          json_data={"subscription_amount_inr": 749, "trial_days": 10})
        if resp.status_code == 200:
            data = resp.json()
            if data.get("subscription_amount_inr") == 749 and data.get("trial_days") == 10:
                result.add_pass("PUT /api/admin/settings - updates to 749/10")
                
                # Verify public settings reflect the change
                pub_resp = requests.get(f"{BASE_URL}/settings/public")
                if pub_resp.status_code == 200:
                    pub_data = pub_resp.json()
                    if pub_data.get("subscription_amount_inr") == 749 and pub_data.get("trial_days") == 10:
                        result.add_pass("GET /api/settings/public - reflects updated values (749/10)")
                    else:
                        result.add_fail("GET /api/settings/public after update", 
                                      "Public settings don't reflect admin changes", 
                                      {"expected": {"subscription_amount_inr": 749, "trial_days": 10},
                                       "actual": pub_data})
            else:
                result.add_fail("PUT /api/admin/settings", 
                              "Response doesn't reflect updated values", 
                              {"expected": {"subscription_amount_inr": 749, "trial_days": 10},
                               "actual": data})
        else:
            result.add_fail("PUT /api/admin/settings", 
                          f"Expected 200, got {resp.status_code}", 
                          {"response": resp.text})
    except Exception as e:
        result.add_fail("PUT /api/admin/settings (749/10)", f"Exception: {str(e)}")
    
    # 6d. PUT /api/admin/settings (restore to 500/7)
    try:
        resp = make_request("PUT", "/admin/settings", token=admin_token, 
                          json_data={"subscription_amount_inr": 500, "trial_days": 7})
        if resp.status_code == 200:
            data = resp.json()
            if data.get("subscription_amount_inr") == 500 and data.get("trial_days") == 7:
                result.add_pass("PUT /api/admin/settings - restores to 500/7")
            else:
                result.add_fail("PUT /api/admin/settings (restore)", 
                              "Failed to restore to 500/7", 
                              {"actual": data})
        else:
            result.add_fail("PUT /api/admin/settings (restore)", 
                          f"Expected 200, got {resp.status_code}")
    except Exception as e:
        result.add_fail("PUT /api/admin/settings (restore)", f"Exception: {str(e)}")
    
    # 6e. GET /api/admin/subscriptions
    try:
        resp = make_request("GET", "/admin/subscriptions", token=admin_token)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) >= 2:
                # Check if anjali and raj are in the list with trial status
                anjali_found = any(u.get("email") == "anjali@practora.in" and 
                                 u.get("subscription_status") == "trial" for u in data)
                raj_found = any(u.get("email") == "raj@practora.in" and 
                              u.get("subscription_status") == "trial" for u in data)
                
                if anjali_found and raj_found:
                    result.add_pass("GET /api/admin/subscriptions - returns array with anjali & raj on trial")
                else:
                    result.add_fail("GET /api/admin/subscriptions", 
                                  "Missing anjali or raj with trial status", 
                                  {"users": [{"email": u.get("email"), "status": u.get("subscription_status")} 
                                           for u in data]})
            else:
                result.add_fail("GET /api/admin/subscriptions", 
                              "Expected array with at least 2 users", 
                              {"response": data})
        else:
            result.add_fail("GET /api/admin/subscriptions", 
                          f"Expected 200, got {resp.status_code}", 
                          {"response": resp.text})
    except Exception as e:
        result.add_fail("GET /api/admin/subscriptions", f"Exception: {str(e)}")
    
    # 6f. Test admin endpoints with non-admin user (should get 403)
    if anjali_token:
        print(f"\n{YELLOW}[TEST 6f] Admin Endpoints with Non-Admin User (403 expected){RESET}")
        
        # GET /api/admin/settings as non-admin
        try:
            resp = make_request("GET", "/admin/settings", token=anjali_token)
            if resp.status_code == 403:
                result.add_pass("GET /api/admin/settings (non-admin) - returns 403")
            else:
                result.add_fail("GET /api/admin/settings (non-admin)", 
                              f"Expected 403, got {resp.status_code}", 
                              {"response": resp.text})
        except Exception as e:
            result.add_fail("GET /api/admin/settings (non-admin)", f"Exception: {str(e)}")
        
        # PUT /api/admin/settings as non-admin
        try:
            resp = make_request("PUT", "/admin/settings", token=anjali_token, 
                              json_data={"subscription_amount_inr": 600, "trial_days": 5})
            if resp.status_code == 403:
                result.add_pass("PUT /api/admin/settings (non-admin) - returns 403")
            else:
                result.add_fail("PUT /api/admin/settings (non-admin)", 
                              f"Expected 403, got {resp.status_code}", 
                              {"response": resp.text})
        except Exception as e:
            result.add_fail("PUT /api/admin/settings (non-admin)", f"Exception: {str(e)}")
        
        # GET /api/admin/subscriptions as non-admin
        try:
            resp = make_request("GET", "/admin/subscriptions", token=anjali_token)
            if resp.status_code == 403:
                result.add_pass("GET /api/admin/subscriptions (non-admin) - returns 403")
            else:
                result.add_fail("GET /api/admin/subscriptions (non-admin)", 
                              f"Expected 403, got {resp.status_code}", 
                              {"response": resp.text})
        except Exception as e:
            result.add_fail("GET /api/admin/subscriptions (non-admin)", f"Exception: {str(e)}")
else:
    result.add_fail("POST /api/auth/login (admin)", "Admin login failed")

# ============================================================================
# TEST 7: Webhook signature verification
# ============================================================================
print(f"\n{YELLOW}[TEST 7] Razorpay Webhook Signature Verification{RESET}")

# 7a. No X-Razorpay-Signature header
try:
    resp = requests.post(f"{BASE_URL}/webhooks/razorpay", 
                        json={"event": "test.event", "payload": {}})
    if resp.status_code == 400:
        data = resp.json()
        if "Invalid signature" in data.get("detail", ""):
            result.add_pass("POST /api/webhooks/razorpay (no signature) - returns 400")
        else:
            result.add_fail("POST /api/webhooks/razorpay (no signature)", 
                          "Expected 'Invalid signature' message", 
                          {"response": data})
    else:
        result.add_fail("POST /api/webhooks/razorpay (no signature)", 
                      f"Expected 400, got {resp.status_code}", 
                      {"response": resp.text})
except Exception as e:
    result.add_fail("POST /api/webhooks/razorpay (no signature)", f"Exception: {str(e)}")

# 7b. Invalid X-Razorpay-Signature
try:
    resp = requests.post(f"{BASE_URL}/webhooks/razorpay", 
                        json={"event": "test.event", "payload": {}},
                        headers={"X-Razorpay-Signature": "garbage"})
    if resp.status_code == 400:
        data = resp.json()
        if "Invalid signature" in data.get("detail", ""):
            result.add_pass("POST /api/webhooks/razorpay (invalid signature) - returns 400")
        else:
            result.add_fail("POST /api/webhooks/razorpay (invalid signature)", 
                          "Expected 'Invalid signature' message", 
                          {"response": data})
    else:
        result.add_fail("POST /api/webhooks/razorpay (invalid signature)", 
                      f"Expected 400, got {resp.status_code}", 
                      {"response": resp.text})
except Exception as e:
    result.add_fail("POST /api/webhooks/razorpay (invalid signature)", f"Exception: {str(e)}")

# ============================================================================
# TEST 8: Public profile / booking gate
# ============================================================================
print(f"\n{YELLOW}[TEST 8] Public Profile & Booking Gate{RESET}")

# 8a. GET /api/p/dr-anjali
try:
    resp = requests.get(f"{BASE_URL}/p/dr-anjali")
    if resp.status_code == 200:
        data = resp.json()
        if (data.get("booking_enabled") == True and 
            data.get("professional") and 
            isinstance(data.get("services"), list)):
            result.add_pass("GET /api/p/dr-anjali - returns booking_enabled=true (trial active)")
            
            # Store service_id for booking test
            services = data.get("services", [])
            if services:
                service_id = services[0].get("id")
                duration_min = services[0].get("duration_min", 45)
                
                # 8b. GET /api/p/dr-anjali/slots
                # Calculate a valid future date (7 days from now, on a weekday)
                future_date = datetime.now() + timedelta(days=7)
                # Ensure it's a weekday (Mon-Fri)
                while future_date.weekday() >= 5:  # 5=Sat, 6=Sun
                    future_date += timedelta(days=1)
                date_str = future_date.strftime("%Y-%m-%d")
                
                try:
                    slots_resp = requests.get(f"{BASE_URL}/p/dr-anjali/slots", 
                                            params={"date": date_str, "service_id": service_id})
                    if slots_resp.status_code == 200:
                        slots_data = slots_resp.json()
                        slots = slots_data.get("slots", [])
                        if isinstance(slots, list) and len(slots) > 0:
                            result.add_pass(f"GET /api/p/dr-anjali/slots - returns slots for {date_str}")
                            
                            # 8c. POST /api/p/dr-anjali/book
                            booking_payload = {
                                "service_id": service_id,
                                "date": date_str,
                                "start_time": slots[0],  # Use first available slot
                                "customer_name": "Test Customer",
                                "customer_email": "test.customer@example.com",
                                "customer_phone": "+91 9876543210",
                                "notes": "Test booking for Phase 3",
                                "intake_answers": []
                            }
                            
                            try:
                                book_resp = requests.post(f"{BASE_URL}/p/dr-anjali/book", 
                                                        json=booking_payload)
                                if book_resp.status_code in [200, 201]:
                                    book_data = book_resp.json()
                                    if book_data.get("id"):
                                        result.add_pass("POST /api/p/dr-anjali/book - booking created during trial")
                                    else:
                                        result.add_fail("POST /api/p/dr-anjali/book", 
                                                      "Response missing booking id", 
                                                      {"response": book_data})
                                else:
                                    result.add_fail("POST /api/p/dr-anjali/book", 
                                                  f"Expected 200/201, got {book_resp.status_code}", 
                                                  {"response": book_resp.text})
                            except Exception as e:
                                result.add_fail("POST /api/p/dr-anjali/book", f"Exception: {str(e)}")
                        else:
                            result.add_fail("GET /api/p/dr-anjali/slots", 
                                          f"No slots available for {date_str}", 
                                          {"response": slots_data})
                    else:
                        result.add_fail("GET /api/p/dr-anjali/slots", 
                                      f"Expected 200, got {slots_resp.status_code}", 
                                      {"response": slots_resp.text})
                except Exception as e:
                    result.add_fail("GET /api/p/dr-anjali/slots", f"Exception: {str(e)}")
            else:
                result.add_fail("GET /api/p/dr-anjali", 
                              "No services found for booking test", 
                              {"response": data})
        else:
            result.add_fail("GET /api/p/dr-anjali", 
                          "Incorrect response structure", 
                          {"expected": {"booking_enabled": True, "professional": "object", "services": "array"},
                           "actual": data})
    else:
        result.add_fail("GET /api/p/dr-anjali", 
                      f"Expected 200, got {resp.status_code}", 
                      {"response": resp.text})
except Exception as e:
    result.add_fail("GET /api/p/dr-anjali", f"Exception: {str(e)}")

# ============================================================================
# TEST 9: Existing lifecycle regression check (Phase 1/2 smoke test)
# ============================================================================
print(f"\n{YELLOW}[TEST 9] Existing Lifecycle Regression Check{RESET}")

if anjali_token:
    # 9a. GET /api/me/services
    try:
        resp = make_request("GET", "/me/services", token=anjali_token)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) >= 2:
                result.add_pass("GET /api/me/services - returns services (Phase 1/2 intact)")
            else:
                result.add_fail("GET /api/me/services", 
                              "Expected at least 2 seeded services", 
                              {"response": data})
        else:
            result.add_fail("GET /api/me/services", 
                          f"Expected 200, got {resp.status_code}", 
                          {"response": resp.text})
    except Exception as e:
        result.add_fail("GET /api/me/services", f"Exception: {str(e)}")
    
    # 9b. GET /api/me/bookings
    try:
        resp = make_request("GET", "/me/bookings", token=anjali_token)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                result.add_pass("GET /api/me/bookings - returns bookings array (Phase 1/2 intact)")
            else:
                result.add_fail("GET /api/me/bookings", 
                              "Expected array response", 
                              {"response": data})
        else:
            result.add_fail("GET /api/me/bookings", 
                          f"Expected 200, got {resp.status_code}", 
                          {"response": resp.text})
    except Exception as e:
        result.add_fail("GET /api/me/bookings", f"Exception: {str(e)}")

# 9c. GET /api/categories
try:
    resp = requests.get(f"{BASE_URL}/categories")
    if resp.status_code == 200:
        data = resp.json()
        if isinstance(data, list) and len(data) == 8:
            result.add_pass("GET /api/categories - returns 8 categories (Phase 1/2 intact)")
        else:
            result.add_fail("GET /api/categories", 
                          "Expected array of 8 categories", 
                          {"response": data})
    else:
        result.add_fail("GET /api/categories", 
                      f"Expected 200, got {resp.status_code}", 
                      {"response": resp.text})
except Exception as e:
    result.add_fail("GET /api/categories", f"Exception: {str(e)}")

# ============================================================================
# FINAL SUMMARY
# ============================================================================
success = result.summary()

if success:
    print(f"\n{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}ALL TESTS PASSED ✓{RESET}")
    print(f"{GREEN}{'='*60}{RESET}\n")
    exit(0)
else:
    print(f"\n{RED}{'='*60}{RESET}")
    print(f"{RED}SOME TESTS FAILED ✗{RESET}")
    print(f"{RED}{'='*60}{RESET}\n")
    exit(1)
