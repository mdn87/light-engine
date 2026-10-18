"""Fire-and-verify output benchmark for Govee LAN bulbs.

Sends color and/or brightness updates at a fixed rate, then reads devStatus just before
the next update to check whether the last update was applied. Never powers a bulb on:
it aborts if a bulb reports off or does not answer devStatus (LAN Control likely off).
The starting color/brightness is restored at the end.

    python -m light_engine.bench --ip 192.168.1.101 --rate 3 --duration 60 --pattern both \
        --out bench-1bulb-3hz.json
"""
import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass, field

from .effects import _rgb
from .models import Device, DeviceStatus, Frame
from .transports import COMMAND_PORT, RESPONSE_PORT, GoveeLanTransport

PATTERNS = ("color", "brightness", "both")


def bench_frame(pattern: str, tick: int) -> Frame:
    """Deterministic frames where consecutive ticks always differ in the tested channel."""
    hue = (tick * 47) % 360
    r, g, b = _rgb(hue) if pattern in ("color", "both") else (255, 120, 0)
    brightness = 20 + (tick * 37) % 70 if pattern in ("brightness", "both") else 60
    return Frame(r, g, b, brightness)


def matches(frame: Frame, status: DeviceStatus, color_tolerance: int = 2) -> bool:
    color_ok = all(abs(a - b) <= color_tolerance
                   for a, b in ((frame.r, status.r), (frame.g, status.g), (frame.b, status.b)))
    return color_ok and status.brightness == frame.brightness and status.color_temp_kelvin == 0


@dataclass
class DeviceResult:
    ip: str
    updates: int = 0
    verified: int = 0
    mismatched: int = 0
    status_timeouts: int = 0
    rtts: list[float] = field(default_factory=list)
    first_mismatch: dict | None = None

    def summary(self) -> dict:
        checked = self.verified + self.mismatched
        rtts = sorted(self.rtts)
        return {
            "ip": self.ip,
            "updates_sent": self.updates,
            "verified": self.verified,
            "mismatched": self.mismatched,
            "status_timeouts": self.status_timeouts,
            "applied_ratio": round(self.verified / checked, 4) if checked else None,
            "status_rtt_ms": {
                "min": round(rtts[0] * 1000, 1),
                "median": round(statistics.median(rtts) * 1000, 1),
                "p95": round(rtts[int(0.95 * (len(rtts) - 1))] * 1000, 1),
                "max": round(rtts[-1] * 1000, 1),
            } if rtts else None,
            "first_mismatch": self.first_mismatch,
        }


async def run_benchmark(transport: GoveeLanTransport, devices: list[Device], rate: float,
                        duration: float, pattern: str, verify: bool = True,
                        restore: bool = True) -> dict:
    if pattern not in PATTERNS:
        raise ValueError(f"pattern must be one of {PATTERNS}")
    initial: dict[str, DeviceStatus] = {}
    for device in devices:
        try:
            status = await transport.request_status(device)
        except TimeoutError as exc:
            raise SystemExit(f"{exc}. Is LAN Control enabled for this bulb?") from None
        if not status.on:
            raise SystemExit(f"{device.ip} reports off; turn it on yourself before benchmarking")
        initial[device.ip] = status

    results = {device.ip: DeviceResult(device.ip) for device in devices}
    previous: dict[str, Frame | None] = {device.ip: None for device in devices}
    interval = 1.0 / rate
    start = time.monotonic()
    late_ticks = 0
    tick = 0
    tick_starts: list[float] = []
    try:
        while tick * interval < duration:
            deadline = start + tick * interval
            lag = time.monotonic() - deadline
            if lag > interval:
                late_ticks += 1
            elif lag < 0:
                await asyncio.sleep(-lag)
            tick_starts.append(time.monotonic())
            for device in devices:
                frame = bench_frame(pattern, tick)
                await transport.apply(device, frame, previous[device.ip])
                previous[device.ip] = frame
                results[device.ip].updates += 1
            if verify:
                # Verify late in the interval so the device has had time to apply.
                next_deadline = start + (tick + 1) * interval
                await asyncio.sleep(max(0.0, next_deadline - time.monotonic() - interval * 0.35))
                for device in devices:
                    result = results[device.ip]
                    sent_at = time.monotonic()
                    try:
                        status = await transport.request_status(device, timeout=interval * 0.3)
                    except TimeoutError:
                        result.status_timeouts += 1
                        continue
                    result.rtts.append(time.monotonic() - sent_at)
                    if matches(previous[device.ip], status):
                        result.verified += 1
                    else:
                        result.mismatched += 1
                        result.first_mismatch = result.first_mismatch or {
                            "tick": tick, "sent": previous[device.ip].as_dict(),
                            "reported": status.as_dict()}
            tick += 1
    finally:
        elapsed = time.monotonic() - start
        if restore:
            for device in devices:
                state = initial[device.ip]
                await transport.apply(device, Frame(state.r, state.g, state.b, state.brightness),
                                      None)
    return {
        "pattern": pattern,
        "target_rate_hz": rate,
        "duration_s": round(elapsed, 2),
        # Mean spacing between tick starts; independent of the verify tail.
        "achieved_rate_hz": round((len(tick_starts) - 1) / (tick_starts[-1] - tick_starts[0]), 3)
        if len(tick_starts) > 1 else None,
        "late_ticks": late_ticks,
        "command_gap_ms": transport.command_gap_seconds * 1000,
        "verify": verify,
        "devices": [results[device.ip].summary() for device in devices],
        "initial_status": {ip: status.as_dict() for ip, status in initial.items()},
        "unmatched_replies": transport.unmatched_replies,
    }


async def _main(args) -> dict:
    transport = GoveeLanTransport(command_gap_seconds=args.gap_ms / 1000,
                                  command_port=args.command_port,
                                  response_host=args.listen_host,
                                  response_port=args.response_port)
    devices = [Device(f"bench-{i}", ip, ip=ip) for i, ip in enumerate(args.ip, 1)]
    try:
        return await run_benchmark(transport, devices, args.rate, args.duration, args.pattern,
                                   verify=not args.no_verify)
    finally:
        transport.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Govee LAN fire-and-verify benchmark")
    parser.add_argument("--ip", action="append", required=True, help="bulb IP (repeatable)")
    parser.add_argument("--rate", type=float, default=3.0, help="updates per second per bulb")
    parser.add_argument("--duration", type=float, default=60.0, help="seconds")
    parser.add_argument("--pattern", choices=PATTERNS, default="both")
    parser.add_argument("--gap-ms", type=float, default=25.0, help="spacing between commands")
    parser.add_argument("--no-verify", action="store_true", help="send only, no devStatus")
    parser.add_argument("--out", help="write JSON result to this file")
    parser.add_argument("--listen-host", default="0.0.0.0")
    parser.add_argument("--command-port", type=int, default=COMMAND_PORT)
    parser.add_argument("--response-port", type=int, default=RESPONSE_PORT)
    args = parser.parse_args(argv)
    if args.rate <= 0 or args.duration <= 0:
        parser.error("--rate and --duration must be positive")
    result = asyncio.run(_main(args))
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


if __name__ == "__main__":
    main()
