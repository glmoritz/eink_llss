"""
Admin routes - Administrative interface for managing HLSS types, instances, and devices.

These endpoints provide the administrative API for:
- Managing HLSS type registry
- Creating and managing HLSS instances
- Assigning instances to devices
- Viewing system status
"""

import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from database import get_db
from db_models import (
    Device,
    DeviceAuthStatus,
    DeviceInstanceMap,
    HLSSType as HLSSTypeModel,
    Instance,
)
from hlss_service import initialize_hlss_instance, refresh_hlss_status, HLSSService
from models import (
    AdminInstance,
    AdminInstanceCreate,
    AdminInstanceUpdate,
    DeviceInstanceAssignment,
    DeviceWithInstances,
    DisplayCapabilities,
    HLSSType,
    HLSSTypeCreate,
    HLSSTypeUpdate,
)

router = APIRouter(prefix="/admin", tags=["Admin"])


def get_llss_base_url(request: Request) -> str:
    """Get the base URL of the LLSS API from the request."""
    # Use environment variable if set, otherwise construct from request
    base_url = os.getenv("LLSS_BASE_URL")
    if base_url:
        return base_url
    return str(request.base_url).rstrip("/")


# ============================================================
# HLSS Type Management
# ============================================================


@router.get("/hlss-types", response_model=List[HLSSType])
async def list_hlss_types(
    active_only: bool = Query(default=False, description="Only return active types"),
    db: Session = Depends(get_db),
) -> List[HLSSType]:
    """
    List all registered HLSS types.

    HLSS types are templates for creating instances. Each type represents
    a specific HLSS backend (e.g., lichess, homeassistant).
    """
    query = db.query(HLSSTypeModel)
    if active_only:
        query = query.filter(HLSSTypeModel.is_active == True)

    types = query.order_by(HLSSTypeModel.name).all()

    return [
        HLSSType(
            type_id=t.type_id,
            name=t.name,
            description=t.description,
            base_url=t.base_url,
            default_width=t.default_width,
            default_height=t.default_height,
            default_bit_depth=t.default_bit_depth,
            is_active=t.is_active,
            created_at=t.created_at,
        )
        for t in types
    ]


@router.post("/hlss-types", response_model=HLSSType, status_code=201)
async def create_hlss_type(
    hlss_type: HLSSTypeCreate,
    db: Session = Depends(get_db),
) -> HLSSType:
    """
    Register a new HLSS type.

    This registers a new HLSS backend that can be used to create instances.
    The base_url should point to the HLSS API (e.g., https://lichess-hlss.example/api).
    """
    # Check if type_id already exists
    existing = (
        db.query(HLSSTypeModel)
        .filter(HLSSTypeModel.type_id == hlss_type.type_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409, detail=f"HLSS type '{hlss_type.type_id}' already exists"
        )

    db_type = HLSSTypeModel(
        type_id=hlss_type.type_id,
        name=hlss_type.name,
        description=hlss_type.description,
        base_url=hlss_type.base_url,
        auth_token=hlss_type.auth_token,
        default_width=hlss_type.default_width,
        default_height=hlss_type.default_height,
        default_bit_depth=hlss_type.default_bit_depth,
        is_active=True,
    )

    db.add(db_type)
    db.commit()
    db.refresh(db_type)

    return HLSSType(
        type_id=db_type.type_id,
        name=db_type.name,
        description=db_type.description,
        base_url=db_type.base_url,
        default_width=db_type.default_width,
        default_height=db_type.default_height,
        default_bit_depth=db_type.default_bit_depth,
        is_active=db_type.is_active,
        created_at=db_type.created_at,
    )


@router.get("/hlss-types/{type_id}", response_model=HLSSType)
async def get_hlss_type(
    type_id: str,
    db: Session = Depends(get_db),
) -> HLSSType:
    """Get a specific HLSS type by ID."""
    db_type = db.query(HLSSTypeModel).filter(HLSSTypeModel.type_id == type_id).first()
    if not db_type:
        raise HTTPException(status_code=404, detail=f"HLSS type '{type_id}' not found")

    return HLSSType(
        type_id=db_type.type_id,
        name=db_type.name,
        description=db_type.description,
        base_url=db_type.base_url,
        default_width=db_type.default_width,
        default_height=db_type.default_height,
        default_bit_depth=db_type.default_bit_depth,
        is_active=db_type.is_active,
        created_at=db_type.created_at,
    )


@router.patch("/hlss-types/{type_id}", response_model=HLSSType)
async def update_hlss_type(
    type_id: str,
    update: HLSSTypeUpdate,
    db: Session = Depends(get_db),
) -> HLSSType:
    """Update an HLSS type."""
    db_type = db.query(HLSSTypeModel).filter(HLSSTypeModel.type_id == type_id).first()
    if not db_type:
        raise HTTPException(status_code=404, detail=f"HLSS type '{type_id}' not found")

    # Update fields that are provided
    if update.name is not None:
        db_type.name = update.name
    if update.description is not None:
        db_type.description = update.description
    if update.base_url is not None:
        db_type.base_url = update.base_url
    if update.auth_token is not None:
        db_type.auth_token = update.auth_token
    if update.default_width is not None:
        db_type.default_width = update.default_width
    if update.default_height is not None:
        db_type.default_height = update.default_height
    if update.default_bit_depth is not None:
        db_type.default_bit_depth = update.default_bit_depth
    if update.is_active is not None:
        db_type.is_active = update.is_active

    db.commit()
    db.refresh(db_type)

    return HLSSType(
        type_id=db_type.type_id,
        name=db_type.name,
        description=db_type.description,
        base_url=db_type.base_url,
        default_width=db_type.default_width,
        default_height=db_type.default_height,
        default_bit_depth=db_type.default_bit_depth,
        is_active=db_type.is_active,
        created_at=db_type.created_at,
    )


@router.delete("/hlss-types/{type_id}", status_code=204)
async def delete_hlss_type(
    type_id: str,
    db: Session = Depends(get_db),
) -> None:
    """
    Delete an HLSS type.

    This will fail if there are instances using this type.
    """
    db_type = db.query(HLSSTypeModel).filter(HLSSTypeModel.type_id == type_id).first()
    if not db_type:
        raise HTTPException(status_code=404, detail=f"HLSS type '{type_id}' not found")

    # Check for instances using this type
    instance_count = db.query(Instance).filter(Instance.hlss_type_id == type_id).count()
    if instance_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete HLSS type '{type_id}': {instance_count} instances are using it",
        )

    db.delete(db_type)
    db.commit()


# ============================================================
# Instance Management
# ============================================================


