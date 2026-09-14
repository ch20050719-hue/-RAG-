"""MQTT 适配器传输边界测试。"""

import pytest

from app.home_automation import mqtt_adapter
from app.home_automation.default_devices import DEFAULT_DEVICE_REGISTRATIONS
from app.home_automation.mqtt_adapter import MqttDeviceAdapter, MqttTransportError


class _RejectedClient:
    def __init__(self, **kwargs):
        self.on_connect = None
        self.on_message = None

    def connect(self, host, port, keepalive):
        return 5

    def loop_start(self):
        raise AssertionError("rejected connection must not start loop")


class _RejectedMqtt:
    Client = _RejectedClient


def test_connect_rejects_broker_return_code(monkeypatch):
    monkeypatch.setattr(mqtt_adapter, "mqtt", _RejectedMqtt)
    monkeypatch.setattr(mqtt_adapter, "PAHO_AVAILABLE", True)

    adapter = MqttDeviceAdapter(list(DEFAULT_DEVICE_REGISTRATIONS))

    with pytest.raises(MqttTransportError, match="return code 5"):
        adapter.connect()
