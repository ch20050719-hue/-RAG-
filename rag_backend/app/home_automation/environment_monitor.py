"""环境读数质量、分级与报警确认服务。"""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Mapping
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .device_models import (
    AlertState,
    EnvironmentAlert,
    EnvironmentLevel,
    SensorKind,
    SensorQuality,
    SensorReading,
)


class MetricThreshold(BaseModel):
    """单个环境指标的正常、危险和物理有效范围。"""

    model_config = ConfigDict(frozen=True)

    normal_min: float | None = None
    normal_max: float | None = None
    danger_min: float | None = None
    danger_max: float | None = None
    valid_min: float | None = None
    valid_max: float | None = None

    def level_for(self, value: float) -> EnvironmentLevel:
        """根据统一阈值配置计算环境等级。"""

        if (self.danger_min is not None and value < self.danger_min) or (
            self.danger_max is not None and value >= self.danger_max
        ):
            return EnvironmentLevel.DANGER
        if (self.normal_min is not None and value < self.normal_min) or (
            self.normal_max is not None and value >= self.normal_max
        ):
            return EnvironmentLevel.ATTENTION
        return EnvironmentLevel.NORMAL

    def threshold_for(self, value: float) -> float | None:
        """返回触发危险等级的边界。"""

        if self.danger_min is not None and value < self.danger_min:
            return self.danger_min
        if self.danger_max is not None and value >= self.danger_max:
            return self.danger_max
        return None


class EnvironmentMonitorConfig(BaseModel):
    """环境监测运行参数，默认值与改造方案第 5 节一致。"""

    model_config = ConfigDict(frozen=True)

    temperature: MetricThreshold
    humidity: MetricThreshold
    smoke: MetricThreshold
    flame: MetricThreshold
    presence: MetricThreshold
    confirmation_count: int = Field(default=3, ge=1, le=20)
    recovery_count: int = Field(default=3, ge=1, le=20)
    sensor_max_age_seconds: int = Field(default=30, ge=1, le=3600)

    def threshold_for(self, kind: SensorKind) -> MetricThreshold | None:
        """返回受支持指标的阈值配置。"""

        return {
            SensorKind.TEMPERATURE: self.temperature,
            SensorKind.HUMIDITY: self.humidity,
            SensorKind.SMOKE: self.smoke,
            SensorKind.FLAME: self.flame,
            SensorKind.PRESENCE: self.presence,
        }.get(kind)


DEFAULT_ENVIRONMENT_CONFIG = EnvironmentMonitorConfig(
    temperature=MetricThreshold(
        normal_min=18,
        normal_max=28,
        danger_min=10,
        danger_max=35,
        valid_min=-40,
        valid_max=85,
    ),
    humidity=MetricThreshold(
        normal_min=30,
        normal_max=60,
        danger_min=20,
        danger_max=80,
        valid_min=0,
        valid_max=100,
    ),
    smoke=MetricThreshold(
        normal_max=500,
        danger_max=800,
        valid_min=0,
        valid_max=4095,
    ),
    flame=MetricThreshold(
        normal_max=1,
        danger_max=1,
        valid_min=0,
        valid_max=1,
    ),
    presence=MetricThreshold(
        normal_max=1,
        danger_max=1,
        valid_min=0,
        valid_max=1,
    ),
)


class ReadingAssessment(BaseModel):
    """一次读数的质量、等级和判定依据。"""

    model_config = ConfigDict(frozen=True)

    quality: SensorQuality
    level: EnvironmentLevel
    threshold: float | None = None
    reason: str = ""


