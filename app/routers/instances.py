"""
Instance routes - HLSS instances managed by LLSS
"""

import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, UploadFile

from app.dependencies import get_current_instance
from app.models import (
    FrameCreateResponse,
    InputEvent,
    Instance,
    InstanceCreate,
)
from app.store import device_instance_map, device_store, frame_store, instance_store

router = APIRouter(prefix="/instances", tags=["Instances"])


@router.post("", response_model=Instance, status_code=201)
async def create_instance(instance: InstanceCreate) -> Instance:
    """
    Create a new HLSS instance.

    Creates a new logical HLSS instance (e.g. a chess game or HA dashboard).
    """
    instance_id = f"inst_{uuid.uuid4().hex[:12]}"
    created_at = datetime.now(timezone.utc)

    instance_store[instance_id] = {
        "instance_id": instance_id,
        "name": instance.name,
        "type": instance.type,
        "created_at": created_at,
    }

    return Instance(
        instance_id=instance_id,
        name=instance.name,
        type=instance.type,
        created_at=created_at,
    )


@router.post(
    "/{instance_id}/frames", response_model=FrameCreateResponse, status_code=201
)
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
    content = await file.read()

    # Generate frame ID and hash
    frame_id = f"frame_{uuid.uuid4().hex[:12]}"
    frame_hash = hashlib.sha256(content).hexdigest()[:16]
    created_at = datetime.now(timezone.utc)

    # Store the frame
    frame_store[frame_id] = content

    # Update all devices linked to this instance
    for device_id, linked_instance_id in device_instance_map.items():
        if linked_instance_id == instance_id:
            if device_id in device_store:
                device_store[device_id]["current_frame_id"] = frame_id

    # Also update any device that has this as active_instance_id
    for device_id, device in device_store.items():
        if device.get("active_instance_id") == instance_id:
            device["current_frame_id"] = frame_id

    return FrameCreateResponse(
        frame_id=frame_id,
        hash=frame_hash,
        created_at=created_at,
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
