"""
Device routes - Physical e-Ink devices (ESP32-based)
"""

import secrets
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Response

from app.dependencies import get_current_device
from app.models import (
    DeviceAction,
    DeviceRegistration,
    DeviceRegistrationResponse,
    DeviceStateResponse,
    InputEvent,
)
from app.store import device_store, frame_store

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.post("/register", response_model=DeviceRegistrationResponse, status_code=201)
async def register_device(
    registration: DeviceRegistration,
) -> DeviceRegistrationResponse:
    """
    Register a new physical device.

    Registers a new device and returns credentials used for future authentication.
    """
    # Generate unique identifiers
    device_id = f"dev_{uuid.uuid4().hex[:12]}"
    device_secret = secrets.token_urlsafe(32)
    access_token = secrets.token_urlsafe(32)

    # Store device information
    device_store[device_id] = {
        "device_id": device_id,
        "device_secret": device_secret,
        "access_token": access_token,
        "hardware_id": registration.hardware_id,
        "firmware_version": registration.firmware_version,
        "display": {
            "width": registration.display.width,
            "height": registration.display.height,
            "bit_depth": registration.display.bit_depth,
            "partial_refresh": registration.display.partial_refresh,
        },
        "current_frame_id": None,
        "active_instance_id": None,
    }

    return DeviceRegistrationResponse(
        device_id=device_id,
        device_secret=device_secret,
        access_token=access_token,
    )


@router.get("/{device_id}/state", response_model=DeviceStateResponse)
async def get_device_state(
    device_id: str,
    last_frame_id: Optional[str] = None,
    last_event_id: Optional[str] = None,
    _: str = Depends(get_current_device),
) -> DeviceStateResponse:
    """
    Device heartbeat and action polling.

    Core polling endpoint used by devices to report status.
    LLSS responds with the next action to perform.
    """
    device = device_store.get(device_id)
    if not device:
        return DeviceStateResponse(
            action=DeviceAction.NOOP,
            frame_id=None,
            active_instance_id=None,
            poll_after_ms=5000,
        )

    current_frame_id = device.get("current_frame_id")

    # Check if there's a new frame
    if current_frame_id and current_frame_id != last_frame_id:
        return DeviceStateResponse(
            action=DeviceAction.FETCH_FRAME,
            frame_id=current_frame_id,
            active_instance_id=device.get("active_instance_id"),
            poll_after_ms=5000,
        )

    return DeviceStateResponse(
        action=DeviceAction.NOOP,
        frame_id=None,
        active_instance_id=device.get("active_instance_id"),
        poll_after_ms=5000,
    )


@router.get("/{device_id}/frames/{frame_id}")
async def get_frame(
    device_id: str,
    frame_id: str,
    _: str = Depends(get_current_device),
) -> Response:
    """
    Fetch rendered frame data.

    Returns raw framebuffer data ready to be written to the e-Ink display.
    """
    frame_data = frame_store.get(frame_id)

    if frame_data:
        return Response(
            content=frame_data,
            media_type="image/png",
        )

    return Response(
        content=b"",
        media_type="application/octet-stream",
    )


@router.post("/{device_id}/inputs", status_code=202)
async def submit_input(
    device_id: str,
    event: InputEvent,
    _: str = Depends(get_current_device),
) -> None:
    """
    Submit input events from a device.

    Sends button presses or other input events from the device to LLSS.
    LLSS routes them to the active HLSS instance.
    """
    # TODO: Implement input routing logic
    # - Find active instance for device
    # - Forward input event to the instance
    pass
