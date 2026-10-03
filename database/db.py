import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "wellness_sessions.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Sessions table
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
    
    # Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    # Set defaults if not present
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

def save_session(session_data: dict):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO sessions (
            timestamp, duration_seconds, avg_posture_score,
            good_posture_pct, slouch_pct, tilt_pct,
            total_blinks, avg_blink_rate, breaks_completed,
            slouch_alerts_count, ergonomic_grade
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
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

def get_recent_sessions(limit=10):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_analytics_summary():
    conn = get_db()
    cursor = conn.cursor()
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
    print("Database initialized successfully at", DB_PATH)
