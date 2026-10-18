"""Single-writer animation scheduler with bounded per-device sends."""
import asyncio
import time
from dataclasses import dataclass

from .effects import render
from .models import Device, DeviceStatus, Frame, StartRequest
from .transports import Transport

MAX_BACKOFF_SECONDS = 30.0


class PolicyError(Exception):
    """The requested action is disabled by configuration."""


class ConflictError(Exception):
    """The requested action conflicts with current fixture ownership."""


@dataclass
class DeviceStats:
    sends: int = 0
    errors: int = 0
    consecutive_errors: int = 0
    skipped_backoff: int = 0
    last_error: str | None = None
    last_sent_at: float | None = None
    backoff_until: float = 0.0

    def as_dict(self, now: float) -> dict:
        return {
            "sends": self.sends,
            "errors": self.errors,
            "consecutive_errors": self.consecutive_errors,
            "skipped_backoff": self.skipped_backoff,
            "last_error": self.last_error,
            "seconds_since_send": None if self.last_sent_at is None else now - self.last_sent_at,
            "backoff_remaining": max(0.0, self.backoff_until - now),
        }


class LightingEngine:
    def __init__(self, devices: list[Device], transport: Transport, max_hz: float = 3.0,
                 allow_power: bool = False) -> None:
        if max_hz <= 0:
            raise ValueError("max_hz must be positive")
        self.devices = {device.id: device for device in devices}
        self.transport = transport
        self.max_hz = max_hz
        self.allow_power = allow_power
        self.playback: StartRequest | None = None
        self.started_at = 0.0
        self._last_sent_at: dict[str, float] = {}
        self._last_frames: dict[str, Frame] = {}
        self.stats: dict[str, DeviceStats] = {device_id: DeviceStats() for device_id in self.devices}
        self._lock = asyncio.Lock()
        self._in_flight: set[str] = set()
        # Bumped on start so a send that finishes after a restart cannot record a stale frame.
        self._generation = 0
        self.last_error: str | None = None

    async def start(self, config: StartRequest) -> dict:
        targets = config.device_ids or list(self.devices)
        if not targets:
            raise ValueError("No devices available")
        unknown = set(targets) - set(self.devices)
        if unknown:
            raise ValueError(f"Unknown device IDs: {', '.join(sorted(unknown))}")
        if len(set(targets)) != len(targets):
            raise ValueError("device_ids must be unique")
        async with self._lock:
            self.playback = config.model_copy(update={"device_ids": targets})
            self.started_at = time.monotonic()
            self._generation += 1
            self._last_sent_at.clear()
            self._last_frames.clear()
            self.last_error = None
            for stats in self.stats.values():
                stats.consecutive_errors = 0
                stats.backoff_until = 0.0
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

    def diagnostics(self, now: float | None = None) -> dict:
        now = time.monotonic() if now is None else now
        return {
            "max_hz": self.max_hz,
            "allow_power": self.allow_power,
            "running": self.playback is not None,
            "devices": {device_id: stats.as_dict(now) for device_id, stats in self.stats.items()},
            "unmatched_replies": getattr(self.transport, "unmatched_replies", 0),
        }

    def _device(self, device_id: str) -> Device:
        try:
            return self.devices[device_id]
        except KeyError:
            raise KeyError(f"Unknown device ID: {device_id}") from None

    async def set_power(self, device_id: str, on: bool) -> dict:
        device = self._device(device_id)
        if not self.allow_power:
            raise PolicyError("Power control is disabled; set LIGHT_ENGINE_ALLOW_POWER=1 to enable")
        async with self._lock:
            if self.playback is not None and device_id in self.playback.device_ids:
                raise ConflictError(f"{device_id} is owned by running playback; stop it first")
            await self.transport.set_power(device, on)
        return {"id": device_id, "on": on}

    async def device_status(self, device_id: str) -> DeviceStatus:
        # Not under the lock: a slow reply must not stall the animation clock.
        return await self.transport.request_status(self._device(device_id))

    def _position(self, device_id: str, index: int) -> float:
        position = self.devices[device_id].position
        return index if position is None else position

    async def step(self, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        due: list[tuple[str, Frame, Frame | None]] = []
        async with self._lock:
            config = self.playback
            if config is None:
                return
            generation = self._generation
            for index, device_id in enumerate(config.device_ids):
                if device_id in self._in_flight:
                    continue
                if now - self._last_sent_at.get(device_id, -float("inf")) < 1.0 / self.max_hz:
                    continue
                stats = self.stats[device_id]
                if now < stats.backoff_until:
                    stats.skipped_backoff += 1
                    continue
                # Every bulb renders the same instant: a dropped or late tick is skipped,
                # never replayed.
                frame = render(config, now - self.started_at, self._position(device_id, index))
                previous = self._last_frames.get(device_id)
                self._last_sent_at[device_id] = now
                if frame == previous:
                    stats.consecutive_errors = 0
                    continue
                self._in_flight.add(device_id)
                due.append((device_id, frame, previous))
        if not due:
            return
        # Send outside the lock and to all bulbs at once, so stop() and status reads never
        # wait on the network and bulb 4 does not trail bulb 1 by three command gaps.
        results = await asyncio.gather(
            *(self.transport.apply(self.devices[device_id], frame, previous)
              for device_id, frame, previous in due),
            return_exceptions=True)
        unexpected: BaseException | None = None
        async with self._lock:
            for (device_id, frame, _), result in zip(due, results, strict=True):
                self._in_flight.discard(device_id)
                stats = self.stats[device_id]
                if isinstance(result, (OSError, ValueError)):
                    self.last_error = f"{device_id}: {result}"
                    stats.errors += 1
                    stats.consecutive_errors += 1
                    stats.last_error = str(result)
                    backoff = (2 ** stats.consecutive_errors) / self.max_hz
                    stats.backoff_until = now + min(MAX_BACKOFF_SECONDS, backoff)
                    # Forget the last frame so recovery resends full state.
                    self._last_frames.pop(device_id, None)
                    continue
                if isinstance(result, BaseException):
                    unexpected = unexpected or result
                    continue
                stats.sends += 1
                stats.last_sent_at = now
                stats.consecutive_errors = 0
                if generation == self._generation:
                    self._last_frames[device_id] = frame
        if unexpected is not None:
            raise unexpected

    async def run(self) -> None:
        while True:
            await self.step()
            await asyncio.sleep(0.05)
