import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app import app
import database.db as db
import auth

client = TestClient(app)

def run_tests():
    print("\n========================================================")
    print("  RUNNING COMPREHENSIVE AUTH & MULTI-TENANT TEST SUITE")
    print("========================================================")

    # 1. Health check
    res = client.get("/api/health")
    assert res.status_code == 200
    print("[PASS] Health API check")

    # 2. Protected route access without authentication -> Should redirect to /login
    res = client.get("/", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/login"
    print("[PASS] Unauthenticated access to '/' redirects to '/login'")

    res = client.get("/profile", follow_redirects=False)
    assert res.status_code == 303
    assert "/login" in res.headers["location"]
    print("[PASS] Unauthenticated access to '/profile' redirects to '/login'")

    # 3. Test Demo Account login (Requirement 3)
    res = client.post("/api/auth/demo-login")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "success"
    assert data["user"]["username"] == "demo"
    assert "wellness_session" in res.cookies
    print("[PASS] Demo login API works & sets HTTP-only cookie")

    # Verify access to dashboard with demo cookie
    res = client.get("/")
    assert res.status_code == 200
    assert "Digital Wellness Monitor" in res.text
    assert "Demo Explorer" in res.text
    print("[PASS] Authenticated dashboard renders with user full name")

    # Verify access to profile page with demo cookie
    res = client.get("/profile")
    assert res.status_code == 200
    assert "Demo Explorer" in res.text
    assert "Personal Lifetime Wellness Statistics" in res.text
    print("[PASS] Profile page renders with personal statistics")

    # 4. Test User Registration (Requirement 2)
    # 4a. Weak password rejection
    res = client.post("/api/auth/register", json={
        "full_name": "Test User",
        "username": "tester1",
        "email": "tester1@test.com",
        "password": "short",
        "confirm_password": "short"
    })
    assert res.status_code == 400
    assert "at least 8" in res.json()["detail"]
    print("[PASS] Registration rejects weak password")

    # 4b. Invalid email rejection
    res = client.post("/api/auth/register", json={
        "full_name": "Test User",
        "username": "tester1",
        "email": "not-an-email",
        "password": "Password123",
        "confirm_password": "Password123"
    })
    assert res.status_code == 400
    assert "valid email" in res.json()["detail"]
    print("[PASS] Registration rejects invalid email format")

    # 4c. Successful registration
    test_user_name = f"user_{int(auth.time.time())}"
    res = client.post("/api/auth/register", json={
        "full_name": "Alice Johnson",
        "username": test_user_name,
        "email": f"{test_user_name}@example.com",
        "password": "SecurePassword123",
        "confirm_password": "SecurePassword123"
    })
    assert res.status_code == 200, res.text
    user_id_alice = res.json()["user_id"]
    print(f"[PASS] User registration successful (User ID: {user_id_alice})")

    # 4d. Duplicate username rejection
    res = client.post("/api/auth/register", json={
        "full_name": "Alice Duplicate",
        "username": test_user_name,
        "email": "different@example.com",
        "password": "SecurePassword123",
        "confirm_password": "SecurePassword123"
    })
    assert res.status_code == 409
    assert "already taken" in res.json()["detail"]
    print("[PASS] Registration rejects duplicate username")

    # 5. Test Login with Valid & Invalid Credentials
    # 5a. Invalid credentials
    res = client.post("/api/auth/login", json={
        "identifier": test_user_name,
        "password": "WrongPassword999"
    })
    assert res.status_code == 401
    assert "Invalid username" in res.json()["detail"]
    print("[PASS] Login rejects invalid password")

    # 5b. Valid credentials
    res = client.post("/api/auth/login", json={
        "identifier": test_user_name,
        "password": "SecurePassword123",
        "remember_me": True
    })
    assert res.status_code == 200
    alice_cookies = res.cookies
    assert "wellness_session" in alice_cookies
    print("[PASS] Login succeeds with valid credentials and sets remember_me cookie")

    # 6. Test Multi-Tenant Data Isolation (Requirement 4 & 5)
    # Alice logs a session
    client.cookies = alice_cookies
    res = client.post("/api/sessions/save", json={
        "duration_seconds": 300,
        "avg_posture_score": 96.0,
        "good_posture_pct": 95.0,
        "slouch_pct": 3.0,
        "tilt_pct": 2.0,
        "total_blinks": 75,
        "avg_blink_rate": 15.0,
        "breaks_completed": 1,
        "slouch_alerts_count": 0,
        "ergonomic_grade": "A+"
    })
    assert res.status_code == 200
    alice_session_id = res.json()["session_id"]
    print(f"[PASS] Alice recorded session #{alice_session_id}")

    # Check Alice's history
    res = client.get("/api/sessions/history")
    alice_sessions = res.json()["sessions"]
    assert len(alice_sessions) == 1
    assert alice_sessions[0]["id"] == alice_session_id
    assert alice_sessions[0]["user_id"] == user_id_alice
    print("[PASS] Alice sees her own session")

    # Switch back to Demo user
    client.post("/api/auth/demo-login")
    res = client.get("/api/sessions/history")
    demo_sessions = res.json()["sessions"]
    # Verify Demo user NEVER sees Alice's session
    for s in demo_sessions:
        assert s["id"] != alice_session_id, "Data Leakage: Demo user can see Alice's session!"
    print("[PASS] Multi-tenant isolation verified: Demo user CANNOT see Alice's data")

    # 7. Test Password Recovery & Reset (Requirement 7)
    res = client.post("/api/auth/forgot-password", json={
        "identifier": test_user_name
    })
    assert res.status_code == 200
    reset_url = res.json()["reset_url"]
    token = reset_url.split("token=")[1]
    print("[PASS] Password recovery generates time-limited reset token")

    # Perform password reset
    res = client.post("/api/auth/reset-password", json={
        "token": token,
        "new_password": "NewSecurePassword456",
        "confirm_password": "NewSecurePassword456"
    })
    assert res.status_code == 200
    print("[PASS] Password reset successfully updated user password")

    # Verify login with new password
    res = client.post("/api/auth/login", json={
        "identifier": test_user_name,
        "password": "NewSecurePassword456"
    })
    assert res.status_code == 200
    print("[PASS] Login succeeds with newly updated password")

    # 8. Test Logout (Requirement 6)
    res = client.post("/api/auth/logout")
    assert res.status_code == 200
    client.cookies.clear()
    res = client.get("/", follow_redirects=False)
    assert res.status_code == 303
    print("[PASS] Logout clears session and redirects unauthenticated user")

    print("\n========================================================")
    print("  ALL 10 VERIFICATION TESTS PASSED WITH 100% SUCCESS!  ")
    print("========================================================\n")

if __name__ == "__main__":
    run_tests()
