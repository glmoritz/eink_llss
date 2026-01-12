"""
Routers Package
"""

from app.routers.debug import router as debug_router
from app.routers.devices import router as devices_router
from app.routers.instances import router as instances_router

__all__ = ["debug_router", "devices_router", "instances_router"]