@router.get("/instances", response_model=List[AdminInstance])
async def list_instances(
    hlss_type_id: Optional[str] = Query(
        default=None, description="Filter by HLSS type"
    ),
    db: Session = Depends(get_db),
) -> List[AdminInstance]:
    """List all HLSS instances."""
    query = db.query(Instance)
    if hlss_type_id:
        query = query.filter(Instance.hlss_type_id == hlss_type_id)

    instances = query.order_by(Instance.created_at.desc()).all()

    return [
        AdminInstance(
            instance_id=inst.instance_id,
            name=inst.name,
            type=inst.type,
            hlss_type_id=inst.hlss_type_id,
            access_token=inst.access_token,
            hlss_initialized=inst.hlss_initialized,
            hlss_ready=inst.hlss_ready,
            needs_configuration=inst.needs_configuration,
            configuration_url=inst.configuration_url,
            display=(
                DisplayCapabilities(
                    width=inst.display_width,
                    height=inst.display_height,
                    bit_depth=inst.display_bit_depth,
                )
                if inst.display_width
                else None
            ),
            created_at=inst.created_at,
            initialized_at=inst.initialized_at,
        )
        for inst in instances
    ]


@router.post("/instances", response_model=AdminInstance, status_code=201)
async def create_instance(
    request: Request,
    instance_create: AdminInstanceCreate,
    db: Session = Depends(get_db),
) -> AdminInstance:
    """
    Create a new HLSS instance.

    If auto_initialize is true (default), LLSS will immediately call the HLSS
    backend to initialize the instance and establish trust.
    """
    # Verify HLSS type exists and is active
    hlss_type = (
        db.query(HLSSTypeModel)
        .filter(HLSSTypeModel.type_id == instance_create.hlss_type_id)
        .first()
    )

    if not hlss_type:
        raise HTTPException(
            status_code=404,
            detail=f"HLSS type '{instance_create.hlss_type_id}' not found",
        )
    if not hlss_type.is_active:
        raise HTTPException(
            status_code=400,
            detail=f"HLSS type '{instance_create.hlss_type_id}' is not active",
        )

    # Generate instance credentials
    instance_id = f"inst_{uuid.uuid4().hex[:12]}"
    access_token = secrets.token_urlsafe(32)
    created_at = datetime.now(timezone.utc)

    # Determine display configuration
    display_width = instance_create.display_width or hlss_type.default_width
    display_height = instance_create.display_height or hlss_type.default_height
    display_bit_depth = instance_create.display_bit_depth or hlss_type.default_bit_depth

    # Create instance in database
    db_instance = Instance(
        instance_id=instance_id,
        name=instance_create.name,
        type=hlss_type.type_id,  # Use HLSS type as the instance type
        hlss_type_id=hlss_type.type_id,
        access_token=access_token,
        display_width=display_width,
        display_height=display_height,
        display_bit_depth=display_bit_depth,
        hlss_initialized=False,
        hlss_ready=False,
        needs_configuration=False,
        created_at=created_at,
    )

    db.add(db_instance)
    db.commit()
    db.refresh(db_instance)

    # Auto-initialize with HLSS backend if requested
    if instance_create.auto_initialize:
        llss_base_url = get_llss_base_url(request)
        success, error = await initialize_hlss_instance(
            db=db,
            instance=db_instance,
            hlss_type=hlss_type,
            llss_base_url=llss_base_url,
        )
        if not success:
            # Instance was created but initialization failed
            # The instance remains in pending state
            pass  # We still return the instance, user can retry initialization

    return AdminInstance(
        instance_id=db_instance.instance_id,
        name=db_instance.name,
        type=db_instance.type,
        hlss_type_id=db_instance.hlss_type_id,
        access_token=db_instance.access_token,
        hlss_initialized=db_instance.hlss_initialized,
        hlss_ready=db_instance.hlss_ready,
        needs_configuration=db_instance.needs_configuration,
        configuration_url=db_instance.configuration_url,
        display=(
            DisplayCapabilities(
                width=db_instance.display_width,
                height=db_instance.display_height,
                bit_depth=db_instance.display_bit_depth,
            )
            if db_instance.display_width
            else None
        ),
        created_at=db_instance.created_at,
        initialized_at=db_instance.initialized_at,
    )


@router.get("/instances/{instance_id}", response_model=AdminInstance)
async def get_instance(
    instance_id: str,
    db: Session = Depends(get_db),
) -> AdminInstance:
    """Get a specific instance by ID."""
    inst = db.query(Instance).filter(Instance.instance_id == instance_id).first()
    if not inst:
        raise HTTPException(
            status_code=404, detail=f"Instance '{instance_id}' not found"
        )

    return AdminInstance(
        instance_id=inst.instance_id,
        name=inst.name,
        type=inst.type,
        hlss_type_id=inst.hlss_type_id,
        access_token=inst.access_token,
        hlss_initialized=inst.hlss_initialized,
        hlss_ready=inst.hlss_ready,
        needs_configuration=inst.needs_configuration,
        configuration_url=inst.configuration_url,
        display=(
            DisplayCapabilities(
                width=inst.display_width,
                height=inst.display_height,
                bit_depth=inst.display_bit_depth,
            )
            if inst.display_width
            else None
        ),
        created_at=inst.created_at,
        initialized_at=inst.initialized_at,
    )


@router.patch("/instances/{instance_id}", response_model=AdminInstance)
async def update_instance(
    instance_id: str,
    update: AdminInstanceUpdate,
    db: Session = Depends(get_db),
) -> AdminInstance:
    """Update an instance."""
    inst = db.query(Instance).filter(Instance.instance_id == instance_id).first()
    if not inst:
        raise HTTPException(
            status_code=404, detail=f"Instance '{instance_id}' not found"
        )

    if update.name is not None:
        inst.name = update.name
    if update.display_width is not None:
        inst.display_width = update.display_width
    if update.display_height is not None:
        inst.display_height = update.display_height
    if update.display_bit_depth is not None:
        inst.display_bit_depth = update.display_bit_depth

    db.commit()
    db.refresh(inst)

    return AdminInstance(
        instance_id=inst.instance_id,
        name=inst.name,
        type=inst.type,
        hlss_type_id=inst.hlss_type_id,
        access_token=inst.access_token,
        hlss_initialized=inst.hlss_initialized,
        hlss_ready=inst.hlss_ready,
        needs_configuration=inst.needs_configuration,
        configuration_url=inst.configuration_url,
        display=(
            DisplayCapabilities(
                width=inst.display_width,
                height=inst.display_height,
                bit_depth=inst.display_bit_depth,
            )
            if inst.display_width
            else None
        ),
        created_at=inst.created_at,
        initialized_at=inst.initialized_at,
    )


@router.delete("/instances/{instance_id}", status_code=204)
async def delete_instance(
    request: Request,
    instance_id: str,
    db: Session = Depends(get_db),
) -> None:
    """Delete an instance and notify the HLSS backend."""
    inst = db.query(Instance).filter(Instance.instance_id == instance_id).first()
    if not inst:
        raise HTTPException(
            status_code=404, detail=f"Instance '{instance_id}' not found"
        )

    # Notify HLSS backend if instance was initialized
    if inst.hlss_initialized and inst.hlss_type_id:
        hlss_type = (
            db.query(HLSSTypeModel)
            .filter(HLSSTypeModel.type_id == inst.hlss_type_id)
            .first()
        )
        if hlss_type:
            llss_base_url = get_llss_base_url(request)
            service = HLSSService.from_hlss_type(hlss_type, llss_base_url)
            success, error = await service.delete_instance(
                instance_id=instance_id,
            )
            # Log but don't fail if HLSS notification fails
            if not success:
                import logging

                logging.getLogger(__name__).warning(
                    f"Failed to notify HLSS about instance deletion: {error}"
                )

    # Remove from any device mappings
    db.query(DeviceInstanceMap).filter(
        DeviceInstanceMap.instance_id == instance_id
    ).delete()

    # Update devices that have this as active instance
    db.query(Device).filter(Device.active_instance_id == instance_id).update(
        {"active_instance_id": None}
    )

    db.delete(inst)
    db.commit()


