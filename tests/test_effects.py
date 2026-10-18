import pytest

from light_engine.effects import render
from light_engine.models import StartRequest


@pytest.mark.parametrize("effect", ["pulse", "rainbow", "fire", "chase"])
def test_effect_frames_bounded(effect):
    config = StartRequest(effect=effect, brightness=85, minimum_brightness=4)
    for timestamp in [0, 0.04, 0.3, 2.4, 1000]:
        for index in range(4):
            frame = render(config, timestamp, index)
            assert 1 <= frame.brightness <= 100
            assert all(0 <= n <= 255 for n in [frame.r, frame.g, frame.b])


def test_effects_are_deterministic():
    config = StartRequest(effect="fire")
    assert render(config, 1.234, 2) == render(config, 1.234, 2)


def test_rainbow_changes_hue_over_time():
    config = StartRequest(effect="rainbow")
    assert render(config, 0) != render(config, 1)
