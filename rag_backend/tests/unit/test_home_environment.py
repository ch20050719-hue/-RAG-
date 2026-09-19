"""环境监测分级、报警确认与历史缓存测试。"""

from datetime import datetime, timedelta, timezone

from app.home_automation.device_models import (
    AlertState,
    EnvironmentLevel,
    SensorKind,
    SensorQuality,
    SensorReading,
)
from app.home_automation.environment_history import EnvironmentHistoryService
from app.home_automation.environment_monitor import (
    DEFAULT_ENVIRONMENT_CONFIG,
    EnvironmentAlertService,
    assess_reading,
    environment_config_from_env,
)


def _reading(
    value: float,
    *,
    sensor_id: str = "room_smoke",
    kind: SensorKind = SensorKind.SMOKE,
    recorded_at: datetime | None = None,
) -> SensorReading:
    return SensorReading(
        sensor_id=sensor_id,
        room="study",
        kind=kind,
        value=value,
        unit="raw" if kind is SensorKind.SMOKE else "celsius",
        online=True,
        recorded_at=recorded_at or datetime.now(timezone.utc),
    )


def test_threshold_boundaries_match_the_plan():
    assert assess_reading(_reading(499)).level is EnvironmentLevel.NORMAL
    assert assess_reading(_reading(500)).level is EnvironmentLevel.ATTENTION
    assert assess_reading(_reading(799)).level is EnvironmentLevel.ATTENTION
    assert assess_reading(_reading(800)).level is EnvironmentLevel.DANGER


def test_danger_alert_is_suspected_then_active_after_three_samples():
    service = EnvironmentAlertService(DEFAULT_ENVIRONMENT_CONFIG)

    first = service.evaluate(_reading(850))
    second = service.evaluate(_reading(900))
    third = service.evaluate(_reading(950))

    assert first is not None and first.state is AlertState.SUSPECTED
    assert second is not None and second.state is AlertState.SUSPECTED
    assert third is not None and third.state is AlertState.ACTIVE
    assert third.consecutive_count == 3
    assert third.related_action == "fan_on"


def test_three_normal_samples_recover_an_active_alert():
    service = EnvironmentAlertService(DEFAULT_ENVIRONMENT_CONFIG)

    for value in (850, 900, 950):
        service.evaluate(_reading(value))
    recovered = [service.evaluate(_reading(300)) for _ in range(3)][-1]

    assert recovered is not None
    assert recovered.state is AlertState.RECOVERED
    assert recovered.consecutive_count == 3


def test_stale_reading_is_sensor_fault_and_does_not_request_fan():
    stale = _reading(850, recorded_at=datetime.now(timezone.utc) - timedelta(seconds=31))
    assessed = assess_reading(stale, now=datetime.now(timezone.utc))

    assert assessed.quality is SensorQuality.STALE
    assert assessed.level is EnvironmentLevel.FAULT


def test_environment_history_keeps_recent_snapshots_only():
    history = EnvironmentHistoryService(max_samples=2)
    now = datetime.now(timezone.utc)

    from app.home_automation.device_models import EnvironmentSnapshot

    for offset in (2, 1, 0):
        history.append(
            EnvironmentSnapshot(
                room="study",
                readings=(_reading(600, recorded_at=now - timedelta(seconds=offset)),),
                generated_at=now - timedelta(seconds=offset),
            )
        )

    snapshots = history.list_snapshots(room="study", minutes=10, now=now)

    assert len(snapshots) == 2
    assert snapshots[0].generated_at == now - timedelta(seconds=1)


def test_environment_config_accepts_plan_environment_variable_names():
    config = environment_config_from_env(
        {
            "HOME_SMOKE_DANGER_HIGH": "700",
            "HOME_ALERT_CONFIRM_COUNT": "2",
        }
    )

    assert config.smoke.danger_max == 700
    assert config.confirmation_count == 2
