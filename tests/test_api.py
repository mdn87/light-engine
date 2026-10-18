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
