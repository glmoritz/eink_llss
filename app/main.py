"""
LLSS - Low Level Screen Service

The Low Level Screen Service (LLSS) brokers communication between
e-Ink display devices and High Level Screen Service (HLSS) instances.
It manages authentication, frame storage, diffing, and device orchestration.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI

from database import init_db
from routers import (
    admin_router,
    debug_router,
    device_auth_router,
    devices_router,
    instances_router,
)

# Load environment variables
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup: Initialize database tables
    init_db()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="Low Level Screen Service (LLSS) API",
    version="0.1.0",
    description="""
The Low Level Screen Service (LLSS) brokers communication between
e-Ink display devices and High Level Screen Service (HLSS) instances.
It manages authentication, frame storage, diffing, and device orchestration.
    """,
    servers=[{"url": "https://eink.tutu.eng.br/api"}],
    lifespan=lifespan,
)

# All public API routes live under /api so the URL surface matches the
# OpenAPI `servers` declaration above and the client's CONFIG_LLSS_SERVER_URL.
# Wrap every existing router so individual prefixes (/auth, /devices, ...)
# stay intact and become /api/auth, /api/devices, etc.
api_router = APIRouter(prefix="/api")
api_router.include_router(admin_router)
api_router.include_router(debug_router)
api_router.include_router(device_auth_router)
api_router.include_router(devices_router)
api_router.include_router(instances_router)
app.include_router(api_router)


# /health stays at the root so reverse-proxy / load-balancer probes don't
# need to know about the /api prefix.
@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "true").lower() == "true"

    uvicorn.run("main:app", host=host, port=port, reload=debug)
