import asyncio

from app.api.v1.endpoints import home_devices
from app.home_automation.device_models import DeviceStateValue
from app.home_automation.device_tools import create_device_service, set_device_service


def test_generic_state_endpoint_rejects_door_lock():
    service = create_device_service(mode="simulated")
    set_device_service(service)
    try:
        payload = asyncio.run(
            home_devices.set_device_state(
                "door_lock",
                home_devices.SetDeviceStateRequest(state=DeviceStateValue.ON),
                current_user=None,
            )
        )
        assert payload["accepted"] is False
        assert "dedicated" in payload["blocked_reason"].lower()
        assert service.get_door_lock().lock_state.value == "unlocked"
    finally:
        set_device_service(None)


def test_version_three_window_threshold_and_mode_endpoints():
    service = create_device_service(mode="simulated")
    set_device_service(service)
    try:
        window = asyncio.run(
            home_devices.set_window_state(
                home_devices.WindowStateRequest(state=DeviceStateValue.OPEN),
                current_user=None,
            )
        )
        threshold = asyncio.run(
            home_devices.set_threshold(
                home_devices.ThresholdRequest(name="smoke_max", value=700),
                current_user=None,
            )
        )
        mode = asyncio.run(
            home_devices.set_automation_mode(
                home_devices.AutomationModeRequest(mode="automatic"),
                current_user=None,
            )
        )

        assert window["state"] == "open"
        assert threshold["thresholds"]["smoke_max"] == 700
        assert mode["automation_mode"] == "automatic"
        assert service.get_mode().value == "normal"
    finally:
        set_device_service(None)
