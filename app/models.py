"""
LLSS - Low Level Screen Service
Pydantic models derived from OpenAPI schemas
"""

from datetime import datetime
from enum import Enum
from typing import Optional

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
    created_at: datetime


# Frame Models
class FrameCreateResponse(BaseModel):
    frame_id: str
    hash: str
    created_at: datetime
