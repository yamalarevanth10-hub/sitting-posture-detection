-- =====================================================================
-- DIGITAL WELLNESS MONITOR - MAJOR PROJECT DATABASE SCHEMA
-- Target Database: SQLite 3.x (Compatible with MySQL / PostgreSQL)
-- Description: Multi-tenant relational schema for sitting posture analysis,
--              eye blink frequency, ergonomic break tracking & user accounts.
-- =====================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- 1. USERS TABLE
-- ---------------------------------------------------------------------
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
);

-- ---------------------------------------------------------------------
-- 2. SESSIONS TABLE (Posture Monitoring Sessions)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
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
);

-- ---------------------------------------------------------------------
-- 3. POSTURE MEASUREMENTS TABLE (Periodic Angles & Spine Telemetry)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS posture_measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL,
    shoulder_tilt REAL NOT NULL,
    head_tilt REAL NOT NULL,
    slouch_ratio REAL NOT NULL,
    is_good_posture INTEGER NOT NULL DEFAULT 1
);

-- ---------------------------------------------------------------------
-- 4. SLOUCH EVENTS TABLE (Slouching Incidents & Alerts)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS slouch_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL,
    slouch_ratio REAL NOT NULL,
    baseline_ratio REAL NOT NULL,
    duration_seconds REAL NOT NULL,
    alert_triggered INTEGER NOT NULL DEFAULT 1
);

-- ---------------------------------------------------------------------
-- 5. EYE BLINK LOGS TABLE (Ocular Fatigue & Eye Aspect Ratio)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eye_blink_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL,
    ear_value REAL NOT NULL,
    blink_rate_bpm REAL NOT NULL,
    fatigue_level TEXT NOT NULL DEFAULT 'Low',
    microsleep_detected INTEGER NOT NULL DEFAULT 0
);

-- ---------------------------------------------------------------------
-- 6. BREAK REMINDERS TABLE (20-20-20 & Sedentary Habit Records)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS break_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL,
    break_type TEXT NOT NULL DEFAULT '20-20-20',
    scheduled_duration_sec INTEGER NOT NULL DEFAULT 20,
    completed INTEGER NOT NULL DEFAULT 1,
    skipped INTEGER NOT NULL DEFAULT 0
);

-- ---------------------------------------------------------------------
-- 7. WELLNESS REPORTS TABLE (Formal Viva Reports & Assessments)
-- ---------------------------------------------------------------------
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
);

-- ---------------------------------------------------------------------
-- 8. PASSWORD RESETS TABLE (Cryptographic Recovery Tokens)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS password_resets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used INTEGER DEFAULT 0
);

-- ---------------------------------------------------------------------
-- 9. SETTINGS TABLE (Configurable Ergonomic Thresholds)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- =====================================================================
-- PERFORMANCE INDEXES (Optimizes lookup from O(N) to O(log N))
-- =====================================================================
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(account_status);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_timestamp ON sessions(timestamp);
CREATE INDEX IF NOT EXISTS idx_posture_user_session ON posture_measurements(user_id, session_id);
CREATE INDEX IF NOT EXISTS idx_slouch_user ON slouch_events(user_id);
CREATE INDEX IF NOT EXISTS idx_blink_user ON eye_blink_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_break_user ON break_reminders(user_id);
CREATE INDEX IF NOT EXISTS idx_reports_user ON wellness_reports(user_id);

-- =====================================================================
-- DEFAULT CONFIGURATION SETTINGS
-- =====================================================================
INSERT OR IGNORE INTO settings (key, value) VALUES 
('shoulder_tilt_thresh', '4.5'),
('head_tilt_thresh', '6.0'),
('slouch_ratio_thresh', '0.15'),
('baseline_slouch_ratio', '0.50'),
('ear_thresh', '0.21'),
('audio_enabled', 'true'),
('voice_enabled', 'true'),
('break_202020_interval_min', '20'),
('sedentary_alert_min', '45'),
('overlay_lines_enabled', 'true');
