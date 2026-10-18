"""Domain types kept independent of Govee and Home Assistant."""
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class Device:
    id: str
    name: str
    ip: str | None = None
    sku: str = "H6004"


@dataclass(frozen=True)
class Frame:
    r: int
    g: int
    b: int
    brightness: int

    def as_dict(self) -> dict[str, int]:
        return {"r": self.r, "g": self.g, "b": self.b, "brightness": self.brightness}


EffectName = Literal["pulse", "rainbow", "fire", "chase"]


class StartRequest(BaseModel):
    effect: EffectName = "pulse"
    device_ids: list[str] = Field(default_factory=list)
    hue: float = Field(default=28, ge=0, le=360)
    speed: float = Field(default=1, ge=0.05, le=10)
    brightness: int = Field(default=80, ge=1, le=100)
    minimum_brightness: int = Field(default=10, ge=1, le=100)
    phase_spread: float = Field(default=0.25, ge=0, le=1)


EFFECT_NAMES: tuple[EffectName, ...] = ("pulse", "rainbow", "fire", "chase")
