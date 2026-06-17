import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as api_router
from app.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="Cortex Knowledge OS",
    description="Multi-tenant corporate corporate Knowledge OS API",
    version="1.0.0"
)

# Enable CORS for the Next.js admin UI frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount endpoints
app.include_router(api_router, prefix="/v1")

# Prometheus Metrics instrumentation
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
from app.api.routes import QUERIES_COUNTER, LATENCY_HISTOGRAM

@app.get("/metrics")
def get_metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/")
def read_root():
    return {
        "status": "healthy",
        "service": "Cortex Knowledge OS Backend",
        "version": "1.0.0"
    }

@app.on_event("startup")
def startup_event():
    logger.info("backend_startup", msg="Cortex server starting up...")

@app.on_event("shutdown")
def shutdown_event():
    from app.database.connection import close_all_connections
    close_all_connections()
    logger.info("backend_shutdown", msg="Cortex server shutting down...")