@router.post("/instances/{instance_id}/initialize", response_model=AdminInstance)
async def initialize_instance(
    request: Request,
    instance_id: str,
    db: Session = Depends(get_db),
) -> AdminInstance:
    """
    Initialize or re-initialize an instance with its HLSS backend.

    This calls the HLSS /instances/init endpoint to establish trust.
    Use this if initial auto-initialization failed or to re-establish connection.
    """
    inst = db.query(Instance).filter(Instance.instance_id == instance_id).first()
    if not inst:
        raise HTTPException(
            status_code=404, detail=f"Instance '{instance_id}' not found"
        )

    if not inst.hlss_type_id:
        raise HTTPException(
            status_code=400, detail="Instance has no HLSS type configured"
        )

    hlss_type = (
        db.query(HLSSTypeModel)
        .filter(HLSSTypeModel.type_id == inst.hlss_type_id)
        .first()
    )

    if not hlss_type:
        raise HTTPException(
            status_code=404, detail=f"HLSS type '{inst.hlss_type_id}' not found"
        )

    llss_base_url = get_llss_base_url(request)
    success, error = await initialize_hlss_instance(
        db=db,
        instance=inst,
        hlss_type=hlss_type,
        llss_base_url=llss_base_url,
    )

    if not success:
        raise HTTPException(
            status_code=502, detail=f"Failed to initialize with HLSS: {error}"
        )

    db.refresh(inst)

    return AdminInstance(
        instance_id=inst.instance_id,
        name=inst.name,
        type=inst.type,
        hlss_type_id=inst.hlss_type_id,
        access_token=inst.access_token,
        hlss_initialized=inst.hlss_initialized,
        hlss_ready=inst.hlss_ready,
        needs_configuration=inst.needs_configuration,
        configuration_url=inst.configuration_url,
        display=(
            DisplayCapabilities(
                width=inst.display_width,
                height=inst.display_height,
                bit_depth=inst.display_bit_depth,
            )
            if inst.display_width
            else None
        ),
        created_at=inst.created_at,
        initialized_at=inst.initialized_at,
    )


@router.post("/instances/{instance_id}/refresh-status", response_model=AdminInstance)
async def refresh_instance_status(
    request: Request,
    instance_id: str,
    db: Session = Depends(get_db),
) -> AdminInstance:
    """
    Refresh the status of an instance from its HLSS backend.

    This checks if the instance is ready, needs configuration, etc.
    """
    inst = db.query(Instance).filter(Instance.instance_id == instance_id).first()
    if not inst:
        raise HTTPException(
            status_code=404, detail=f"Instance '{instance_id}' not found"
        )

    if not inst.hlss_type_id:
        raise HTTPException(
            status_code=400, detail="Instance has no HLSS type configured"
        )

    hlss_type = (
        db.query(HLSSTypeModel)
        .filter(HLSSTypeModel.type_id == inst.hlss_type_id)
        .first()
    )

    if not hlss_type:
        raise HTTPException(
            status_code=404, detail=f"HLSS type '{inst.hlss_type_id}' not found"
        )

    llss_base_url = get_llss_base_url(request)
    success, error = await refresh_hlss_status(
        db=db,
        instance=inst,
        hlss_type=hlss_type,
        llss_base_url=llss_base_url,
    )

    if not success:
        raise HTTPException(
            status_code=502, detail=f"Failed to get status from HLSS: {error}"
        )

    db.refresh(inst)

    return AdminInstance(
        instance_id=inst.instance_id,
        name=inst.name,
        type=inst.type,
        hlss_type_id=inst.hlss_type_id,
        access_token=inst.access_token,
        hlss_initialized=inst.hlss_initialized,
        hlss_ready=inst.hlss_ready,
        needs_configuration=inst.needs_configuration,
        configuration_url=inst.configuration_url,
        display=(
            DisplayCapabilities(
                width=inst.display_width,
                height=inst.display_height,
                bit_depth=inst.display_bit_depth,
            )
            if inst.display_width
            else None
        ),
        created_at=inst.created_at,
        initialized_at=inst.initialized_at,
    )


@router.get("/instances/{instance_id}/frame-status")
async def get_instance_frame_status(
    request: Request,
    instance_id: str,
    db: Session = Depends(get_db),
):
    """
    Get frame status from both LLSS and HLSS.

    Compares the current frame in LLSS with what HLSS reports to detect
    if frames are out of sync.
    """
    from models import FrameSyncResult

    inst = db.query(Instance).filter(Instance.instance_id == instance_id).first()
    if not inst:
        raise HTTPException(
            status_code=404, detail=f"Instance '{instance_id}' not found"
        )

    if not inst.hlss_type_id:
        raise HTTPException(
            status_code=400, detail="Instance has no HLSS type configured"
        )

    hlss_type = (
        db.query(HLSSTypeModel)
        .filter(HLSSTypeModel.type_id == inst.hlss_type_id)
        .first()
    )

    if not hlss_type:
        raise HTTPException(
            status_code=404, detail=f"HLSS type '{inst.hlss_type_id}' not found"
        )

    # Get LLSS frame status
    from db_models import Frame

    llss_frame = (
        db.query(Frame)
        .filter(Frame.instance_id == instance_id)
        .order_by(Frame.created_at.desc())
        .first()
    )

    llss_has_frame = llss_frame is not None
    llss_frame_hash = llss_frame.hash if llss_frame else None

    # Get HLSS frame status
    llss_base_url = get_llss_base_url(request)
    service = HLSSService.from_hlss_type(hlss_type, llss_base_url)
    success, hlss_metadata, error = await service.get_frame_metadata(
        instance_id=instance_id,
    )

    if not success:
        return FrameSyncResult(
            instance_id=instance_id,
            instance_name=inst.name,
            hlss_has_frame=False,
            llss_has_frame=llss_has_frame,
            llss_frame_hash=llss_frame_hash,
            in_sync=False,
            error=f"Failed to get HLSS frame status: {error}",
        )

    hlss_has_frame = hlss_metadata.has_frame if hlss_metadata else False
    hlss_frame_hash = hlss_metadata.frame_hash if hlss_metadata else None

    # Determine if in sync
    if not hlss_has_frame and not llss_has_frame:
        in_sync = True
    elif hlss_has_frame and llss_has_frame and hlss_frame_hash == llss_frame_hash:
        in_sync = True
    else:
        in_sync = False

    return FrameSyncResult(
        instance_id=instance_id,
        instance_name=inst.name,
        hlss_has_frame=hlss_has_frame,
        hlss_frame_hash=hlss_frame_hash,
        llss_has_frame=llss_has_frame,
        llss_frame_hash=llss_frame_hash,
        in_sync=in_sync,
    )


