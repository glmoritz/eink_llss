"""
Device routes - Physical e-Ink devices (ESP32-based)
"""

import logging
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional, cast

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
    Strip,
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
    EventType,
    InputEvent as InputEventSchema,
    InputProcessResponse,
    InputProcessStatus,
)

router = APIRouter(prefix="/devices", tags=["Devices"])
logger = logging.getLogger(__name__)


def _get_llss_base_url() -> str:
    """Get the base URL of the LLSS API from environment."""
    return os.getenv("LLSS_BASE_URL", "http://localhost:8000")


def _frame_press_metadata(
    db: Session, frame_id: Optional[str]
) -> tuple[Optional[str], Optional[str], Optional[int], Optional[int], Optional[bool]]:
    """Look up the per-frame metadata HLSS uploaded:
    (top_strip_id, bottom_strip_id, top_enabled_mask, bottom_enabled_mask,
    full_refresh). All five ride alongside FETCH_FRAME / NEW_FRAME
    responses so the device can populate its press-feedback cache, gate
    disabled slots, and choose full vs partial refresh without an extra
    round trip."""
    if not frame_id:
        return None, None, None, None, None
    frame = (
        db.query(
            Frame.top_strip_id,
            Frame.bottom_strip_id,
            Frame.top_enabled_mask,
            Frame.bottom_enabled_mask,
            Frame.full_refresh,
        )
        .filter(Frame.frame_id == frame_id)
        .first()
    )
    if not frame:
        return None, None, None, None, None
    return (
        frame.top_strip_id,
        frame.bottom_strip_id,
        frame.top_enabled_mask,
        frame.bottom_enabled_mask,
        # Normalise to None when False so response_model_exclude_none
        # drops the field from the wire (smaller JSON, default-safe for
        # older device firmware that doesn't parse it).
        frame.full_refresh or None,
    )


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


