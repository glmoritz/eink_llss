"""
Authentication and authorization dependencies
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from auth import verify_token
from database import get_db
from db_models import Device, DeviceAuthStatus, Instance

security = HTTPBearer(auto_error=False)


async def get_current_device(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> str:
    """
    Validate device JWT access token and return device_id.

    Requires a valid JWT access token with type "device_access".
    The device must also be in "authorized" status.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify JWT token
    token_data = verify_token(token, "device_access")

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify device exists and is authorized
    device = db.query(Device).filter(Device.device_id == token_data.subject_id).first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Device not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if str(device.auth_status) != DeviceAuthStatus.AUTHORIZED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Device not authorized. Status: {device.auth_status}",
        )

    return str(device.device_id)


async def get_device_from_refresh_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Device:
    """
    Validate device JWT refresh token and return the Device object.

    Used for the token refresh endpoint.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify JWT refresh token
    token_data = verify_token(token, "device_refresh")

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify device exists and is authorized
    device = db.query(Device).filter(Device.device_id == token_data.subject_id).first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Device not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if str(device.auth_status) != DeviceAuthStatus.AUTHORIZED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Device not authorized. Status: {device.auth_status}",
        )

    # Verify the refresh token JTI matches (for revocation support)
    if token_data.jti and str(device.current_refresh_jti) != token_data.jti:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return device


async def get_current_instance(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> str:
    """
    Validate instance authentication token and return instance_id.

    Supports both JWT tokens and legacy static tokens for backwards compatibility.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # First try JWT token
    token_data = verify_token(token, "instance_access")

    if token_data:
        # Valid JWT token
        instance = (
            db.query(Instance)
            .filter(Instance.instance_id == token_data.subject_id)
            .first()
        )
        if instance:
            return str(instance.instance_id)

    # Fall back to legacy static token lookup
    instance = db.query(Instance).filter(Instance.access_token == token).first()

    if not instance:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return str(instance.instance_id)