@router.post("/instances/{instance_id}/sync-frame")
async def sync_instance_frame(
    request: Request,
    instance_id: str,
    db: Session = Depends(get_db),
):
    """
    Sync frame from HLSS to LLSS.

    Checks if HLSS has a frame that LLSS doesn't have, and requests
    HLSS to send it if needed.
    """
    from models import FrameSyncResult

    inst = db.query(Instance).filter(Instance.instance_id == instance_id).first()
    if not inst:
        raise HTTPException(
            status_code=404, detail=f"Instance '{instance_id}' not found"
        )

    if not inst.hlss_type_id:
        raise HTTPException(
            status_code=400, detail="Instance has no HLSS type configured"
        )

    hlss_type = (
        db.query(HLSSTypeModel)
        .filter(HLSSTypeModel.type_id == inst.hlss_type_id)
        .first()
    )

    if not hlss_type:
        raise HTTPException(
            status_code=404, detail=f"HLSS type '{inst.hlss_type_id}' not found"
        )

    # Get LLSS frame status
    from db_models import Frame

    llss_frame = (
        db.query(Frame)
        .filter(Frame.instance_id == instance_id)
        .order_by(Frame.created_at.desc())
        .first()
    )

    llss_has_frame = llss_frame is not None
    llss_frame_hash = llss_frame.hash if llss_frame else None

    # Get HLSS frame status
    llss_base_url = get_llss_base_url(request)
    service = HLSSService.from_hlss_type(hlss_type, llss_base_url)
    success, hlss_metadata, error = await service.get_frame_metadata(
        instance_id=instance_id,
    )

    if not success:
        return FrameSyncResult(
            instance_id=instance_id,
            instance_name=inst.name,
            hlss_has_frame=False,
            llss_has_frame=llss_has_frame,
            llss_frame_hash=llss_frame_hash,
            in_sync=False,
            error=f"Failed to get HLSS frame status: {error}",
        )

    hlss_has_frame = hlss_metadata.has_frame if hlss_metadata else False
    hlss_frame_hash = hlss_metadata.frame_hash if hlss_metadata else None

    # Check if already in sync
    if not hlss_has_frame and not llss_has_frame:
        return FrameSyncResult(
            instance_id=instance_id,
            instance_name=inst.name,
            hlss_has_frame=False,
            llss_has_frame=False,
            in_sync=True,
            action_taken="No frames exist on either side",
        )

    if hlss_has_frame and llss_has_frame and hlss_frame_hash == llss_frame_hash:
        return FrameSyncResult(
            instance_id=instance_id,
            instance_name=inst.name,
            hlss_has_frame=True,
            hlss_frame_hash=hlss_frame_hash,
            llss_has_frame=True,
            llss_frame_hash=llss_frame_hash,
            in_sync=True,
            action_taken="Frames already in sync",
        )

    # Request HLSS to send the frame
    send_success, send_response, send_error = await service.request_frame_send(
        instance_id=instance_id,
    )

    if not send_success:
        return FrameSyncResult(
            instance_id=instance_id,
            instance_name=inst.name,
            hlss_has_frame=hlss_has_frame,
            hlss_frame_hash=hlss_frame_hash,
            llss_has_frame=llss_has_frame,
            llss_frame_hash=llss_frame_hash,
            in_sync=False,
            error=f"Failed to request frame from HLSS: {send_error}",
        )

    action = f"Requested frame from HLSS: status={send_response.status}"
    if send_response.frame_id:
        action += f", frame_id={send_response.frame_id}"

    return FrameSyncResult(
        instance_id=instance_id,
        instance_name=inst.name,
        hlss_has_frame=hlss_has_frame,
        hlss_frame_hash=hlss_frame_hash,
        llss_has_frame=llss_has_frame,
        llss_frame_hash=llss_frame_hash,
        in_sync=False,
        action_taken=action,
    )


# ============================================================
# Device Management
# ============================================================


@router.get("/devices", response_model=List[DeviceWithInstances])
async def list_devices(
    db: Session = Depends(get_db),
) -> List[DeviceWithInstances]:
    """List all registered devices with their assigned instances."""
    devices = db.query(Device).order_by(Device.created_at.desc()).all()

    result = []
    for dev in devices:
        # Get assigned instances
        mappings = (
            db.query(DeviceInstanceMap)
            .filter(DeviceInstanceMap.device_id == dev.device_id)
            .all()
        )
        assigned_instances = [m.instance_id for m in mappings]

        result.append(
            DeviceWithInstances(
                device_id=dev.device_id,
                hardware_id=dev.hardware_id,
                firmware_version=dev.firmware_version,
                auth_status=dev.auth_status,
                display=DisplayCapabilities(
                    width=dev.display_width,
                    height=dev.display_height,
                    bit_depth=dev.display_bit_depth,
                    partial_refresh=dev.display_partial_refresh,
                ),
                active_instance_id=dev.active_instance_id,
                assigned_instances=assigned_instances,
                last_seen_at=dev.last_seen_at,
                created_at=dev.created_at,
            )
        )

    return result


