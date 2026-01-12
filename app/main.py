"""
LLSS - Low Level Screen Service

The Low Level Screen Service (LLSS) brokers communication between
e-Ink display devices and High Level Screen Service (HLSS) instances.
It manages authentication, frame storage, diffing, and device orchestration.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

# Load environment variables
load_dotenv()

from app.database import init_db
from app.routers import debug_router, devices_router, instances_router


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

# Include routers
app.include_router(debug_router)
app.include_router(devices_router)
app.include_router(instances_router)


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "true").lower() == "true"

    uvicorn.run("app.main:app", host=host, port=port, reload=debug)
