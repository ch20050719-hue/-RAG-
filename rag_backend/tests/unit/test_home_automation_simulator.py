"""模拟设备适配器的行为测试。"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.home_automation.device_models import (
    DeviceCommand,
    DeviceRegistration,
    DeviceStateValue,
    DeviceType,
)
from app.home_automation.simulated_device import (
    DeviceOfflineError,
    DeviceNotFoundError,
    ExpiredCommandError,
    SimulatedDeviceAdapter,
)


def _adapter() -> SimulatedDeviceAdapter:
    return SimulatedDeviceAdapter(
        [
            DeviceRegistration(device_id="desk_light", room="study", device_type=DeviceType.LIGHT),
            DeviceRegistration(device_id="desk_fan", room="study", device_type=DeviceType.FAN),
        ]
    )


def test_registered_devices_start_offline_safe_state():
    adapter = _adapter()

    light = adapter.read_state("desk_light")

    assert light.device_id == "desk_light"
    assert light.state is DeviceStateValue.OFF
    assert light.online is True


def test_set_state_returns_acknowledged_result_and_updates_state():
    adapter = _adapter()
    request_id = uuid4()

    result = adapter.send_command(
        DeviceCommand(request_id=request_id, device_id="desk_light", action="set_state", state=DeviceStateValue.ON)
    )

    assert result.accepted is True
    assert result.request_id == request_id
    assert adapter.read_state("desk_light").state is DeviceStateValue.ON


def test_repeated_request_is_idempotent():
    adapter = _adapter()
    command = DeviceCommand(
        request_id=uuid4(), device_id="desk_fan", action="set_state", state=DeviceStateValue.ON
    )

    first = adapter.send_command(command)
    second = adapter.send_command(command)

    assert second == first


def test_unknown_device_is_rejected():
    with pytest.raises(DeviceNotFoundError):
        _adapter().send_command(
            DeviceCommand(request_id=uuid4(), device_id="missing", action="set_state", state=DeviceStateValue.ON)
        )


def test_offline_device_is_rejected():
    adapter = SimulatedDeviceAdapter(
        [DeviceRegistration(device_id="desk_light", room="study", device_type=DeviceType.LIGHT, online=False)]
    )

    with pytest.raises(DeviceOfflineError):
        adapter.send_command(
            DeviceCommand(request_id=uuid4(), device_id="desk_light", action="set_state", state=DeviceStateValue.ON)
        )


def test_expired_command_is_rejected_before_state_change():
    adapter = _adapter()
    expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    with pytest.raises(ExpiredCommandError):
        adapter.send_command(
            DeviceCommand(
                request_id=uuid4(),
                device_id="desk_light",
                action="set_state",
                state=DeviceStateValue.ON,
                expires_at=expired_at,
            )
        )

    assert adapter.read_state("desk_light").state is DeviceStateValue.OFF
