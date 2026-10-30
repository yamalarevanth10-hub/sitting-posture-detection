import os
import uvicorn
from typing import Optional, List
from fastapi import FastAPI, Request, Response, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from database.db import (
    get_db, init_db, get_user_by_id, get_user_by_username_or_email,
    create_user, check_duplicate_user, update_user_last_login,
    update_user_password, update_user_profile, update_user_status,
    get_all_users, get_total_users_count, get_active_users_count,
    get_total_sessions_count_global,
    save_session, get_recent_sessions, get_analytics_summary,
    log_posture_measurement, log_slouch_event, log_eye_blink,
    log_break_reminder, save_wellness_report, get_user_wellness_reports,
    get_settings, update_settings
)
import auth

# Initialize SQLite database, indexes and seeded accounts
init_db()

app = FastAPI(
    title="Digital Wellness Monitor - Posture & Eye Blink Detection AI",
    description="Multi-user AI system for real-time sitting posture detection, eye blinking, break alerts, and user administration.",
    version="2.2.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ==========================================
# Authentication Helpers & Dependencies
# ==========================================

def get_current_user_from_request(request: Request) -> Optional[dict]:
    """Extracts and verifies the authenticated user from the HTTP-only session cookie."""
    cookie = request.cookies.get(auth.SESSION_COOKIE_NAME)
    if not cookie:
        return None
    user_id = auth.verify_session_token(cookie)
    if not user_id:
        return None
    user = get_user_by_id(user_id)
    # Check if account is suspended
    if user and user.get("account_status") == "suspended":
        return None
    return user

async def require_auth_user(request: Request) -> dict:
    """Dependency ensuring user is authenticated; raises 401 if not."""
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in to continue."
        )
    return user

async def require_admin_user(request: Request) -> dict:
    """Dependency ensuring user is an authenticated administrator; raises 403 if not."""
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required."
        )
    if not user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required."
        )
    return user

