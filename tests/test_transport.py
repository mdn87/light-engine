import asyncio
import json
from unittest.mock import Mock

from light_engine.models import Device, Frame
from light_engine.transports import GoveeLanTransport


def test_protocol_payloads():
    transport = GoveeLanTransport(command_gap_seconds=0)
    try:
        fake_socket = Mock()
        transport.socket.close()
        transport.socket = fake_socket
        asyncio.run(transport.apply(Device("one", "Test", ip="192.168.1.10"),
                                    Frame(255, 64, 0, 40), None))
        sent = [json.loads(call.args[0])["msg"] for call in fake_socket.sendto.call_args_list]
        assert [entry["cmd"] for entry in sent] == ["colorwc", "brightness"]
        assert sent[0]["data"]["colorTemInKelvin"] == 0
        assert sent[1]["data"]["value"] == 40
    finally:
        transport.close()
