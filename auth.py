import os
import re
import time
from typing import Optional, Tuple
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

# Secret key for cryptographically signing cookies & tokens
SECRET_KEY = os.getenv("SECRET_KEY", "digital-wellness-major-project-secure-jwt-cookie-key-2026")
SESSION_COOKIE_NAME = "wellness_session"

# Argon2 password hasher (OWASP recommended gold standard)
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16
)

# Token serializer
_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="user-auth-session")
_reset_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="password-reset-salt")

# In-memory login rate limiter: {identifier: [timestamps]}
_login_attempts = {}
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 60

def hash_password(password: str) -> str:
    """Hashes a plain-text password using Argon2id."""
    return _hasher.hash(password)

def verify_password(hash_str: str, password: str) -> bool:
    """Verifies a plain-text password against an Argon2id hash."""
    try:
        return _hasher.verify(hash_str, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False

def create_session_token(user_id: int) -> str:
    """Creates a signed, timestamped session token."""
    return _serializer.dumps({"user_id": user_id})

def verify_session_token(token: str, max_age: int = 86400 * 7) -> Optional[int]:
    """
    Verifies a session token. Returns user_id if valid, or None if invalid/expired.
    Default max_age: 7 days.
    """
    if not token:
        return None
    try:
        data = _serializer.loads(token, max_age=max_age)
        return data.get("user_id")
    except (BadSignature, SignatureExpired, Exception):
        return None

def create_reset_token(user_id: int) -> str:
    """Generates a secure password reset token valid for 15 minutes."""
    return _reset_serializer.dumps({"user_id": user_id, "ts": time.time()})

def verify_reset_token(token: str, max_age: int = 900) -> Optional[int]:
    """Verifies a password reset token within 15 minutes (900 seconds)."""
    if not token:
        return None
    try:
        data = _reset_serializer.loads(token, max_age=max_age)
        return data.get("user_id")
    except (BadSignature, SignatureExpired, Exception):
        return None

def validate_email(email: str) -> bool:
    """Validates email format using standard regex."""
    if not email or len(email) > 120:
        return False
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))

def validate_password_strength(password: str) -> Tuple[bool, str]:
    """Enforces minimum 8 characters, at least one letter, and at least one number."""
    if not password:
        return False, "Password cannot be empty."
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Za-z]", password):
        return False, "Password must contain at least one letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit (0-9)."
    return True, ""

def is_rate_limited(identifier: str) -> Tuple[bool, int]:
    """
    Checks if an IP or username is rate-limited after too many failed attempts.
    Returns (is_limited, remaining_seconds).
    """
    now = time.time()
    attempts = _login_attempts.get(identifier, [])
    # Filter attempts within the lockout window
    recent_attempts = [t for t in attempts if now - t < LOCKOUT_SECONDS]
    _login_attempts[identifier] = recent_attempts

    if len(recent_attempts) >= MAX_ATTEMPTS:
        oldest = recent_attempts[0]
        remaining = int(LOCKOUT_SECONDS - (now - oldest))
        return True, max(1, remaining)
    return False, 0

def record_failed_attempt(identifier: str):
    """Records a failed login attempt for rate limiting."""
    now = time.time()
    attempts = _login_attempts.get(identifier, [])
    attempts.append(now)
    _login_attempts[identifier] = attempts

def clear_failed_attempts(identifier: str):
    """Clears failed attempts upon successful authentication."""
    if identifier in _login_attempts:
        del _login_attempts[identifier]
