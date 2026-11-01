"""最终版本三功能需求的行为测试。"""

from app.home_automation.default_devices import DEFAULT_DEVICE_REGISTRATIONS, DEFAULT_SENSOR_REGISTRATIONS
from app.home_automation.device_models import (
    AutomationMode,
    DeviceStateValue,
    DeviceType,
    SensorKind,
    ThresholdName,
)
from app.home_automation.device_tools import (
    create_device_service,
    get_home_tools,
    set_alarm_buzzer_state,
    set_device_service,
    set_sprinkler_pump_state,
)


def test_default_registry_matches_final_sensor_and_actuator_scope():
    assert {item.device_id for item in DEFAULT_DEVICE_REGISTRATIONS} == {
        "desk_light",
        "desk_fan",
        "sprinkler_pump",
        "alarm_buzzer",
        "door_lock",
    }
    assert {item.device_type for item in DEFAULT_DEVICE_REGISTRATIONS} == {
        DeviceType.LIGHT,
        DeviceType.FAN,
        DeviceType.WATER_PUMP,
        DeviceType.BUZZER,
        DeviceType.DOOR_LOCK,
    }
    assert {item.sensor_id for item in DEFAULT_SENSOR_REGISTRATIONS} == {
        "room_temp",
        "room_humidity",
        "room_smoke",
        "room_flame",
        "room_presence",
    }
    assert {item.kind for item in DEFAULT_SENSOR_REGISTRATIONS} == {
        SensorKind.TEMPERATURE,
        SensorKind.HUMIDITY,
        SensorKind.SMOKE,
        SensorKind.FLAME,
        SensorKind.PRESENCE,
    }


def test_final_thresholds_exclude_removed_illuminance_threshold():
    assert {item.value for item in ThresholdName} == {
        "temperature_max",
        "humidity_max",
        "smoke_max",
    }


def test_home_tools_exclude_removed_window_and_old_mode_controls_but_keep_scene_presets():
    names = {item.name for item in get_home_tools()}

    assert "set_window_state" not in names
    assert "get_home_mode" not in names
    assert "set_home_mode" not in names
    assert "run_home_scenario" in names


def test_automatic_temperature_rule_starts_fan_and_buzzer():
    service = create_device_service(mode="simulated")
    service.set_automation_mode(AutomationMode.AUTOMATIC)
    service._adapter.update_sensor_value("room_temp", 40.0)

    for _ in range(3):
        service.evaluate_environment()

    assert service.get_device("desk_fan").state is DeviceStateValue.ON
    assert service.get_device("alarm_buzzer").state is DeviceStateValue.ON


def test_automatic_smoke_rule_starts_fan_and_buzzer():
    service = create_device_service(mode="simulated")
    service.set_automation_mode(AutomationMode.AUTOMATIC)
    service._adapter.update_sensor_value("room_smoke", 900.0)

    for _ in range(3):
        service.evaluate_environment()

    assert service.get_device("desk_fan").state is DeviceStateValue.ON
    assert service.get_device("alarm_buzzer").state is DeviceStateValue.ON


def test_automatic_flame_rule_starts_pump_and_buzzer():
    service = create_device_service(mode="simulated")
    service.set_automation_mode(AutomationMode.AUTOMATIC)
    service._adapter.update_sensor_value("room_flame", 1.0)

    for _ in range(3):
        service.evaluate_environment()

    assert service.get_device("sprinkler_pump").state is DeviceStateValue.ON
    assert service.get_device("alarm_buzzer").state is DeviceStateValue.ON


def test_automatic_presence_rule_starts_led_without_alarm_buzzer():
    service = create_device_service(mode="simulated")
    service.set_automation_mode(AutomationMode.AUTOMATIC)
    service._adapter.update_sensor_value("room_presence", 1.0)

    for _ in range(3):
        service.evaluate_environment()

    assert service.get_device("desk_light").state is DeviceStateValue.ON
    assert service.get_device("alarm_buzzer").state is DeviceStateValue.OFF


def test_manual_mode_does_not_apply_automatic_actions():
    service = create_device_service(mode="simulated")
    service._adapter.update_sensor_value("room_flame", 1.0)

    for _ in range(3):
        service.evaluate_environment()

    assert service.get_device("sprinkler_pump").state is DeviceStateValue.OFF
    assert service.get_device("alarm_buzzer").state is DeviceStateValue.OFF


def test_manual_tools_control_pump_and_buzzer_through_fixed_endpoints():
    service = create_device_service(mode="simulated")
    set_device_service(service)

    try:
        pump = set_sprinkler_pump_state.invoke({"state": "on"})
        buzzer = set_alarm_buzzer_state.invoke({"state": "on"})

        assert '"accepted": true' in pump
        assert '"accepted": true' in buzzer
        assert service.get_device("sprinkler_pump").state is DeviceStateValue.ON
        assert service.get_device("alarm_buzzer").state is DeviceStateValue.ON
    finally:
        set_device_service(None)
