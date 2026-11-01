"""MQTT 适配器传输边界测试。"""

import json
import threading

import pytest

from app.home_automation import mqtt_adapter
from app.home_automation.default_devices import DEFAULT_DEVICE_REGISTRATIONS, DEFAULT_SENSOR_REGISTRATIONS
from app.home_automation.device_models import DeviceStateValue, DoorLockAction, SensorQuality
from app.home_automation.mqtt_adapter import (
    MqttDeviceAdapter,
    MqttTransportError,
    topic_for_door_ack,
    topic_for_door_set,
)


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


def test_ingest_smoke_telemetry_refreshes_reading_quality(monkeypatch):
    monkeypatch.setattr(mqtt_adapter, "PAHO_AVAILABLE", True)

    adapter = MqttDeviceAdapter(
        list(DEFAULT_DEVICE_REGISTRATIONS),
        list(DEFAULT_SENSOR_REGISTRATIONS),
    )
    adapter.ingest_telemetry("study", "room_node", {"sensors": {"room_smoke": 850}})

    reading = next(item for item in adapter.list_sensor_readings("study") if item.sensor_id == "room_smoke")
    assert reading.value == 850
    assert reading.quality is SensorQuality.VALID


def test_door_motion_topic_contract():
    assert topic_for_door_set("study", "door_lock") == "home/v1/study/door_lock/door/set"
    assert topic_for_door_ack("study", "door_lock") == "home/v1/study/door_lock/door/ack"


class _PublishResult:
    rc = 0

    def wait_for_publish(self, timeout):
        return None


class _DoorPublishClient:
    def __init__(self, adapter):
        self.adapter = adapter
        self.topic = None
        self.payload = None

    def publish(self, topic, payload, qos):
        self.topic = topic
        self.payload = payload
        command = json.loads(payload)
        self.adapter.ingest_door_ack(
            "study",
            "door_lock",
            {
                "request_id": command["request_id"],
                "action": command["action"],
                "accepted": True,
                "ack_status": "success",
                "message": "ack",
            },
        )
        return _PublishResult()


def test_mqtt_door_motion_publishes_and_waits_for_ack(monkeypatch):
    monkeypatch.setattr(mqtt_adapter, "PAHO_AVAILABLE", True)
    adapter = MqttDeviceAdapter(
        list(DEFAULT_DEVICE_REGISTRATIONS),
        list(DEFAULT_SENSOR_REGISTRATIONS),
    )
    client = _DoorPublishClient(adapter)
    adapter._client = client
    adapter._connected = True

    from uuid import uuid4

    result = adapter.execute_door_motion(
        "door_lock",
        DoorLockAction.OPEN_DOOR,
        request_id=uuid4(),
        expires_at=None,
    )

    assert result.accepted is True
    assert result.action is DoorLockAction.OPEN_DOOR
    assert client.topic == "home/v1/study/door_lock/door/set"
    assert json.loads(client.payload)["action"] == "open_door"


def test_ingest_ack_ignores_mismatched_device_or_room(monkeypatch):
    monkeypatch.setattr(mqtt_adapter, "PAHO_AVAILABLE", True)
    adapter = MqttDeviceAdapter(
        list(DEFAULT_DEVICE_REGISTRATIONS),
        list(DEFAULT_SENSOR_REGISTRATIONS),
    )
    from uuid import uuid4

    request_id = uuid4()
    event = threading.Event()
    request_key = str(request_id)
    adapter._pending_acks[request_key] = event
    adapter._pending_ack_targets[request_key] = ("study", "desk_light")

    adapter.ingest_ack(
        "study",
        "desk_fan",
        {
            "request_id": request_key,
            "accepted": True,
            "state": DeviceStateValue.ON.value,
            "message": "unexpected device ack",
        },
    )

    assert request_key not in adapter._ack_payloads
    assert not event.is_set()


def test_ingest_door_ack_ignores_mismatched_action_or_device(monkeypatch):
    monkeypatch.setattr(mqtt_adapter, "PAHO_AVAILABLE", True)
    adapter = MqttDeviceAdapter(
        list(DEFAULT_DEVICE_REGISTRATIONS),
        list(DEFAULT_SENSOR_REGISTRATIONS),
    )
    from uuid import uuid4

    request_id = uuid4()
    event = threading.Event()
    request_key = str(request_id)
    adapter._pending_door_acks[request_key] = event
    adapter._pending_door_ack_targets[request_key] = (
        "study",
        "door_lock",
        DoorLockAction.OPEN_DOOR,
    )

    adapter.ingest_door_ack(
        "study",
        "desk_light",
        {
            "request_id": request_key,
            "action": DoorLockAction.CLOSE_DOOR.value,
            "accepted": True,
            "ack_status": "success",
            "message": "unexpected door ack",
        },
    )

    assert request_key not in adapter._door_ack_payloads
    assert not event.is_set()
