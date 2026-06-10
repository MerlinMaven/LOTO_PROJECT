"""
JWT utilities — architecture skeleton for Phase 3 authentication.

Auth is NOT enforced in Phase 2. These utilities are here so Phase 3
can plug in without touching any other file.

The dependency `get_current_user` in api/deps.py uses `StubUser` in
Phase 2. When auth is activated, replace the stub with the real
`verify_access_token` call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.core.config import get_settings


@dataclass
class TokenData:
    sub: str               # user identifier (email or UUID)
    role: str = "operator"
    exp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_access_token(token: str) -> TokenData:
    """
    Decode and validate a JWT bearer token.
    Raises jose.JWTError on failure — caught by error_handlers.py.
    """
    settings = get_settings()
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    sub: str = payload.get("sub", "")
    role: str = payload.get("role", "operator")
    if not sub:
        raise JWTError("Token missing 'sub' claim.")
    return TokenData(sub=sub, role=role)
