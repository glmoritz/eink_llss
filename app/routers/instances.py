"""
Instance routes - HLSS instances managed by LLSS
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.db_models import Device, Frame, Instance as InstanceModel
from app.dependencies import get_current_instance
from app.models import (
    FrameCreateResponse,
    InputEvent,
    Instance,
    InstanceCreate,
)

router = APIRouter(prefix="/instances", tags=["Instances"])


@router.post("", response_model=Instance, status_code=201)
async def create_instance(
    instance: InstanceCreate,
    db: Session = Depends(get_db),
) -> Instance:
    """
    Create a new HLSS instance.

    Creates a new logical HLSS instance (e.g. a chess game or HA dashboard).
    """
    instance_id = uuid.uuid4()
    access_token = secrets.token_urlsafe(32)
    created_at = datetime.now(timezone.utc)

    # Create instance in database
    db_instance = InstanceModel(
        instance_id=instance_id,
        name=instance.name,
        type=instance.type,
        access_token=access_token,
        created_at=created_at,
    )

    db.add(db_instance)
    db.commit()
    db.refresh(db_instance)

    return Instance(
        instance_id=str(instance_id),
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
    db: Session = Depends(get_db),
) -> FrameCreateResponse:
    """
    Submit a new logical frame.

    HLSS submits a newly rendered frame (PNG).
    LLSS stores, diffs, and schedules device refreshes.
    """
    content = await file.read()

    # Generate frame ID and hash
    frame_id = uuid.uuid4()
    frame_hash = hashlib.sha256(content).hexdigest()[:16]
    created_at = datetime.now(timezone.utc)

    # Store the frame in database
    frame = Frame(
        frame_id=frame_id,
        instance_id=instance_id,
        data=content,
        hash=frame_hash,
        created_at=created_at,
    )
    db.add(frame)

    # Update all devices that have this instance as active
    devices = db.query(Device).filter(Device.active_instance_id == instance_id).all()
    for device in devices:
        device.current_frame_id = frame_id

    db.commit()

    return FrameCreateResponse(
        frame_id=str(frame_id),
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
