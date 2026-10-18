import json

import pytest

from light_engine.config import build_engine, load_devices
from light_engine.discovery import device_id_for, merge_cache, parse_scan_reply, write_cache
from light_engine.transports import decode_message, encode_command, parse_status


def write(tmp_path, entries):
    path = tmp_path / "devices.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def test_load_devices_accepts_mac_and_rejects_bad_entries(tmp_path):
    good = {"id": "a", "name": "A", "ip": "192.168.1.5", "mac": "AA:BB"}
    assert load_devices(write(tmp_path, [good]))[0].mac == "AA:BB"
    with pytest.raises(ValueError, match="Unknown device fields"):
        load_devices(write(tmp_path, [{**good, "colour": "red"}]))
    with pytest.raises(ValueError, match="Duplicate device IPs"):
        load_devices(write(tmp_path, [good, {**good, "id": "b"}]))
    with pytest.raises(ValueError, match="private-network"):
        load_devices(write(tmp_path, [{**good, "ip": "8.8.8.8"}]))
    with pytest.raises(ValueError, match="private-network"):
        load_devices(write(tmp_path, [{"id": "a", "name": "A"}]))


def test_power_control_is_opt_in(monkeypatch):
    monkeypatch.delenv("LIGHT_ENGINE_ALLOW_POWER", raising=False)
    assert build_engine().allow_power is False
    monkeypatch.setenv("LIGHT_ENGINE_ALLOW_POWER", "1")
    assert build_engine().allow_power is True


def test_protocol_codec():
    assert decode_message(encode_command("turn", {"value": 1})) == ("turn", {"value": 1})
    for junk in (b"", b"not json", b'{"msg":1}', b'{"msg":{"cmd":"x","data":[]}}'):
        assert decode_message(junk) is None
    status = parse_status({"onOff": 0, "brightness": 5, "color": {"r": 1, "g": 2, "b": 3},
                           "colorTemInKelvin": 0})
    assert (status.on, status.brightness, status.r, status.b) == (False, 5, 1, 3)


def test_scan_reply_uses_source_ip():
    raw = encode_command("scan", {"ip": "10.0.0.9", "device": "AA:BB", "sku": "H6004"})
    parsed = parse_scan_reply(raw, "192.168.1.7")
    assert parsed["ip"] == "192.168.1.7" and parsed["reported_ip"] == "10.0.0.9"
    assert parse_scan_reply(encode_command("devStatus", {}), "192.168.1.7") is None


def test_merge_cache_keeps_ids_and_names_across_ip_changes():
    existing = [{"id": "pumpkin", "name": "Pumpkin", "mac": "aa:bb:cc:dd:ee:01",
                 "ip": "192.168.1.10", "sku": "H6004"},
                {"id": "stale", "name": "Stale", "mac": "AA:BB:CC:DD:EE:09",
                 "ip": "192.168.1.11", "sku": "H6004"}]
    found = [{"device": "AA:BB:CC:DD:EE:01", "ip": "192.168.1.11", "sku": "H6004"},
             {"device": "AA:BB:CC:DD:EE:02", "ip": "192.168.1.12", "sku": "H6004"}]
    merged = {entry["id"]: entry for entry in merge_cache(existing, found)}
    assert merged["pumpkin"]["name"] == "Pumpkin"
    assert merged["pumpkin"]["ip"] == "192.168.1.11"
    assert "ip" not in merged["stale"]  # its old IP now belongs to another bulb
    new_id = device_id_for("AA:BB:CC:DD:EE:02")
    assert new_id == "govee-aabbccddee02" and merged[new_id]["ip"] == "192.168.1.12"


def test_write_cache_output_loads_as_device_file(tmp_path):
    path = tmp_path / "devices.json"
    write_cache(path, [{"device": "AA:BB:CC:DD:EE:01", "ip": "192.168.1.20", "sku": "H6004"}])
    write_cache(path, [{"device": "AA:BB:CC:DD:EE:01", "ip": "192.168.1.21", "sku": "H6004"}])
    devices = load_devices(path)
    assert [(device.id, device.ip) for device in devices] == [("govee-aabbccddee01",
                                                                "192.168.1.21")]
