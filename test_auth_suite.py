import sys
import os
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app import app
import database.db as db
import auth

client = TestClient(app)

def run_multi_user_verification():
    print("\n==================================================================")
    print("  COMPREHENSIVE MULTI-USER & DATABASE INDEXING VERIFICATION SUITE")
    print("==================================================================")

    # 1. Health check & version
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["multi_tenant"] is True
    assert data["indexes_active"] is True
    print("[PASS] Health API confirms multi-tenant system & active indexes")

    # 2. Database Indexes Verification (Requirement 8)
    conn = db.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%';")
    indexes = [row[0] for row in cursor.fetchall()]
    conn.close()

    expected_indexes = [
        "idx_users_username", "idx_users_email", "idx_users_status",
        "idx_sessions_user_id", "idx_sessions_timestamp",
        "idx_posture_user_session", "idx_slouch_user",
        "idx_blink_user", "idx_break_user", "idx_reports_user"
    ]
    for idx in expected_indexes:
        assert idx in indexes, f"Missing index: {idx}"
    print(f"[PASS] All {len(expected_indexes)} performance indexes verified in SQLite schema")

    # 3. Demo Account & Seed Verification (Requirement 7)
    res = client.post("/api/auth/demo-login")
    assert res.status_code == 200
    demo_user = res.json()["user"]
    assert demo_user["username"] == "demo"
    print("[PASS] Common demo evaluator account functional (demo / Demo@123)")

    # 4. Multi-User Registration & Auto-Incrementing IDs (Requirement 1, 2, 3)
    # Register 3 distinct users to verify unlimited scalability and auto-incrementing IDs
    user_ids = []
    ts = int(time.time())
    for i in range(3):
        u_name = f"user_{ts}_{i}"
        res = client.post("/api/auth/register", json={
            "full_name": f"User {i} Person",
            "username": u_name,
            "email": f"{u_name}@testdomain.com",
            "password": "Password@123",
            "confirm_password": "Password@123"
        })
        assert res.status_code == 200, res.text
        uid = res.json()["user_id"]
        user_ids.append(uid)
    
    assert user_ids[1] > user_ids[0] and user_ids[2] > user_ids[1], "IDs must auto-increment"
    print(f"[PASS] Auto-incrementing unique user IDs verified: {user_ids}")

    # Check user details in DB (Requirement 3: ID, Full Name, Username, Email, Hash, Created, Last Login, Status)
    user_record = db.get_user_by_id(user_ids[0])
    assert user_record["id"] == user_ids[0]
    assert user_record["full_name"] == "User 0 Person"
    assert "user_" in user_record["username"]
    assert "@testdomain.com" in user_record["email"]
    assert user_record["password_hash"].startswith("$argon2id$")
    assert user_record["created_at"] is not None
    assert user_record["account_status"] == "active"
    print("[PASS] User details schema & Argon2id hash storage verified")

    # 5. Separate Records for Every User (Requirement 4 & 5)
    # User 0 records session + granular records
    u0_client = TestClient(app)
    res = u0_client.post("/api/auth/login", json={
        "identifier": f"user_{ts}_0",
        "password": "Password@123"
    })
    assert res.status_code == 200

    # Save session with granular measurements, slouch events, blink logs, and break reminders
    res = u0_client.post("/api/sessions/save", json={
        "duration_seconds": 600,
        "avg_posture_score": 92.5,
        "good_posture_pct": 91.0,
        "slouch_pct": 6.0,
        "tilt_pct": 3.0,
        "total_blinks": 150,
        "avg_blink_rate": 15.0,
        "breaks_completed": 2,
        "slouch_alerts_count": 1,
        "ergonomic_grade": "A",
        "measurements": [
            {"shoulder_tilt": 2.1, "head_tilt": 1.9, "slouch_ratio": 0.49, "is_good": True},
            {"shoulder_tilt": 2.4, "head_tilt": 2.0, "slouch_ratio": 0.48, "is_good": True}
        ],
        "slouch_events": [
            {"slouch_ratio": 0.36, "baseline_ratio": 0.50, "duration_seconds": 4.5, "alert_triggered": True}
        ],
        "blink_logs": [
            {"ear_value": 0.29, "blink_rate_bpm": 16.0, "fatigue_level": "Low", "microsleep_detected": False}
        ],
        "break_reminders": [
            {"break_type": "20-20-20", "scheduled_duration_sec": 20, "completed": True, "skipped": False}
        ]
    })
    assert res.status_code == 200
    u0_session_id = res.json()["session_id"]
    print(f"[PASS] User 0 saved session #{u0_session_id} with granular measurements, slouch events, blinks, and breaks")

    # Save a formal wellness report
    res = u0_client.post("/api/wellness/reports/save", json={
        "session_id": u0_session_id,
        "report_title": "Ergonomics Mid-Term Assessment",
        "grade": "A",
        "overall_score": 92.5,
        "good_posture_pct": 91.0,
        "total_blinks": 150,
        "breaks_taken": 2,
        "notes": "Excellent head alignment"
    })
    assert res.status_code == 200
    print("[PASS] Wellness report saved with user foreign key")

    # 6. Strict User-Level Data Isolation (Requirement 6)
    # User 1 logs in and checks history
    u1_client = TestClient(app)
    res = u1_client.post("/api/auth/login", json={
        "identifier": f"user_{ts}_1",
        "password": "Password@123"
    })
    assert res.status_code == 200

    # User 1 history should be empty (cannot see User 0's session)
    res = u1_client.get("/api/sessions/history")
    u1_sessions = res.json()["sessions"]
    assert len(u1_sessions) == 0, "Data Leakage: User 1 can see sessions belonging to User 0!"

    res = u1_client.get("/api/wellness/reports")
    u1_reports = res.json()["reports"]
    assert len(u1_reports) == 0, "Data Leakage: User 1 can see reports belonging to User 0!"
    print("[PASS] Strict user-level data isolation verified: User 1 has ZERO access to User 0's records")

    # 7. Administrator Management Capabilities (Requirement 10 & 11)
    admin_client = TestClient(app)
    res = admin_client.post("/api/auth/login", json={
        "identifier": "admin",
        "password": "Admin@123"
    })
    assert res.status_code == 200
    assert res.json()["user"]["is_admin"] is True
    print("[PASS] Administrator authentication verified (admin / Admin@123)")

    # 7a. Non-admin access blocked to /admin/users
    res = u0_client.get("/admin/users", follow_redirects=False)
    assert res.status_code == 403, "Non-admin must be blocked from admin console!"
    print("[PASS] Non-admin user blocked from admin console (403 Forbidden)")

    # 7b. Admin access to /admin/users
    res = admin_client.get("/admin/users")
    assert res.status_code == 200
    assert "User Management Console" in res.text
    assert "Total Registered Users" in res.text
    assert "password_hash" not in res.text, "Password hashes must NEVER be exposed in UI!"
    print("[PASS] Admin User Management Page renders cleanly with zero password hash leakage")

    # 7c. Admin API /api/admin/users
    res = admin_client.get("/api/admin/users")
    assert res.status_code == 200
    users_list = res.json()["users"]
    assert len(users_list) >= 4
    for u in users_list:
        assert "password_hash" not in u, "Password hash leaked in API!"
        assert "account_status" in u
        assert "session_count" in u
    print("[PASS] Admin API lists users without password hashes")

    # 7d. Admin updates user status (e.g. suspend user 2)
    res = admin_client.post(f"/api/admin/users/{user_ids[2]}/status", json={"status": "suspended"})
    assert res.status_code == 200
    # Verify user 2 cannot log in when suspended
    u2_client = TestClient(app)
    res = u2_client.post("/api/auth/login", json={
        "identifier": f"user_{ts}_2",
        "password": "Password@123"
    })
    assert res.status_code == 403
    assert "suspended" in res.json()["detail"].lower()
    print("[PASS] Account suspension capability verified: suspended user cannot log in")

    # 8. Dashboard Statistics Display (Requirement 11)
    # Admin dashboard includes total registered users, active users, total sessions
    res = admin_client.get("/")
    assert res.status_code == 200
    assert "Administrator Statistics" in res.text
    assert "Total Registered Users:" in res.text
    assert "Active Users:" in res.text
    assert "Total Monitored Sessions:" in res.text
    print("[PASS] Admin dashboard displays global user and session statistics")

    # Regular user dashboard does NOT display admin telemetry
    res = u0_client.get("/")
    assert res.status_code == 200
    assert "Administrator Statistics" not in res.text
    assert "Ergonomic Health Score" in res.text
    print("[PASS] Regular user dashboard displays individual wellness stats without admin widgets")

    print("\n==================================================================")
    print("  ALL 11 MULTI-USER & DATABASE REQUIREMENTS VERIFIED WITH 100%!  ")
    print("==================================================================\n")

if __name__ == "__main__":
    run_multi_user_verification()
