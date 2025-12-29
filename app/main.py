from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import time
from app.api.routes import router
from app.utils.logging import setup_logging, get_logger
from app.cost.database import init_db

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="LLM Cost & Reliability Governance Gateway",
    description="Production-grade gateway for LLM provider access with cost tracking, routing, and observability",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests."""
    start_time = time.time()
    logger.info(
        f"Request: {request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else None,
        },
    )
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(
        f"Response: {request.method} {request.url.path} - {response.status_code}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "process_time": process_time,
        },
    )
    return response


# Register routes
app.include_router(router)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "LLM Cost & Reliability Governance Gateway",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
    }

