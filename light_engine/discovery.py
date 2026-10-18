"""One-shot Govee LAN discovery. Run from a trusted local network.

Read-only: sends one multicast scan and listens for replies; never changes device state.

    python -m light_engine.discovery [--interface 192.168.1.20] [--write devices.json]

``--write`` merges results into a device file usable as LIGHT_ENGINE_DEVICES_FILE. Device
IDs derive from the MAC, so they stay stable when DHCP hands out a new IP; existing
names and IDs for known MACs are preserved.
"""
import argparse
import json
import os
import socket
import time
from pathlib import Path

from .transports import RESPONSE_PORT, decode_message, encode_command

MULTICAST = ("239.255.255.250", 4001)


def parse_scan_reply(raw: bytes, source_ip: str) -> dict | None:
    decoded = decode_message(raw)
    if decoded is None or decoded[0] != "scan":
        return None
    device = dict(decoded[1])
    # Trust the packet source over the self-reported field; note any disagreement.
    if device.get("ip") not in (None, source_ip):
        device["reported_ip"] = device["ip"]
    device["ip"] = source_ip
    return device


def discover(timeout: float = 4.0, interface: str | None = None,
             target: tuple[str, int] = MULTICAST, response_port: int = RESPONSE_PORT) -> list[dict]:
    """Listen on UDP 4002 for replies to one scan on 4001; no device changes."""
    seen: dict[str, dict] = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((interface or "", response_port))
        listener.settimeout(0.3)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            sender.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            if interface:
                sender.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF,
                                  socket.inet_aton(interface))
            sender.sendto(encode_command("scan", {"account_topic": "reserve"}), target)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                raw, address = listener.recvfrom(4096)
            except TimeoutError:
                continue
            device = parse_scan_reply(raw, address[0])
            if device is not None:
                seen[device.get("device") or address[0]] = device
    return list(seen.values())


def device_id_for(mac: str) -> str:
    return "govee-" + "".join(ch for ch in mac.lower() if ch.isalnum())


def merge_cache(existing: list[dict], found: list[dict]) -> list[dict]:
    """Merge scan results into a device list keyed by MAC, keeping user-chosen id/name."""
    merged = [dict(entry) for entry in existing]
    by_mac = {entry["mac"].upper(): entry for entry in merged if entry.get("mac")}
    for device in found:
        mac = device.get("device")
        if not mac:
            continue
        entry = by_mac.get(mac.upper())
        if entry is None:
            sku = device.get("sku", "H6004")
            entry = {"id": device_id_for(mac), "name": f"{sku} {mac[-5:]}", "mac": mac}
            merged.append(entry)
            by_mac[mac.upper()] = entry
        entry["ip"] = device["ip"]
        entry["sku"] = device.get("sku", entry.get("sku", "H6004"))
    # A reassigned IP may now collide with a stale entry that was not seen this scan.
    fresh = {device["ip"] for device in found if device.get("device")}
    seen_macs = {device["device"].upper() for device in found if device.get("device")}
    for entry in merged:
        if entry.get("ip") in fresh and (entry.get("mac") or "").upper() not in seen_macs:
            entry.pop("ip")
    return merged


def write_cache(path: Path, found: list[dict]) -> list[dict]:
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    merged = merge_cache(existing, found)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return merged


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Read-only Govee LAN scan")
    parser.add_argument("--timeout", type=float, default=4.0)
    parser.add_argument("--interface", help="local IPv4 address to scan from")
    parser.add_argument("--write", type=Path, help="merge results into this device file")
    args = parser.parse_args(argv)
    found = discover(args.timeout, args.interface)
    print(json.dumps(found, indent=2))
    if args.write:
        merged = write_cache(args.write, found)
        missing_ip = [entry["id"] for entry in merged if not entry.get("ip")]
        print(f"Wrote {len(merged)} device(s) to {args.write}")
        if missing_ip:
            print(f"Without a current IP (fix before LAN mode): {', '.join(missing_ip)}")


if __name__ == "__main__":
    main()
