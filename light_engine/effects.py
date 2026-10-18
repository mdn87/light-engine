"""Deterministic, pure effect rendering. No device I/O here."""
import bisect
import colorsys
import math
from collections.abc import Sequence

from .models import Frame, Keyframe, Repeat, StartRequest

TAU = math.tau


def _rgb(hue: float, saturation: float = 1.0) -> tuple[int, int, int]:
    red, green, blue = colorsys.hsv_to_rgb((hue % 360) / 360, saturation, 1.0)
    return tuple(round(channel * 255) for channel in (red, green, blue))


def _ease(kind: str, f: float) -> float:
    if kind == "step":
        return 0.0
    if kind == "smooth":
        return f * f * (3 - 2 * f)
    return f


def _timeline_time(keyframes: Sequence[Keyframe], t: float, repeat: Repeat) -> float:
    start, end = keyframes[0].t, keyframes[-1].t
    span = end - start
    if repeat == "loop":
        return start + (t - start) % span
    if repeat == "ping_pong":
        x = (t - start) % (2 * span)
        return start + (x if x <= span else 2 * span - x)
    return min(max(t, start), end)


def sample(keyframes: Sequence[Keyframe], t: float,
           repeat: Repeat = "loop") -> tuple[float, float, float]:
    """Hue, saturation and brightness of a keyframe timeline at time t (seconds).

    Before the first keyframe the timeline repeats (loop, ping_pong) or holds it (once).
    A loop jumps from the last keyframe back to the first, so repeat the first values at
    the end for a seamless cycle. Hue takes the short way round the colour wheel.
    """
    u = _timeline_time(keyframes, t, repeat)
    times = [keyframe.t for keyframe in keyframes]
    i = min(max(bisect.bisect_right(times, u) - 1, 0), len(keyframes) - 2)
    a, b = keyframes[i], keyframes[i + 1]
    f = _ease(a.ease, (u - a.t) / (b.t - a.t))
    if u >= b.t:
        f = 1.0
    hue_delta = (b.hue - a.hue + 180) % 360 - 180
    return ((a.hue + hue_delta * f) % 360, a.saturation + (b.saturation - a.saturation) * f,
            a.brightness + (b.brightness - a.brightness) * f)


def render(config: StartRequest, elapsed: float, position: float = 0) -> Frame:
    """Render one fixture at a timestamp; `position` is its place along the layout in slots."""
    t = max(0.0, elapsed) * config.speed
    phase = (position * config.phase_spread) % 1.0
    brightness = config.brightness
    hue = config.hue
    saturation = 1.0

    if config.effect == "timeline":
        # Each slot lags the one before by phase_spread of the timeline's length: a wave.
        span = config.keyframes[-1].t - config.keyframes[0].t
        hue, saturation, level = sample(config.keyframes, t - position * config.phase_spread * span,
                                        config.repeat)
        brightness = round(level)
    elif config.effect == "pulse":
        amplitude = (1 - math.cos(TAU * (t / 3 + phase))) / 2
        brightness = round(config.minimum_brightness + (brightness - config.minimum_brightness) * amplitude)
    elif config.effect == "rainbow":
        hue = (hue + (t / 8 + phase) * 360) % 360
    elif config.effect == "fire":
        # Interference of incommensurate oscillators looks irregular but is reproducible.
        flicker = (math.sin(t * 11.3 + position * 4) + math.sin(t * 19.7 + position) +
                   math.sin(t * 5.1 + position * 2.9)) / 6 + 0.5
        brightness = round(config.minimum_brightness + (brightness - config.minimum_brightness) * flicker)
        hue = 10 + 29 * flicker
    elif config.effect == "chase":
        amplitude = max(0.0, math.cos(TAU * (t / 2 - phase))) ** 4
        brightness = round(config.minimum_brightness + (brightness - config.minimum_brightness) * amplitude)

    r, g, b = _rgb(hue, saturation)
    return Frame(r, g, b, max(1, min(100, brightness)))
