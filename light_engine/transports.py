"""Device transport boundary. Simulation never opens a network socket."""
import asyncio
import json
import socket
from typing import Protocol

from .models import Device, Frame


class Transport(Protocol):
    async def apply(self, device: Device, frame: Frame, previous: Frame | None) -> None: ...


class SimulationTransport:
    def __init__(self) -> None:
        self.states: dict[str, Frame] = {}
        self.history: list[tuple[str, Frame]] = []

    async def apply(self, device: Device, frame: Frame, previous: Frame | None) -> None:
        self.states[device.id] = frame
        self.history.append((device.id, frame))
        if len(self.history) > 1000:
            self.history = self.history[-500:]


class GoveeLanTransport:
    """Official, unencrypted UDP LAN commands. Only use on a trusted LAN."""

    def __init__(self, command_gap_seconds: float = 0.025) -> None:
        self.command_gap_seconds = command_gap_seconds
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def close(self) -> None:
        self.socket.close()

    def _send(self, address: str, command: str, data: dict) -> None:
        message = json.dumps({"msg": {"cmd": command, "data": data}}, separators=(",", ":"))
        self.socket.sendto(message.encode("utf-8"), (address, 4003))

    async def apply(self, device: Device, frame: Frame, previous: Frame | None) -> None:
        if not device.ip:
            raise ValueError(f"LAN device {device.id} needs an IP address")
        # Starting an effect does not implicitly power on the device. Caller must
        # explicitly handle that policy in a later implementation.
        if previous is None or (frame.r, frame.g, frame.b) != (previous.r, previous.g, previous.b):
            self._send(device.ip, "colorwc", {
                "color": {"r": frame.r, "g": frame.g, "b": frame.b},
                "colorTemInKelvin": 0,
            })
            if previous is None or frame.brightness != previous.brightness:
                await asyncio.sleep(self.command_gap_seconds)
        if previous is None or frame.brightness != previous.brightness:
            self._send(device.ip, "brightness", {"value": frame.brightness})
