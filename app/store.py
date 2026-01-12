"""
In-memory storage for development and testing.

In production, this would be replaced with a proper database.
"""

from typing import Any, Dict

# Device storage: device_id -> device data
# Each device entry contains:
# - device_id: str
# - device_secret: str
# - access_token: str
# - hardware_id: str
# - firmware_version: str
# - display: dict (width, height, bit_depth, partial_refresh)
# - current_frame_id: optional str
# - active_instance_id: optional str
device_store: Dict[str, Dict[str, Any]] = {}

# Frame storage: frame_id -> frame binary data (PNG)
frame_store: Dict[str, bytes] = {}

# Instance storage: instance_id -> instance data
instance_store: Dict[str, Dict[str, Any]] = {}

# Device-Instance mapping: device_id -> instance_id
device_instance_map: Dict[str, str] = {}
