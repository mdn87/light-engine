"""Configuration. Real-device mode must be explicitly enabled."""
import ipaddress
import json
import os
from dataclasses import fields
from pathlib import Path

from .engine import LightingEngine
from .models import Device
from .transports import GoveeLanTransport, SimulationTransport

SIMULATED_DEVICES = [Device(id=f"bulb-{i}", name=f"Bulb {i}") for i in range(1, 5)]
DEVICE_FIELDS = {field.name for field in fields(Device)}


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def load_devices(path: str | Path) -> list[Device]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("Device file must be a nonempty JSON list")
    devices: list[Device] = []
    for value in raw:
        if not isinstance(value, dict):
            raise TypeError("Each device entry must be a JSON object")
        unknown = set(value) - DEVICE_FIELDS
        if unknown:
            raise ValueError(f"Unknown device fields: {', '.join(sorted(unknown))}")
        device = Device(**value)
        if not device.ip or not ipaddress.ip_address(device.ip).is_private:
            raise ValueError("Only private-network IP addresses are accepted in LAN mode")
        devices.append(device)
    if len({device.id for device in devices}) != len(devices):
        raise ValueError("Duplicate device IDs")
    if len({device.ip for device in devices}) != len(devices):
        raise ValueError("Duplicate device IPs")
    return devices


def build_engine() -> LightingEngine:
    mode = os.environ.get("LIGHT_ENGINE_MODE", "simulation").lower()
    max_hz = float(os.environ.get("LIGHT_ENGINE_MAX_HZ", "3"))
    allow_power = _flag("LIGHT_ENGINE_ALLOW_POWER")
    if mode == "simulation":
        return LightingEngine(SIMULATED_DEVICES, SimulationTransport(), max_hz=max_hz,
                              allow_power=allow_power)
    if mode != "lan":
        raise ValueError("LIGHT_ENGINE_MODE must be simulation or lan")
    path = os.environ.get("LIGHT_ENGINE_DEVICES_FILE")
    if not path:
        raise ValueError("LAN mode requires LIGHT_ENGINE_DEVICES_FILE")
    gap = float(os.environ.get("LIGHT_ENGINE_COMMAND_GAP_MS", "25")) / 1000
    transport = GoveeLanTransport(command_gap_seconds=gap)
    return LightingEngine(load_devices(path), transport, max_hz=max_hz, allow_power=allow_power)
