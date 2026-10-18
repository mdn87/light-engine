from fastapi.testclient import TestClient

from light_engine.api import make_app
from light_engine.engine import LightingEngine
from light_engine.models import Device
from light_engine.transports import SimulationTransport


def test_api_simulation_roundtrip():
    engine = LightingEngine([Device("bulb-1", "Test")], SimulationTransport())
    with TestClient(make_app(engine)) as client:
        assert client.get("/health").json()["ok"] is True
        assert client.get("/api/devices").json()[0]["id"] == "bulb-1"
        response = client.post("/api/playback/start", json={
            "effect": "pulse", "device_ids": ["bulb-1"], "brightness": 70
        })
        assert response.status_code == 200
        assert response.json()["running"] is True
        assert client.get("/api/playback").json()["running"] is True
        assert client.post("/api/playback/stop").json()["running"] is False


def test_api_rejects_unknown_target():
    engine = LightingEngine([Device("bulb-1", "Test")], SimulationTransport())
    with TestClient(make_app(engine)) as client:
        response = client.post("/api/playback/start", json={"device_ids": ["missing"]})
        assert response.status_code == 400


def test_api_power_status_and_diagnostics():
    transport = SimulationTransport()
    engine = LightingEngine([Device("bulb-1", "Test")], transport)
    with TestClient(make_app(engine)) as client:
        assert client.get("/health").json()["power_control"] is False
        assert client.post("/api/devices/bulb-1/power", json={"on": True}).status_code == 403
        assert transport.power == {}
        engine.allow_power = True
        assert client.post("/api/devices/bulb-1/power", json={"on": False}).json()["on"] is False
        assert client.get("/api/devices/bulb-1/status").json()["on"] is False
        assert client.post("/api/devices/missing/power", json={"on": True}).status_code == 404
        assert client.get("/api/devices/missing/status").status_code == 404
        client.post("/api/playback/start", json={"device_ids": ["bulb-1"]})
        assert client.post("/api/devices/bulb-1/power", json={"on": True}).status_code == 409
        diagnostics = client.get("/api/diagnostics").json()
        assert diagnostics["running"] is True and "bulb-1" in diagnostics["devices"]


def test_api_status_timeout_maps_to_504():
    class SilentTransport(SimulationTransport):
        async def request_status(self, device, timeout=None):
            raise TimeoutError("No devStatus reply from bulb-1")

    engine = LightingEngine([Device("bulb-1", "Test")], SilentTransport())
    with TestClient(make_app(engine)) as client:
        assert client.get("/api/devices/bulb-1/status").status_code == 504
