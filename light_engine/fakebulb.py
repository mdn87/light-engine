"""In-process emulation of a Govee LAN bulb for tests and benchmark rehearsal.

Implements the documented commands (turn, brightness, colorwc, devStatus) and scan, and
can emulate the documented failure mode where a command arriving directly behind two
others is silently dropped. It is a test double, not evidence of real-device behavior.

    python -m light_engine.fakebulb --host 127.0.0.2 --reply-port 4002
"""
import argparse
import asyncio
import time

from .transports import COMMAND_PORT, RESPONSE_PORT, decode_message, encode_command


class FakeGoveeBulb(asyncio.DatagramProtocol):
    def __init__(self, reply_port: int = RESPONSE_PORT, mac: str = "AA:BB:CC:DD:EE:01",
                 sku: str = "H6004", drop_burst_window: float | None = None,
                 respond: bool = True) -> None:
        self.reply_port = reply_port
        self.mac = mac
        self.sku = sku
        # When set, a command arriving within this many seconds of the two commands
        # before it is dropped, mirroring the documented consecutive-command loss.
        self.drop_burst_window = drop_burst_window
        self.respond = respond
        self.on = True
        self.brightness = 100
        self.color = {"r": 255, "g": 255, "b": 255}
        self.color_temp = 0
        self.received: list[tuple[str, dict]] = []
        self.received_at: list[float] = []  # monotonic arrival time of each received entry
        self.dropped = 0
        self._arrivals: list[float] = []
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport) -> None:
        self.transport = transport

    @property
    def address(self) -> tuple[str, int]:
        return self.transport.get_extra_info("sockname")[:2]

    def status_data(self) -> dict:
        return {"onOff": int(self.on), "brightness": self.brightness, "color": dict(self.color),
                "colorTemInKelvin": self.color_temp}

    def _burst_drop(self) -> bool:
        now = time.monotonic()
        recent = self._arrivals[-2:]
        self._arrivals = recent + [now]
        window = self.drop_burst_window
        return window is not None and len(recent) == 2 and now - recent[0] <= window

    def datagram_received(self, data: bytes, addr) -> None:
        decoded = decode_message(data)
        if decoded is None:
            return  # Real devices ignore malformed frames silently.
        command, payload = decoded
        if command == "scan":
            self._reply(addr[0], "scan", {
                "ip": self.address[0], "device": self.mac, "sku": self.sku,
                "bleVersionHard": "", "bleVersionSoft": "",
                "wifiVersionHard": "1.0", "wifiVersionSoft": "fake"})
            return
        if self._burst_drop():
            self.dropped += 1
            return
        self.received.append((command, payload))
        self.received_at.append(time.monotonic())
        if command == "turn":
            self.on = bool(payload.get("value"))
        elif command == "brightness":
            value = payload.get("value")
            if isinstance(value, int) and value >= 0:
                self.brightness = max(1, min(100, value))
        elif command == "colorwc":
            kelvin = int(payload.get("colorTemInKelvin", 0))
            if kelvin > 0:
                self.color_temp, self.color = max(2000, min(9000, kelvin)), {"r": 0, "g": 0, "b": 0}
            else:
                color = payload.get("color", {})
                self.color = {k: int(color.get(k, 0)) for k in ("r", "g", "b")}
                self.color_temp = 0
        elif command == "devStatus":
            self._reply(addr[0], "devStatus", self.status_data())

    def _reply(self, host: str, command: str, data: dict) -> None:
        if self.respond and self.transport is not None:
            self.transport.sendto(encode_command(command, data), (host, self.reply_port))


async def start_fake_bulb(host: str = "127.0.0.2", port: int = 0, **kwargs) -> FakeGoveeBulb:
    loop = asyncio.get_running_loop()
    _, bulb = await loop.create_datagram_endpoint(lambda: FakeGoveeBulb(**kwargs),
                                                  local_addr=(host, port))
    return bulb


async def _serve(args) -> None:
    bulb = await start_fake_bulb(args.host, args.port, reply_port=args.reply_port,
                                 drop_burst_window=args.drop_burst_window)
    print(f"Fake Govee bulb on {bulb.address[0]}:{bulb.address[1]}, replies to :{args.reply_port}")
    try:
        await asyncio.Event().wait()
    finally:
        bulb.transport.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.2")
    parser.add_argument("--port", type=int, default=COMMAND_PORT)
    parser.add_argument("--reply-port", type=int, default=RESPONSE_PORT)
    parser.add_argument("--drop-burst-window", type=float, default=None,
                        help="seconds; emulate dropping a 3rd command inside this window")
    try:
        asyncio.run(_serve(parser.parse_args(argv)))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
