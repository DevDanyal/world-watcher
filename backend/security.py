from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
import time

from cryptography.fernet import Fernet

from config.settings import settings

try:
    from argon2 import PasswordHasher

    ph = PasswordHasher()

    def _hash_password(password: str) -> str:
        return ph.hash(password)

    def _verify_password_hash(pw_hash: str, password: str) -> bool:
        ph.verify(pw_hash, password)
        return True
except Exception:  # fallback for minimal envs
    import hashlib

    ph = None

    def _hash_password(password: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
        return f"pbkdf2${salt}${digest}"

    def _verify_password_hash(pw_hash: str, password: str) -> bool:
        try:
            _, salt, digest = pw_hash.split("$", 2)
            check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
            return hmac.compare_digest(check, digest)
        except Exception:
            return False
SESSION_COOKIE = "ww_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 7


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auth (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS secrets (
                name TEXT PRIMARY KEY,
                value_encrypted TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            )
            """
        )
        conn.commit()


def has_password() -> bool:
    init_auth_db()
    with _conn() as conn:
        row = conn.execute("SELECT 1 FROM auth WHERE id=1").fetchone()
    return row is not None


def set_initial_password(password: str) -> None:
    init_auth_db()
    if has_password():
        raise ValueError("password already set")
    salt = base64.urlsafe_b64encode(os.urandom(16)).decode()
    pw_hash = _hash_password(password)
    with _conn() as conn:
        conn.execute("INSERT INTO auth (id, password_hash, salt) VALUES (1, ?, ?)", (pw_hash, salt))
        conn.commit()


def verify_password(password: str) -> bool:
    init_auth_db()
    with _conn() as conn:
        row = conn.execute("SELECT password_hash FROM auth WHERE id=1").fetchone()
    if not row:
        return False
    try:
        return _verify_password_hash(row["password_hash"], password)
    except Exception:
        return False


def _derive_key(password: str) -> bytes:
    init_auth_db()
    with _conn() as conn:
        row = conn.execute("SELECT salt FROM auth WHERE id=1").fetchone()
    salt = (row["salt"] if row else "default-salt").encode()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000, dklen=32)
    return base64.urlsafe_b64encode(digest)


def store_secret(name: str, value: str, master_password: str) -> None:
    init_auth_db()
    f = Fernet(_derive_key(master_password))
    token = f.encrypt(value.encode()).decode()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO secrets(name, value_encrypted, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(name) DO UPDATE SET value_encrypted=excluded.value_encrypted, updated_at=CURRENT_TIMESTAMP",
            (name, token),
        )
        conn.commit()


def load_secret(name: str, master_password: str) -> str | None:
    init_auth_db()
    with _conn() as conn:
        row = conn.execute("SELECT value_encrypted FROM secrets WHERE name=?", (name,)).fetchone()
    if not row:
        return None
    f = Fernet(_derive_key(master_password))
    return f.decrypt(row["value_encrypted"].encode()).decode()


def create_session() -> str:
    init_auth_db()
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    exp = now + SESSION_TTL_SECONDS
    with _conn() as conn:
        conn.execute("INSERT INTO sessions(token, created_at, expires_at) VALUES (?, ?, ?)", (token, now, exp))
        conn.commit()
    return token


def get_session(token: str | None) -> bool:
    if not token:
        return False
    init_auth_db()
    now = int(time.time())
    with _conn() as conn:
        row = conn.execute("SELECT expires_at FROM sessions WHERE token=?", (token,)).fetchone()
        if not row:
            return False
        if int(row["expires_at"]) < now:
            conn.execute("DELETE FROM sessions WHERE token=?", (token,))
            conn.commit()
            return False
    return True


def delete_session(token: str | None) -> None:
    if not token:
        return
    init_auth_db()
    with _conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))
        conn.commit()


def redact_secrets(text: str) -> str:
    redacted = text
    for value in [
        settings.openai_api_key,
        settings.anthropic_api_key,
        settings.telegram_bot_token,
        settings.secret_key,
    ]:
        if value and len(value) >= 6:
            redacted = redacted.replace(value, "[REDACTED]")
    return redacted
