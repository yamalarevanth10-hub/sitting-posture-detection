import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "wellness_sessions.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Users table (unlimited registrations, auto-incrementing ID)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_login TEXT,
            account_status TEXT NOT NULL DEFAULT 'active',
            is_admin INTEGER NOT NULL DEFAULT 0
        )
    ''')

    # Safe schema migration for existing users table
    cursor.execute("PRAGMA table_info(users)")
    user_cols = [col[1] for col in cursor.fetchall()]
    if "account_status" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN account_status TEXT NOT NULL DEFAULT 'active'")
    if "is_admin" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
    
    # 2. Sessions table (Posture monitoring sessions)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            timestamp TEXT NOT NULL,
            duration_seconds INTEGER DEFAULT 0,
            avg_posture_score REAL DEFAULT 100.0,
            good_posture_pct REAL DEFAULT 100.0,
            slouch_pct REAL DEFAULT 0.0,
            tilt_pct REAL DEFAULT 0.0,
            total_blinks INTEGER DEFAULT 0,
            avg_blink_rate REAL DEFAULT 0.0,
            breaks_completed INTEGER DEFAULT 0,
            slouch_alerts_count INTEGER DEFAULT 0,
            ergonomic_grade TEXT DEFAULT 'A'
        )
    ''')

    # Safe migration: ensure user_id column exists in sessions
    cursor.execute("PRAGMA table_info(sessions)")
    session_cols = [col[1] for col in cursor.fetchall()]
    if "user_id" not in session_cols:
        cursor.execute("ALTER TABLE sessions ADD COLUMN user_id INTEGER REFERENCES users(id)")

    # 3. Posture measurements table (detailed periodic angle telemetry)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posture_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            timestamp TEXT NOT NULL,
            shoulder_tilt REAL NOT NULL,
            head_tilt REAL NOT NULL,
            slouch_ratio REAL NOT NULL,
            is_good_posture INTEGER NOT NULL DEFAULT 1
        )
    ''')

    # 4. Slouch detection events table (slouch incidents & alerts)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS slouch_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            timestamp TEXT NOT NULL,
            slouch_ratio REAL NOT NULL,
            baseline_ratio REAL NOT NULL,
            duration_seconds REAL NOT NULL,
            alert_triggered INTEGER NOT NULL DEFAULT 1
        )
    ''')

    # 5. Eye blink logs table (ocular fatigue & eye strain stats)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS eye_blink_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            timestamp TEXT NOT NULL,
            ear_value REAL NOT NULL,
            blink_rate_bpm REAL NOT NULL,
            fatigue_level TEXT NOT NULL DEFAULT 'Low',
            microsleep_detected INTEGER NOT NULL DEFAULT 0
        )
    ''')

    # 6. Break reminders & compliance records
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS break_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            timestamp TEXT NOT NULL,
            break_type TEXT NOT NULL DEFAULT '20-20-20',
            scheduled_duration_sec INTEGER NOT NULL DEFAULT 20,
            completed INTEGER NOT NULL DEFAULT 1,
            skipped INTEGER NOT NULL DEFAULT 0
        )
    ''')

    # 7. Wellness reports table (saved report exports & viva records)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wellness_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            timestamp TEXT NOT NULL,
            report_title TEXT NOT NULL,
            grade TEXT NOT NULL,
            overall_score REAL NOT NULL,
            good_posture_pct REAL NOT NULL,
            total_blinks INTEGER NOT NULL,
            breaks_taken INTEGER NOT NULL,
            notes TEXT
        )
    ''')

    # 8. Password Resets table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            token TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0
        )
    ''')

    # 9. Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    # Set default settings
    default_settings = {
        "shoulder_tilt_thresh": "4.5",
        "head_tilt_thresh": "6.0",
        "slouch_ratio_thresh": "0.15",
        "baseline_slouch_ratio": "0.50",
        "ear_thresh": "0.21",
        "audio_enabled": "true",
        "voice_enabled": "true",
        "break_202020_interval_min": "20",
        "sedentary_alert_min": "45",
        "overlay_lines_enabled": "true"
    }
    for k, v in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    # ==========================================
    # Database Performance Indexing
    # ==========================================
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON users(account_status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_timestamp ON sessions(timestamp);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_posture_user_session ON posture_measurements(user_id, session_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_slouch_user ON slouch_events(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_blink_user ON eye_blink_logs(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_break_user ON break_reminders(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_user ON wellness_reports(user_id);")
        
    conn.commit()
    conn.close()

    # Seed demo and admin accounts
    seed_accounts()

def seed_accounts():
    """Seeds the common demo account and the administrator account if not present."""
    try:
        from auth import hash_password
    except ImportError:
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from auth import hash_password

    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    # 1. Common Demo Account for evaluators
    cursor.execute("SELECT id FROM users WHERE username = 'demo' OR email = 'demo@digitalwellness.ai'")
    demo_user = cursor.fetchone()
    demo_id = None

    if not demo_user:
        hashed_demo = hash_password("Demo@123")
        cursor.execute('''
            INSERT INTO users (full_name, username, email, password_hash, created_at, last_login, account_status, is_admin)
            VALUES (?, ?, ?, ?, ?, ?, 'active', 0)
        ''', ("Demo Explorer", "demo", "demo@digitalwellness.ai", hashed_demo, now, now))
        demo_id = cursor.lastrowid
    else:
        demo_id = demo_user["id"]

    # 2. Administrator Account for user management & system statistics
    cursor.execute("SELECT id FROM users WHERE username = 'admin' OR email = 'admin@digitalwellness.ai'")
    admin_user = cursor.fetchone()

    if not admin_user:
        hashed_admin = hash_password("Admin@123")
        cursor.execute('''
            INSERT INTO users (full_name, username, email, password_hash, created_at, last_login, account_status, is_admin)
            VALUES (?, ?, ?, ?, ?, ?, 'active', 1)
        ''', ("System Administrator", "admin", "admin@digitalwellness.ai", hashed_admin, now, now))
    else:
        # Ensure is_admin is 1
        cursor.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (admin_user["id"],))

    # Assign any legacy unassigned sessions to demo user
    if demo_id:
        cursor.execute("UPDATE sessions SET user_id = ? WHERE user_id IS NULL", (demo_id,))

    conn.commit()
    conn.close()

# ==========================================
# User Authentication & Management Queries
# ==========================================

def create_user(full_name: str, username: str, email: str, password_hash: str) -> int:
    """Creates a new user record with auto-incrementing ID."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (full_name, username, email, password_hash, created_at, last_login, account_status, is_admin)
        VALUES (?, ?, ?, ?, ?, ?, 'active', 0)
    ''', (
        full_name.strip(),
        username.strip().lower(),
        email.strip().lower(),
        password_hash,
        datetime.now().isoformat(),
        datetime.now().isoformat()
    ))
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return user_id

def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_username_or_email(identifier: str) -> Optional[dict]:
    conn = get_db()
    cursor = conn.cursor()
    clean_id = identifier.strip().lower()
    cursor.execute("SELECT * FROM users WHERE LOWER(username) = ? OR LOWER(email) = ?", (clean_id, clean_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def check_duplicate_user(username: str, email: str, exclude_user_id: Optional[int] = None) -> Tuple[bool, str]:
    conn = get_db()
    cursor = conn.cursor()
    clean_user = username.strip().lower()
    clean_email = email.strip().lower()

    if exclude_user_id:
        cursor.execute("SELECT id, username, email FROM users WHERE (LOWER(username) = ? OR LOWER(email) = ?) AND id != ?", (clean_user, clean_email, exclude_user_id))
    else:
        cursor.execute("SELECT id, username, email FROM users WHERE LOWER(username) = ? OR LOWER(email) = ?", (clean_user, clean_email))
    
    rows = cursor.fetchall()
    conn.close()

    for row in rows:
        if row["username"].lower() == clean_user:
            return True, "This username is already taken. Please choose another."
        if row["email"].lower() == clean_email:
            return True, "An account with this email address already exists."
    return False, ""

def update_user_last_login(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

def update_user_password(user_id: int, new_password_hash: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_password_hash, user_id))
    conn.commit()
    conn.close()

def update_user_profile(user_id: int, full_name: str, email: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET full_name = ?, email = ? WHERE id = ?", (full_name.strip(), email.strip().lower(), user_id))
    conn.commit()
    conn.close()

def update_user_status(user_id: int, new_status: str) -> bool:
    """Updates user account status (e.g. 'active', 'suspended')."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET account_status = ? WHERE id = ?", (new_status.strip().lower(), user_id))
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0

# ==========================================
# Administrator User Management Queries
# ==========================================

def get_all_users() -> List[dict]:
    """
    Returns registered users for the admin management view.
    CRITICAL: Explicitly omits password_hash for security.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            u.id, 
            u.full_name, 
            u.username, 
            u.email, 
            u.created_at, 
            u.last_login, 
            u.account_status, 
            u.is_admin,
            COUNT(s.id) as session_count
        FROM users u
        LEFT JOIN sessions s ON u.id = s.user_id
        GROUP BY u.id
        ORDER BY u.id ASC
    ''')
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users

def get_total_users_count() -> int:
    """Returns the total number of registered users."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_active_users_count() -> int:
    """Returns the number of active users."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE account_status = 'active'")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_total_sessions_count_global() -> int:
    """Returns the total monitoring sessions across all users."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM sessions")
    count = cursor.fetchone()[0]
    conn.close()
    return count

# ==========================================
# Multi-Tenant Session & Analytics Queries
# ==========================================

def save_session(session_data: dict, user_id: Optional[int] = None) -> int:
    """Saves a posture monitoring session associated with the user_id."""
    if user_id is None:
        demo = get_user_by_username_or_email("demo")
        user_id = demo["id"] if demo else 1

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO sessions (
            user_id, timestamp, duration_seconds, avg_posture_score,
            good_posture_pct, slouch_pct, tilt_pct,
            total_blinks, avg_blink_rate, breaks_completed,
            slouch_alerts_count, ergonomic_grade
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        session_data.get("timestamp", datetime.now().isoformat()),
        session_data.get("duration_seconds", 0),
        session_data.get("avg_posture_score", 100.0),
        session_data.get("good_posture_pct", 100.0),
        session_data.get("slouch_pct", 0.0),
        session_data.get("tilt_pct", 0.0),
        session_data.get("total_blinks", 0),
        session_data.get("avg_blink_rate", 0.0),
        session_data.get("breaks_completed", 0),
        session_data.get("slouch_alerts_count", 0),
        session_data.get("ergonomic_grade", "A")
    ))
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id

def get_recent_sessions(user_id: Optional[int] = None, limit: int = 15) -> List[dict]:
    """Retrieves session history strictly isolated to the specified user."""
    conn = get_db()
    cursor = conn.cursor()
    if user_id is not None:
        cursor.execute("SELECT * FROM sessions WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
    else:
        cursor.execute("SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_analytics_summary(user_id: Optional[int] = None) -> dict:
    """Aggregates lifetime analytics strictly for the specified user."""
    conn = get_db()
    cursor = conn.cursor()
    if user_id is not None:
        cursor.execute('''
            SELECT 
                COUNT(*) as total_sessions,
                COALESCE(SUM(duration_seconds), 0) as total_duration_seconds,
                COALESCE(AVG(avg_posture_score), 0.0) as overall_avg_score,
                COALESCE(SUM(total_blinks), 0) as total_blinks_all,
                COALESCE(SUM(breaks_completed), 0) as total_breaks_completed
            FROM sessions
            WHERE user_id = ?
        ''', (user_id,))
    else:
        cursor.execute('''
            SELECT 
                COUNT(*) as total_sessions,
                COALESCE(SUM(duration_seconds), 0) as total_duration_seconds,
                COALESCE(AVG(avg_posture_score), 0.0) as overall_avg_score,
                COALESCE(SUM(total_blinks), 0) as total_blinks_all,
                COALESCE(SUM(breaks_completed), 0) as total_breaks_completed
            FROM sessions
        ''')
    row = dict(cursor.fetchone())
    conn.close()
    return row

# ==========================================
# Granular Telemetry Records Logging
# ==========================================

def log_posture_measurement(user_id: int, session_id: Optional[int], shoulder_tilt: float, head_tilt: float, slouch_ratio: float, is_good_posture: bool) -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO posture_measurements (session_id, user_id, timestamp, shoulder_tilt, head_tilt, slouch_ratio, is_good_posture)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (session_id, user_id, datetime.now().isoformat(), shoulder_tilt, head_tilt, slouch_ratio, 1 if is_good_posture else 0))
    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return entry_id

def log_slouch_event(user_id: int, session_id: Optional[int], slouch_ratio: float, baseline_ratio: float, duration_seconds: float, alert_triggered: bool = True) -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO slouch_events (session_id, user_id, timestamp, slouch_ratio, baseline_ratio, duration_seconds, alert_triggered)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (session_id, user_id, datetime.now().isoformat(), slouch_ratio, baseline_ratio, duration_seconds, 1 if alert_triggered else 0))
    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return entry_id

def log_eye_blink(user_id: int, session_id: Optional[int], ear_value: float, blink_rate_bpm: float, fatigue_level: str = 'Low', microsleep_detected: bool = False) -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO eye_blink_logs (session_id, user_id, timestamp, ear_value, blink_rate_bpm, fatigue_level, microsleep_detected)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (session_id, user_id, datetime.now().isoformat(), ear_value, blink_rate_bpm, fatigue_level, 1 if microsleep_detected else 0))
    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return entry_id

