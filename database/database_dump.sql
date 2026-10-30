BEGIN TRANSACTION;
CREATE TABLE break_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            timestamp TEXT NOT NULL,
            break_type TEXT NOT NULL DEFAULT '20-20-20',
            scheduled_duration_sec INTEGER NOT NULL DEFAULT 20,
            completed INTEGER NOT NULL DEFAULT 1,
            skipped INTEGER NOT NULL DEFAULT 0
        );
INSERT INTO "break_reminders" VALUES(1,NULL,1,'2026-10-30T08:27:43.715595','20-20-20',20,1,0);
INSERT INTO "break_reminders" VALUES(2,3,5,'2026-10-30T08:31:06.367049','20-20-20',20,1,0);
CREATE TABLE eye_blink_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            timestamp TEXT NOT NULL,
            ear_value REAL NOT NULL,
            blink_rate_bpm REAL NOT NULL,
            fatigue_level TEXT NOT NULL DEFAULT 'Low',
            microsleep_detected INTEGER NOT NULL DEFAULT 0
        );
INSERT INTO "eye_blink_logs" VALUES(1,NULL,1,'2026-10-30T08:27:43.712365',0.28,16.0,'Low',0);
INSERT INTO "eye_blink_logs" VALUES(2,3,5,'2026-10-30T08:31:06.363497',0.29,16.0,'Low',0);
CREATE TABLE password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            token TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER DEFAULT 0
        );
CREATE TABLE posture_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            timestamp TEXT NOT NULL,
            shoulder_tilt REAL NOT NULL,
            head_tilt REAL NOT NULL,
            slouch_ratio REAL NOT NULL,
            is_good_posture INTEGER NOT NULL DEFAULT 1
        );
INSERT INTO "posture_measurements" VALUES(1,NULL,1,'2026-10-30T08:27:43.703999',2.5,1.8,0.49,1);
INSERT INTO "posture_measurements" VALUES(2,3,5,'2026-10-30T08:31:06.352391',2.1,1.9,0.49,1);
INSERT INTO "posture_measurements" VALUES(3,3,5,'2026-10-30T08:31:06.355400',2.4,2.0,0.48,1);
CREATE TABLE sessions (
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
        , user_id INTEGER REFERENCES users(id));
INSERT INTO "sessions" VALUES(1,'2026-10-03T08:02:05.487724',120,94.5,92.0,5.0,3.0,35,17.5,1,0,'A+',1);
INSERT INTO "sessions" VALUES(2,'2026-10-30T08:12:56.501843',300,96.0,95.0,3.0,2.0,75,15.0,1,0,'A+',2);
INSERT INTO "sessions" VALUES(3,'2026-10-30T08:31:06.349364',600,92.5,91.0,6.0,3.0,150,15.0,2,1,'A',5);
INSERT INTO "sessions" VALUES(4,'2026-10-30T03:04:29.296Z',4,98.0,100.0,0.0,0.0,0,0.0,0,0,'A+',3);
CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
INSERT INTO "settings" VALUES('shoulder_tilt_thresh','4.5');
INSERT INTO "settings" VALUES('head_tilt_thresh','6.0');
INSERT INTO "settings" VALUES('slouch_ratio_thresh','0.15');
INSERT INTO "settings" VALUES('baseline_slouch_ratio','0.50');
INSERT INTO "settings" VALUES('ear_thresh','0.21');
INSERT INTO "settings" VALUES('audio_enabled','true');
INSERT INTO "settings" VALUES('voice_enabled','true');
INSERT INTO "settings" VALUES('break_202020_interval_min','20');
INSERT INTO "settings" VALUES('sedentary_alert_min','45');
INSERT INTO "settings" VALUES('overlay_lines_enabled','true');
CREATE TABLE slouch_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            timestamp TEXT NOT NULL,
            slouch_ratio REAL NOT NULL,
            baseline_ratio REAL NOT NULL,
            duration_seconds REAL NOT NULL,
            alert_triggered INTEGER NOT NULL DEFAULT 1
        );
INSERT INTO "slouch_events" VALUES(1,NULL,1,'2026-10-30T08:27:43.707722',0.38,0.5,5.2,1);
INSERT INTO "slouch_events" VALUES(2,3,5,'2026-10-30T08:31:06.360363',0.36,0.5,4.5,1);
CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_login TEXT
        , account_status TEXT NOT NULL DEFAULT 'active', is_admin INTEGER NOT NULL DEFAULT 0);