def assess_reading(
    reading: SensorReading,
    config: EnvironmentMonitorConfig = DEFAULT_ENVIRONMENT_CONFIG,
    now: datetime | None = None,
) -> ReadingAssessment:
    """按质量优先、阈值其次的顺序评估一条读数。"""

    current_time = _as_utc(now or datetime.now(timezone.utc))
    recorded_at = _as_utc(reading.recorded_at)
    age_seconds = (current_time - recorded_at).total_seconds()
    if not reading.online:
        return ReadingAssessment(
            quality=SensorQuality.OFFLINE,
            level=EnvironmentLevel.FAULT,
            reason="sensor is offline",
        )
    if reading.quality is not SensorQuality.VALID:
        return ReadingAssessment(
            quality=reading.quality,
            level=EnvironmentLevel.FAULT,
            reason=f"sensor quality is {reading.quality.value}",
        )
    if age_seconds > config.sensor_max_age_seconds:
        return ReadingAssessment(
            quality=SensorQuality.STALE,
            level=EnvironmentLevel.FAULT,
            reason=f"reading is older than {config.sensor_max_age_seconds} seconds",
        )
    if not math.isfinite(reading.value):
        return ReadingAssessment(
            quality=SensorQuality.INVALID,
            level=EnvironmentLevel.FAULT,
            reason="reading is not a finite number",
        )

    threshold = config.threshold_for(reading.kind)
    if threshold is None:
        return ReadingAssessment(
            quality=SensorQuality.VALID,
            level=EnvironmentLevel.NORMAL,
            reason="metric is not included in environment alert rules",
        )
    if (threshold.valid_min is not None and reading.value < threshold.valid_min) or (
        threshold.valid_max is not None and reading.value > threshold.valid_max
    ):
        return ReadingAssessment(
            quality=SensorQuality.INVALID,
            level=EnvironmentLevel.FAULT,
            threshold=threshold.threshold_for(reading.value),
            reason="reading is outside the physical valid range",
        )
    level = threshold.level_for(reading.value)
    return ReadingAssessment(
        quality=SensorQuality.VALID,
        level=level,
        threshold=threshold.threshold_for(reading.value),
        reason=f"{reading.kind.value} level is {level.value}",
    )


def environment_config_from_env(
    environ: Mapping[str, str] | None = None,
) -> EnvironmentMonitorConfig:
    """从环境变量生成配置；未配置项沿用方案默认值。"""

    values = os.environ if environ is None else environ
    return EnvironmentMonitorConfig(
        temperature=_threshold_from_env("HOME_TEMP", DEFAULT_ENVIRONMENT_CONFIG.temperature, values),
        humidity=_threshold_from_env("HOME_HUMIDITY", DEFAULT_ENVIRONMENT_CONFIG.humidity, values),
        smoke=_threshold_from_env("HOME_SMOKE", DEFAULT_ENVIRONMENT_CONFIG.smoke, values),
        flame=DEFAULT_ENVIRONMENT_CONFIG.flame,
        presence=DEFAULT_ENVIRONMENT_CONFIG.presence,
        confirmation_count=_env_int_any(
            values,
            ("HOME_ALERT_CONFIRM_COUNT", "HOME_ALERT_CONFIRMATION_COUNT"),
            3,
        ),
        recovery_count=_env_int(values, "HOME_ALERT_RECOVERY_COUNT", 3),
        sensor_max_age_seconds=_env_int(values, "HOME_SENSOR_MAX_AGE_SECONDS", 30),
    )


