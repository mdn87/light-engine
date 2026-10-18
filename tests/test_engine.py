import asyncio

import pytest

from light_engine.engine import ConflictError, LightingEngine, PolicyError
from light_engine.models import Device, StartRequest
from light_engine.transports import SimulationTransport


def test_start_tick_throttle_and_stop():
    async def scenario():
        transport = SimulationTransport()
        engine = LightingEngine([Device("bulb-1", "Test")], transport, max_hz=3)
        await engine.start(StartRequest(effect="rainbow"))
        initial = engine.started_at
        await engine.step(initial)
        assert len(transport.history) == 1
        await engine.step(initial + 0.01)
        assert len(transport.history) == 1
        await engine.step(initial + 0.4)
        assert len(transport.history) == 2
        status = await engine.stop()
        assert status["running"] is False
        await engine.step(initial + 10)
        assert len(transport.history) == 2

    asyncio.run(scenario())


def test_unknown_device_and_invalid_brightness():
    async def scenario():
        engine = LightingEngine([Device("bulb-1", "Test")], SimulationTransport())
        with pytest.raises(ValueError, match="Unknown device"):
            await engine.start(StartRequest(device_ids=["bad-id"]))
        with pytest.raises(ValueError, match="minimum_brightness"):
            await engine.start(StartRequest(minimum_brightness=90, brightness=10))

    asyncio.run(scenario())


class FlakyTransport(SimulationTransport):
    def __init__(self, failures: int) -> None:
        super().__init__()
        self.failures = failures
        self.attempts = 0

    async def apply(self, device, frame, previous):
        self.attempts += 1
        if self.failures:
            self.failures -= 1
            raise OSError("network unreachable")
        await super().apply(device, frame, previous)


def test_errors_back_off_then_recover_without_backlog():
    async def scenario():
        transport = FlakyTransport(failures=2)
        engine = LightingEngine([Device("bulb-1", "Test")], transport, max_hz=4)
        await engine.start(StartRequest(effect="rainbow"))
        base = engine.started_at
        await engine.step(base)                  # fail 1, backoff 0.5 s
        await engine.step(base + 0.3)            # inside backoff: skipped
        assert transport.attempts == 1
        await engine.step(base + 0.6)            # fail 2, backoff 1.0 s
        await engine.step(base + 1.2)            # still backing off
        stats = engine.diagnostics(base + 1.2)["devices"]["bulb-1"]
        assert stats["errors"] == 2 and stats["consecutive_errors"] == 2
        assert stats["skipped_backoff"] == 2 and "unreachable" in stats["last_error"]
        await engine.step(base + 1.7)            # recovers with the current frame only
        assert transport.attempts == 3 and len(transport.history) == 1
        stats = engine.diagnostics(base + 1.7)["devices"]["bulb-1"]
        assert stats["consecutive_errors"] == 0 and stats["sends"] == 1

    asyncio.run(scenario())


def test_power_policy_and_ownership():
    async def scenario():
        transport = SimulationTransport()
        engine = LightingEngine([Device("bulb-1", "A"), Device("bulb-2", "B")], transport)
        with pytest.raises(PolicyError):
            await engine.set_power("bulb-1", True)
        assert transport.power == {}
        engine.allow_power = True
        await engine.start(StartRequest(device_ids=["bulb-1"]))
        with pytest.raises(ConflictError):
            await engine.set_power("bulb-1", False)
        assert await engine.set_power("bulb-2", False) == {"id": "bulb-2", "on": False}
        assert transport.power == {"bulb-2": False}
        assert (await engine.device_status("bulb-2")).on is False
        with pytest.raises(KeyError):
            await engine.set_power("nope", True)

    asyncio.run(scenario())
