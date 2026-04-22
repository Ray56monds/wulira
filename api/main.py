"""
Wulira API — MVC Controller
"""

import os
import sys
import time
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Any
from collections import defaultdict
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.storage import create_store
from api.auth import APIKeyManager, is_public_path
from api.routes.jobs import create_router

load_dotenv()


class Settings(BaseSettings):
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    env: str = "development"
    cors_origins: str = "*"
    job_timeout_seconds: int = 3600
    job_cleanup_interval_seconds: int = 300
    max_video_duration_seconds: int = 7200
    log_level: str = "INFO"
    redis_url: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
logging.basicConfig(level=getattr(logging, settings.log_level), format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("wulira-api")

store = create_store(settings.redis_url or None)
auth_mgr = APIKeyManager()

# Rate limiter
rate_limits: dict[str, list[float]] = defaultdict(list)

# WebSocket manager
class WSManager:
    def __init__(self):
        self.conns: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, ws: WebSocket, job_id: str):
        await ws.accept()
        self.conns[job_id].append(ws)

    def disconnect(self, ws: WebSocket, job_id: str):
        self.conns[job_id] = [c for c in self.conns[job_id] if c is not ws]

    async def broadcast(self, job_id: str, data: dict):
        for ws in self.conns.get(job_id, []):
            try:
                await ws.send_json(data)
            except Exception:
                pass

ws_mgr = WSManager()


async def notify_progress(job_id: str, stage: str, pct: int = 0):
    await ws_mgr.broadcast(job_id, {"stage": stage, "progress": pct, "job_id": job_id})


async def cleanup_loop():
    while True:
        try:
            await asyncio.sleep(settings.job_cleanup_interval_seconds)
            removed = store.cleanup_expired(settings.job_timeout_seconds)
            if removed:
                logger.info(f"Cleaned {removed} expired jobs")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Wulira API v2.0 (MVC)")
    task = asyncio.create_task(cleanup_loop())
    yield
    task.cancel()


app = FastAPI(title="Wulira API", version="2.0.0", description="Hear every word, in every language.", docs_url="/api/docs", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def middleware(request: Request, call_next):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    rate_limits[ip] = [t for t in rate_limits[ip] if now - t < 60]
    if len(rate_limits[ip]) >= 30:
        return JSONResponse(429, {"detail": "Rate limit exceeded"}, headers={"Retry-After": "60"})
    rate_limits[ip].append(now)

    if auth_mgr.enabled and not is_public_path(request.url.path):
        key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if not key or not auth_mgr.validate(key):
            return JSONResponse(401, {"detail": "Invalid API key"})

    return await call_next(request)


# Mount MVC routes
app.include_router(create_router(store, notify_progress, settings.max_video_duration_seconds))


# WebSocket
@app.websocket("/ws/job/{job_id}")
async def ws_progress(ws: WebSocket, job_id: str):
    await ws_mgr.connect(ws, job_id)
    try:
        job = store.get(job_id)
        if job:
            await ws.send_json({"stage": job.get("status", "unknown"), "job_id": job_id})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_mgr.disconnect(ws, job_id)


# Dashboard
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        with open(os.path.join(static_dir, "index.html"), "r", encoding="utf-8") as f:
            return f.read()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host=settings.api_host, port=settings.api_port, reload=True)
