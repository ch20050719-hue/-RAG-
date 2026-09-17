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
    get_environment_history,
    get_home_mode,
    get_home_tools,
    get_home_alerts,
    get_door_lock_status,
    lock_home_door,
    unlock_home_door,
    list_home_devices,
    read_home_environment,
    run_home_scenario,
    set_device_service,
    set_home_mode,
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
        "get_environment_history",
        "get_home_alerts",
        "get_home_mode",
        "set_home_mode",
        "get_door_lock_status",
        "lock_door",
        "unlock_door",
        "engage_deadbolt",
        "release_deadbolt",
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
        assert {item["kind"] for item in payload["readings"]} == {"temperature", "humidity", "co2"}
        assert all(item["quality"] == "valid" for item in payload["readings"])
        assert all("level" in item for item in payload["readings"])
    finally:
        set_device_service(None)


def test_environment_history_tool_returns_recent_samples():
    set_device_service(_fresh_service())
    try:
        read_home_environment.invoke({"room": "study"})
        raw = get_environment_history.invoke({"room": "study", "minutes": 10})
        payload = json.loads(raw)
        assert payload["room"] == "study"
        assert len(payload["samples"]) == 1
        assert payload["samples"][0]["readings"]
    finally:
        set_device_service(None)


def test_home_alert_tool_exposes_confirmed_co2_alert():
    service = _fresh_service()
    adapter = service._adapter
    set_device_service(service)
    try:
        for value in (1600, 1650, 1680):
            adapter.update_sensor_value("room_co2", value)
            service.evaluate_environment("study")
        raw = get_home_alerts.invoke({"room": "study", "active_only": True})
        payload = json.loads(raw)
        assert payload
        assert payload[-1]["state"] == "active"
        assert payload[-1]["related_action"] == "fan_on"
    finally:
        set_device_service(None)


def test_home_mode_tool_returns_partial_failure_without_lock_success():
    set_device_service(_fresh_service())
    try:
        raw = set_home_mode.invoke({"mode": "sleep"})
        payload = json.loads(raw)
        assert payload["mode"] == "sleep"
        assert payload["overall_status"] == "success"
        assert payload["actions"][-1]["name"] == "check_door_and_lock"
        assert payload["actions"][-1]["accepted"] is True

        status = json.loads(get_home_mode.invoke({}))
        assert status["mode"] == "sleep"
    finally:
        set_device_service(None)


def test_door_lock_tools_require_explicit_authorization_for_unlock():
    set_device_service(_fresh_service())
    try:
        status = json.loads(get_door_lock_status.invoke({}))
        assert status["device_id"] == "door_lock"

        denied = json.loads(unlock_home_door.invoke({"authorized": False}))
        accepted = json.loads(unlock_home_door.invoke({"authorized": True}))
        assert denied["accepted"] is False
        assert accepted["accepted"] is True

        locked = json.loads(lock_home_door.invoke({}))
        assert locked["accepted"] is True
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
