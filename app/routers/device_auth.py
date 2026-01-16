"""
Authentication routes for device token management.

This module provides endpoints for:
- Device initial registration (get refresh token)
- Token refresh (exchange refresh token for access token)
- Token renewal (get new refresh token using access token)
"""

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import (
    create_access_token,
    create_refresh_token,
    get_token_expiry_seconds,
)
from database import get_db
from db_models import Device, DeviceAuthStatus
from dependencies import get_current_device, get_device_from_refresh_token
from models import DisplayCapabilities

router = APIRouter(prefix="/auth", tags=["Authentication"])


# Request/Response models
class DeviceAuthRequest(BaseModel):
    """Request to authenticate a device and get initial refresh token."""

    hardware_id: str
    device_secret: str
    firmware_version: str
    display: DisplayCapabilities


class DeviceAuthResponse(BaseModel):
    """Response with device credentials after authentication."""

    device_id: str
    refresh_token: str
    refresh_token_expires_in: int  # seconds
    auth_status: str
    message: str


class TokenRefreshResponse(BaseModel):
    """Response with new access token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshTokenRenewalResponse(BaseModel):
    """Response with new refresh token."""

    refresh_token: str
    expires_in: int  # seconds


class DeviceRegistrationRequest(BaseModel):
    """Request to register a new device."""

    hardware_id: str
    firmware_version: str
    display: DisplayCapabilities


class DeviceRegistrationResponse(BaseModel):
    """Response after device registration."""

    device_id: str
    device_secret: str
    auth_status: str
    message: str


@router.post(
    "/devices/register", response_model=DeviceRegistrationResponse, status_code=201
)
async def register_device(
    registration: DeviceRegistrationRequest,
    db: Session = Depends(get_db),
) -> DeviceRegistrationResponse:
    """
    Register a new device.

    This is an UNAUTHENTICATED endpoint. When a new device registers:
    1. If hardware_id already exists, return error
    2. Create a new device record with PENDING status
    3. Return device_id and device_secret
    4. Device must wait for admin authorization before getting tokens

    The device should store the device_secret securely (EEPROM/SPIFFS).
    """
    # Check if device with this hardware_id already exists
    existing = (
        db.query(Device).filter(Device.hardware_id == registration.hardware_id).first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device with hardware_id '{registration.hardware_id}' already registered",
        )

    # Generate identifiers
    device_id = f"dev_{uuid.uuid4().hex[:12]}"
    device_secret = secrets.token_urlsafe(32)

    # Create device with PENDING status
    device = Device(
        device_id=device_id,
        hardware_id=registration.hardware_id,
        device_secret=device_secret,
        firmware_version=registration.firmware_version,
        display_width=registration.display.width,
        display_height=registration.display.height,
        display_bit_depth=registration.display.bit_depth,
        display_partial_refresh=registration.display.partial_refresh,
        auth_status=DeviceAuthStatus.PENDING.value,
    )

    db.add(device)
    db.commit()
    db.refresh(device)

    return DeviceRegistrationResponse(
        device_id=device_id,
        device_secret=device_secret,
        auth_status=DeviceAuthStatus.PENDING.value,
        message="Device registered. Waiting for admin authorization.",
    )


@router.post("/devices/token", response_model=DeviceAuthResponse)
async def authenticate_device(
    auth_request: DeviceAuthRequest,
    db: Session = Depends(get_db),
) -> DeviceAuthResponse:
    """
    Authenticate device and get refresh token.

    This is an UNAUTHENTICATED endpoint. The device provides:
    - hardware_id: Unique hardware identifier
    - device_secret: Secret received during registration

    If the device is AUTHORIZED, returns a refresh token (30 days).
    If PENDING, returns status indicating waiting for authorization.
    If REJECTED/REVOKED, returns error.
    """
    # Find device by hardware_id
    device = (
        db.query(Device).filter(Device.hardware_id == auth_request.hardware_id).first()
    )

    if not device:
        # Device not registered - register it as pending
        device_id = f"dev_{uuid.uuid4().hex[:12]}"
        device_secret = secrets.token_urlsafe(32)

        device = Device(
            device_id=device_id,
            hardware_id=auth_request.hardware_id,
            device_secret=device_secret,
            firmware_version=auth_request.firmware_version,
            display_width=auth_request.display.width,
            display_height=auth_request.display.height,
            display_bit_depth=auth_request.display.bit_depth,
            display_partial_refresh=auth_request.display.partial_refresh,
            auth_status=DeviceAuthStatus.PENDING.value,
        )

        db.add(device)
        db.commit()
        db.refresh(device)

        return DeviceAuthResponse(
            device_id=device_id,
            refresh_token="",
            refresh_token_expires_in=0,
            auth_status=DeviceAuthStatus.PENDING.value,
            message="Device registered and pending authorization. Please wait for admin approval.",
        )

    # Verify device_secret
    if str(device.device_secret) != auth_request.device_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device credentials",
        )

    # Update firmware version if changed
    if str(device.firmware_version) != auth_request.firmware_version:
        device.firmware_version = auth_request.firmware_version  # type: ignore[assignment]
        db.commit()

    # Check authorization status
    if str(device.auth_status) == DeviceAuthStatus.PENDING.value:
        return DeviceAuthResponse(
            device_id=str(device.device_id),
            refresh_token="",
            refresh_token_expires_in=0,
            auth_status=str(device.auth_status),
            message="Device pending authorization. Please wait for admin approval.",
        )

    if str(device.auth_status) in (
        DeviceAuthStatus.REJECTED.value,
        DeviceAuthStatus.REVOKED.value,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Device access {device.auth_status}. Contact administrator.",
        )

    if str(device.auth_status) != DeviceAuthStatus.AUTHORIZED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid device status: {device.auth_status}",
        )

    # Device is authorized - generate refresh token
    jti = secrets.token_urlsafe(16)
    refresh_token = create_refresh_token(str(device.device_id), jti=jti)

    # Store the JTI for revocation support
    device.current_refresh_jti = jti  # type: ignore[assignment]
    db.commit()

    return DeviceAuthResponse(
        device_id=str(device.device_id),
        refresh_token=refresh_token,
        refresh_token_expires_in=get_token_expiry_seconds("device_refresh"),
        auth_status=str(device.auth_status),
        message="Authentication successful.",
    )


@router.post("/devices/refresh", response_model=TokenRefreshResponse)
async def refresh_access_token(
    device: Device = Depends(get_device_from_refresh_token),
) -> TokenRefreshResponse:
    """
    Exchange refresh token for a new access token.

    Requires a valid refresh token in the Authorization header.
    Returns a new access token (valid for 1 day).

    When the device receives a 401 on any API call, it should call
    this endpoint with its refresh token to get a new access token.
    """
    access_token = create_access_token(
        str(device.device_id), token_type="device_access"
    )

    return TokenRefreshResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=get_token_expiry_seconds("device_access"),
    )


@router.post("/devices/renew-refresh", response_model=RefreshTokenRenewalResponse)
async def renew_refresh_token(
    device_id: str = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> RefreshTokenRenewalResponse:
    """
    Get a new refresh token using access token.

    Requires a valid access token in the Authorization header.
    Returns a new refresh token (valid for 30 days).

    The device should call this periodically (e.g., every 15 days)
    to ensure the refresh token doesn't expire.
    """
    device = db.query(Device).filter(Device.device_id == device_id).first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Generate new refresh token with new JTI
    jti = secrets.token_urlsafe(16)
    refresh_token = create_refresh_token(str(device.device_id), jti=jti)

    # Update the JTI (invalidates old refresh token)
    device.current_refresh_jti = jti  # type: ignore[assignment]
    db.commit()

    return RefreshTokenRenewalResponse(
        refresh_token=refresh_token,
        expires_in=get_token_expiry_seconds("device_refresh"),
    )


@router.get("/devices/status")
async def get_auth_status(
    device_id: str = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get current authentication status.

    Requires a valid access token.
    Returns device authorization status and token info.
    """
    device = db.query(Device).filter(Device.device_id == device_id).first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    return {
        "device_id": device.device_id,
        "auth_status": device.auth_status,
        "authorized_at": (
            device.authorized_at.isoformat() if device.authorized_at else None
        ),
    }
