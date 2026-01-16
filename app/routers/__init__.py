"""
Routers Package
"""

from routers.admin import router as admin_router
from routers.debug import router as debug_router
from routers.device_auth import router as device_auth_router
from routers.devices import router as devices_router
from routers.instances import router as instances_router

__all__ = [
    "admin_router",
    "debug_router",
    "device_auth_router",
    "devices_router",
    "instances_router",
]
