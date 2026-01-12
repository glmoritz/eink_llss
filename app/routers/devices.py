"""
Device routes - Physical e-Ink devices (ESP32-based)
"""

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

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.post("/register", response_model=DeviceRegistrationResponse, status_code=201)
async def register_device(registration: DeviceRegistration) -> DeviceRegistrationResponse:
    """
    Register a new physical device.
    
    Registers a new device and returns credentials used for future authentication.
    """
    # TODO: Implement device registration logic
    # - Validate hardware_id uniqueness
    # - Generate device_id and device_secret
    # - Create and return access_token (JWT)
    
    return DeviceRegistrationResponse(
        device_id="dev_placeholder",
        device_secret="secret_placeholder",
        access_token="token_placeholder",
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
    # TODO: Implement state check logic
    # - Check if there's a new frame for the device
    # - Compare last_frame_id with current frame
    # - Return appropriate action (NOOP, FETCH_FRAME, SLEEP)
    
    return DeviceStateResponse(
        action=DeviceAction.NOOP,
        frame_id=None,
        active_instance_id=None,
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
    # TODO: Implement frame retrieval logic
    # - Fetch the rendered frame from storage
    # - Return raw framebuffer data
    
    return Response(
        content=b"",  # Placeholder empty frame
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
