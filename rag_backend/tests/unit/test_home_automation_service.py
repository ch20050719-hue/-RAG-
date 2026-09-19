"""智能家居设备服务与安全规则单元测试。"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.home_automation.default_devices import (
    DEFAULT_DEVICE_REGISTRATIONS,
    DEFAULT_SENSOR_REGISTRATIONS,
)
from app.home_automation.device_models import (
    AlertState,
    AutomationMode,
    DeviceCommand,
    DeviceType,
    DeviceStateValue,
    DoorLockAction,
    DoorState,
    HomeModeName,
    HomeScenarioName,
    ModeExecutionStatus,
    ThresholdName,
)
from app.home_automation.device_service import DeviceService
from app.home_automation.safety_rules import evaluate_control_risk, validate_command_shape
from app.home_automation.simulated_device import SimulatedDeviceAdapter


@pytest.fixture()
def service() -> DeviceService:
    adapter = SimulatedDeviceAdapter(
        registrations=list(DEFAULT_DEVICE_REGISTRATIONS),
        sensor_registrations=list(DEFAULT_SENSOR_REGISTRATIONS),
    )
    return DeviceService(adapter=adapter)


def test_list_devices_contains_default_desk_devices(service: DeviceService):
    ids = {item.device_id for item in service.list_devices()}
    assert {"desk_light", "desk_fan"} <= ids


def test_set_light_on_returns_accepted_receipt(service: DeviceService):
    result = service.set_device_state("desk_light", DeviceStateValue.ON, request_id=str(uuid4()))

    assert result.accepted is True
    assert service.get_device("desk_light").state is DeviceStateValue.ON


def test_unknown_device_control_is_blocked(service: DeviceService):
    result = service.set_device_state("missing_light", DeviceStateValue.ON)

    assert result.accepted is False
    assert result.blocked_reason
    assert "not registered" in result.blocked_reason.lower()


def test_environment_snapshot_contains_version_three_sensors(service: DeviceService):
    snapshot = service.get_environment("study")

    kinds = {reading.kind.value for reading in snapshot.readings}
    assert kinds == {"temperature", "humidity", "illuminance", "smoke"}


def test_environment_snapshot_exposes_smoke_quality_and_level(service: DeviceService):
    snapshot = service.get_environment("study")

    smoke = next(reading for reading in snapshot.readings if reading.sensor_id == "room_smoke")

    assert smoke.value == 120
    assert smoke.unit == "raw"
    assert smoke.quality.value == "valid"
    assert smoke.level.value == "normal"


def test_automatic_mode_turns_on_fan_after_confirmed_smoke_alert():
    adapter = SimulatedDeviceAdapter(
        registrations=list(DEFAULT_DEVICE_REGISTRATIONS),
        sensor_registrations=list(DEFAULT_SENSOR_REGISTRATIONS),
    )
    service = DeviceService(adapter=adapter)
    service.set_automation_mode(AutomationMode.AUTOMATIC)

    alerts = []
    for value in (850, 900, 950):
        adapter.update_sensor_value("room_smoke", value)
        alerts = service.evaluate_environment("study")

    assert any(alert.state is AlertState.ACTIVE for alert in alerts)
    assert service.get_device("desk_fan").state is DeviceStateValue.ON


def test_manual_mode_keeps_alerts_but_does_not_override_devices(service: DeviceService):
    adapter = service._adapter
    for value in (850, 900, 950):
        adapter.update_sensor_value("room_smoke", value)
        service.evaluate_environment("study")

    assert service.get_automation_mode() is AutomationMode.MANUAL
    assert service.get_device("desk_fan").state is DeviceStateValue.OFF


def test_generic_switch_control_rejects_door_lock(service: DeviceService):
    result = service.set_switch_state("door_lock", DeviceStateValue.ON)
    low_level_result = service.set_device_state("door_lock", DeviceStateValue.ON)

    assert result.accepted is False
    assert low_level_result.accepted is False
    assert "type" in (result.blocked_reason or "").lower()
    assert "dedicated" in (low_level_result.blocked_reason or "").lower()


def test_window_and_thresholds_are_typed_and_validated(service: DeviceService):
    opened = service.set_window_state(DeviceStateValue.OPEN)
    changed = service.set_threshold(ThresholdName.SMOKE_MAX, 700)

    assert opened.accepted is True
    assert service.get_device("window_motor").state is DeviceStateValue.OPEN
    assert changed.smoke_max == 700
    with pytest.raises(ValueError, match="range"):
        service.set_threshold(ThresholdName.HUMIDITY_MAX, 101)


def test_automation_mode_does_not_replace_sleep_or_away_profile(service: DeviceService):
    service.set_automation_mode(AutomationMode.AUTOMATIC)
    service.set_mode(HomeModeName.SLEEP)

    assert service.get_automation_mode() is AutomationMode.AUTOMATIC
    assert service.get_mode() is HomeModeName.SLEEP


def test_normal_mode_is_an_explicit_successful_state_transition(service: DeviceService):
    result = service.set_mode(HomeModeName.NORMAL)

    assert result.accepted is True
    assert result.overall_status is ModeExecutionStatus.SUCCESS
    assert service.get_mode() is HomeModeName.NORMAL


def test_sleep_mode_closes_light_and_engages_deadbolt(service: DeviceService):
    service.set_device_state("desk_light", DeviceStateValue.ON)

    result = service.set_mode(HomeModeName.SLEEP)

    assert result.accepted is True
    assert result.overall_status is ModeExecutionStatus.SUCCESS
    assert [action.name for action in result.actions] == ["turn_off_light", "check_door_and_lock"]
    assert result.actions[0].accepted is True
    assert result.actions[1].accepted is True
    assert service.get_device("desk_light").state is DeviceStateValue.OFF
    assert service.get_mode() is HomeModeName.SLEEP
    assert service.get_door_lock().deadbolt_state.value == "engaged"


def test_away_mode_closes_light_and_fan_before_lock_step(service: DeviceService):
    service.set_device_state("desk_light", DeviceStateValue.ON)
    service.set_device_state("desk_fan", DeviceStateValue.ON)

    result = service.set_mode(HomeModeName.AWAY)

    assert result.accepted is True
    assert result.overall_status is ModeExecutionStatus.SUCCESS
    assert [action.name for action in result.actions] == [
        "turn_off_light",
        "turn_off_fan",
        "check_door_and_lock",
    ]
    assert service.get_device("desk_light").state is DeviceStateValue.OFF
    assert service.get_device("desk_fan").state is DeviceStateValue.OFF
    assert service.get_door_lock().latch_state.value == "locked"


def test_door_lock_rejects_lock_when_door_is_open(service: DeviceService):
    service.set_door_state(DoorState.OPEN)

    result = service.command_door_lock(DoorLockAction.LOCK)

    assert result.accepted is False
    assert "open" in result.message.lower()
    assert service.get_door_lock().latch_state.value == "unlocked"


def test_door_lock_requires_authorization_for_remote_unlock(service: DeviceService):
    denied = service.command_door_lock(DoorLockAction.UNLOCK)
    accepted = service.command_door_lock(DoorLockAction.UNLOCK, authorized=True)

    assert denied.accepted is False
    assert "authorization" in denied.message.lower()
    assert accepted.accepted is True


def test_servo_door_actions_open_and_close_the_door(service: DeviceService):
    service.command_door_lock(DoorLockAction.UNLOCK, authorized=True)

    opened = service.command_door_lock(DoorLockAction.OPEN_DOOR, authorized=True)

    assert opened.accepted is True
    assert opened.action is DoorLockAction.OPEN_DOOR
    assert opened.door_state is DoorState.OPEN
    assert service.get_door_lock().door_state is DoorState.OPEN

    closed = service.command_door_lock(DoorLockAction.CLOSE_DOOR, authorized=True)

    assert closed.accepted is True
    assert closed.action is DoorLockAction.CLOSE_DOOR
    assert closed.door_state is DoorState.CLOSED
    assert service.get_door_lock().door_state is DoorState.CLOSED


def test_servo_door_open_requires_authorization(service: DeviceService):
    result = service.command_door_lock(DoorLockAction.OPEN_DOOR)

    assert result.accepted is False
    assert "authorization" in result.message.lower()


def test_servo_door_open_is_blocked_until_the_latch_is_unlocked(service: DeviceService):
    service.command_door_lock(DoorLockAction.LOCK)

    result = service.command_door_lock(DoorLockAction.OPEN_DOOR, authorized=True)

    assert result.accepted is False
    assert "unlock" in result.message.lower()
    assert service.get_door_lock().door_state is DoorState.CLOSED


def test_releasing_deadbolt_requires_authorization_and_second_confirmation(service: DeviceService):
    service.command_door_lock(DoorLockAction.ENGAGE_DEADBOLT)

    denied = service.command_door_lock(DoorLockAction.RELEASE_DEADBOLT, authorized=True)
    accepted = service.command_door_lock(
        DoorLockAction.RELEASE_DEADBOLT,
        authorized=True,
        confirmed=True,
    )

    assert denied.accepted is False
    assert "confirmation" in denied.message.lower()
    assert accepted.accepted is True
    assert service.get_door_lock().deadbolt_state.value == "released"


def test_sleep_scenario_turns_off_light_and_fan(service: DeviceService):
    service.set_device_state("desk_light", DeviceStateValue.ON)
    service.set_device_state("desk_fan", DeviceStateValue.ON)

    result = service.run_scenario(HomeScenarioName.SLEEP)

    assert result.accepted is True
    assert service.get_device("desk_light").state is DeviceStateValue.OFF
    assert service.get_device("desk_fan").state is DeviceStateValue.OFF


def test_repeat_request_id_is_idempotent(service: DeviceService):
    request_id = str(uuid4())
    first = service.set_device_state("desk_fan", DeviceStateValue.ON, request_id=request_id)
    second = service.set_device_state("desk_fan", DeviceStateValue.ON, request_id=request_id)

    assert first.request_id == second.request_id
    assert second.accepted is True


def test_expired_command_is_rejected_by_safety_rules():
    command = DeviceCommand(
        request_id=uuid4(),
        device_id="desk_light",
        action="set_state",
        state=DeviceStateValue.ON,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    decision = validate_command_shape(command)
    assert decision.allowed is False
    assert "expired" in decision.reason.lower()


def test_control_risk_allows_fixed_set_state():
    command = DeviceCommand(
        request_id=uuid4(),
        device_id="desk_light",
        action="set_state",
        state=DeviceStateValue.ON,
    )

    decision = evaluate_control_risk(command)
    assert decision.allowed is True
    assert decision.requires_human_confirmation is False


def test_set_device_state_can_enforce_expected_device_type(service: DeviceService):
    result = service.set_device_state(
        "desk_fan",
        DeviceStateValue.ON,
        expected_device_type=DeviceType.LIGHT,
    )

    assert result.accepted is False
    assert "type" in (result.blocked_reason or "").lower()
    assert service.get_device("desk_fan").state is DeviceStateValue.OFF
