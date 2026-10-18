"""Configuration. Real-device mode must be explicitly enabled."""
import ipaddress
import json
import os
from pathlib import Path

from .engine import LightingEngine
from .models import Device
from .transports import GoveeLanTransport, SimulationTransport

SIMULATED_DEVICES = [Device(id=f"bulb-{i}", name=f"Bulb {i}") for i in range(1, 5)]


def build_engine() -> LightingEngine:
    mode = os.environ.get("LIGHT_ENGINE_MODE", "simulation").lower()
    max_hz = float(os.environ.get("LIGHT_ENGINE_MAX_HZ", "3"))
    if mode == "simulation":
        return LightingEngine(SIMULATED_DEVICES, SimulationTransport(), max_hz=max_hz)
    if mode != "lan":
        raise ValueError("LIGHT_ENGINE_MODE must be simulation or lan")
    path = os.environ.get("LIGHT_ENGINE_DEVICES_FILE")
    if not path:
        raise ValueError("LAN mode requires LIGHT_ENGINE_DEVICES_FILE")
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("Device file must be a nonempty JSON list")
    devices: list[Device] = []
    for value in raw:
        device = Device(**value)
        if not device.ip or not ipaddress.ip_address(device.ip).is_private:
            raise ValueError("Only private-network IP addresses are accepted in LAN mode")
        devices.append(device)
    if len({device.id for device in devices}) != len(devices):
        raise ValueError("Duplicate device IDs")
    return LightingEngine(devices, GoveeLanTransport(), max_hz=max_hz)
