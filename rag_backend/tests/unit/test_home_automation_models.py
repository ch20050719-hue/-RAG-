"""智能家居新增环境、门锁与报警模型契约测试。"""

from datetime import datetime, timezone
from uuid import uuid4

from app.home_automation.device_models import (
    AlertState,
    DoorLockAckStatus,
    DoorLockAction,
    BatteryState,
    DeadboltState,
    DoorLockState,
    DoorState,
    DeviceType,
    EnvironmentAlert,
    AutomationMode,
    HomeModeName,
    LockState,
    ModeExecutionResult,
    ModeExecutionStatus,
    SensorKind,
    ThresholdName,
)


def test_new_sensor_and_device_types_are_explicitly_supported():
    assert SensorKind.ILLUMINANCE.value == "illuminance"
    assert SensorKind.SMOKE.value == "smoke"
    assert DeviceType.WINDOW.value == "window"
    assert DeviceType.DOOR_LOCK.value == "door_lock"


def test_automation_mode_is_separate_from_scene_profile():
    assert {item.value for item in AutomationMode} == {"manual", "automatic"}
    assert HomeModeName.SLEEP.value == "sleep"
    assert ThresholdName.SMOKE_MAX.value == "smoke_max"


def test_door_lock_state_carries_safety_relevant_status():
    snapshot = DoorLockState(
        device_id="door_lock",
        room="study",
        door_state=DoorState.CLOSED,
        lock_state=LockState.LOCKED,
        deadbolt_state=DeadboltState.ENGAGED,
        online=True,
        battery_state=BatteryState.NORMAL,
        updated_at=datetime.now(timezone.utc),
        latch_state=LockState.LOCKED,
        battery_level=96,
        last_command=DoorLockAction.ENGAGE_DEADBOLT.value,
        ack_status=DoorLockAckStatus.SUCCESS,
    )

    assert snapshot.door_state is DoorState.CLOSED
    assert snapshot.lock_state is LockState.LOCKED
    assert snapshot.deadbolt_state is DeadboltState.ENGAGED
    assert snapshot.jammed is False
    assert snapshot.tampered is False
    assert snapshot.latch_state is LockState.LOCKED
    assert snapshot.battery_level == 96
    assert snapshot.ack_status is DoorLockAckStatus.SUCCESS


def test_environment_alert_contains_auditable_diagnosis_fields():
    alert = EnvironmentAlert(
        alert_id=uuid4(),
        room="study",
        sensor_id="room_co2",
        metric="co2",
        current_value=1680,
        threshold=1500,
        consecutive_count=3,
        state=AlertState.ACTIVE,
        source="mqtt",
        last_updated_at=datetime.now(timezone.utc),
    )

    assert alert.state is AlertState.ACTIVE
    assert alert.consecutive_count == 3
    assert alert.current_value > alert.threshold


def test_mode_execution_contains_explicit_overall_status_and_actions():
    result = ModeExecutionResult(
        mode=HomeModeName.SLEEP,
        previous_mode=HomeModeName.NORMAL,
        accepted=False,
        overall_status=ModeExecutionStatus.PARTIAL_FAILED,
        actions=(),
        message="door lock integration is unavailable",
    )

    assert result.mode is HomeModeName.SLEEP
    assert result.overall_status is ModeExecutionStatus.PARTIAL_FAILED
