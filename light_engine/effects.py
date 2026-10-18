"""Deterministic, pure effect rendering. No device I/O here."""
import colorsys
import math

from .models import Frame, StartRequest

TAU = math.tau


def _rgb(hue: float, saturation: float = 1.0) -> tuple[int, int, int]:
    red, green, blue = colorsys.hsv_to_rgb((hue % 360) / 360, saturation, 1.0)
    return tuple(round(channel * 255) for channel in (red, green, blue))


def render(config: StartRequest, elapsed: float, index: int = 0) -> Frame:
    """Render one fixture at a timestamp, with optional per-fixture phase."""
    t = max(0.0, elapsed) * config.speed
    phase = (index * config.phase_spread) % 1.0
    brightness = config.brightness
    hue = config.hue

    if config.effect == "pulse":
        amplitude = (1 - math.cos(TAU * (t / 3 + phase))) / 2
        brightness = round(config.minimum_brightness + (brightness - config.minimum_brightness) * amplitude)
    elif config.effect == "rainbow":
        hue = (hue + (t / 8 + phase) * 360) % 360
    elif config.effect == "fire":
        # Interference of incommensurate oscillators looks irregular but is reproducible.
        flicker = (math.sin(t * 11.3 + index * 4) + math.sin(t * 19.7 + index) +
                   math.sin(t * 5.1 + index * 2.9)) / 6 + 0.5
        brightness = round(config.minimum_brightness + (brightness - config.minimum_brightness) * flicker)
        hue = 10 + 29 * flicker
    elif config.effect == "chase":
        amplitude = max(0.0, math.cos(TAU * (t / 2 - phase))) ** 4
        brightness = round(config.minimum_brightness + (brightness - config.minimum_brightness) * amplitude)

    r, g, b = _rgb(hue)
    return Frame(r, g, b, max(1, min(100, brightness)))
