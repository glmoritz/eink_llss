"""
Instance routes - HLSS instances managed by LLSS
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, UploadFile

from app.dependencies import get_current_instance
from app.models import (
    FrameCreateResponse,
    InputEvent,
    Instance,
    InstanceCreate,
)

router = APIRouter(prefix="/instances", tags=["Instances"])


@router.post("", response_model=Instance, status_code=201)
async def create_instance(instance: InstanceCreate) -> Instance:
    """
    Create a new HLSS instance.
    
    Creates a new logical HLSS instance (e.g. a chess game or HA dashboard).
    """
    # TODO: Implement instance creation logic
    # - Generate unique instance_id
    # - Store instance metadata
    # - Return created instance
    
    return Instance(
        instance_id="inst_placeholder",
        name=instance.name,
        type=instance.type,
        created_at=datetime.now(timezone.utc),
    )


@router.post("/{instance_id}/frames", response_model=FrameCreateResponse, status_code=201)
async def submit_frame(
    instance_id: str,
    file: UploadFile,
    _: str = Depends(get_current_instance),
) -> FrameCreateResponse:
    """
    Submit a new logical frame.
    
    HLSS submits a newly rendered frame (PNG).
    LLSS stores, diffs, and schedules device refreshes.
    """
    # TODO: Implement frame processing logic
    # - Validate PNG format
    # - Store frame
    # - Calculate hash for diffing
    # - Schedule device refresh if needed
    
    content = await file.read()
    
    return FrameCreateResponse(
        frame_id="frame_placeholder",
        hash="hash_placeholder",
        created_at=datetime.now(timezone.utc),
    )


@router.post("/{instance_id}/notify", status_code=202)
async def notify_instance(
    instance_id: str,
    _: str = Depends(get_current_instance),
) -> None:
    """
    Notify LLSS of instance state change.
    
    Notifies LLSS that the instance state has changed and a new frame
    may be available or should be requested.
    """
    # TODO: Implement notification logic
    # - Mark instance as having pending changes
    # - Trigger frame fetch if needed
    pass


@router.post("/{instance_id}/inputs", status_code=200)
async def receive_input(
    instance_id: str,
    event: InputEvent,
    _: str = Depends(get_current_instance),
) -> None:
    """
    Receive forwarded input events.
    
    LLSS forwards device input events to the active HLSS instance.
    """
    # TODO: Implement input processing logic
    # - Process the input event
    # - Update instance state as needed
    pass
