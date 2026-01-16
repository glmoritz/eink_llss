"""
LLSS - Low Level Screen Service
Pydantic models derived from OpenAPI schemas
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# Enums
class ButtonType(str, Enum):
    BTN_1 = "BTN_1"
    BTN_2 = "BTN_2"
    BTN_3 = "BTN_3"
    BTN_4 = "BTN_4"
    BTN_5 = "BTN_5"
    BTN_6 = "BTN_6"
    BTN_7 = "BTN_7"
    BTN_8 = "BTN_8"
    ENTER = "ENTER"
    ESC = "ESC"
    HL_LEFT = "HL_LEFT"
    HL_RIGHT = "HL_RIGHT"


class EventType(str, Enum):
    PRESS = "PRESS"
    LONG_PRESS = "LONG_PRESS"
    RELEASE = "RELEASE"


class DeviceAction(str, Enum):
    NOOP = "NOOP"
    FETCH_FRAME = "FETCH_FRAME"
    SLEEP = "SLEEP"


class InstanceStatus(str, Enum):
    """Status of an HLSS instance."""

    PENDING = "pending"  # Created but not initialized
    INITIALIZING = "initializing"  # Initialization in progress
    NEEDS_CONFIG = "needs_config"  # Waiting for user configuration
    READY = "ready"  # Fully operational
    ERROR = "error"  # Initialization failed


# Display Capabilities
class DisplayCapabilities(BaseModel):
    width: int
    height: int
    bit_depth: int
    partial_refresh: bool = False


# Device Models
class DeviceRegistration(BaseModel):
    hardware_id: str
    firmware_version: str
    display: DisplayCapabilities


class DeviceRegistrationResponse(BaseModel):
    device_id: str
    device_secret: str
    access_token: str


class DeviceStateResponse(BaseModel):
    action: DeviceAction
    frame_id: Optional[str] = None
    active_instance_id: Optional[str] = None
    poll_after_ms: Optional[int] = Field(
        default=None, description="Hint for next poll interval"
    )


# Input Models
class InputEvent(BaseModel):
    button: ButtonType
    event_type: EventType
    timestamp: datetime


# Instance Models
class InstanceCreate(BaseModel):
    name: str
    type: str = Field(description="Instance type (e.g. chess, homeassistant)")


class Instance(BaseModel):
    instance_id: str
    name: str
    type: str
    access_token: Optional[str] = None
    created_at: datetime


# Frame Models
class FrameCreateResponse(BaseModel):
    frame_id: str
    hash: str
    created_at: datetime


class FrameSyncResult(BaseModel):
    """Result of frame synchronization check."""

    instance_id: str
    instance_name: str
    hlss_has_frame: bool
    hlss_frame_hash: Optional[str] = None
    llss_has_frame: bool
    llss_frame_hash: Optional[str] = None
    in_sync: bool
    action_taken: Optional[str] = None
    error: Optional[str] = None


# ============================================================
# Admin API Models
# ============================================================


# HLSS Type Models
class HLSSTypeCreate(BaseModel):
    """Request to register a new HLSS type."""

    type_id: str = Field(
        description="Unique identifier (e.g., 'lichess', 'homeassistant')"
    )
    name: str = Field(description="Human-readable name")
    description: Optional[str] = Field(
        default=None, description="Description of this HLSS type"
    )
    base_url: str = Field(
        description="Base URL of the HLSS backend (e.g., https://lichess-hlss.example/api)"
    )
    auth_token: Optional[str] = Field(
        default=None, description="Token for LLSS to authenticate with HLSS"
    )
    default_width: Optional[int] = Field(
        default=None, description="Default display width"
    )
    default_height: Optional[int] = Field(
        default=None, description="Default display height"
    )
    default_bit_depth: Optional[int] = Field(
        default=None, description="Default bit depth"
    )


class HLSSTypeUpdate(BaseModel):
    """Request to update an HLSS type."""

    name: Optional[str] = None
    description: Optional[str] = None
    base_url: Optional[str] = None
    auth_token: Optional[str] = None
    default_width: Optional[int] = None
    default_height: Optional[int] = None
    default_bit_depth: Optional[int] = None
    is_active: Optional[bool] = None


class HLSSType(BaseModel):
    """HLSS type registry entry."""

    type_id: str
    name: str
    description: Optional[str] = None
    base_url: str
    default_width: Optional[int] = None
    default_height: Optional[int] = None
    default_bit_depth: Optional[int] = None
    is_active: bool = True
    created_at: Optional[datetime] = None


# Admin Instance Models
class AdminInstanceCreate(BaseModel):
    """Request to create and initialize a new HLSS instance."""

    name: str = Field(description="Instance name")
    hlss_type_id: str = Field(description="HLSS type to use")
    display_width: Optional[int] = Field(
        default=None, description="Override display width"
    )
    display_height: Optional[int] = Field(
        default=None, description="Override display height"
    )
    display_bit_depth: Optional[int] = Field(
        default=None, description="Override bit depth"
    )
    auto_initialize: bool = Field(
        default=True, description="Automatically initialize with HLSS backend"
    )


class AdminInstanceUpdate(BaseModel):
    """Request to update an instance."""

    name: Optional[str] = None
    display_width: Optional[int] = None
    display_height: Optional[int] = None
    display_bit_depth: Optional[int] = None


class AdminInstance(BaseModel):
    """Admin view of an HLSS instance."""

    instance_id: str
    name: str
    type: str
    hlss_type_id: Optional[str] = None
    access_token: Optional[str] = None
    hlss_initialized: bool = False
    hlss_ready: bool = False
    needs_configuration: bool = False
    configuration_url: Optional[str] = None
    display: Optional[DisplayCapabilities] = None
    created_at: Optional[datetime] = None
    initialized_at: Optional[datetime] = None


# Device Assignment Models
class DeviceInstanceAssignment(BaseModel):
    """Request to assign an instance to a device."""

    device_id: str
    instance_id: str
    position: Optional[int] = Field(
        default=None, description="Position in device's instance list"
    )


class DeviceWithInstances(BaseModel):
    """Device with its assigned instances."""

    device_id: str
    hardware_id: str
    firmware_version: str
    auth_status: str = "pending"
    display: DisplayCapabilities
    active_instance_id: Optional[str] = None
    assigned_instances: List[str] = Field(default_factory=list)
    last_seen_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


# HLSS Initialization Models (for server-to-server communication)
class HLSSCallbacks(BaseModel):
    """Callback URLs provided to HLSS during initialization."""

    frames: str = Field(description="URL for HLSS to submit frames")
    inputs: str = Field(
        description="URL for HLSS to receive inputs (not used directly)"
    )
    notify: str = Field(description="URL for HLSS to notify state changes")


class HLSSInitRequest(BaseModel):
    """Request sent to HLSS to initialize an instance."""

    instance_id: str
    callbacks: HLSSCallbacks
    display: DisplayCapabilities


class HLSSInitResponse(BaseModel):
    """Response from HLSS after initialization."""

    status: str = Field(description="Must be 'initialized'")
    needs_configuration: bool = False
    configuration_url: Optional[str] = None


class HLSSStatusResponse(BaseModel):
    """Response from HLSS status endpoint."""

    instance_id: str
    ready: bool
    needs_configuration: bool = False
    configuration_url: Optional[str] = None
    active_screen: Optional[str] = None


class HLSSFrameMetadata(BaseModel):
    """Response from HLSS frame metadata endpoint."""

    instance_id: str
    has_frame: bool
    frame_id: Optional[str] = None
    frame_hash: Optional[str] = None
    screen_type: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: Optional[datetime] = None


class HLSSFrameSendResponse(BaseModel):
    """Response from HLSS frame send endpoint."""

    status: str = Field(description="'sent', 'no_frame', or 'scheduled'")
    frame_id: Optional[str] = None