@router.get(
    "/{device_id}/state",
    response_model=DeviceStateResponse,
    response_model_exclude_none=True,
)
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
        t_id, b_id, t_mask, b_mask, full_ref = _frame_press_metadata(db, current_frame_id)
        return DeviceStateResponse(
            action=DeviceAction.FETCH_FRAME,
            frame_id=current_frame_id,
            active_instance_id=active_instance_id,
            poll_after_ms=5000,
            top_strip_id=t_id,
            bottom_strip_id=b_id,
            top_enabled_mask=t_mask,
            bottom_enabled_mask=b_mask,
            full_refresh=full_ref,
        )

    # Check HLSS for new frames if device has an active instance
    if active_instance_id:
        new_frame_id = await _check_hlss_for_new_frame(db, device, active_instance_id)
        if new_frame_id and new_frame_id != last_frame_id:
            t_id, b_id, t_mask, b_mask, full_ref = _frame_press_metadata(db, new_frame_id)
            return DeviceStateResponse(
                action=DeviceAction.FETCH_FRAME,
                frame_id=new_frame_id,
                active_instance_id=active_instance_id,
                poll_after_ms=5000,
                top_strip_id=t_id,
                bottom_strip_id=b_id,
                top_enabled_mask=t_mask,
                bottom_enabled_mask=b_mask,
                full_refresh=full_ref,
            )

    # NOOP: still advertise the strip ids of the frame the device already
    # holds so a device that booted before strips landed can populate its
    # cache on the next heartbeat.
    t_id, b_id, t_mask, b_mask, full_ref = _frame_press_metadata(db, last_frame_id)
    return DeviceStateResponse(
        action=DeviceAction.NOOP,
        frame_id=None,
        active_instance_id=active_instance_id,
        poll_after_ms=5000,
        top_strip_id=t_id,
        bottom_strip_id=b_id,
        top_enabled_mask=t_mask,
        bottom_enabled_mask=b_mask,
        full_refresh=full_ref,
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
    raw: bool = False,
    pattern: bool = False,
    _: str = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> Response:
    """
    Fetch rendered frame data.

    By default always returns a PNG image:
    - bit_depth=1: 1-bit grayscale PNG (threshold at 128)
    - bit_depth=2: 8-bit grayscale PNG quantized to 4 levels (0, 85, 170, 255)
    - bit_depth=4: 8-bit grayscale PNG quantized to 16 levels
    - bit_depth>4: full PNG as stored (no conversion)

    Use ?raw=true to receive packed raw framebuffer bytes (application/octet-stream):
    - bit_depth=1: 1-bit packed monochrome (width*height/8 bytes)
    - bit_depth=2: Two concatenated 1-bit planes (MSB plane for 0x24, LSB for 0x26)
    - bit_depth=4: 4-bit packed grayscale (width*height/2 bytes)
    """
    from frame_converter import convert_png_to_framebuffer, convert_png_to_quantized_png

    frame = db.query(Frame).filter(Frame.frame_id == frame_id).first()

    if not frame or not frame.data:
        return Response(
            content=b"",
            media_type="application/octet-stream",
        )

    # Get device to check display capabilities
    device = db.query(Device).filter(Device.device_id == device_id).first()

    if not device:
        # Device not found, return PNG as fallback
        return Response(
            content=frame.data,
            media_type="image/png",
        )

    bit_depth = device.display_bit_depth or 4
    display_width = device.display_width
    display_height = device.display_height

    if pattern:
        # TEMPORARY: deterministic self-test pattern instead of real content.
        # Byte-for-byte identical to firmware src/pattern_check.c. Only the
        # 1bpp packed form is implemented (the firmware test path).
        from frame_converter import pattern_framebuffer_1bpp

        logger.info(
            f"Serving SELF-TEST pattern for {device_id} "
            f"({display_width}x{display_height}, 1bpp)"
        )
        return Response(
            content=pattern_framebuffer_1bpp(display_width, display_height),
            media_type="application/octet-stream",
        )

    if raw:
        # Return packed raw framebuffer bytes
        try:
            framebuffer_data, media_type = convert_png_to_framebuffer(
                png_data=frame.data,
                target_bit_depth=bit_depth,
                expected_width=display_width,
                expected_height=display_height,
            )
            return Response(
                content=framebuffer_data,
                media_type=media_type,
            )
        except Exception as e:
            logger.warning(f"Failed to convert frame to raw bit_depth={bit_depth}: {e}")
            return Response(
                content=b"",
                media_type="application/octet-stream",
            )

    # Default: return PNG (quantized for bit_depth <= 4, as-is for higher)
    try:
        png_data = convert_png_to_quantized_png(
            png_data=frame.data,
            target_bit_depth=bit_depth,
            expected_width=display_width,
            expected_height=display_height,
        )
        return Response(
            content=png_data,
            media_type="image/png",
        )
    except Exception as e:
        logger.warning(f"Failed to quantize PNG for bit_depth={bit_depth}: {e}")
        return Response(
            content=frame.data,
            media_type="image/png",
        )


@router.get("/{device_id}/strips/{strip_id}")
async def get_strip(
    device_id: str,
    strip_id: str,
    raw: bool = False,
    _: str = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> Response:
    """
    Fetch a pressed-state button strip (content-addressable).

    Strips are immutable for a given id, so the device caches them
    indefinitely keyed by ``strip_id``. The device discovers strip ids
    through DeviceStateResponse / InputProcessResponse and only requests
    ids it has not already cached.

    Encoding follows the same rules as the full-frame endpoint:
    PNG by default, raw=true returns the panel-native packed bytes at
    the device's declared bit depth.

    Returns 404 if the id is unknown to the server (evicted or the
    instance never uploaded one). The device treats 404 as "no press
    feedback available" and falls back to local invert.
    """
    from frame_converter import convert_png_to_framebuffer, convert_png_to_quantized_png

    strip = db.query(Strip).filter(Strip.strip_id == strip_id).first()
    if not strip or not strip.data:
        raise HTTPException(status_code=404, detail="Strip not found")

    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        return Response(content=strip.data, media_type="image/png")

    bit_depth = device.display_bit_depth or 4
    display_width = device.display_width

    if raw:
        # Strip dimensions: width matches the device's display, height is
        # the device-declared top_strip_height / bottom_strip_height. We
        # convert against the strip's own height (decoded from PNG) so the
        # raw output matches what the device's invert/merge pipeline expects.
        try:
            from PIL import Image
            from io import BytesIO

            img = Image.open(BytesIO(strip.data))
            strip_height = img.height
            framebuffer_data, media_type = convert_png_to_framebuffer(
                png_data=strip.data,
                target_bit_depth=bit_depth,
                expected_width=display_width,
                expected_height=strip_height,
            )
            return Response(content=framebuffer_data, media_type=media_type)
        except Exception as e:
            logger.warning(
                f"Failed to convert strip to raw bit_depth={bit_depth}: {e}"
            )
            return Response(content=b"", media_type="application/octet-stream")

    try:
        from PIL import Image
        from io import BytesIO

        img = Image.open(BytesIO(strip.data))
        png_data = convert_png_to_quantized_png(
            png_data=strip.data,
            target_bit_depth=bit_depth,
            expected_width=display_width,
            expected_height=img.height,
        )
        return Response(content=png_data, media_type="image/png")
    except Exception as e:
        logger.warning(f"Failed to quantize strip PNG for bit_depth={bit_depth}: {e}")
        return Response(content=strip.data, media_type="image/png")


@router.post(
    "/{device_id}/inputs",
    response_model=InputProcessResponse,
    status_code=200,
    response_model_exclude_none=True,
)
async def submit_input(
    device_id: str,
    event: InputEventSchema,
    _: str = Depends(get_current_device),
    db: Session = Depends(get_db),
) -> InputProcessResponse:
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
        return InputProcessResponse(
            status=InputProcessStatus.ERROR,
            message="Device not found",
        )

    previous_frame_id = cast(Optional[str], device.current_frame_id)

    # Log the input event
    input_event = InputEvent(
        device_id=device_id,
        instance_id=device.active_instance_id,
        button=event.button.value,
        event_type=event.event_type.value,
        event_timestamp=event.timestamp,
    )
    db.add(input_event)

    # Instance-switching on HL_LEFT/HL_RIGHT LONG_PRESS is only useful
    # when the device has more than one assigned instance to cycle
    # through. With a single assignment the cycle is a no-op AND the
    # press never reaches HLSS — which means app-level handlers (e.g.
    # the PLAY screen's view toggle) silently swallow the press. Skip
    # the LLSS-side switch in the single-instance case and let the event
    # forward normally to HLSS.
    if (
        event.button in (ButtonType.HL_LEFT, ButtonType.HL_RIGHT)
        and event.event_type == EventType.LONG_PRESS
    ):
        assigned_count = (
            db.query(DeviceInstanceMap)
            .filter(DeviceInstanceMap.device_id == device.device_id)
            .count()
        )
        if assigned_count > 1:
            await _handle_screen_switch(db, device, event.button)
            db.commit()
            current_frame_id = cast(Optional[str], device.current_frame_id)
            if current_frame_id and current_frame_id != previous_frame_id:
                t_id, b_id, t_mask, b_mask, full_ref = _frame_press_metadata(
                    db, current_frame_id
                )
                return InputProcessResponse(
                    status=InputProcessStatus.NEW_FRAME,
                    frame_id=current_frame_id,
                    message="Screen switch processed",
                    top_strip_id=t_id,
                    bottom_strip_id=b_id,
                    top_enabled_mask=t_mask,
                    bottom_enabled_mask=b_mask,
                )
            return InputProcessResponse(
                status=InputProcessStatus.NO_CHANGE,
                message="Screen switch processed",
            )

    db.commit()

    # Forward to active HLSS instance
    active_instance_id = cast(Optional[str], device.active_instance_id)
    if active_instance_id:
        success, error, hlss_resp = await _forward_input_to_hlss(
            db, active_instance_id, event
        )
        if not success:
            return InputProcessResponse(
                status=InputProcessStatus.ERROR,
                message=error or "Failed to forward input to HLSS",
            )

        # HLSS renders synchronously and reports the outcome directly — use it
        # so the device can chain a fetch immediately instead of re-polling.
        if hlss_resp:
            hlss_status = hlss_resp.get("status")
            hlss_frame_id = hlss_resp.get("frame_id")
            if hlss_status == InputProcessStatus.NEW_FRAME.value and hlss_frame_id:
                t_id, b_id, t_mask, b_mask, full_ref = _frame_press_metadata(
                    db, hlss_frame_id
                )
                return InputProcessResponse(
                    status=InputProcessStatus.NEW_FRAME,
                    frame_id=hlss_frame_id,
                    message="Input processed",
                    notice=hlss_resp.get("notice"),
                    top_strip_id=t_id,
                    bottom_strip_id=b_id,
                    top_enabled_mask=t_mask,
                    bottom_enabled_mask=b_mask,
                )
            if hlss_status == InputProcessStatus.NO_CHANGE.value:
                return InputProcessResponse(
                    status=InputProcessStatus.NO_CHANGE,
                    message="Input processed; no change",
                    notice=hlss_resp.get("notice"),
                )

    # Fallback: detect a frame committed via the frame-submit callback
    # (refresh first to avoid a stale cached read from this session).
    db.refresh(device)
    current_frame_id = cast(Optional[str], device.current_frame_id)
    if current_frame_id and current_frame_id != previous_frame_id:
        t_id, b_id, t_mask, b_mask, full_ref = _frame_press_metadata(db, current_frame_id)
        return InputProcessResponse(
            status=InputProcessStatus.NEW_FRAME,
            frame_id=current_frame_id,
            message="Input processed",
            top_strip_id=t_id,
            bottom_strip_id=b_id,
            top_enabled_mask=t_mask,
            bottom_enabled_mask=b_mask,
            full_refresh=full_ref,
        )

    if active_instance_id:
        return InputProcessResponse(
            status=InputProcessStatus.POLL,
            poll_after_ms=200,
            message="Input processed; poll for new frame",
        )

    return InputProcessResponse(
        status=InputProcessStatus.NO_CHANGE,
        message="Input processed",
    )


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
) -> tuple[bool, Optional[str], Optional[dict]]:
    """Forward an input event to the HLSS backend.

    Returns (success, error, hlss_response) where hlss_response is HLSS's parsed
    InputProcessResponse (status / frame_id). HLSS renders synchronously, so a
    NEW_FRAME there lets the device chain an immediate fetch.
    """
    # Get instance and its HLSS type
    instance = db.query(Instance).filter(Instance.instance_id == instance_id).first()
    if not instance or not instance.hlss_type_id:
        return False, "Instance or HLSS type not configured", None

    hlss_type = (
        db.query(HLSSTypeModel)
        .filter(HLSSTypeModel.type_id == instance.hlss_type_id)
        .first()
    )

    if not hlss_type or not hlss_type.is_active:
        return False, "HLSS type is not active", None

    # Forward the input event
    try:
        llss_base_url = _get_llss_base_url()
        service = HLSSService.from_hlss_type(hlss_type, llss_base_url)
        success, error, hlss_resp = await service.forward_input(
            instance_id=instance_id,
            event=event,
        )
        if not success:
            logger.warning(f"Failed to forward input to HLSS: {error}")
            return False, error or "Failed to forward input to HLSS", None
        return True, None, hlss_resp
    except Exception as e:
        logger.error(f"Error forwarding input to HLSS: {e}")
        return False, "Error forwarding input to HLSS", None
