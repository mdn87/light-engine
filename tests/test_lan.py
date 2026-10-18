"""Integration tests over real loopback UDP against the in-process fake bulb."""
import asyncio
import socket

import pytest

from light_engine.bench import run_benchmark
from light_engine.discovery import discover
from light_engine.engine import LightingEngine
from light_engine.fakebulb import start_fake_bulb
from light_engine.models import Device, Frame, StartRequest
from light_engine.transports import GoveeLanTransport


def free_udp_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind((host, 0))
        return probe.getsockname()[1]


async def lan_setup(hosts=("127.0.0.2",), gap=0.0, **bulb_kwargs):
    """Fake bulbs share one command port on distinct loopback IPs, like real devices."""
    transport = GoveeLanTransport(command_gap_seconds=gap, response_host="127.0.0.1",
                                  response_port=0, status_timeout=0.5)
    reply_port = await transport.start_listener()
    first = await start_fake_bulb(hosts[0], 0, reply_port=reply_port, **bulb_kwargs)
    command_port = first.address[1]
    bulbs = [first] + [
        await start_fake_bulb(host, command_port, reply_port=reply_port,
                              mac=f"AA:BB:CC:DD:EE:{index:02X}", **bulb_kwargs)
        for index, host in enumerate(hosts[1:], 2)
    ]
    transport.command_port = command_port
    devices = [Device(f"bulb-{i}", f"Bulb {i}", ip=host) for i, host in enumerate(hosts, 1)]
    return transport, bulbs, devices


def close_all(transport, bulbs):
    transport.close()
    for bulb in bulbs:
        bulb.transport.close()


def test_status_roundtrip_and_power():
    async def scenario():
        transport, bulbs, (device,) = await lan_setup()
        try:
            await transport.apply(device, Frame(10, 20, 30, 40), None)
            await transport.set_power(device, False)
            status = await transport.request_status(device)
            assert (status.r, status.g, status.b, status.brightness) == (10, 20, 30, 40)
            assert status.on is False
            assert [command for command, _ in bulbs[0].received] == [
                "colorwc", "brightness", "turn", "devStatus"]
        finally:
            close_all(transport, bulbs)

    asyncio.run(scenario())


def test_status_timeout_when_device_silent():
    async def scenario():
        transport, bulbs, (device,) = await lan_setup(respond=False)
        try:
            with pytest.raises(TimeoutError, match="No devStatus reply"):
                await transport.request_status(device, timeout=0.2)
            assert transport._waiters == {}
        finally:
            close_all(transport, bulbs)

    asyncio.run(scenario())


def test_replies_are_matched_by_source_ip():
    async def scenario():
        transport, bulbs, devices = await lan_setup(hosts=("127.0.0.2", "127.0.0.3"))
        try:
            await transport.apply(devices[0], Frame(255, 0, 0, 11), None)
            await transport.apply(devices[1], Frame(0, 0, 255, 22), None)
            first, second = await asyncio.gather(transport.request_status(devices[0]),
                                                 transport.request_status(devices[1]))
            assert (first.r, first.brightness) == (255, 11)
            assert (second.b, second.brightness) == (255, 22)
        finally:
            close_all(transport, bulbs)

    asyncio.run(scenario())


def test_command_gap_prevents_documented_burst_drop():
    async def scenario(gap):
        transport, bulbs, (device,) = await lan_setup(gap=gap, drop_burst_window=0.02)
        try:
            await transport.set_power(device, True)
            await transport.apply(device, Frame(1, 2, 3, 44), None)
            await asyncio.sleep(0.05)
            return bulbs[0].dropped, bulbs[0].brightness
        finally:
            close_all(transport, bulbs)

    dropped, brightness = asyncio.run(scenario(0.0))
    assert dropped == 1 and brightness == 100  # third command lost silently
    dropped, brightness = asyncio.run(scenario(0.03))
    assert dropped == 0 and brightness == 44


def test_engine_drives_fake_bulbs_over_udp():
    async def scenario():
        hosts = ("127.0.0.2", "127.0.0.3", "127.0.0.4", "127.0.0.5")
        transport, bulbs, devices = await lan_setup(hosts=hosts, gap=0.005)
        try:
            engine = LightingEngine(devices, transport, max_hz=3)
            await engine.start(StartRequest(effect="rainbow"))
            base = engine.started_at
            for offset in (0.0, 0.34, 0.68):
                await engine.step(base + offset)
            await asyncio.sleep(0.05)
            for bulb, device in zip(bulbs, devices):
                frame = engine._last_frames[device.id]
                assert bulb.color == {"r": frame.r, "g": frame.g, "b": frame.b}
                assert bulb.brightness == frame.brightness
                status = await engine.device_status(device.id)
                assert status.brightness == frame.brightness
            assert all(stats.sends == 3 for stats in engine.stats.values())
        finally:
            close_all(transport, bulbs)

    asyncio.run(scenario())


def test_benchmark_against_fake_bulb_restores_state():
    async def scenario():
        transport, bulbs, devices = await lan_setup(hosts=("127.0.0.2", "127.0.0.3"), gap=0.005)
        try:
            result = await run_benchmark(transport, devices, rate=10, duration=0.6,
                                         pattern="both")
            for summary in result["devices"]:
                assert summary["updates_sent"] >= 5
                assert summary["mismatched"] == 0
                assert summary["applied_ratio"] == 1.0
                assert summary["status_rtt_ms"]["max"] < 300
            await asyncio.sleep(0.05)
            assert all(bulb.brightness == 100 and bulb.color == {"r": 255, "g": 255, "b": 255}
                       for bulb in bulbs)
        finally:
            close_all(transport, bulbs)

    asyncio.run(scenario())


def test_benchmark_detects_silent_drops():
    async def scenario():
        transport, bulbs, devices = await lan_setup(gap=0.0, drop_burst_window=0.05)
        try:
            result = await run_benchmark(transport, devices, rate=8, duration=0.6,
                                         pattern="both", restore=False)
            summary = result["devices"][0]
            # devStatus is the third back-to-back command, so drops surface as timeouts
            # or as unapplied updates; either way the benchmark must not report success.
            assert summary["status_timeouts"] + summary["mismatched"] > 0
        finally:
            close_all(transport, bulbs)

    asyncio.run(scenario())


def test_benchmark_refuses_off_or_silent_bulb():
    async def scenario(**kwargs):
        transport, bulbs, devices = await lan_setup(**kwargs)
        if kwargs.get("respond", True):
            bulbs[0].on = False
        try:
            with pytest.raises(SystemExit) as raised:
                await run_benchmark(transport, devices, rate=3, duration=1, pattern="both")
            return str(raised.value), bulbs[0].received
        finally:
            close_all(transport, bulbs)

    message, received = asyncio.run(scenario())
    assert "reports off" in message
    assert [command for command, _ in received] == ["devStatus"]  # never powered on
    message, _ = asyncio.run(scenario(respond=False))
    assert "LAN Control" in message


def test_discovery_against_fake_responder():
    async def scenario():
        response_port = free_udp_port()
        bulb = await start_fake_bulb("127.0.0.2", 0, reply_port=response_port,
                                     mac="11:22:33:44:55:66")
        try:
            return await asyncio.to_thread(discover, 0.5, "127.0.0.1", bulb.address,
                                           response_port)
        finally:
            bulb.transport.close()

    found = asyncio.run(scenario())
    assert len(found) == 1
    assert found[0]["device"] == "11:22:33:44:55:66"
    assert found[0]["ip"] == "127.0.0.2"
    assert found[0]["sku"] == "H6004"
