"""智能家居 Agent 工具与 MQTT 契约测试。"""

import json
from datetime import datetime, timezone
from uuid import uuid4

from app.home_automation.default_devices import (
    DEFAULT_DEVICE_REGISTRATIONS,
    DEFAULT_SENSOR_REGISTRATIONS,
)
from app.home_automation.device_models import (
    DeviceCommand,
    DeviceRegistration,
    DeviceStateValue,
    DeviceType,
    SensorKind,
    SensorRegistration,
)
from app.home_automation.device_service import DeviceService
from app.home_automation.device_tools import (
    get_device_service,
    get_home_tools,
    list_home_devices,
    read_home_environment,
    run_home_scenario,
    set_device_service,
    set_light_state,
)
from app.home_automation.mqtt_adapter import (
    topic_for_state_ack,
    topic_for_state_set,
    topic_for_telemetry,
)
from app.home_automation.simulated_device import SimulatedDeviceAdapter


def _fresh_service() -> DeviceService:
    adapter = SimulatedDeviceAdapter(
        registrations=list(DEFAULT_DEVICE_REGISTRATIONS),
        sensor_registrations=list(DEFAULT_SENSOR_REGISTRATIONS),
    )
    return DeviceService(adapter=adapter)


def test_home_tools_are_registered():
    names = {item.name for item in get_home_tools()}
    assert {
        "get_device_status",
        "list_home_devices",
        "read_home_environment",
        "set_light_state",
        "set_fan_state",
        "run_home_scenario",
    } <= names


def test_list_home_devices_tool_returns_json():
    set_device_service(_fresh_service())
    try:
        raw = list_home_devices.invoke({})
        payload = json.loads(raw)
        assert isinstance(payload, list)
        assert any(item["device_id"] == "desk_light" for item in payload)
    finally:
        set_device_service(None)


def test_set_light_state_tool_rejects_invalid_state():
    set_device_service(_fresh_service())
    try:
        raw = set_light_state.invoke({"device_id": "desk_light", "state": "maybe"})
        payload = json.loads(raw)
        assert payload["accepted"] is False
    finally:
        set_device_service(None)


def test_light_tool_rejects_a_fan_device():
    set_device_service(_fresh_service())
    try:
        raw = set_light_state.invoke({"device_id": "desk_fan", "state": "on"})
        payload = json.loads(raw)
        assert payload["accepted"] is False
        assert "type" in payload["blocked_reason"].lower()
    finally:
        set_device_service(None)


def test_run_home_scenario_tool_sleep():
    set_device_service(_fresh_service())
    try:
        service = get_device_service()
        service.set_device_state("desk_light", DeviceStateValue.ON)
        raw = run_home_scenario.invoke({"scenario": "sleep"})
        payload = json.loads(raw)
        assert payload["accepted"] is True
        assert service.get_device("desk_light").state is DeviceStateValue.OFF
    finally:
        set_device_service(None)


def test_read_environment_tool_includes_source():
    set_device_service(_fresh_service())
    try:
        raw = read_home_environment.invoke({"room": "study"})
        payload = json.loads(raw)
        assert payload["room"] == "study"
        assert payload["readings"]
        assert payload["readings"][0]["source"] == "simulated"
    finally:
        set_device_service(None)


def test_mqtt_topic_contract():
    assert topic_for_state_set("study", "desk_light") == "home/v1/study/desk_light/state/set"
    assert topic_for_state_ack("study", "desk_light") == "home/v1/study/desk_light/state/ack"
    assert topic_for_telemetry("study", "desk_light") == "home/v1/study/desk_light/telemetry"


def test_mqtt_adapter_requires_paho_or_uses_simulated():
    # 在无 paho 环境中应明确失败；若已安装 paho，则至少可构造
    try:
        from app.home_automation.mqtt_adapter import MqttDeviceAdapter, PAHO_AVAILABLE
    except Exception:
        return

    if not PAHO_AVAILABLE:
        import pytest

        from app.home_automation.mqtt_adapter import MqttTransportError

        with pytest.raises(MqttTransportError):
            MqttDeviceAdapter(registrations=[DeviceRegistration(
                device_id="desk_light",
                room="study",
                device_type=DeviceType.LIGHT,
            )])
    else:
        adapter = MqttDeviceAdapter(
            registrations=[
                DeviceRegistration(device_id="desk_light", room="study", device_type=DeviceType.LIGHT)
            ],
            sensor_registrations=[
                SensorRegistration(sensor_id="room_temp", room="study", kind=SensorKind.TEMPERATURE)
            ],
        )
        assert adapter.read_state("desk_light").device_id == "desk_light"


def test_simulated_adapter_ingest_path_for_command():
    adapter = SimulatedDeviceAdapter(
        registrations=[
            DeviceRegistration(device_id="desk_light", room="study", device_type=DeviceType.LIGHT)
        ]
    )
    request_id = uuid4()
    result = adapter.send_command(
        DeviceCommand(
            request_id=request_id,
            device_id="desk_light",
            action="set_state",
            state=DeviceStateValue.ON,
        )
    )
    assert result.accepted is True
    assert adapter.read_state("desk_light").updated_at <= datetime.now(timezone.utc)
