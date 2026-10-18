"""One-shot Govee LAN discovery. Run from a trusted local network."""
import json
import socket
import time

MULTICAST = ("239.255.255.250", 4001)


def discover(timeout: float = 4.0) -> list[dict]:
    """Listen on UDP 4002 for replies to scan on 4001; no device changes."""
    seen: dict[str, dict] = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("", 4002))
        listener.settimeout(0.3)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            sender.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            payload = {"msg": {"cmd": "scan", "data": {"account_topic": "reserve"}}}
            sender.sendto(json.dumps(payload).encode("utf-8"), MULTICAST)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                raw, address = listener.recvfrom(4096)
                parsed = json.loads(raw)
                if parsed.get("msg", {}).get("cmd") == "scan":
                    device = parsed["msg"]["data"]
                    device["ip"] = address[0]
                    seen[device.get("device", address[0])] = device
            except (socket.timeout, ValueError, KeyError, TypeError):
                continue
    return list(seen.values())


if __name__ == "__main__":
    print(json.dumps(discover(), indent=2))