INSERT INTO "users" VALUES(1,'Demo Explorer','demo','demo@digitalwellness.ai','$argon2id$v=19$m=65536,t=3,p=4$tBkNOjKbdA/pn9CP8ucgtA$O+DIprnRq3DhHi2IxzZQvk6OEyg3ubZwmuNF4ieLAMc','2026-10-30T08:08:44.060858','2026-10-30T08:31:06.083313','active',0);
INSERT INTO "users" VALUES(2,'Alice Johnson','user_1793328176','user_1793328176@example.com','$argon2id$v=19$m=65536,t=3,p=4$F5vj/et6TJy0/yM5F4D4EQ$266WMvFjgnkgadwAdMHnsKmwa40tAPeR48l4SSMepuM','2026-10-30T08:12:56.382365','2026-10-30T08:12:56.633501','active',0);
INSERT INTO "users" VALUES(3,'Yamala Revanth','tnrrevanth','yamalarevanth10@gmail.com','$argon2id$v=19$m=65536,t=3,p=4$Bwv/l5KtbA7RurlXAMLWZg$293TbJiHXwL/hHUQ1ArzUwLEbLuHZL3sv66ON4C33fQ','2026-10-30T08:23:20.091644','2026-10-30T08:33:37.275359','active',0);
INSERT INTO "users" VALUES(4,'System Administrator','admin','admin@digitalwellness.ai','$argon2id$v=19$m=65536,t=3,p=4$pPp52UQHr/RWmjPufozn9A$Qcr9hvdWBZ4vgg5Q4zqsw6Y8YO1tMzOnRqb8kDtlzEQ','2026-10-30T08:27:07.794484','2026-10-30T08:31:06.525608','active',1);
INSERT INTO "users" VALUES(5,'User 0 Person','user_1793329266_0','user_1793329266_0@testdomain.com','$argon2id$v=19$m=65536,t=3,p=4$W2h6lA9eo2qJHTMfjIOf+A$W8x0NE48E+o7pF3m7AQKFHOsPL8eWSlYNhPNjbcPWwc','2026-10-30T08:31:06.150434','2026-10-30T08:31:06.341940','active',0);
INSERT INTO "users" VALUES(6,'User 1 Person','user_1793329266_1','user_1793329266_1@testdomain.com','$argon2id$v=19$m=65536,t=3,p=4$JlUAwJc1CH6Z6ODx5z/nRQ$8u6TnVU3vuBHVHZ9OX7m+15dY8/Frolyd004MO/hcXA','2026-10-30T08:31:06.212639','2026-10-30T08:31:06.445412','active',0);
INSERT INTO "users" VALUES(7,'User 2 Person','user_1793329266_2','user_1793329266_2@testdomain.com','$argon2id$v=19$m=65536,t=3,p=4$5fAMrwPCWS8XfHakpeXbww$NalZLvY/05ogtlJjK5ZP0dUYKWtcxD2q62crBw9QBlw','2026-10-30T08:31:06.276219','2026-10-30T08:31:06.276226','suspended',0);
CREATE TABLE wellness_reports (
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
INSERT INTO "wellness_reports" VALUES(1,NULL,1,'2026-10-30T08:27:43.720498','Test Report','A',95.0,92.0,40,2,'Good posture');
INSERT INTO "wellness_reports" VALUES(2,3,5,'2026-10-30T08:31:06.374430','Ergonomics Mid-Term Assessment','A',92.5,91.0,150,2,'Excellent head alignment');
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(account_status);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_timestamp ON sessions(timestamp);
CREATE INDEX idx_posture_user_session ON posture_measurements(user_id, session_id);
CREATE INDEX idx_slouch_user ON slouch_events(user_id);
CREATE INDEX idx_blink_user ON eye_blink_logs(user_id);
CREATE INDEX idx_break_user ON break_reminders(user_id);
CREATE INDEX idx_reports_user ON wellness_reports(user_id);
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('sessions',4);
INSERT INTO "sqlite_sequence" VALUES('users',7);
INSERT INTO "sqlite_sequence" VALUES('posture_measurements',3);
INSERT INTO "sqlite_sequence" VALUES('slouch_events',2);
INSERT INTO "sqlite_sequence" VALUES('eye_blink_logs',2);
INSERT INTO "sqlite_sequence" VALUES('break_reminders',2);
INSERT INTO "sqlite_sequence" VALUES('wellness_reports',2);
COMMIT;