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


class DeviceStateValue(str, Enum):
    """首版设备开关状态。"""

    ON = "on"
    OFF = "off"


class SensorKind(str, Enum):
    """桌面原型传感器类型。"""

    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    ILLUMINANCE = "illuminance"
    MOTION = "motion"


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


class EnvironmentSnapshot(BaseModel):
    """某一房间的环境快照。"""

    model_config = ConfigDict(frozen=True)

    room: str
    readings: tuple[SensorReading, ...] = ()
    generated_at: datetime


class HomeScenarioName(str, Enum):
    """预置场景名。"""

    SLEEP = "sleep"
    AWAY = "away"
    MOVIE = "movie"


class ScenarioExecutionResult(BaseModel):
    """场景执行汇总回执。"""

    model_config = ConfigDict(frozen=True)

    scenario: HomeScenarioName
    accepted: bool
    results: tuple[DeviceCommandResult, ...] = ()
    message: str