# ==========================================
# Page Routes (HTML)
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Main Monitoring Dashboard - Protected Route (Requires Login)."""
    user = get_current_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    
    context = {
        "user": user,
        "personal_summary": get_analytics_summary(user_id=user["id"])
    }

    # If administrator, provide platform-wide telemetry
    if user.get("is_admin"):
        context["total_registered_users"] = get_total_users_count()
        context["active_users"] = get_active_users_count()
        context["total_sessions_global"] = get_total_sessions_count_global()

    return templates.TemplateResponse(request=request, name="index.html", context=context)

@app.get("/login", response_class=HTMLResponse)
async def read_login(request: Request):
    """Login Page."""
    user = get_current_user_from_request(request)
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request=request, name="login.html")

@app.get("/register", response_class=HTMLResponse)
async def read_register(request: Request):
    """Registration Page (Supports unlimited registrations)."""
    user = get_current_user_from_request(request)
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request=request, name="register.html")

@app.get("/forgot-password", response_class=HTMLResponse)
async def read_forgot_password(request: Request):
    """Forgot Password Page."""
    return templates.TemplateResponse(request=request, name="forgot_password.html")

@app.get("/reset-password", response_class=HTMLResponse)
async def read_reset_password(request: Request):
    """Reset Password Page with token."""
    return templates.TemplateResponse(request=request, name="reset_password.html")

@app.get("/profile", response_class=HTMLResponse)
async def read_profile(request: Request):
    """User Profile & Lifetime Statistics Dashboard - Protected Route."""
    user = get_current_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login?next=/profile", status_code=status.HTTP_303_SEE_OTHER)
    summary = get_analytics_summary(user_id=user["id"])
    return templates.TemplateResponse(request=request, name="profile.html", context={"user": user, "summary": summary})

@app.get("/admin/users", response_class=HTMLResponse)
async def read_admin_users(request: Request):
    """Administrator User Management Console (Requirement 10 & 11)."""
    user = get_current_user_from_request(request)
    if not user:
        return RedirectResponse(url="/login?next=/admin/users", status_code=status.HTTP_303_SEE_OTHER)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Administrator access required.")

    users_list = get_all_users()
    return templates.TemplateResponse(
        request=request,
        name="admin_users.html",
        context={
            "current_user": user,
            "users": users_list,
            "total_users": get_total_users_count(),
            "active_users": get_active_users_count(),
            "total_sessions": get_total_sessions_count_global()
        }
    )

@app.get("/logout")
async def handle_logout_redirect(response: Response):
    """Logs the user out and clears the session cookie."""
    redirect = RedirectResponse(url="/login?logged_out=1", status_code=status.HTTP_303_SEE_OTHER)
    redirect.delete_cookie(auth.SESSION_COOKIE_NAME, path="/")
    return redirect

# ==========================================
# Authentication & Account API Endpoints
# ==========================================

@app.post("/api/auth/login")
async def api_login(request: Request, response: Response):
    """Authenticates username/email & password and sets an HTTP-only session cookie."""
    data = await request.json()
    identifier = data.get("identifier", "").strip()
    password = data.get("password", "")
    remember_me = bool(data.get("remember_me", False))

    if not identifier or not password:
        raise HTTPException(status_code=400, detail="Username/email and password are required.")

    # Rate limiting check
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{client_ip}:{identifier.lower()}"
    is_limited, remaining_secs = auth.is_rate_limited(rate_key)
    if is_limited:
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed login attempts. Please wait {remaining_secs} seconds before trying again."
        )

    user = get_user_by_username_or_email(identifier)
    if not user or not auth.verify_password(user["password_hash"], password):
        auth.record_failed_attempt(rate_key)
        raise HTTPException(status_code=401, detail="Invalid username/email or password.")

    if user.get("account_status") == "suspended":
        raise HTTPException(status_code=403, detail="Your account has been suspended. Please contact the administrator.")

    # Clear rate limit and update last login
    auth.clear_failed_attempts(rate_key)
    update_user_last_login(user["id"])

    # Session duration: 7 days if remember_me is checked, 24 hours otherwise
    max_age = 86400 * 7 if remember_me else 86400
    token = auth.create_session_token(user["id"])

    res = JSONResponse({
        "status": "success",
        "message": "Authenticated successfully",
        "user": {
            "id": user["id"],
            "full_name": user["full_name"],
            "username": user["username"],
            "email": user["email"],
            "is_admin": bool(user.get("is_admin", 0))
        }
    })
    res.set_cookie(
        key=auth.SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/"
    )
    return res

@app.post("/api/auth/demo-login")
async def api_demo_login(response: Response):
    """Instant 1-click login for the public demo account."""
    demo_user = get_user_by_username_or_email("demo")
    if not demo_user:
        raise HTTPException(status_code=500, detail="Demo account not initialized.")

    update_user_last_login(demo_user["id"])
    token = auth.create_session_token(demo_user["id"])

    res = JSONResponse({
        "status": "success",
        "message": "Demo session started",
        "user": {
            "id": demo_user["id"],
            "full_name": demo_user["full_name"],
            "username": demo_user["username"],
            "email": demo_user["email"],
            "is_admin": False
        }
    })
    res.set_cookie(
        key=auth.SESSION_COOKIE_NAME,
        value=token,
        max_age=86400 * 3,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/"
    )
    return res

@app.post("/api/auth/register")
async def api_register(request: Request):
    """Registers a new user account (unlimited users supported)."""
    data = await request.json()
    full_name = data.get("full_name", "").strip()
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")
    confirm_password = data.get("confirm_password", "")

    if not full_name or not username or not email or not password:
        raise HTTPException(status_code=400, detail="All fields are required.")

    if password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    # Validate email
    if not auth.validate_email(email):
        raise HTTPException(status_code=400, detail="Please provide a valid email address.")

    # Validate username format
    if len(username) < 3 or not username.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Username must be at least 3 alphanumeric characters.")

    # Validate password strength
    valid_pwd, pwd_msg = auth.validate_password_strength(password)
    if not valid_pwd:
        raise HTTPException(status_code=400, detail=pwd_msg)

    # Check duplicates
    is_dup, dup_msg = check_duplicate_user(username, email)
    if is_dup:
        raise HTTPException(status_code=409, detail=dup_msg)

    # Hash password with Argon2
    pwd_hash = auth.hash_password(password)
    user_id = create_user(full_name, username, email, pwd_hash)

    return {"status": "success", "message": "Account created successfully.", "user_id": user_id}

@app.post("/api/auth/forgot-password")
async def api_forgot_password(request: Request):
    """Generates a secure password reset token."""
    data = await request.json()
    identifier = data.get("identifier", "").strip()

    if not identifier:
        raise HTTPException(status_code=400, detail="Username or email is required.")

    user = get_user_by_username_or_email(identifier)
    if not user:
        raise HTTPException(status_code=404, detail="No registered account found with that username or email.")

    token = auth.create_reset_token(user["id"])
    reset_url = f"/reset-password?token={token}"

    return {
        "status": "success",
        "message": f"Password reset link generated for {user['email']}.",
        "reset_url": reset_url
    }

@app.post("/api/auth/reset-password")
async def api_reset_password(request: Request):
    """Validates token and updates the user's password."""
    data = await request.json()
    token = data.get("token", "")
    new_password = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")

    if not token or not new_password:
        raise HTTPException(status_code=400, detail="Reset token and new password are required.")

    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    user_id = auth.verify_reset_token(token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token. Please request a new link.")

    valid_pwd, pwd_msg = auth.validate_password_strength(new_password)
    if not valid_pwd:
        raise HTTPException(status_code=400, detail=pwd_msg)

    new_hash = auth.hash_password(new_password)
    update_user_password(user_id, new_hash)

    return {"status": "success", "message": "Password updated successfully."}

@app.post("/api/auth/logout")
async def api_logout(response: Response):
    """Clears the session cookie."""
    res = JSONResponse({"status": "success", "message": "Logged out successfully."})
    res.delete_cookie(auth.SESSION_COOKIE_NAME, path="/")
    return res

# ==========================================
# Administrator Management Endpoints
# ==========================================

@app.get("/api/admin/users")
async def api_admin_list_users(current_admin: dict = Depends(require_admin_user)):
    """Returns list of registered users. Password hashes are strictly omitted."""
    users_list = get_all_users()
    return {"status": "success", "users": users_list, "total": len(users_list)}

@app.post("/api/admin/users/{user_id}/status")
async def api_admin_toggle_status(user_id: int, request: Request, current_admin: dict = Depends(require_admin_user)):
    """Updates user account status (active/suspended)."""
    if user_id == current_admin["id"]:
        raise HTTPException(status_code=400, detail="Cannot alter your own administrator account status.")
    
    data = await request.json()
    new_status = data.get("status", "active").strip().lower()
    if new_status not in ["active", "suspended"]:
        raise HTTPException(status_code=400, detail="Status must be 'active' or 'suspended'.")

    success = update_user_status(user_id, new_status)
    if not success:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"status": "success", "message": f"User #{user_id} status updated to {new_status}."}

