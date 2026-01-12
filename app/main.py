"""
LLSS - Low Level Screen Service

The Low Level Screen Service (LLSS) brokers communication between
e-Ink display devices and High Level Screen Service (HLSS) instances.
It manages authentication, frame storage, diffing, and device orchestration.
"""

from fastapi import FastAPI

from app.routers import debug_router, devices_router, instances_router

app = FastAPI(
    title="Low Level Screen Service (LLSS) API",
    version="0.1.0",
    description="""
The Low Level Screen Service (LLSS) brokers communication between
e-Ink display devices and High Level Screen Service (HLSS) instances.
It manages authentication, frame storage, diffing, and device orchestration.
    """,
    servers=[{"url": "https://eink.tutu.eng.br/api"}],
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

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
