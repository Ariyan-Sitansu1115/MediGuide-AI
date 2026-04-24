"""
Database models and utilities for MediGuide AI.

Provides SQLite-backed persistence for consent records, symptom submissions,
and audit logs.  Sensitive fields are encrypted at rest using Fernet
(AES-CBC with 256-bit keys and HMAC-SHA256) from the `cryptography` package.
"""

import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

try:
    from cryptography.fernet import Fernet

    _CRYPTO_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CRYPTO_AVAILABLE = False

ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "data" / "mediguide.db"
_KEY_FILE = ROOT_DIR / "data" / ".encryption_key"


# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------


def _get_or_create_key() -> bytes | None:
    """Return encryption key from env var or auto-generated key file."""
    env_key = os.getenv("ENCRYPTION_KEY")
    if env_key:
        return env_key.encode() if isinstance(env_key, str) else env_key

    if not _CRYPTO_AVAILABLE:
        return None

    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes().strip()

    new_key = Fernet.generate_key()
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _KEY_FILE.write_bytes(new_key)
    try:
        _KEY_FILE.chmod(0o600)
    except Exception:  # pragma: no cover – Windows
        pass
    return new_key


def encrypt_data(plaintext: str) -> str:
    """Return encrypted, URL-safe ciphertext, or *plaintext* if unavailable."""
    if not _CRYPTO_AVAILABLE:
        return plaintext
    key = _get_or_create_key()
    if not key:
        return plaintext
    return Fernet(key).encrypt(plaintext.encode()).decode()


def decrypt_data(ciphertext: str) -> str:
    """Decrypt a value produced by :func:`encrypt_data`."""
    if not _CRYPTO_AVAILABLE:
        return ciphertext
    key = _get_or_create_key()
    if not key:
        return ciphertext
    try:
        return Fernet(key).decrypt(ciphertext.encode()).decode()
    except Exception:
        return ciphertext


# ---------------------------------------------------------------------------
# Connection / initialisation
# ---------------------------------------------------------------------------


def get_db_connection() -> sqlite3.Connection:
    """Open and return a SQLite connection with row factory enabled."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create database tables if they do not already exist."""
    conn = get_db_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS consent_records (
                id               TEXT PRIMARY KEY,
                session_id       TEXT NOT NULL,
                disclaimer_version TEXT NOT NULL,
                consent_given    INTEGER NOT NULL DEFAULT 1,
                ip_address       TEXT,
                user_agent       TEXT,
                created_at       TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS symptom_records (
                id           TEXT PRIMARY KEY,
                session_id   TEXT NOT NULL,
                symptom_data TEXT NOT NULL,
                created_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id          TEXT PRIMARY KEY,
                session_id  TEXT,
                action      TEXT NOT NULL,
                resource    TEXT,
                ip_address  TEXT,
                details     TEXT,
                created_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_consent_session
                ON consent_records(session_id);
            CREATE INDEX IF NOT EXISTS idx_symptom_session
                ON symptom_records(session_id);
            CREATE INDEX IF NOT EXISTS idx_audit_session
                ON audit_logs(session_id);
            """
        )
        conn.commit()
    finally:
        conn.close()


def new_id() -> str:
    """Return a new UUID4 string."""
    return str(uuid.uuid4())


def utcnow() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.utcnow().isoformat()
