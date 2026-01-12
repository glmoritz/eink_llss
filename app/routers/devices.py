"""
Device routes - Physical e-Ink devices (ESP32-based)
"""

import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.db_models import Device, Frame, InputEvent
from app.dependencies import get_current_device
from app.models import (
    DeviceAction,
    DeviceRegistration,
    DeviceRegistrationResponse,
    DeviceStateResponse,
    InputEvent as InputEventSchema,
)

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.post("/register", response_model=DeviceRegistrationResponse, status_code=201)
async def register_device(
    registration: DeviceRegistration,
    db: Session = Depends(get_db),
) -> DeviceRegistrationResponse:
    """
    Register a new physical device.

    Registers a new device and returns credentials used for future authentication.
    """
    # Generate unique identifiers
    device_id = uuid.uuid4()
    device_secret = secrets.token_urlsafe(32)
    access_token = secrets.token_urlsafe(32)

    # Create device in database
    device = Device(
        device_id=device_id,
        device_secret=device_secret,
        access_token=access_token,
        hardware_id=registration.hardware_id,
        firmware_version=registration.firmware_version,
        display_width=registration.display.width,
        display_height=registration.display.height,
        display_bit_depth=registration.display.bit_depth,
        display_partial_refresh=registration.display.partial_refresh,
    )

    db.add(device)
    db.commit()
    db.refresh(device)

    return DeviceRegistrationResponse(
        device_id=str(device_id),
        device_secret=device_secret,
        access_token=access_token,
    )


@router.get("/{device_id}/state", response_model=DeviceStateResponse)
async def get_device_state(
    device_id: str,
    last_frame_id: Optional[str] = None,
    last_event_id: Optional[str] = None,
    _: str = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> DeviceStateResponse:
    """
    Device heartbeat and action polling.

    Core polling endpoint used by devices to report status.
    LLSS responds with the next action to perform.
    """
    device = db.query(Device).filter(Device.device_id == device_id).first()

    if not device:
        return DeviceStateResponse(
            action=DeviceAction.NOOP,
            frame_id=None,
            active_instance_id=None,
            poll_after_ms=5000,
        )

    # Update last seen
    device.last_seen_at = datetime.now(timezone.utc)
    db.commit()

    current_frame_id = device.current_frame_id

    # Check if there's a new frame
    if current_frame_id and str(current_frame_id) != last_frame_id:
        return DeviceStateResponse(
            action=DeviceAction.FETCH_FRAME,
            frame_id=str(current_frame_id),
            active_instance_id=(
                str(device.active_instance_id) if device.active_instance_id else None
            ),
            poll_after_ms=5000,
        )

    return DeviceStateResponse(
        action=DeviceAction.NOOP,
        frame_id=None,
        active_instance_id=(
            str(device.active_instance_id) if device.active_instance_id else None
        ),
        poll_after_ms=5000,
    )


@router.get("/{device_id}/frames/{frame_id}")
async def get_frame(
    device_id: str,
    frame_id: str,
    _: str = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> Response:
    """
    Fetch rendered frame data.

    Returns raw framebuffer data ready to be written to the e-Ink display.
    """
    frame = db.query(Frame).filter(Frame.frame_id == frame_id).first()

    if frame and frame.data:
        return Response(
            content=frame.data,
            media_type="image/png",
        )

    return Response(
        content=b"",
        media_type="application/octet-stream",
    )


@router.post("/{device_id}/inputs", status_code=202)
async def submit_input(
    device_id: str,
    event: InputEventSchema,
    _: str = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> None:
    """
    Submit input events from a device.

    Sends button presses or other input events from the device to LLSS.
    LLSS routes them to the active HLSS instance.
    """
    # Get device to find active instance
    device = db.query(Device).filter(Device.device_id == device_id).first()

    # Log the input event
    input_event = InputEvent(
        device_id=device_id,
        instance_id=device.active_instance_id if device else None,
        button=event.button.value,
        event_type=event.event_type.value,
        event_timestamp=event.timestamp,
    )
    db.add(input_event)
    db.commit()

    # TODO: Forward to active instance via webhook or message queue
