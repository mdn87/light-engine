"""HTTP interface. Bind localhost until an authenticated reverse proxy exists."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .config import build_engine
from .engine import LightingEngine
from .models import EFFECT_NAMES, StartRequest

WEB_FILE = Path(__file__).resolve().parent.parent / "web" / "index.html"


def make_app(engine: LightingEngine | None = None) -> FastAPI:
    engine = engine or build_engine()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(engine.run())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            close = getattr(engine.transport, "close", None)
            if close:
                close()

    app = FastAPI(title="Light Engine", version="0.1.0", lifespan=lifespan)

    @app.get("/")
    def home():
        return FileResponse(WEB_FILE)

    @app.get("/health")
    def health():
        return {"ok": True, "devices": len(engine.devices)}

    @app.get("/api/effects")
    def effects():
        return {"effects": list(EFFECT_NAMES)}

    @app.get("/api/devices")
    def devices():
        return [
            {"id": device.id, "name": device.name, "sku": device.sku, "ip": device.ip}
            for device in engine.devices.values()
        ]

    @app.get("/api/playback")
    def playback():
        return engine.status()

    @app.post("/api/playback/start")
    async def start(config: StartRequest):
        try:
            return await engine.start(config)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/playback/stop")
    async def stop():
        return await engine.stop()

    return app


app = make_app()
