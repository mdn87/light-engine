"""Keyframe timelines, layout positions and the synchronized multi-bulb send path."""
import asyncio
import time

import pytest
from pydantic import ValidationError

from light_engine.effects import render, sample
from light_engine.engine import LightingEngine
from light_engine.models import Device, Frame, Keyframe, StartRequest
from light_engine.transports import SimulationTransport

THREE = [Keyframe(t=0, hue=0, brightness=20, ease="linear"),
         Keyframe(t=2, hue=120, brightness=100, ease="smooth"),
         Keyframe(t=4, hue=0, brightness=20)]


def wave(**kw) -> StartRequest:
    return StartRequest(effect="timeline", keyframes=THREE, **kw)


def test_sample_golden_values():
    assert sample(THREE, 0) == (0, 1, 20)
    assert sample(THREE, 1) == (60, 1, 60)           # linear midpoint
    hue, _, level = sample(THREE, 3)                  # smoothstep(0.5) is also 0.5
    assert (round(hue), level) == (60, 60)
    hue, _, level = sample(THREE, 2.5)                # smoothstep(0.25) = 0.15625
    assert round(level, 3) == round(100 - 80 * 0.15625, 3)
    assert sample(THREE, 5) == sample(THREE, 1)       # loop


def test_repeat_modes_and_step_ease():
    assert sample(THREE, 5, "ping_pong") == sample(THREE, 3, "ping_pong")
    assert sample(THREE, 99, "once") == (0, 1, 20)
    assert sample(THREE, 0, "once") == (0, 1, 20)
    held = [Keyframe(t=0, hue=200, brightness=50, ease="step"),
            Keyframe(t=1, hue=10, brightness=90)]
    assert sample(held, 0.99, "once") == (200, 1, 50)
    assert sample(held, 1, "once") == (10, 1, 90)


def test_hue_takes_the_short_way_round():
    keys = [Keyframe(t=0, hue=350, brightness=50, ease="linear"),
            Keyframe(t=1, hue=10, brightness=50)]
    hue, _, _ = sample(keys, 0.5, "once")
    assert round(hue) % 360 == 0                      # through red, not through cyan


def test_timeline_validation():
    with pytest.raises(ValidationError, match="at least two"):
        StartRequest(effect="timeline", keyframes=THREE[:1])
    with pytest.raises(ValidationError, match="strictly increase"):
        StartRequest(effect="timeline", keyframes=[THREE[1], THREE[0]])
    with pytest.raises(ValidationError):
        Keyframe(t=0, hue=0, brightness=50, colour="red")


def test_wave_offsets_follow_position_not_list_order():
    config = wave(phase_spread=0.25)
    # Each slot lags the previous by a quarter of the 4 s timeline.
    for position in range(4):
        assert render(config, 3.0, position) == render(config, 3.0 - position, 0)
    reordered = [Device("b1", "B1", position=3), Device("b2", "B2", position=2),
                 Device("b3", "B3", position=1), Device("b4", "B4", position=0)]

    async def scenario():
        transport = SimulationTransport()
        engine = LightingEngine(reordered, transport, max_hz=3)
        await engine.start(config)
        await engine.step(engine.started_at + 1.0)
        return transport.states

    states = asyncio.run(scenario())
    assert states["b1"] == render(config, 1.0, 3)
    assert states["b4"] == render(config, 1.0, 0)


class SlowTransport(SimulationTransport):
    def __init__(self, delay: float) -> None:
        super().__init__()
        self.delay = delay

    async def apply(self, device: Device, frame: Frame, previous: Frame | None) -> None:
        await asyncio.sleep(self.delay)
        await super().apply(device, frame, previous)


def test_stop_does_not_wait_for_a_slow_send():
    async def scenario():
        engine = LightingEngine([Device("bulb-1", "Test")], SlowTransport(0.5), max_hz=3)
        await engine.start(StartRequest(effect="rainbow"))
        step = asyncio.create_task(engine.step())
        await asyncio.sleep(0.05)
        began = time.monotonic()
        await engine.stop()
        stop_seconds = time.monotonic() - began
        # A second tick while the send is in flight must not queue another one.
        await engine.step(time.monotonic() + 10)
        await step
        return stop_seconds, engine.stats["bulb-1"].sends

    stop_seconds, sends = asyncio.run(scenario())
    assert stop_seconds < 0.1
    assert sends == 1


def test_send_finishing_after_restart_does_not_record_stale_frame():
    async def scenario():
        engine = LightingEngine([Device("bulb-1", "Test")], SlowTransport(0.2), max_hz=3)
        await engine.start(StartRequest(effect="rainbow"))
        step = asyncio.create_task(engine.step())
        await asyncio.sleep(0.05)
        await engine.start(StartRequest(effect="pulse"))
        await step
        return engine._last_frames

    assert asyncio.run(scenario()) == {}