def log_break_reminder(user_id: int, session_id: Optional[int], break_type: str = '20-20-20', scheduled_duration_sec: int = 20, completed: bool = True, skipped: bool = False) -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO break_reminders (session_id, user_id, timestamp, break_type, scheduled_duration_sec, completed, skipped)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (session_id, user_id, datetime.now().isoformat(), break_type, scheduled_duration_sec, 1 if completed else 0, 1 if skipped else 0))
    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return entry_id

def save_wellness_report(user_id: int, session_id: Optional[int], report_title: str, grade: str, overall_score: float, good_posture_pct: float, total_blinks: int, breaks_taken: int, notes: str = "") -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO wellness_reports (session_id, user_id, timestamp, report_title, grade, overall_score, good_posture_pct, total_blinks, breaks_taken, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (session_id, user_id, datetime.now().isoformat(), report_title, grade, overall_score, good_posture_pct, total_blinks, breaks_taken, notes))
    report_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return report_id

def get_user_wellness_reports(user_id: int, limit: int = 20) -> List[dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM wellness_reports WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_settings():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    settings = {row["key"]: row["value"] for row in cursor.fetchall()}
    conn.close()
    return settings

def update_settings(new_settings: dict):
    conn = get_db()
    cursor = conn.cursor()
    for k, v in new_settings.items():
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))
    conn.commit()
    conn.close()
    return True

if __name__ == "__main__":
    init_db()
    print("Multi-user database initialized, indexed & accounts seeded at", DB_PATH)
