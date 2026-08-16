import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import health, projects, upload
from app.core.access import AccessKeyMiddleware
from app.core.config import CLIPS_DIR, THUMBNAILS_DIR, UPLOADS_DIR, settings
from app.core.database import Base, engine, ensure_schema
from app.core.logging import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    ensure_schema()
    logger.info("RECAST API started. OpenAI configured: %s", settings.openai_configured)
    yield


app = FastAPI(title="RECAST API", version="0.1.0", lifespan=lifespan)

# Order matters: this is added first, so it runs *inside* CORS. A rejected
# request still gets CORS headers and the browser can read the 401 rather than
# reporting an opaque network failure.
if settings.access_key:
    app.add_middleware(AccessKeyMiddleware, access_key=settings.access_key)
    logger.info("Access key required: API is gated.")
else:
    logger.warning(
        "ACCESS_KEY is not set: the API is open to anyone who can reach it. "
        "Set it in backend/.env before exposing this instance publicly."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(upload.router, prefix="/api")

app.mount("/media/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
app.mount("/media/clips", StaticFiles(directory=CLIPS_DIR), name="clips")
app.mount("/media/thumbnails", StaticFiles(directory=THUMBNAILS_DIR), name="thumbnails")
