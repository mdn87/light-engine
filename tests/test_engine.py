import asyncio

import pytest

from light_engine.engine import LightingEngine
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