class EnvironmentAlertService:
    """以连续样本确认危险并记录可审计报警事件。"""

    def __init__(self, config: EnvironmentMonitorConfig = DEFAULT_ENVIRONMENT_CONFIG) -> None:
        self._config = config
        self._danger_counts: dict[str, int] = {}
        self._recovery_counts: dict[str, int] = {}
        self._current: dict[str, EnvironmentAlert] = {}
        self._events: tuple[EnvironmentAlert, ...] = ()

    def evaluate(self, reading: SensorReading, now: datetime | None = None) -> EnvironmentAlert | None:
        """评估一条新读数并返回当前报警状态变化。"""

        assessed = assess_reading(reading, self._config, now=now)
        event_time = _as_utc(now or datetime.now(timezone.utc))
        key = reading.sensor_id
        current = self._current.get(key)

        if assessed.level is EnvironmentLevel.FAULT:
            self._danger_counts[key] = 0
            self._recovery_counts[key] = 0
            alert = self._build_alert(
                reading,
                AlertState.FAULT,
                1,
                assessed,
                event_time,
                current=current,
                reason=assessed.reason,
            )
            self._current[key] = alert
            self._record(alert)
            return alert

        if assessed.level is EnvironmentLevel.DANGER:
            count = self._danger_counts.get(key, 0) + 1
            self._danger_counts[key] = count
            self._recovery_counts[key] = 0
            state = (
                AlertState.ACTIVE
                if count >= self._config.confirmation_count
                else AlertState.SUSPECTED
            )
            related_action = (
                {
                    SensorKind.TEMPERATURE: "fan_and_buzzer_on",
                    SensorKind.SMOKE: "fan_and_buzzer_on",
                    SensorKind.FLAME: "sprinkler_and_buzzer_on",
                    SensorKind.PRESENCE: "light_on",
                }.get(reading.kind)
                if state is AlertState.ACTIVE
                else None
            )
            alert = self._build_alert(
                reading,
                state,
                count,
                assessed,
                event_time,
                current=current,
                related_action=related_action,
                reason=f"{assessed.reason}; consecutive danger samples: {count}",
            )
            self._current[key] = alert
            self._record(alert)
            return alert

        self._danger_counts[key] = 0
        if current is None:
            self._recovery_counts[key] = 0
            return None
        if current.state is AlertState.SUSPECTED:
            self._recovery_counts[key] = 0
            self._current.pop(key, None)
            return None
        if assessed.level is not EnvironmentLevel.NORMAL:
            self._recovery_counts[key] = 0
            return current

        recovery_count = self._recovery_counts.get(key, 0) + 1
        self._recovery_counts[key] = recovery_count
        if recovery_count >= self._config.recovery_count:
            recovered = self._build_alert(
                reading,
                AlertState.RECOVERED,
                recovery_count,
                assessed,
                event_time,
                current=current,
                reason=f"{assessed.reason}; consecutive recovery samples: {recovery_count}",
            )
            self._current.pop(key, None)
            self._record(recovered)
            return recovered
        return current

    def list_alerts(self, room: str | None = None, active_only: bool = False) -> list[EnvironmentAlert]:
        """查询报警事件；active_only 只返回当前未恢复状态。"""

        if active_only:
            alerts = list(self._current.values())
        else:
            alerts = list(self._events)
        if room is not None:
            alerts = [alert for alert in alerts if alert.room == room]
        return alerts

    def _build_alert(
        self,
        reading: SensorReading,
        state: AlertState,
        count: int,
        assessed: ReadingAssessment,
        event_time: datetime,
        *,
        current: EnvironmentAlert | None,
        reason: str,
        related_action: str | None = None,
    ) -> EnvironmentAlert:
        alert_id = current.alert_id if current is not None else uuid4()
        occurred_at = current.occurred_at if current is not None else event_time
        return EnvironmentAlert(
            alert_id=alert_id,
            room=reading.room,
            sensor_id=reading.sensor_id,
            metric=reading.kind.value,
            current_value=reading.value,
            threshold=assessed.threshold if assessed.threshold is not None else (
                current.threshold if current is not None else None
            ),
            consecutive_count=count,
            state=state,
            source=reading.source,
            reason=reason,
            related_action=related_action if related_action is not None else (
                current.related_action if current is not None and state is not AlertState.RECOVERED else None
            ),
            occurred_at=occurred_at,
            last_updated_at=event_time,
        )

    def _record(self, alert: EnvironmentAlert) -> None:
        self._events = (*self._events, alert)


def _threshold_from_env(
    prefix: str,
    base: MetricThreshold,
    environ: Mapping[str, str],
) -> MetricThreshold:
    updates: dict[str, float] = {}
    for field_name in (
        "normal_min",
        "normal_max",
        "danger_min",
        "danger_max",
        "valid_min",
        "valid_max",
    ):
        value = environ.get(f"{prefix}_{field_name.upper()}")
        if value is None and field_name == "danger_min":
            value = environ.get(f"{prefix}_DANGER_LOW")
        if value is None and field_name == "danger_max":
            value = environ.get(f"{prefix}_DANGER_HIGH")
        if value is not None:
            updates[field_name] = float(value)
    return base.model_copy(update=updates)


def _env_int(environ: Mapping[str, str], key: str, default: int) -> int:
    value = environ.get(key)
    return default if value is None else int(value)


def _env_int_any(environ: Mapping[str, str], keys: tuple[str, ...], default: int) -> int:
    for key in keys:
        value = environ.get(key)
        if value is not None:
            return int(value)
    return default


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = [
    "DEFAULT_ENVIRONMENT_CONFIG",
    "EnvironmentAlertService",
    "EnvironmentMonitorConfig",
    "MetricThreshold",
    "ReadingAssessment",
    "assess_reading",
    "environment_config_from_env",
]
