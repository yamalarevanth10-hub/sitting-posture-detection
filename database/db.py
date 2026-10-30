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
    
    # 1. Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_login TEXT
        )
    ''')
    
    # 2. Sessions table (original base schema)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    # Safe schema migration: Add user_id column if not exists
    cursor.execute("PRAGMA table_info(sessions)")
    columns = [col[1] for col in cursor.fetchall()]
    if "user_id" not in columns:
        cursor.execute("ALTER TABLE sessions ADD COLUMN user_id INTEGER REFERENCES users(id)")

    # 3. Password Resets table
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

    # 4. Settings table
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
        
    conn.commit()
    conn.close()

    # Seed demo account and migrate unassigned sessions
    seed_demo_user()

def seed_demo_user():
    """Automatically seeds the public demo account if it doesn't exist."""
    # Import hash_password locally to avoid circular import
    try:
        from auth import hash_password
    except ImportError:
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from auth import hash_password

    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM users WHERE username = 'demo' OR email = 'demo@digitalwellness.ai'")
    demo_user = cursor.fetchone()

    demo_id = None
    if not demo_user:
        hashed = hash_password("Demo@123")
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO users (full_name, username, email, password_hash, created_at, last_login)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ("Demo Explorer", "demo", "demo@digitalwellness.ai", hashed, now, now))
        demo_id = cursor.lastrowid
        conn.commit()
    else:
        demo_id = demo_user["id"]

    # Assign any legacy sessions that have no user_id to demo user
    if demo_id:
        cursor.execute("UPDATE sessions SET user_id = ? WHERE user_id IS NULL", (demo_id,))
        conn.commit()

    conn.close()
    return demo_id

# ==========================================
# User Management & Authentication Queries
# ==========================================

def create_user(full_name: str, username: str, email: str, password_hash: str) -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (full_name, username, email, password_hash, created_at, last_login)
        VALUES (?, ?, ?, ?, ?, ?)
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

# ==========================================
# Multi-Tenant Session & Analytics Queries
# ==========================================

def save_session(session_data: dict, user_id: Optional[int] = None):
    # If user_id is None (e.g. from standalone desktop app), use demo user ID
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
    print("Database initialized & demo user seeded successfully at", DB_PATH)
