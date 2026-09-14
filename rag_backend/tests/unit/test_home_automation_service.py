"""智能家居设备服务与安全规则单元测试。"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.home_automation.default_devices import (
    DEFAULT_DEVICE_REGISTRATIONS,
    DEFAULT_SENSOR_REGISTRATIONS,
)
from app.home_automation.device_models import (
    DeviceCommand,
    DeviceType,
    DeviceStateValue,
    HomeScenarioName,
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


def test_environment_snapshot_contains_four_sensors(service: DeviceService):
    snapshot = service.get_environment("study")

    kinds = {reading.kind.value for reading in snapshot.readings}
    assert {"temperature", "humidity", "illuminance", "motion"} <= kinds


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
