import time
import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from rmd.api import health
from rmd.config import get_settings
from rmd.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level, json_output=settings.is_production)
log = get_logger("rmd.api")

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="RMD LLM V2 API",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id, path=request.url.path, method=request.method
    )
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("unhandled_error")
        return JSONResponse(
            {"detail": "Internal server error", "request_id": request_id}, status_code=500
        )
    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    response.headers["x-request-id"] = request_id
    if request.url.path not in ("/health", "/ready"):
        log.info("request", status=response.status_code, elapsed_ms=elapsed_ms)
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    return JSONResponse({"detail": "Invalid request", "errors": exc.errors()}, status_code=422)


app.include_router(health.router)
