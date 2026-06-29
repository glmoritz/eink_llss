"""
Instance routes - HLSS instances managed by LLSS
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from auth import create_instance_access_token
from database import get_db
from db_models import Device, Frame, Instance as InstanceModel, Strip
from dependencies import get_current_instance, get_llss_admin
from models import (
    FrameCreateResponse,
    InputEvent,
    Instance,
    InstanceCreate,
)


async def _ingest_strip(
    db: Session, upload: Optional[UploadFile]
) -> Optional[str]:
    """Compute a stable content-hash id for an uploaded strip part, store the
    bytes once (deduped by id), and return the id. Returns None when the
    caller did not send the part."""
    if upload is None:
        return None
    content = await upload.read()
    if not content:
        return None
    strip_id = hashlib.sha256(content).hexdigest()[:32]
    if db.query(Strip).filter(Strip.strip_id == strip_id).first() is None:
        db.add(Strip(strip_id=strip_id, data=content))
    return strip_id

router = APIRouter(prefix="/instances", tags=["Instances"])


@router.post("", response_model=Instance, status_code=201)
async def create_instance(
    instance: InstanceCreate,
    _: str = Depends(get_llss_admin),
    db: Session = Depends(get_db),
) -> Instance:
    """
    Create a new HLSS instance.

    Creates a new logical HLSS instance (e.g. a chess game or HA dashboard).
    """
    instance_id = f"inst_{uuid.uuid4().hex[:12]}"
    access_token = create_instance_access_token(instance_id)
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
        instance_id=instance_id,
        name=instance.name,
        type=instance.type,
        access_token=access_token,
        created_at=created_at,
    )


@router.post(
    "/{instance_id}/frames", response_model=FrameCreateResponse, status_code=201
)
async def submit_frame(
    instance_id: str,
    file: UploadFile,
    top_pressed: Optional[UploadFile] = File(default=None),
    bottom_pressed: Optional[UploadFile] = File(default=None),
    _: str = Depends(get_current_instance),
    db: Session = Depends(get_db),
) -> FrameCreateResponse:
    """
    Submit a new logical frame.

    HLSS submits a newly rendered frame (PNG) plus optional pressed-state
    button strips (top_pressed / bottom_pressed). LLSS stores them, diffs
    the frame, and schedules device refreshes. Strips are content-addressed
    and reused across frames with visually-identical buttons.
    """
    content = await file.read()
    frame_hash = hashlib.sha256(content).hexdigest()[:16]

    # Compute strip ids up front so the dedup path can compare them. Strip
    # rows are inserted lazily — duplicates are detected by primary-key
    # lookup before insert. Empty parts produce None and skip both storage
    # and the device-side advertisement.
    top_strip_id = await _ingest_strip(db, top_pressed)
    bottom_strip_id = await _ingest_strip(db, bottom_pressed)

    # Dedup: if this instance already has a frame with identical content AND
    # the same strip ids, reuse it. The strip ids participate in the key so
    # that HLSS swapping out the pressed-state visual (e.g. shifting the
    # disabled-button style) bumps to a fresh frame_id and lets the device
    # repaint. Without strip ids in the key, an updated strip would never
    # reach the device.
    existing = (
        db.query(Frame)
        .filter(
            Frame.instance_id == instance_id,
            Frame.hash == frame_hash,
            Frame.top_strip_id == top_strip_id,
            Frame.bottom_strip_id == bottom_strip_id,
        )
        .order_by(Frame.created_at.desc())
        .first()
    )

    if existing:
        # Flush any new Strip rows _ingest_strip queued — even on the reuse
        # path they need to land so the device can fetch by id.
        db.commit()
        frame_id = existing.frame_id
        devices = (
            db.query(Device).filter(Device.active_instance_id == instance_id).all()
        )
        changed = False
        for device in devices:
            if device.current_frame_id != frame_id:
                device.current_frame_id = frame_id
                changed = True
        if changed:
            db.commit()
        return FrameCreateResponse(
            frame_id=frame_id,
            hash=frame_hash,
            created_at=existing.created_at,
        )

    # New content — store it and point devices at it.
    frame_id = f"frame_{uuid.uuid4().hex[:12]}"
    created_at = datetime.now(timezone.utc)

    frame = Frame(
        frame_id=frame_id,
        instance_id=instance_id,
        data=content,
        hash=frame_hash,
        top_strip_id=top_strip_id,
        bottom_strip_id=bottom_strip_id,
        created_at=created_at,
    )
    db.add(frame)

    # Update all devices that have this instance as active
    devices = db.query(Device).filter(Device.active_instance_id == instance_id).all()
    for device in devices:
        device.current_frame_id = frame_id

    db.commit()

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
