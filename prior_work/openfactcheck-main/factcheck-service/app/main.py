import asyncio
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pythonjsonlogger import jsonlogger

from .api import router as api_router
from .cache import get_redis, set_memory_fallback
from .metrics import REQUESTS_FAILED_TOTAL, REQUESTS_TOTAL, REQUEST_LATENCY_SECONDS
from .ofc_engine import init_engine
from .settings import settings


def _configure_logging() -> None:
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s"
    )
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.LOG_LEVEL)


_configure_logging()
logger = logging.getLogger(__name__)


app = FastAPI(
    title=settings.SERVICE_NAME,
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid4().hex
    request.state.request_id = request_id
    start = time.time()
    try:
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        request.state.status_code = response.status_code
        return response
    except Exception as exc:
        REQUESTS_FAILED_TOTAL.labels(
            endpoint=request.url.path, method=request.method, reason=type(exc).__name__
        ).inc()
        logger.exception(
            "Unhandled error",
            extra={"request_id": request_id, "path": request.url.path},
        )
        raise
    finally:
        duration = time.time() - start
        REQUESTS_TOTAL.labels(endpoint=request.url.path, method=request.method).inc()
        REQUEST_LATENCY_SECONDS.labels(
            endpoint=request.url.path, method=request.method
        ).observe(duration)
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round(duration * 1000, 2),
                "status_code": getattr(request.state, "status_code", None),
            },
        )


@app.on_event("startup")
async def on_startup() -> None:
    init_engine()
    redis = get_redis()
    redis_available = False
    for _ in range(5):
        try:
            await redis.ping()
            redis_available = True
            break
        except Exception:
            await asyncio.sleep(1)
    
    if not redis_available:
        try:
            await redis.ping()
            redis_available = True
        except Exception:
            logger.warning(
                "Redis unavailable; switching to memory cache",
                extra={"service": settings.SERVICE_NAME},
            )
            set_memory_fallback()
    
    logger.info("Service ready", extra={"service": settings.SERVICE_NAME})


@app.get("/healthz")
async def healthz() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/")
async def root() -> dict:
    """Root endpoint for platform health checks."""
    return {"status": "ok", "service": settings.SERVICE_NAME}


app.include_router(api_router)
