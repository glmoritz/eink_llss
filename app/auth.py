"""
JWT Authentication module for LLSS.

This module handles JWT token generation and validation for:
- Device access tokens (short-lived, 1 day)
- Device refresh tokens (long-lived, 30 days)
- Instance access tokens
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from pydantic import BaseModel

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
ALGORITHM = "HS256"

# Token expiration times
ACCESS_TOKEN_EXPIRE_DAYS = 1  # 1 day for access tokens
REFRESH_TOKEN_EXPIRE_DAYS = 30  # 30 days for refresh tokens


class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str  # Subject (device_id or instance_id)
    type: str  # Token type: "device_access", "device_refresh", "instance_access"
    exp: datetime  # Expiration time
    iat: datetime  # Issued at
    jti: Optional[str] = None  # JWT ID (for tracking/revocation)


class TokenData(BaseModel):
    """Decoded token data."""

    subject_id: str
    token_type: str
    expires_at: datetime
    issued_at: datetime
    jti: Optional[str] = None


def create_access_token(
    subject_id: str,
    token_type: str = "device_access",
    expires_delta: Optional[timedelta] = None,
    jti: Optional[str] = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        subject_id: The device_id or instance_id
        token_type: Type of token (device_access, instance_access)
        expires_delta: Custom expiration time
        jti: Optional JWT ID for tracking

    Returns:
        Encoded JWT token string
    """
    if expires_delta is None:
        expires_delta = timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    to_encode = {
        "sub": subject_id,
        "type": token_type,
        "exp": expire,
        "iat": now,
    }

    if jti:
        to_encode["jti"] = jti

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(
    subject_id: str,
    expires_delta: Optional[timedelta] = None,
    jti: Optional[str] = None,
) -> str:
    """
    Create a JWT refresh token for devices.

    Args:
        subject_id: The device_id
        expires_delta: Custom expiration time (default 30 days)
        jti: Optional JWT ID for tracking

    Returns:
        Encoded JWT refresh token string
    """
    if expires_delta is None:
        expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    to_encode = {
        "sub": subject_id,
        "type": "device_refresh",
        "exp": expire,
        "iat": now,
    }

    if jti:
        to_encode["jti"] = jti

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[TokenData]:
    """
    Decode and validate a JWT token.

    Args:
        token: The JWT token string

    Returns:
        TokenData if valid, None if invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        return TokenData(
            subject_id=payload.get("sub", ""),
            token_type=payload.get("type", ""),
            expires_at=datetime.fromtimestamp(payload.get("exp", 0), tz=timezone.utc),
            issued_at=datetime.fromtimestamp(payload.get("iat", 0), tz=timezone.utc),
            jti=payload.get("jti"),
        )
    except JWTError:
        return None


def verify_token(token: str, expected_type: str) -> Optional[TokenData]:
    """
    Verify a JWT token and check its type.

    Args:
        token: The JWT token string
        expected_type: Expected token type (device_access, device_refresh, instance_access)

    Returns:
        TokenData if valid and correct type, None otherwise
    """
    token_data = decode_token(token)

    if token_data is None:
        return None

    if token_data.token_type != expected_type:
        return None

    # Check expiration (jose already does this, but explicit check is clearer)
    if token_data.expires_at < datetime.now(timezone.utc):
        return None

    return token_data


def get_token_expiry_seconds(token_type: str) -> int:
    """Get the expiration time in seconds for a token type."""
    if token_type == "device_refresh":
        return REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    return ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
