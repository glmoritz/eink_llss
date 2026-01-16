"""
Device routes - Physical e-Ink devices (ESP32-based)
"""

import logging
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from database import get_db
from db_models import (
    Device,
    DeviceAuthStatus,
    DeviceInstanceMap,
    Frame,
    InputEvent,
    Instance,
)
from db_models import HLSSType as HLSSTypeModel
from dependencies import get_current_device
from hlss_service import HLSSService
from models import (
    ButtonType,
    DeviceAction,
    DeviceRegistration,
    DeviceRegistrationResponse,
    DeviceStateResponse,
    InputEvent as InputEventSchema,
)

router = APIRouter(prefix="/devices", tags=["Devices"])
logger = logging.getLogger(__name__)


def _get_llss_base_url() -> str:
    """Get the base URL of the LLSS API from environment."""
    return os.getenv("LLSS_BASE_URL", "http://localhost:8000")


@router.post(
    "/register",
    response_model=DeviceRegistrationResponse,
    status_code=201,
    deprecated=True,
)
async def register_device(
    registration: DeviceRegistration,
    db: Session = Depends(get_db),
) -> DeviceRegistrationResponse:
    """
    Register a new physical device.

    DEPRECATED: Use POST /auth/devices/register instead.

    This endpoint is kept for backwards compatibility but will be removed
    in a future version. The new auth system uses JWT tokens.

    Registers a new device with PENDING status. Admin must authorize
    the device before it can get tokens and use the API.
    """
    # Check if device already exists
    existing = (
        db.query(Device).filter(Device.hardware_id == registration.hardware_id).first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Device with hardware_id '{registration.hardware_id}' already registered",
        )

    # Generate unique identifiers
    device_id = f"dev_{uuid.uuid4().hex[:12]}"
    device_secret = secrets.token_urlsafe(32)

    # Create device in database with PENDING status
    device = Device(
        device_id=device_id,
        device_secret=device_secret,
        hardware_id=registration.hardware_id,
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
        access_token="",  # No longer provided - use auth endpoints
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
    device.last_seen_at = datetime.now(timezone.utc)  # type: ignore[assignment]
    db.commit()

    current_frame_id: str | None = device.current_frame_id  # type: ignore[assignment]
    active_instance_id: str | None = device.active_instance_id  # type: ignore[assignment]

    # Check if there's a new frame already cached
    if current_frame_id and current_frame_id != last_frame_id:
        return DeviceStateResponse(
            action=DeviceAction.FETCH_FRAME,
            frame_id=current_frame_id,
            active_instance_id=active_instance_id,
            poll_after_ms=5000,
        )

    # Check HLSS for new frames if device has an active instance
    if active_instance_id:
        new_frame_id = await _check_hlss_for_new_frame(db, device, active_instance_id)
        if new_frame_id and new_frame_id != last_frame_id:
            return DeviceStateResponse(
                action=DeviceAction.FETCH_FRAME,
                frame_id=new_frame_id,
                active_instance_id=active_instance_id,
                poll_after_ms=5000,
            )

    return DeviceStateResponse(
        action=DeviceAction.NOOP,
        frame_id=None,
        active_instance_id=active_instance_id,
        poll_after_ms=5000,
    )


async def _check_hlss_for_new_frame(
    db: Session,
    device: Device,
    instance_id: str,
) -> Optional[str]:
    """Check HLSS backend for a new frame and store it if available."""
    instance = db.query(Instance).filter(Instance.instance_id == instance_id).first()
    if not instance or not instance.hlss_type_id:
        return None

    hlss_type = (
        db.query(HLSSTypeModel)
        .filter(HLSSTypeModel.type_id == instance.hlss_type_id)
        .first()
    )

    if not hlss_type or not hlss_type.is_active:
        return None

    try:
        llss_base_url = _get_llss_base_url()
        service = HLSSService.from_hlss_type(hlss_type, llss_base_url)

        # First check frame metadata to see if there's a new frame
        success, frame_metadata, error = await service.get_frame_metadata(
            instance_id=instance_id,
        )

        if not success or not frame_metadata:
            return None

        hlss_frame_id = frame_metadata.frame_id

        # Check if this is a new frame compared to what we have cached
        if not hlss_frame_id:
            return None

        # Check if we already have this frame
        existing_frame = (
            db.query(Frame)
            .filter(Frame.instance_id == instance_id)
            .filter(Frame.frame_id == hlss_frame_id)
            .first()
        )

        if existing_frame:
            # We already have this frame, just return its ID if it's different from current
            if device.current_frame_id != existing_frame.frame_id:
                device.current_frame_id = existing_frame.frame_id  # type: ignore[assignment]
                db.commit()
                return existing_frame.frame_id
            return None

        # Request HLSS to send the frame - it will POST to our /instances/{instance_id}/frames endpoint
        success, _, _ = await service.request_frame_send(
            instance_id=instance_id,
        )

        if not success:
            logger.warning(
                f"Failed to request frame send from HLSS for instance {instance_id}"
            )
            return None

        # The frame will be received asynchronously via POST /instances/{instance_id}/frames
        # For now, return None and the device will poll again
        return None

    except Exception as e:
        logger.error(f"Error checking HLSS for new frame: {e}")

    return None


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
) -> dict:
    """
    Submit input events from a device.

    Sends button presses or other input events from the device to LLSS.
    LLSS routes them to the active HLSS instance.

    Special handling for HL_LEFT and HL_RIGHT buttons to switch between
    assigned HLSS instances.
    """
    # Get device to find active instance
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        return {"message": "Device not found"}

    # Log the input event
    input_event = InputEvent(
        device_id=device_id,
        instance_id=device.active_instance_id,
        button=event.button.value,
        event_type=event.event_type.value,
        event_timestamp=event.timestamp,
    )
    db.add(input_event)

    # Handle screen switching with HL_LEFT and HL_RIGHT
    if event.button in (ButtonType.HL_LEFT, ButtonType.HL_RIGHT):
        await _handle_screen_switch(db, device, event.button)
        db.commit()
        return {"message": "Screen switch processed"}

    db.commit()

    # Forward to active HLSS instance
    if device.active_instance_id:
        await _forward_input_to_hlss(db, device.active_instance_id, event)

    return {"message": "Input processed"}


