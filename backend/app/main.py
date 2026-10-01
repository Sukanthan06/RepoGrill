"""FastAPI application: wiring, CORS, error handling and routes."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.errors import AppError
from app.routes import dossier, ingest, session, transcribe
from app.services import Services
from app.store import run_periodic_cleanup

settings = get_settings()
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("repogrill")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    services = Services.create(settings)
    app.state.services = services
    cleanup = asyncio.create_task(run_periodic_cleanup(services.stores))
    yield
    cleanup.cancel()
    await services.aclose()


app = FastAPI(title="RepoGrill API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    if exc.status_code >= 500:
        logger.error("%s: %s", exc.code, exc.message)
    headers = {}
    body: dict[str, object] = {"error": exc.code, "detail": exc.message}
    if exc.retry_after is not None:
        headers["Retry-After"] = str(int(exc.retry_after) + 1)
        body["retry_after"] = exc.retry_after
    return JSONResponse(status_code=exc.status_code, content=body, headers=headers)


app.include_router(ingest.router)
app.include_router(dossier.router)
app.include_router(session.router)
app.include_router(transcribe.router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
