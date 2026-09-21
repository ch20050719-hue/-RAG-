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


def test_version_three_pump_threshold_and_mode_endpoints():
    service = create_device_service(mode="simulated")
    set_device_service(service)
    try:
        pump = asyncio.run(
            home_devices.set_pump_state(
                home_devices.SetDeviceStateRequest(state=DeviceStateValue.ON),
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

        assert pump["state"] == "on"
        assert threshold["thresholds"]["smoke_max"] == 700
        assert mode["automation_mode"] == "automatic"
    finally:
        set_device_service(None)


def test_scene_endpoint_executes_away_preset_without_old_mode_api():
    service = create_device_service(mode="simulated")
    set_device_service(service)
    try:
        payload = asyncio.run(
            home_devices.run_home_scenario(
                home_devices.ScenarioRequest(scenario="away"),
                current_user=None,
            )
        )
        assert payload["scene"] == "away"
        assert payload["accepted"] is True
        assert service.get_device("desk_light").state.value == "off"
        assert service.get_door_lock().lock_state.value == "locked"
    finally:
        set_device_service(None)


def test_scene_get_endpoint_returns_current_preset():
    service = create_device_service(mode="simulated")
    set_device_service(service)
    try:
        asyncio.run(
            home_devices.run_home_scenario(
                home_devices.ScenarioRequest(scenario="sleep"),
                current_user=None,
            )
        )
        payload = asyncio.run(home_devices.get_home_scenario(current_user=object()))
    finally:
        set_device_service(None)

    assert payload == {"room": "study", "scene": "sleep"}
