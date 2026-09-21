"""正常、睡眠、离家场景预设的行为测试。"""

import json

from app.home_automation.device_models import (
    AutomationMode,
    DeviceStateValue,
    DoorState,
    HomeScenarioName,
)
from app.home_automation.device_tools import create_device_service, run_home_scenario


def test_scene_presets_are_distinct_from_manual_automatic_control_mode():
    assert {item.value for item in HomeScenarioName} == {"normal", "sleep", "away"}

    service = create_device_service(mode="simulated")
    service.set_automation_mode(AutomationMode.AUTOMATIC)
    result = service.run_scenario(HomeScenarioName.NORMAL)

    assert result.accepted is True
    assert result.scene is HomeScenarioName.NORMAL
    assert service.get_automation_mode() is AutomationMode.AUTOMATIC


def test_sleep_scene_turns_off_light_and_engages_deadbolt():
    service = create_device_service(mode="simulated")
    service.set_door_state(DoorState.CLOSED)
    service.set_switch_state("desk_light", DeviceStateValue.ON)

    result = service.run_scenario(HomeScenarioName.SLEEP)

    assert result.accepted is True
    assert service.get_device("desk_light").state is DeviceStateValue.OFF
    assert service.get_door_lock().deadbolt_state.value == "engaged"


def test_away_scene_turns_off_light_and_fan_then_locks_door():
    service = create_device_service(mode="simulated")
    service.set_door_state(DoorState.CLOSED)
    service.set_switch_state("desk_light", DeviceStateValue.ON)
    service.set_switch_state("desk_fan", DeviceStateValue.ON)

    result = service.run_scenario(HomeScenarioName.AWAY)

    assert result.accepted is True
    assert service.get_device("desk_light").state is DeviceStateValue.OFF
    assert service.get_device("desk_fan").state is DeviceStateValue.OFF
    assert service.get_door_lock().lock_state.value == "locked"


def test_scene_door_action_failure_is_reported_and_does_not_claim_success():
    service = create_device_service(mode="simulated")
    service.set_door_state(DoorState.OPEN)

    result = service.run_scenario(HomeScenarioName.SLEEP)

    assert result.accepted is False
    assert result.overall_status == "partial_failed"
    assert service.get_door_lock().deadbolt_state.value == "released"


def test_scene_tool_exposes_only_three_presets():
    raw = run_home_scenario.invoke({"scenario": "away"})

    payload = json.loads(raw)
    assert payload["scene"] == "away"
    assert payload["accepted"] is True


def test_sleep_scene_allows_light_fan_buzzer_but_blocks_manual_pump():
    service = create_device_service(mode="simulated")
    service.run_scenario(HomeScenarioName.SLEEP)

    light = service.set_switch_state("desk_light", DeviceStateValue.ON)
    pump = service.set_pump_state(DeviceStateValue.ON)
    buzzer = service.set_buzzer_state(DeviceStateValue.ON)

    assert light.accepted is True
    assert pump.accepted is False
    assert "sleep" in pump.blocked_reason.lower()
    assert buzzer.accepted is True


def test_away_scene_allows_pump_buzzer_but_blocks_manual_light_and_fan():
    service = create_device_service(mode="simulated")
    service.run_scenario(HomeScenarioName.AWAY)

    light = service.set_switch_state("desk_light", DeviceStateValue.ON)
    fan = service.set_switch_state("desk_fan", DeviceStateValue.ON)
    pump = service.set_pump_state(DeviceStateValue.ON)

    assert light.accepted is False
    assert fan.accepted is False
    assert pump.accepted is True


def test_sleep_and_away_block_manual_mode_and_threshold_changes():
    service = create_device_service(mode="simulated")

    service.run_scenario(HomeScenarioName.SLEEP)
    try:
        service.set_automation_mode(AutomationMode.AUTOMATIC)
    except ValueError as exc:
        assert "sleep" in str(exc).lower()
    else:
        raise AssertionError("sleep scene must block manual mode switching")

    service.run_scenario(HomeScenarioName.AWAY)
    try:
        service.set_threshold("smoke_max", 700)
    except ValueError as exc:
        assert "away" in str(exc).lower()
    else:
        raise AssertionError("away scene must block manual threshold changes")
