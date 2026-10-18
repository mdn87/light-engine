"""Domain types kept independent of Govee and Home Assistant."""
from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


@dataclass(frozen=True)
class Device:
    id: str
    name: str
    ip: str | None = None
    sku: str = "H6004"
    mac: str | None = None
    # Place along the layout in slot units; defaults to the bulb's order in the playback.
    position: float | None = None


@dataclass(frozen=True)
class Frame:
    r: int
    g: int
    b: int
    brightness: int

    def as_dict(self) -> dict[str, int]:
        return {"r": self.r, "g": self.g, "b": self.b, "brightness": self.brightness}


@dataclass(frozen=True)
class DeviceStatus:
    """State a device reports about itself (Govee devStatus)."""
    on: bool
    brightness: int
    r: int
    g: int
    b: int
    color_temp_kelvin: int = 0

    def as_dict(self) -> dict:
        return {
            "on": self.on,
            "brightness": self.brightness,
            "color": {"r": self.r, "g": self.g, "b": self.b},
            "color_temp_kelvin": self.color_temp_kelvin,
        }


EffectName = Literal["pulse", "rainbow", "fire", "chase", "timeline"]
Ease = Literal["linear", "smooth", "step"]
Repeat = Literal["loop", "ping_pong", "once"]


class Keyframe(BaseModel):
    """One point on a timeline; `ease` shapes the move from here to the next keyframe."""
    model_config = ConfigDict(extra="forbid")

    t: float = Field(ge=0)
    hue: float = Field(ge=0, le=360)
    saturation: float = Field(default=1, ge=0, le=1)
    brightness: int = Field(ge=1, le=100)
    ease: Ease = "smooth"


class StartRequest(BaseModel):
    effect: EffectName = "pulse"
    device_ids: list[str] = Field(default_factory=list)
    hue: float = Field(default=28, ge=0, le=360)
    speed: float = Field(default=1, ge=0.05, le=10)
    brightness: int = Field(default=80, ge=1, le=100)
    minimum_brightness: int = Field(default=10, ge=1, le=100)
    phase_spread: float = Field(default=0.25, ge=0, le=1)
    keyframes: list[Keyframe] = Field(default_factory=list)
    repeat: Repeat = "loop"

    @model_validator(mode="after")
    def _check(self) -> "StartRequest":
        if self.minimum_brightness > self.brightness:
            raise ValueError("minimum_brightness cannot exceed brightness")
        if self.effect == "timeline":
            if len(self.keyframes) < 2:
                raise ValueError("timeline needs at least two keyframes")
            times = [keyframe.t for keyframe in self.keyframes]
            if any(later <= earlier for earlier, later in pairwise(times)):
                raise ValueError("keyframe times must strictly increase")
        return self


class PowerRequest(BaseModel):
    on: bool


EFFECT_NAMES: tuple[EffectName, ...] = ("pulse", "rainbow", "fire", "chase", "timeline")