@router.get("/devices/{device_id}", response_model=DeviceWithInstances)
async def get_device(
    device_id: str,
    db: Session = Depends(get_db),
) -> DeviceWithInstances:
    """Get a specific device by ID."""
    dev = db.query(Device).filter(Device.device_id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")

    # Get assigned instances
    mappings = (
        db.query(DeviceInstanceMap)
        .filter(DeviceInstanceMap.device_id == device_id)
        .all()
    )
    assigned_instances = [m.instance_id for m in mappings]

    return DeviceWithInstances(
        device_id=dev.device_id,
        hardware_id=dev.hardware_id,
        firmware_version=dev.firmware_version,
        auth_status=dev.auth_status,
        display=DisplayCapabilities(
            width=dev.display_width,
            height=dev.display_height,
            bit_depth=dev.display_bit_depth,
            partial_refresh=dev.display_partial_refresh,
        ),
        active_instance_id=dev.active_instance_id,
        assigned_instances=assigned_instances,
        last_seen_at=dev.last_seen_at,
        created_at=dev.created_at,
    )


@router.post("/devices/{device_id}/assign-instance", status_code=200)
async def assign_instance_to_device(
    device_id: str,
    assignment: DeviceInstanceAssignment,
    db: Session = Depends(get_db),
) -> dict:
    """
    Assign an HLSS instance to a device.

    The instance will be added to the device's list of available instances.
    """
    # Verify device exists
    dev = db.query(Device).filter(Device.device_id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")

    # Verify instance exists
    inst = (
        db.query(Instance)
        .filter(Instance.instance_id == assignment.instance_id)
        .first()
    )
    if not inst:
        raise HTTPException(
            status_code=404, detail=f"Instance '{assignment.instance_id}' not found"
        )

    # Check if mapping already exists
    existing = (
        db.query(DeviceInstanceMap)
        .filter(
            DeviceInstanceMap.device_id == device_id,
            DeviceInstanceMap.instance_id == assignment.instance_id,
        )
        .first()
    )

    if existing:
        return {"message": "Instance already assigned to device"}

    # Create mapping
    mapping = DeviceInstanceMap(
        device_id=device_id,
        instance_id=assignment.instance_id,
    )
    db.add(mapping)

    # If device has no active instance, set this one
    if not dev.active_instance_id:
        dev.active_instance_id = assignment.instance_id

    db.commit()

    return {"message": "Instance assigned to device"}


@router.delete("/devices/{device_id}/instances/{instance_id}", status_code=204)
async def unassign_instance_from_device(
    device_id: str,
    instance_id: str,
    db: Session = Depends(get_db),
) -> None:
    """Remove an instance assignment from a device."""
    # Verify device exists
    dev = db.query(Device).filter(Device.device_id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")

    # Remove mapping
    deleted = (
        db.query(DeviceInstanceMap)
        .filter(
            DeviceInstanceMap.device_id == device_id,
            DeviceInstanceMap.instance_id == instance_id,
        )
        .delete()
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="Assignment not found")

    # If this was the active instance, clear it
    if dev.active_instance_id == instance_id:
        # Try to set another assigned instance as active
        other = (
            db.query(DeviceInstanceMap)
            .filter(DeviceInstanceMap.device_id == device_id)
            .first()
        )
        dev.active_instance_id = other.instance_id if other else None

    db.commit()


@router.post("/devices/{device_id}/set-active-instance", status_code=200)
async def set_device_active_instance(
    device_id: str,
    instance_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Set the active instance for a device."""
    # Verify device exists
    dev = db.query(Device).filter(Device.device_id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")

    # Verify instance is assigned to device
    mapping = (
        db.query(DeviceInstanceMap)
        .filter(
            DeviceInstanceMap.device_id == device_id,
            DeviceInstanceMap.instance_id == instance_id,
        )
        .first()
    )

    if not mapping:
        raise HTTPException(
            status_code=400,
            detail=f"Instance '{instance_id}' is not assigned to device '{device_id}'",
        )

    dev.active_instance_id = instance_id
    db.commit()

    return {"message": "Active instance updated"}


# ============================================================
# Device Authorization Management
# ============================================================


@router.get("/devices/pending")
async def list_pending_devices(
    db: Session = Depends(get_db),
) -> List[dict]:
    """
    List all devices pending authorization.

    Admin should review these devices and authorize or reject them.
    """
    devices = (
        db.query(Device)
        .filter(Device.auth_status == DeviceAuthStatus.PENDING.value)
        .order_by(Device.created_at.desc())
        .all()
    )

    return [
        {
            "device_id": dev.device_id,
            "hardware_id": dev.hardware_id,
            "firmware_version": dev.firmware_version,
            "display": {
                "width": dev.display_width,
                "height": dev.display_height,
                "bit_depth": dev.display_bit_depth,
                "partial_refresh": dev.display_partial_refresh,
            },
            "auth_status": dev.auth_status,
            "created_at": dev.created_at.isoformat() if dev.created_at else None,
        }
        for dev in devices
    ]


@router.post("/devices/{device_id}/authorize")
async def authorize_device(
    device_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """
    Authorize a pending device.

    Once authorized, the device can obtain tokens and use the API.
    """
    device = db.query(Device).filter(Device.device_id == device_id).first()

    if not device:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")

    if device.auth_status == DeviceAuthStatus.AUTHORIZED.value:
        return {
            "message": "Device already authorized",
            "auth_status": device.auth_status,
        }

    device.auth_status = DeviceAuthStatus.AUTHORIZED.value
    device.authorized_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "message": "Device authorized successfully",
        "device_id": device_id,
        "auth_status": device.auth_status,
    }


@router.post("/devices/{device_id}/reject")
async def reject_device(
    device_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """
    Reject a pending device.

    Rejected devices cannot obtain tokens.
    """
    device = db.query(Device).filter(Device.device_id == device_id).first()

    if not device:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")

    device.auth_status = DeviceAuthStatus.REJECTED.value
    db.commit()

    return {
        "message": "Device rejected",
        "device_id": device_id,
        "auth_status": device.auth_status,
    }


@router.post("/devices/{device_id}/revoke")
async def revoke_device(
    device_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """
    Revoke access for an authorized device.

    This invalidates the device's current refresh token.
    The device will need to be re-authorized by admin.
    """
    device = db.query(Device).filter(Device.device_id == device_id).first()

    if not device:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")

    device.auth_status = DeviceAuthStatus.REVOKED.value
    device.current_refresh_jti = None  # Invalidate refresh token
    db.commit()

    return {
        "message": "Device access revoked",
        "device_id": device_id,
        "auth_status": device.auth_status,
    }


@router.post("/devices/{device_id}/reauthorize")
async def reauthorize_device(
    device_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """
    Re-authorize a rejected or revoked device.
    """
    device = db.query(Device).filter(Device.device_id == device_id).first()

    if not device:
        raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")

    if device.auth_status == DeviceAuthStatus.AUTHORIZED.value:
        return {
            "message": "Device already authorized",
            "auth_status": device.auth_status,
        }

    device.auth_status = DeviceAuthStatus.AUTHORIZED.value
    device.authorized_at = datetime.now(timezone.utc)
    device.current_refresh_jti = None  # Force device to get new refresh token
    db.commit()

    return {
        "message": "Device re-authorized successfully",
        "device_id": device_id,
        "auth_status": device.auth_status,
    }


# ============================================================
# System Status
# ============================================================


@router.get("/status")
async def get_system_status(
    db: Session = Depends(get_db),
) -> dict:
    """Get overall system status and statistics."""
    device_count = db.query(Device).count()
    instance_count = db.query(Instance).count()
    hlss_type_count = (
        db.query(HLSSTypeModel).filter(HLSSTypeModel.is_active == True).count()
    )

    ready_instances = db.query(Instance).filter(Instance.hlss_ready == True).count()
    pending_instances = (
        db.query(Instance).filter(Instance.hlss_initialized == False).count()
    )
    config_needed = (
        db.query(Instance).filter(Instance.needs_configuration == True).count()
    )

    return {
        "status": "healthy",
        "statistics": {
            "devices": device_count,
            "instances": {
                "total": instance_count,
                "ready": ready_instances,
                "pending_initialization": pending_instances,
                "needs_configuration": config_needed,
            },
            "hlss_types": hlss_type_count,
        },
    }


# ============================================================
# Admin Web Interface
# ============================================================


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request) -> HTMLResponse:
    """
    Serve the admin dashboard web interface.

    Provides a comprehensive UI for managing HLSS types, instances, and devices.
    """
    base_url = get_llss_base_url(request)

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLSS Admin Dashboard</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            margin: 0;
            padding: 20px;
            color: #eee;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ text-align: center; color: #00d9ff; margin-bottom: 10px; font-size: 2rem; }}
        .subtitle {{ text-align: center; color: #888; margin-bottom: 30px; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: rgba(255,255,255,0.1);
            padding: 20px;
            border-radius: 12px;
            text-align: center;
        }}
        .stat-value {{ font-size: 2.5rem; font-weight: bold; color: #00d9ff; }}
        .stat-label {{ color: #aaa; margin-top: 5px; }}
        .tabs {{ display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }}
        .tab {{
            padding: 12px 24px;
            background: rgba(255,255,255,0.1);
            border: none;
            border-radius: 8px;
            color: #aaa;
            cursor: pointer;
            font-size: 1rem;
            transition: all 0.2s;
        }}
        .tab:hover {{ background: rgba(255,255,255,0.15); }}
        .tab.active {{ background: #00d9ff; color: #1a1a2e; font-weight: bold; }}
        .panel {{
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 20px;
            display: none;
        }}
        .panel.active {{ display: block; }}
        .panel-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .panel-title {{ font-size: 1.3rem; color: #fff; }}
        .btn {{
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: bold;
            transition: all 0.2s;
        }}
        .btn-primary {{ background: #00d9ff; color: #1a1a2e; }}
        .btn-primary:hover {{ background: #00c4e6; }}
        .btn-secondary {{ background: rgba(255,255,255,0.2); color: #fff; }}
        .btn-secondary:hover {{ background: rgba(255,255,255,0.3); }}
        .btn-danger {{ background: #ff4757; color: #fff; }}
        .btn-danger:hover {{ background: #ff3344; }}
        .btn-success {{ background: #2ed573; color: #1a1a2e; }}
        .btn-small {{ padding: 6px 12px; font-size: 0.8rem; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }}
        th {{ color: #888; font-weight: normal; font-size: 0.85rem; text-transform: uppercase; }}
        tr:hover {{ background: rgba(255,255,255,0.05); }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: bold;
        }}
        .badge-success {{ background: rgba(46, 213, 115, 0.2); color: #2ed573; }}
        .badge-warning {{ background: rgba(255, 165, 0, 0.2); color: #ffa500; }}
        .badge-danger {{ background: rgba(255, 71, 87, 0.2); color: #ff4757; }}
        .badge-info {{ background: rgba(0, 217, 255, 0.2); color: #00d9ff; }}
        .modal {{
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.7);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }}
        .modal.active {{ display: flex; }}
        .modal-content {{
            background: #1a1a2e;
            border-radius: 12px;
            padding: 30px;
            max-width: 500px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
        }}
        .modal-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }}
        .modal-title {{ font-size: 1.3rem; color: #fff; }}
        .modal-close {{ background: none; border: none; color: #888; font-size: 1.5rem; cursor: pointer; }}
        .form-group {{ margin-bottom: 15px; }}
        .form-group label {{ display: block; margin-bottom: 5px; color: #aaa; font-size: 0.9rem; }}
        .form-group input, .form-group select, .form-group textarea {{
            width: 100%;
            padding: 12px;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 8px;
            background: rgba(255,255,255,0.1);
            color: #fff;
            font-size: 1rem;
        }}
        .form-group select option {{
            background: #1a1a2e;
            color: #fff;
        }}
        .form-group input:focus, .form-group select:focus {{ outline: none; border-color: #00d9ff; }}
        .form-row {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }}
        .form-actions {{ display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }}
        .empty-state {{ text-align: center; padding: 40px; color: #888; }}
        .empty-state-icon {{ font-size: 3rem; margin-bottom: 10px; }}
        .actions {{ display: flex; gap: 5px; }}
        .toast {{
            position: fixed;
            bottom: 20px; right: 20px;
            padding: 15px 25px;
            background: #2ed573;
            color: #1a1a2e;
            border-radius: 8px;
            font-weight: bold;
            display: none;
            z-index: 2000;
        }}
        .toast.error {{ background: #ff4757; color: #fff; }}
        .toast.active {{ display: block; }}
        .config-url {{ word-break: break-all; font-size: 0.85rem; color: #00d9ff; }}
        .instance-token {{
            font-family: monospace;
            font-size: 0.8rem;
            background: rgba(0,0,0,0.3);
            padding: 4px 8px;
            border-radius: 4px;
            word-break: break-all;
        }}
        @media (max-width: 768px) {{
            .form-row {{ grid-template-columns: 1fr; }}
            table {{ font-size: 0.85rem; }}
            th, td {{ padding: 8px; }}
            .actions {{ flex-direction: column; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🖥️ LLSS Admin Dashboard</h1>
        <p class="subtitle">Low Level Screen Service Administration</p>
        <div class="stats-grid" id="statsGrid">
            <div class="stat-card"><div class="stat-value" id="statDevices">-</div><div class="stat-label">Devices</div></div>
            <div class="stat-card"><div class="stat-value" id="statInstances">-</div><div class="stat-label">Instances</div></div>
            <div class="stat-card"><div class="stat-value" id="statReady">-</div><div class="stat-label">Ready</div></div>
            <div class="stat-card"><div class="stat-value" id="statTypes">-</div><div class="stat-label">HLSS Types</div></div>
        </div>
        <div class="tabs">
            <button class="tab active" onclick="showPanel('hlss-types')">HLSS Types</button>
            <button class="tab" onclick="showPanel('instances')">Instances</button>
            <button class="tab" onclick="showPanel('devices')">Devices</button>
        </div>
        <div class="panel active" id="panel-hlss-types">
            <div class="panel-header">
                <div class="panel-title">HLSS Type Registry</div>
                <button class="btn btn-primary" onclick="showCreateTypeModal()">+ Add HLSS Type</button>
            </div>
            <div id="hlssTypesTable"></div>
        </div>
        <div class="panel" id="panel-instances">
            <div class="panel-header">
                <div class="panel-title">HLSS Instances</div>
                <button class="btn btn-primary" onclick="showCreateInstanceModal()">+ Create Instance</button>
            </div>
            <div id="instancesTable"></div>
        </div>
        <div class="panel" id="panel-devices">
            <div class="panel-header">
                <div class="panel-title">Registered Devices</div>
            </div>
            <div id="devicesTable"></div>
        </div>
    </div>
    <div class="modal" id="createTypeModal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title">Register HLSS Type</div>
                <button class="modal-close" onclick="closeModal('createTypeModal')">&times;</button>
            </div>
            <form id="createTypeForm">
                <div class="form-group"><label>Type ID *</label><input type="text" name="type_id" placeholder="e.g., lichess" required></div>
                <div class="form-group"><label>Name *</label><input type="text" name="name" placeholder="Human-readable name" required></div>
                <div class="form-group"><label>Base URL *</label><input type="url" name="base_url" placeholder="https://hlss.example/api" required></div>
                <div class="form-group"><label>Auth Token</label><input type="text" name="auth_token" placeholder="Optional"></div>
                <div class="form-group"><label>Description</label><textarea name="description" rows="2"></textarea></div>
                <div class="form-row">
                    <div class="form-group"><label>Width</label><input type="number" name="default_width" placeholder="800"></div>
                    <div class="form-group"><label>Height</label><input type="number" name="default_height" placeholder="480"></div>
                    <div class="form-group"><label>Bit Depth</label><input type="number" name="default_bit_depth" placeholder="4"></div>
                </div>
                <div class="form-actions">
                    <button type="button" class="btn btn-secondary" onclick="closeModal('createTypeModal')">Cancel</button>
                    <button type="submit" class="btn btn-primary">Create Type</button>
                </div>
            </form>
        </div>
    </div>
    <div class="modal" id="createInstanceModal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title">Create HLSS Instance</div>
                <button class="modal-close" onclick="closeModal('createInstanceModal')">&times;</button>
            </div>
            <form id="createInstanceForm">
                <div class="form-group"><label>Instance Name *</label><input type="text" name="name" placeholder="e.g., Living Room Chess" required></div>
                <div class="form-group"><label>HLSS Type *</label><select name="hlss_type_id" required><option value="">Select HLSS Type...</option></select></div>
                <div class="form-row">
                    <div class="form-group"><label>Width</label><input type="number" name="display_width" placeholder="Default"></div>
                    <div class="form-group"><label>Height</label><input type="number" name="display_height" placeholder="Default"></div>
                    <div class="form-group"><label>Bit Depth</label><input type="number" name="display_bit_depth" placeholder="Default"></div>
                </div>
                <div class="form-group"><label><input type="checkbox" name="auto_initialize" checked> Auto-initialize with HLSS backend</label></div>
                <div class="form-actions">
                    <button type="button" class="btn btn-secondary" onclick="closeModal('createInstanceModal')">Cancel</button>
                    <button type="submit" class="btn btn-primary">Create Instance</button>
                </div>
            </form>
        </div>
    </div>
    <div class="modal" id="assignInstanceModal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title">Assign Instance to Device</div>
                <button class="modal-close" onclick="closeModal('assignInstanceModal')">&times;</button>
            </div>
            <form id="assignInstanceForm">
                <input type="hidden" name="device_id" id="assignDeviceId">
                <div class="form-group"><label>Device</label><input type="text" id="assignDeviceName" disabled></div>
                <div class="form-group"><label>Instance *</label><select name="instance_id" required><option value="">Select Instance...</option></select></div>
                <div class="form-actions">
                    <button type="button" class="btn btn-secondary" onclick="closeModal('assignInstanceModal')">Cancel</button>
                    <button type="submit" class="btn btn-primary">Assign Instance</button>
                </div>
            </form>
        </div>
    </div>
    <div class="toast" id="toast"></div>
    <script>
        const BASE_URL = '{base_url}';
        let hlssTypes = [], instances = [], devices = [];

        document.addEventListener('DOMContentLoaded', () => {{
            loadStats(); loadHLSSTypes(); loadInstances(); loadDevices();
            document.getElementById('createTypeForm').addEventListener('submit', handleCreateType);
            document.getElementById('createInstanceForm').addEventListener('submit', handleCreateInstance);
            document.getElementById('assignInstanceForm').addEventListener('submit', handleAssignInstance);
        }});

        async function apiCall(endpoint, method = 'GET', body = null) {{
            const options = {{ method, headers: {{'Content-Type': 'application/json'}} }};
            if (body) options.body = JSON.stringify(body);
            const response = await fetch(BASE_URL + endpoint, options);
            if (!response.ok) {{
                const error = await response.json().catch(() => ({{detail: 'Unknown error'}}));
                throw new Error(error.detail || 'Request failed');
            }}
            if (response.status === 204) return null;
            return response.json();
        }}

        function showPanel(panelId) {{
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
            document.querySelector(`[onclick="showPanel('${{panelId}}')"]`).classList.add('active');
            document.getElementById(`panel-${{panelId}}`).classList.add('active');
        }}

        function showModal(id) {{ document.getElementById(id).classList.add('active'); }}
        function closeModal(id) {{ document.getElementById(id).classList.remove('active'); }}
        function showToast(msg, isError = false) {{
            const t = document.getElementById('toast');
            t.textContent = msg;
            t.className = 'toast active' + (isError ? ' error' : '');
            setTimeout(() => t.classList.remove('active'), 3000);
        }}

        async function loadStats() {{
            try {{
                const s = await apiCall('/admin/status');
                document.getElementById('statDevices').textContent = s.statistics.devices;
                document.getElementById('statInstances').textContent = s.statistics.instances.total;
                document.getElementById('statReady').textContent = s.statistics.instances.ready;
                document.getElementById('statTypes').textContent = s.statistics.hlss_types;
            }} catch (e) {{ console.error(e); }}
        }}

        async function loadHLSSTypes() {{
            try {{ hlssTypes = await apiCall('/admin/hlss-types'); renderHLSSTypes(); updateTypeSelects(); }} catch (e) {{ console.error(e); }}
        }}

        async function loadInstances() {{
            try {{ instances = await apiCall('/admin/instances'); renderInstances(); updateInstanceSelects(); }} catch (e) {{ console.error(e); }}
        }}

        async function loadDevices() {{
            try {{ devices = await apiCall('/admin/devices'); renderDevices(); }} catch (e) {{ console.error(e); }}
        }}

        function renderHLSSTypes() {{
            const c = document.getElementById('hlssTypesTable');
            if (!hlssTypes.length) {{ c.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📡</div><div>No HLSS types registered</div></div>'; return; }}
            c.innerHTML = `<table><thead><tr><th>Type ID</th><th>Name</th><th>Base URL</th><th>Defaults</th><th>Status</th><th>Actions</th></tr></thead><tbody>${{hlssTypes.map(t => `<tr><td><strong>${{t.type_id}}</strong></td><td>${{t.name}}</td><td style="font-size:0.85rem;color:#888">${{t.base_url}}</td><td>${{t.default_width||'-'}}x${{t.default_height||'-'}} @${{t.default_bit_depth||'-'}}bpp</td><td>${{t.is_active?'<span class="badge badge-success">Active</span>':'<span class="badge badge-danger">Inactive</span>'}}</td><td class="actions"><button class="btn btn-danger btn-small" onclick="deleteType('${{t.type_id}}')">🗑️</button></td></tr>`).join('')}}</tbody></table>`;
        }}

        function renderInstances() {{
            const c = document.getElementById('instancesTable');
            if (!instances.length) {{ c.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📱</div><div>No instances created</div></div>'; return; }}
            c.innerHTML = `<table><thead><tr><th>Name</th><th>Type</th><th>Status</th><th>Display</th><th>Token</th><th>Actions</th></tr></thead><tbody>${{instances.map(i => `<tr><td><strong>${{i.name}}</strong><div style="font-size:0.8rem;color:#666">${{i.instance_id}}</div></td><td>${{i.type}}</td><td>${{getStatusBadge(i)}}${{i.configuration_url?`<div class="config-url"><a href="${{i.configuration_url}}" target="_blank">Configure →</a></div>`:''}}</td><td>${{i.display?`${{i.display.width}}x${{i.display.height}}`:'-'}}</td><td><span class="instance-token" onclick="copyToken('${{i.access_token}}')" style="cursor:pointer">${{i.access_token?i.access_token.substring(0,16)+'...':'-'}}</span></td><td class="actions">${{!i.hlss_initialized?`<button class="btn btn-success btn-small" onclick="initInstance('${{i.instance_id}}')">⚡</button>`:''}}<button class="btn btn-secondary btn-small" onclick="refreshStatus('${{i.instance_id}}')">🔄</button><button class="btn btn-danger btn-small" onclick="deleteInstance('${{i.instance_id}}')">🗑️</button></td></tr>`).join('')}}</tbody></table>`;
        }}

        function getStatusBadge(i) {{
            if (!i.hlss_initialized) return '<span class="badge badge-warning">Pending</span>';
            if (i.needs_configuration) return '<span class="badge badge-info">Needs Config</span>';
            if (i.hlss_ready) return '<span class="badge badge-success">Ready</span>';
            return '<span class="badge badge-warning">Initializing</span>';
        }}

        function renderDevices() {{
            const c = document.getElementById('devicesTable');
            if (!devices.length) {{ c.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🖥️</div><div>No devices registered</div></div>'; return; }}
            c.innerHTML = `<table><thead><tr><th>Device</th><th>Display</th><th>Active Instance</th><th>Assigned</th><th>Last Seen</th><th>Actions</th></tr></thead><tbody>${{devices.map(d => `<tr><td><strong>${{d.hardware_id}}</strong><div style="font-size:0.8rem;color:#666">${{d.device_id}}</div></td><td>${{d.display.width}}x${{d.display.height}} @${{d.display.bit_depth}}bpp</td><td>${{d.active_instance_id?`<span class="badge badge-success">${{getInstName(d.active_instance_id)}}</span>`:'<span class="badge badge-warning">None</span>'}}</td><td>${{d.assigned_instances.length}}</td><td style="font-size:0.85rem;color:#888">${{d.last_seen_at?new Date(d.last_seen_at).toLocaleString():'Never'}}</td><td class="actions"><button class="btn btn-primary btn-small" onclick="showAssignModal('${{d.device_id}}','${{d.hardware_id}}')">+</button></td></tr>`).join('')}}</tbody></table>`;
        }}

        function getInstName(id) {{ const i = instances.find(x => x.instance_id === id); return i ? i.name : id; }}
        function updateTypeSelects() {{ document.querySelector('#createInstanceForm select[name="hlss_type_id"]').innerHTML = '<option value="">Select HLSS Type...</option>' + hlssTypes.filter(t=>t.is_active).map(t=>`<option value="${{t.type_id}}">${{t.name}}</option>`).join(''); }}
        function updateInstanceSelects() {{ document.querySelector('#assignInstanceForm select[name="instance_id"]').innerHTML = '<option value="">Select Instance...</option>' + instances.filter(i=>i.hlss_initialized).map(i=>`<option value="${{i.instance_id}}">${{i.name}}${{i.hlss_ready?'':' (configuring)'}}</option>`).join(''); }}

        function showCreateTypeModal() {{ document.getElementById('createTypeForm').reset(); showModal('createTypeModal'); }}
        function showCreateInstanceModal() {{ document.getElementById('createInstanceForm').reset(); document.querySelector('#createInstanceForm input[name="auto_initialize"]').checked = true; updateTypeSelects(); showModal('createInstanceModal'); }}
        function showAssignModal(devId, devName) {{ document.getElementById('assignDeviceId').value = devId; document.getElementById('assignDeviceName').value = devName; updateInstanceSelects(); showModal('assignInstanceModal'); }}

        async function handleCreateType(e) {{
            e.preventDefault();
            const f = e.target;
            try {{
                await apiCall('/admin/hlss-types', 'POST', {{
                    type_id: f.type_id.value, name: f.name.value, base_url: f.base_url.value,
                    auth_token: f.auth_token.value || null, description: f.description.value || null,
                    default_width: f.default_width.value ? parseInt(f.default_width.value) : null,
                    default_height: f.default_height.value ? parseInt(f.default_height.value) : null,
                    default_bit_depth: f.default_bit_depth.value ? parseInt(f.default_bit_depth.value) : null,
                }});
                closeModal('createTypeModal'); showToast('HLSS type created'); loadHLSSTypes(); loadStats();
            }} catch (e) {{ showToast(e.message, true); }}
        }}

        async function handleCreateInstance(e) {{
            e.preventDefault();
            const f = e.target;
            try {{
                await apiCall('/admin/instances', 'POST', {{
                    name: f.name.value, hlss_type_id: f.hlss_type_id.value,
                    display_width: f.display_width.value ? parseInt(f.display_width.value) : null,
                    display_height: f.display_height.value ? parseInt(f.display_height.value) : null,
                    display_bit_depth: f.display_bit_depth.value ? parseInt(f.display_bit_depth.value) : null,
                    auto_initialize: f.auto_initialize.checked,
                }});
                closeModal('createInstanceModal'); showToast('Instance created'); loadInstances(); loadStats();
            }} catch (e) {{ showToast(e.message, true); }}
        }}

        async function handleAssignInstance(e) {{
            e.preventDefault();
            const f = e.target;
            const devId = f.device_id.value;
            try {{
                await apiCall(`/admin/devices/${{devId}}/assign-instance`, 'POST', {{ device_id: devId, instance_id: f.instance_id.value }});
                closeModal('assignInstanceModal'); showToast('Instance assigned'); loadDevices();
            }} catch (e) {{ showToast(e.message, true); }}
        }}

        async function deleteType(id) {{ if (!confirm(`Delete HLSS type "${{id}}"?`)) return; try {{ await apiCall(`/admin/hlss-types/${{id}}`, 'DELETE'); showToast('Deleted'); loadHLSSTypes(); loadStats(); }} catch (e) {{ showToast(e.message, true); }} }}
        async function deleteInstance(id) {{ if (!confirm('Delete this instance?')) return; try {{ await apiCall(`/admin/instances/${{id}}`, 'DELETE'); showToast('Deleted'); loadInstances(); loadStats(); }} catch (e) {{ showToast(e.message, true); }} }}
        async function initInstance(id) {{ try {{ await apiCall(`/admin/instances/${{id}}/initialize`, 'POST'); showToast('Initialized'); loadInstances(); loadStats(); }} catch (e) {{ showToast(e.message, true); }} }}
        async function refreshStatus(id) {{ try {{ await apiCall(`/admin/instances/${{id}}/refresh-status`, 'POST'); showToast('Refreshed'); loadInstances(); }} catch (e) {{ showToast(e.message, true); }} }}
        function copyToken(t) {{ if (!t) return; navigator.clipboard.writeText(t).then(() => showToast('Token copied')).catch(() => showToast('Copy failed', true)); }}
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)
