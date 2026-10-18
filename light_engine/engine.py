"""Single-writer animation scheduler with bounded per-device sends."""
import asyncio
import time

from .effects import render
from .models import Device, Frame, StartRequest
from .transports import Transport


class LightingEngine:
    def __init__(self, devices: list[Device], transport: Transport, max_hz: float = 3.0) -> None:
        if max_hz <= 0:
            raise ValueError("max_hz must be positive")
        self.devices = {device.id: device for device in devices}
        self.transport = transport
        self.max_hz = max_hz
        self.playback: StartRequest | None = None
        self.started_at = 0.0
        self._last_sent_at: dict[str, float] = {}
        self._last_frames: dict[str, Frame] = {}
        self._lock = asyncio.Lock()
        self.last_error: str | None = None

    async def start(self, config: StartRequest) -> dict:
        targets = config.device_ids or list(self.devices)
        if not targets:
            raise ValueError("No devices available")
        unknown = set(targets) - set(self.devices)
        if unknown:
            raise ValueError(f"Unknown device IDs: {', '.join(sorted(unknown))}")
        if config.minimum_brightness > config.brightness:
            raise ValueError("minimum_brightness cannot exceed brightness")
        if len(set(targets)) != len(targets):
            raise ValueError("device_ids must be unique")
        async with self._lock:
            self.playback = config.model_copy(update={"device_ids": targets})
            self.started_at = time.monotonic()
            self._last_sent_at.clear()
            self._last_frames.clear()
            self.last_error = None
        return self.status()

    async def stop(self) -> dict:
        async with self._lock:
            self.playback = None
            # Deliberately leave bulbs at last emitted color, not power them off.
        return self.status()

    def status(self) -> dict:
        return {
            "running": self.playback is not None,
            "playback": self.playback.model_dump() if self.playback else None,
            "last_error": self.last_error,
            "last_frames": {device_id: frame.as_dict() for device_id, frame in self._last_frames.items()},
        }

    async def step(self, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        async with self._lock:
            config = self.playback
            if config is None:
                return
            for index, device_id in enumerate(config.device_ids):
                if now - self._last_sent_at.get(device_id, -float("inf")) < 1.0 / self.max_hz:
                    continue
                device = self.devices[device_id]
                frame = render(config, now - self.started_at, index)
                previous = self._last_frames.get(device_id)
                if frame != previous:
                    try:
                        await self.transport.apply(device, frame, previous)
                    except (OSError, ValueError) as exc:
                        self.last_error = str(exc)
                        continue
                    self._last_frames[device_id] = frame
                self._last_sent_at[device_id] = now

    async def run(self) -> None:
        while True:
            await self.step()
            await asyncio.sleep(0.05)
