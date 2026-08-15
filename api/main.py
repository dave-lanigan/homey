from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from api import chat
from api.db import init_db

UI_DIST = Path(__file__).resolve().parent.parent / "ui" / ".output" / "public"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Homey API",
    description="AI assistant for Airbnb listings",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/{path:path}")
async def serve_frontend(path: str):
    file = (UI_DIST / path).resolve()
    if not file.is_relative_to(UI_DIST.resolve()) or not file.is_file():
        file = UI_DIST / "index.html"

    # Hashed build assets can be cached forever; the HTML shell must always
    # be revalidated so new builds are picked up on reload.
    rel = file.relative_to(UI_DIST.resolve())
    if rel.parts and rel.parts[0] in ("_nuxt", "_fonts"):
        cache_control = "public, max-age=31536000, immutable"
    else:
        cache_control = "no-cache"

    return FileResponse(file, headers={"Cache-Control": cache_control})