@app.get("/api/admin/stats")
async def api_admin_stats(current_admin: dict = Depends(require_admin_user)):
    """Returns platform-wide statistics for the administrator."""
    return {
        "status": "success",
        "total_registered_users": get_total_users_count(),
        "active_users": get_active_users_count(),
        "total_sessions_global": get_total_sessions_count_global()
    }

# ==========================================
# User Profile API Endpoints
# ==========================================

@app.post("/api/profile/update")
async def api_profile_update(request: Request, current_user: dict = Depends(require_auth_user)):
    """Updates user full name and email."""
    data = await request.json()
    full_name = data.get("full_name", "").strip()
    email = data.get("email", "").strip()

    if not full_name or not email:
        raise HTTPException(status_code=400, detail="Name and email are required.")

    if not auth.validate_email(email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")

    is_dup, dup_msg = check_duplicate_user(current_user["username"], email, exclude_user_id=current_user["id"])
    if is_dup:
        raise HTTPException(status_code=409, detail=dup_msg)

    update_user_profile(current_user["id"], full_name, email)
    return {"status": "success", "message": "Profile updated successfully."}

@app.post("/api/profile/change-password")
async def api_change_password(request: Request, current_user: dict = Depends(require_auth_user)):
    """Validates existing password and changes to new password."""
    data = await request.json()
    current_pwd = data.get("current_password", "")
    new_pwd = data.get("new_password", "")
    confirm_pwd = data.get("confirm_password", "")

    if not current_pwd or not new_pwd:
        raise HTTPException(status_code=400, detail="Current and new password are required.")

    if new_pwd != confirm_pwd:
        raise HTTPException(status_code=400, detail="New passwords do not match.")

    if not auth.verify_password(current_user["password_hash"], current_pwd):
        raise HTTPException(status_code=400, detail="Incorrect current password.")

    valid_pwd, pwd_msg = auth.validate_password_strength(new_pwd)
    if not valid_pwd:
        raise HTTPException(status_code=400, detail=pwd_msg)

    new_hash = auth.hash_password(new_pwd)
    update_user_password(current_user["id"], new_hash)
    return {"status": "success", "message": "Password changed successfully."}

# ==========================================
# Multi-Tenant Session & Analytics APIs
# ==========================================

@app.post("/api/sessions/save")
async def record_session(request: Request):
    """
    Saves session and optional granular records.
    Automatically associates with authenticated user (or demo account).
    """
    user = get_current_user_from_request(request)
    user_id = user["id"] if user else None

    data = await request.json()
    session_id = save_session(data, user_id=user_id)

    # Optional granular records logging (Requirement 5)
    actual_user_id = user_id if user_id else 1

    if "measurements" in data and isinstance(data["measurements"], list):
        for m in data["measurements"]:
            log_posture_measurement(
                actual_user_id, session_id,
                m.get("shoulder_tilt", 0.0), m.get("head_tilt", 0.0),
                m.get("slouch_ratio", 0.5), m.get("is_good", True)
            )

    if "slouch_events" in data and isinstance(data["slouch_events"], list):
        for s in data["slouch_events"]:
            log_slouch_event(
                actual_user_id, session_id,
                s.get("slouch_ratio", 0.0), s.get("baseline_ratio", 0.5),
                s.get("duration_seconds", 0.0), s.get("alert_triggered", True)
            )

    if "blink_logs" in data and isinstance(data["blink_logs"], list):
        for b in data["blink_logs"]:
            log_eye_blink(
                actual_user_id, session_id,
                b.get("ear_value", 0.28), b.get("blink_rate_bpm", 16.0),
                b.get("fatigue_level", "Low"), b.get("microsleep_detected", False)
            )

    if "break_reminders" in data and isinstance(data["break_reminders"], list):
        for br in data["break_reminders"]:
            log_break_reminder(
                actual_user_id, session_id,
                br.get("break_type", "20-20-20"), br.get("scheduled_duration_sec", 20),
                br.get("completed", True), br.get("skipped", False)
            )

    return {"status": "success", "session_id": session_id, "user_id": actual_user_id}

@app.get("/api/sessions/history")
async def fetch_history(request: Request, limit: int = 15):
    """Retrieves session history strictly isolated to the logged-in user."""
    user = get_current_user_from_request(request)
    user_id = user["id"] if user else None
    sessions = get_recent_sessions(user_id=user_id, limit=limit)
    return {"sessions": sessions}

@app.get("/api/sessions/summary")
async def fetch_summary(request: Request):
    """Retrieves lifetime analytics strictly isolated to the logged-in user."""
    user = get_current_user_from_request(request)
    user_id = user["id"] if user else None
    summary = get_analytics_summary(user_id=user_id)
    return {"summary": summary}

@app.post("/api/wellness/reports/save")
async def api_save_report(request: Request, current_user: dict = Depends(require_auth_user)):
    """Saves a formal wellness report record for the user (Requirement 5)."""
    data = await request.json()
    report_id = save_wellness_report(
        user_id=current_user["id"],
        session_id=data.get("session_id"),
        report_title=data.get("report_title", "Session Ergonomic Viva Report"),
        grade=data.get("grade", "A"),
        overall_score=float(data.get("overall_score", 95.0)),
        good_posture_pct=float(data.get("good_posture_pct", 90.0)),
        total_blinks=int(data.get("total_blinks", 0)),
        breaks_taken=int(data.get("breaks_taken", 0)),
        notes=data.get("notes", "")
    )
    return {"status": "success", "report_id": report_id}

@app.get("/api/wellness/reports")
async def api_get_reports(current_user: dict = Depends(require_auth_user)):
    """Retrieves user's saved wellness reports."""
    reports = get_user_wellness_reports(current_user["id"])
    return {"status": "success", "reports": reports}

@app.get("/api/settings")
async def fetch_settings():
    return get_settings()

@app.post("/api/settings")
async def save_settings_endpoint(request: Request):
    data = await request.json()
    update_settings(data)
    return {"status": "success", "message": "Settings updated"}

@app.get("/api/database/download-sql")
async def download_database_sql():
    """Exports and downloads the live SQLite database as a SQL dump file."""
    conn = get_db()
    sql_dump = "\n".join(conn.iterdump())
    conn.close()
    return Response(
        content=sql_dump,
        media_type="application/sql",
        headers={"Content-Disposition": 'attachment; filename="digital_wellness_database.sql"'}
    )

@app.get("/api/database/schema-sql")
async def download_schema_sql():
    """Downloads the clean DDL schema SQL script."""
    schema_path = os.path.join(BASE_DIR, "database", "schema.sql")
    if os.path.exists(schema_path):
        with open(schema_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        conn = get_db()
        content = "\n".join(conn.iterdump())
        conn.close()
    return Response(
        content=content,
        media_type="application/sql",
        headers={"Content-Disposition": 'attachment; filename="digital_wellness_schema.sql"'}
    )

@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "Digital Wellness Monitor",
        "version": "2.2.0",
        "multi_tenant": True,
        "indexes_active": True
    }

if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("  [*] Digital Wellness Monitor Multi-User Server Starting...")
    print("  [>] Web Interface:  http://localhost:8000")
    print("  [>] Login Page:     http://localhost:8000/login")
    print("  [>] Admin Console:  http://localhost:8000/admin/users")
    print("  [>] API Docs:       http://localhost:8000/docs")
    print("=" * 65 + "\n")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