async def _handle_screen_switch(
    db: Session,
    device: Device,
    button: ButtonType,
) -> None:
    """Handle HL_LEFT/HL_RIGHT to switch between assigned instances."""
    # Get all assigned instances for this device
    mappings = (
        db.query(DeviceInstanceMap)
        .filter(DeviceInstanceMap.device_id == device.device_id)
        .order_by(DeviceInstanceMap.id)
        .all()
    )

    if not mappings:
        return

    instance_ids = [m.instance_id for m in mappings]

    if not device.active_instance_id:
        # No active instance, set the first one
        device.active_instance_id = instance_ids[0]
        return

    try:
        current_index = instance_ids.index(device.active_instance_id)
    except ValueError:
        # Active instance not in list, set to first
        device.active_instance_id = instance_ids[0]
        return

    # Calculate new index
    if button == ButtonType.HL_LEFT:
        new_index = (current_index - 1) % len(instance_ids)
    else:  # HL_RIGHT
        new_index = (current_index + 1) % len(instance_ids)

    new_instance_id = instance_ids[new_index]
    device.active_instance_id = new_instance_id

    # Query HLSS for the latest frame for the new instance
    new_frame_id = await _check_hlss_for_new_frame(db, device, new_instance_id)
    if new_frame_id:
        device.current_frame_id = new_frame_id
        return

    # Fall back to the latest cached frame if HLSS check didn't return a new one
    latest_frame = (
        db.query(Frame)
        .filter(Frame.instance_id == new_instance_id)
        .order_by(Frame.created_at.desc())
        .first()
    )

    if latest_frame:
        device.current_frame_id = latest_frame.frame_id


async def _forward_input_to_hlss(
    db: Session,
    instance_id: str,
    event: InputEventSchema,
) -> None:
    """Forward an input event to the HLSS backend."""
    # Get instance and its HLSS type
    instance = db.query(Instance).filter(Instance.instance_id == instance_id).first()
    if not instance or not instance.hlss_type_id:
        return

    hlss_type = (
        db.query(HLSSTypeModel)
        .filter(HLSSTypeModel.type_id == instance.hlss_type_id)
        .first()
    )

    if not hlss_type or not hlss_type.is_active:
        return

    # Forward the input event
    try:
        llss_base_url = _get_llss_base_url()
        service = HLSSService.from_hlss_type(hlss_type, llss_base_url)
        success, error = await service.forward_input(
            instance_id=instance_id,
            event=event,
        )
        if not success:
            logger.warning(f"Failed to forward input to HLSS: {error}")
    except Exception as e:
        logger.error(f"Error forwarding input to HLSS: {e}")
