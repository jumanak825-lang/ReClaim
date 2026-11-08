"""Users and server-side sessions (docs/11 §1: Postgres sessions, HttpOnly cookie, rotated on login).

Passwords: argon2id. Session cookies: random tokens; only their SHA-256 is stored.

Registration with an existing email returns 409, which reveals that the account exists.
Accepted for the hackathon (no email verification to send a neutral "check your inbox"
response); mitigated by per-IP rate limits on /auth/*. Revisit when email verification lands.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import delete, select

from ..core import config
from ..core.errors import ApiError
from ..db.models import Session, User, now
from ..db.session import db

_hasher = PasswordHasher()  # argon2id with library defaults
# Verified against when the email is unknown, so failed logins take similar time either way.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, stored: str) -> bool:
    try:
        return _hasher.verify(stored, password)
    except (VerificationError, InvalidHashError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def user_by_email(email: str) -> User | None:
    return db().scalar(select(User).where(User.email == email.strip().lower()))


def register(email: str, password: str, display_name: str) -> User:
    if user_by_email(email):
        raise ApiError(409, "REGISTRATION_FAILED", "Could not create an account with these details.")
    user = User(email=email.strip().lower(), password_hash=hash_password(password), display_name=display_name)
    db().add(user)
    db().flush()
    return user


def login(email: str, password: str) -> User:
    user = user_by_email(email)
    if not user:
        verify_password(password, _DUMMY_HASH)
        raise ApiError(401, "INVALID_CREDENTIALS", "Email or password is incorrect.")
    if not verify_password(password, user.password_hash):
        raise ApiError(401, "INVALID_CREDENTIALS", "Email or password is incorrect.")
    if _hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return user


def create_session(user: User) -> str:
    token = secrets.token_urlsafe(32)
    db().add(Session(token_hash=_token_hash(token), user_id=user.id,
                     expires_at=now() + timedelta(hours=config.settings.session_ttl_hours)))
    return token


def session_user(token: str | None) -> User | None:
    if not token:
        return None
    s = db().scalar(select(Session).where(Session.token_hash == _token_hash(token)))
    if not s:
        return None
    if s.expires_at < now():
        db().delete(s)
        return None
    return db().get(User, s.user_id)


def end_session(token: str | None) -> None:
    if token:
        db().execute(delete(Session).where(Session.token_hash == _token_hash(token)))
