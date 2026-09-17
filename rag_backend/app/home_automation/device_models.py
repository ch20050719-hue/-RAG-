"""智能家居设备、传感器与场景领域模型。"""

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DeviceType(str, Enum):
    """首版支持的安全演示设备类型。"""

    LIGHT = "light"
    FAN = "fan"
    DOOR_LOCK = "door_lock"


class DeviceStateValue(str, Enum):
    """首版设备开关状态。"""

    ON = "on"
    OFF = "off"


class SensorKind(str, Enum):
    """桌面原型传感器类型。"""

    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    CO2 = "co2"
    ILLUMINANCE = "illuminance"
    MOTION = "motion"


class SensorQuality(str, Enum):
    """传感器读数质量。"""

    VALID = "valid"
    STALE = "stale"
    INVALID = "invalid"
    OFFLINE = "offline"


class EnvironmentLevel(str, Enum):
    """环境指标分级。"""

    NORMAL = "normal"
    ATTENTION = "attention"
    DANGER = "danger"
    FAULT = "fault"


class DoorState(str, Enum):
    """门磁状态。"""

    OPEN = "open"
    CLOSED = "closed"


class LockState(str, Enum):
    """门锁锁定状态。"""

    LOCKED = "locked"
    UNLOCKED = "unlocked"


class DeadboltState(str, Enum):
    """门锁反锁状态。"""

    ENGAGED = "engaged"
    RELEASED = "released"


class DoorLockAction(str, Enum):
    """实验门锁允许的固定动作。"""

    UNLOCK = "unlock"
    LOCK = "lock"
    ENGAGE_DEADBOLT = "engage_deadbolt"
    RELEASE_DEADBOLT = "release_deadbolt"


class DoorLockAckStatus(str, Enum):
    """门锁命令回执状态。"""

    ACCEPTED = "accepted"
    SUCCESS = "success"
    FAILED = "failed"


class BatteryState(str, Enum):
    """设备电池状态。"""

    NORMAL = "normal"
    LOW = "low"


class AlertState(str, Enum):
    """环境报警生命周期状态。"""

    NORMAL = "normal"
    SUSPECTED = "suspected"
    ACTIVE = "active"
    FAULT = "fault"
    SENSOR_FAULT = "fault"
    RECOVERED = "recovered"


class DeviceAction(str, Enum):
    """允许的固定设备动作。"""

    SET_STATE = "set_state"


class DeviceRegistration(BaseModel):
    """设备注册信息。"""

    model_config = ConfigDict(frozen=True)

    device_id: str = Field(min_length=1, max_length=100)
    room: str = Field(min_length=1, max_length=100)
    device_type: DeviceType
    online: bool = True


class SensorRegistration(BaseModel):
    """传感器注册信息。"""

    model_config = ConfigDict(frozen=True)

    sensor_id: str = Field(min_length=1, max_length=100)
    room: str = Field(min_length=1, max_length=100)
    kind: SensorKind
    online: bool = True


class DeviceCommand(BaseModel):
    """发往设备适配器的固定动作命令。"""

    model_config = ConfigDict(frozen=True)

    request_id: UUID
    device_id: str = Field(min_length=1, max_length=100)
    action: Literal["set_state"]
    state: DeviceStateValue
    expires_at: datetime | None = None


class DeviceState(BaseModel):
    """设备当前状态快照。"""

    model_config = ConfigDict(frozen=True)

    device_id: str
    room: str
    device_type: DeviceType
    state: DeviceStateValue = DeviceStateValue.OFF
    online: bool
    updated_at: datetime
    last_request_id: UUID | None = None


class SensorReading(BaseModel):
    """传感器读数快照。"""

    model_config = ConfigDict(frozen=True)

    sensor_id: str
    room: str
    kind: SensorKind
    value: float
    unit: str
    online: bool
    recorded_at: datetime
    source: str = "simulated"
    quality: SensorQuality = SensorQuality.VALID
    level: EnvironmentLevel = EnvironmentLevel.NORMAL


class DeviceCommandResult(BaseModel):
    """设备命令执行回执。"""

    model_config = ConfigDict(frozen=True)

    request_id: UUID
    device_id: str
    accepted: bool
    state: DeviceStateValue
    acknowledged_at: datetime
    message: str
    blocked_reason: str | None = None


class DoorLockCommandResult(BaseModel):
    """门锁固定命令的可审计回执。"""

    model_config = ConfigDict(frozen=True)

    request_id: UUID
    device_id: str
    room: str
    action: DoorLockAction
    accepted: bool
    ack_status: DoorLockAckStatus
    message: str
    blocked_reason: str | None = None
    door_state: DoorState
    latch_state: LockState
    deadbolt_state: DeadboltState
    battery_level: int = Field(ge=0, le=100)
    expires_at: datetime | None = None
    acknowledged_at: datetime


class EnvironmentSnapshot(BaseModel):
    """某一房间的环境快照。"""

    model_config = ConfigDict(frozen=True)

    room: str
    readings: tuple[SensorReading, ...] = ()
    generated_at: datetime


class DoorLockState(BaseModel):
    """门锁与门磁的当前状态快照。"""

    model_config = ConfigDict(frozen=True)

    device_id: str = Field(min_length=1, max_length=100)
    room: str = Field(min_length=1, max_length=100)
    door_state: DoorState
    lock_state: LockState
    latch_state: LockState | None = None
    deadbolt_state: DeadboltState
    online: bool
    battery_state: BatteryState
    battery_level: int = Field(default=100, ge=0, le=100)
    jammed: bool = False
    tampered: bool = False
    last_command: str | None = None
    ack_status: DoorLockAckStatus = DoorLockAckStatus.SUCCESS
    updated_at: datetime


class EnvironmentAlert(BaseModel):
    """可审计的环境报警与诊断证据。"""

    model_config = ConfigDict(frozen=True)

    alert_id: UUID
    room: str = Field(min_length=1, max_length=100)
    sensor_id: str = Field(min_length=1, max_length=100)
    metric: str = Field(min_length=1, max_length=100)
    current_value: float
    threshold: float | None = None
    consecutive_count: int = Field(ge=1)
    state: AlertState
    source: str = Field(min_length=1, max_length=100)
    reason: str = ""
    related_action: str | None = None
    occurred_at: datetime | None = None
    last_updated_at: datetime


class HomeScenarioName(str, Enum):
    """预置场景名。"""

    SLEEP = "sleep"
    AWAY = "away"
    MOVIE = "movie"


class HomeModeName(str, Enum):
    """本科版固定运行模式。"""

    NORMAL = "normal"
    SLEEP = "sleep"
    AWAY = "away"


class ModeExecutionStatus(str, Enum):
    """模式切换的整体执行状态。"""

    SUCCESS = "success"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"


class ModeStepResult(BaseModel):
    """模式切换中单个动作的真实执行结果。"""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=100)
    accepted: bool
    message: str
    device_id: str | None = None
    command_result: DeviceCommandResult | None = None
    lock_result: DoorLockCommandResult | None = None


class ModeExecutionResult(BaseModel):
    """模式切换汇总，包含每一步动作结果。"""

    model_config = ConfigDict(frozen=True)

    mode: HomeModeName
    previous_mode: HomeModeName
    accepted: bool
    overall_status: ModeExecutionStatus
    actions: tuple[ModeStepResult, ...] = ()
    message: str


class ScenarioExecutionResult(BaseModel):
    """场景执行汇总回执。"""

    model_config = ConfigDict(frozen=True)

    scenario: HomeScenarioName
    accepted: bool
    results: tuple[DeviceCommandResult, ...] = ()
    message: str
