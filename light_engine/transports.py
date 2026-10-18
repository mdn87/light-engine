"""Device transport boundary. Simulation never opens a network socket.

Govee LAN protocol (official WLAN guide, https://app-h5.govee.com/user-manual/wlan-guide,
summarized at https://github.com/damient/govee-toolkit/blob/main/docs/protocol/lan.md):
commands go to device:4003, scan/devStatus replies arrive on client:4002. Nothing is
acknowledged, and a device can silently drop a command sent directly behind two others,
so every send to one device is spaced by ``command_gap_seconds``.
"""
import asyncio
import json
import socket
import time
from typing import Protocol

from .models import Device, DeviceStatus, Frame

COMMAND_PORT = 4003
RESPONSE_PORT = 4002


def encode_command(command: str, data: dict) -> bytes:
    return json.dumps({"msg": {"cmd": command, "data": data}}, separators=(",", ":")).encode()


def decode_message(raw: bytes) -> tuple[str, dict] | None:
    """Return (cmd, data) from a Govee envelope, or None if malformed."""
    try:
        msg = json.loads(raw)["msg"]
        command, data = msg["cmd"], msg["data"]
    except (ValueError, KeyError, TypeError):
        return None
    if not isinstance(command, str) or not isinstance(data, dict):
        return None
    return command, data


def parse_status(data: dict) -> DeviceStatus:
    color = data.get("color") or {}
    return DeviceStatus(
        on=bool(data["onOff"]),
        brightness=int(data["brightness"]),
        r=int(color.get("r", 0)),
        g=int(color.get("g", 0)),
        b=int(color.get("b", 0)),
        color_temp_kelvin=int(data.get("colorTemInKelvin", 0)),
    )


class Transport(Protocol):
    async def apply(self, device: Device, frame: Frame, previous: Frame | None) -> None: ...

    async def set_power(self, device: Device, on: bool) -> None: ...

    async def request_status(self, device: Device, timeout: float | None = None) -> DeviceStatus: ...


class SimulationTransport:
    def __init__(self) -> None:
        self.states: dict[str, Frame] = {}
        self.power: dict[str, bool] = {}
        self.history: list[tuple[str, Frame]] = []

    async def apply(self, device: Device, frame: Frame, previous: Frame | None) -> None:
        self.states[device.id] = frame
        self.history.append((device.id, frame))
        if len(self.history) > 1000:
            self.history = self.history[-500:]

    async def set_power(self, device: Device, on: bool) -> None:
        self.power[device.id] = on

    async def request_status(self, device: Device, timeout: float | None = None) -> DeviceStatus:
        frame = self.states.get(device.id, Frame(255, 255, 255, 100))
        return DeviceStatus(self.power.get(device.id, True), frame.brightness,
                            frame.r, frame.g, frame.b)


class _ResponseProtocol(asyncio.DatagramProtocol):
    def __init__(self, owner: "GoveeLanTransport") -> None:
        self.owner = owner

    def datagram_received(self, data: bytes, addr) -> None:
        self.owner._on_response(data, addr[0])


class GoveeLanTransport:
    """Official, unencrypted UDP LAN commands. Only use on a trusted LAN."""

    def __init__(self, command_gap_seconds: float = 0.025, command_port: int = COMMAND_PORT,
                 response_host: str = "0.0.0.0", response_port: int = RESPONSE_PORT,
                 status_timeout: float = 1.0) -> None:
        self.command_gap_seconds = command_gap_seconds
        self.command_port = command_port
        self.response_host = response_host
        self.response_port = response_port
        self.status_timeout = status_timeout
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._last_send: dict[str, float] = {}
        self._waiters: dict[str, list[asyncio.Future]] = {}
        self._listener: asyncio.DatagramTransport | None = None
        self._listener_lock: asyncio.Lock | None = None
        self.unmatched_replies = 0

    def close(self) -> None:
        if self._listener is not None:
            self._listener.close()
            self._listener = None
        self.socket.close()

    async def _send(self, address: str, command: str, data: dict) -> None:
        wait = self._last_send.get(address, -float("inf")) + self.command_gap_seconds
        delay = wait - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)
        self.socket.sendto(encode_command(command, data), (address, self.command_port))
        self._last_send[address] = time.monotonic()

    @staticmethod
    def _address(device: Device) -> str:
        if not device.ip:
            raise ValueError(f"LAN device {device.id} needs an IP address")
        return device.ip

    async def apply(self, device: Device, frame: Frame, previous: Frame | None) -> None:
        address = self._address(device)
        # Effects never power a device on; power is a separate, opt-in action.
        if previous is None or (frame.r, frame.g, frame.b) != (previous.r, previous.g, previous.b):
            await self._send(address, "colorwc", {
                "color": {"r": frame.r, "g": frame.g, "b": frame.b},
                "colorTemInKelvin": 0,
            })
        if previous is None or frame.brightness != previous.brightness:
            await self._send(address, "brightness", {"value": frame.brightness})

    async def set_power(self, device: Device, on: bool) -> None:
        await self._send(self._address(device), "turn", {"value": 1 if on else 0})

    async def start_listener(self) -> int:
        """Bind the UDP reply listener (idempotent). Returns the bound port."""
        if self._listener_lock is None:
            self._listener_lock = asyncio.Lock()
        async with self._listener_lock:
            if self._listener is None:
                loop = asyncio.get_running_loop()
                self._listener, _ = await loop.create_datagram_endpoint(
                    lambda: _ResponseProtocol(self),
                    local_addr=(self.response_host, self.response_port))
            return self._listener.get_extra_info("sockname")[1]

    def _on_response(self, raw: bytes, source_ip: str) -> None:
        decoded = decode_message(raw)
        waiters = self._waiters.pop(source_ip, []) if decoded and decoded[0] == "devStatus" else []
        if not waiters:
            self.unmatched_replies += 1
            return
        try:
            result: DeviceStatus | Exception = parse_status(decoded[1])
        except (KeyError, TypeError, ValueError) as exc:
            result = ValueError(f"Malformed devStatus from {source_ip}: {exc}")
        for future in waiters:
            if future.done():
                continue
            if isinstance(result, Exception):
                future.set_exception(result)
            else:
                future.set_result(result)

    async def request_status(self, device: Device, timeout: float | None = None) -> DeviceStatus:
        address = self._address(device)
        await self.start_listener()
        future = asyncio.get_running_loop().create_future()
        self._waiters.setdefault(address, []).append(future)
        try:
            await self._send(address, "devStatus", {})
            return await asyncio.wait_for(future, timeout or self.status_timeout)
        except TimeoutError:
            raise TimeoutError(f"No devStatus reply from {device.id} ({address})") from None
        finally:
            pending = self._waiters.get(address)
            if pending and future in pending:
                pending.remove(future)
                if not pending:
                    del self._waiters[address]
