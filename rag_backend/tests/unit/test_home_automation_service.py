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
    DeviceCommand,
    DeviceType,
    DeviceStateValue,
    DoorLockAction,
    DoorState,
    HomeModeName,
    HomeScenarioName,
    ModeExecutionStatus,
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


def test_environment_snapshot_contains_three_core_sensors(service: DeviceService):
    snapshot = service.get_environment("study")

    kinds = {reading.kind.value for reading in snapshot.readings}
    assert kinds == {"temperature", "humidity", "co2"}


def test_environment_snapshot_exposes_co2_quality_and_level(service: DeviceService):
    snapshot = service.get_environment("study")

    co2 = next(reading for reading in snapshot.readings if reading.sensor_id == "room_co2")

    assert co2.value == 600
    assert co2.unit == "ppm"
    assert co2.quality.value == "valid"
    assert co2.level.value == "normal"


def test_three_dangerous_co2_samples_turn_on_the_fan():
    adapter = SimulatedDeviceAdapter(
        registrations=list(DEFAULT_DEVICE_REGISTRATIONS),
        sensor_registrations=list(DEFAULT_SENSOR_REGISTRATIONS),
    )
    service = DeviceService(adapter=adapter)

    alerts = []
    for value in (1600, 1650, 1680):
        adapter.update_sensor_value("room_co2", value)
        alerts = service.evaluate_environment("study")

    assert any(alert.state is AlertState.ACTIVE for alert in alerts)
    assert service.get_device("desk_fan").state is DeviceStateValue.ON


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
