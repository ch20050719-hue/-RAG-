"""无硬件环境下的设备适配器。"""

import math
from datetime import datetime, timezone
from typing import Final
from uuid import UUID

from .default_devices import SENSOR_UNITS
from .device_models import (
    DoorActuatorResult,
    DeviceCommand,
    DeviceCommandResult,
    DeviceRegistration,
    DeviceState,
    DeviceStateValue,
    DeviceType,
    DoorLockAction,
    DoorLockAckStatus,
    SensorKind,
    SensorQuality,
    SensorReading,
    SensorRegistration,
)


class DeviceError(RuntimeError):
    """设备操作基类异常。"""


class DeviceNotFoundError(DeviceError):
    """设备未注册。"""


class DeviceOfflineError(DeviceError):
    """设备当前离线。"""


class ExpiredCommandError(DeviceError):
    """命令已超过有效期。"""


_SET_STATE_ACTION: Final[str] = "set_state"

_DEFAULT_SENSOR_VALUES: Final[dict[SensorKind, float]] = {
    SensorKind.TEMPERATURE: 26.5,
    SensorKind.HUMIDITY: 48.0,
    SensorKind.SMOKE: 120.0,
    SensorKind.FLAME: 0.0,
    SensorKind.PRESENCE: 0.0,
}


class SimulatedDeviceAdapter:
    """提供与未来 MQTT 适配器一致的最小同步接口。"""

    def __init__(
        self,
        registrations: list[DeviceRegistration],
        sensor_registrations: list[SensorRegistration] | None = None,
    ) -> None:
        self._states: dict[str, DeviceState] = {}
        self._results: dict[str, DeviceCommandResult] = {}
        self._door_results: dict[str, DoorActuatorResult] = {}
        self._sensors: dict[str, SensorReading] = {}
        for registration in registrations:
            if registration.device_id in self._states:
                raise ValueError(f"Duplicate device: {registration.device_id}")
            self._states = {
                **self._states,
                registration.device_id: DeviceState(
                    device_id=registration.device_id,
                    room=registration.room,
                    device_type=registration.device_type,
                    online=registration.online,
                    state=DeviceStateValue.OFF,
                    updated_at=datetime.now(timezone.utc),
                ),
            }
        for sensor in sensor_registrations or []:
            if sensor.sensor_id in self._sensors:
                raise ValueError(f"Duplicate sensor: {sensor.sensor_id}")
            self._sensors = {
                **self._sensors,
                sensor.sensor_id: SensorReading(
                    sensor_id=sensor.sensor_id,
                    room=sensor.room,
                    kind=sensor.kind,
                    value=_DEFAULT_SENSOR_VALUES[sensor.kind],
                    unit=SENSOR_UNITS[sensor.kind],
                    online=sensor.online,
                    recorded_at=datetime.now(timezone.utc),
                    source="simulated",
                    quality=SensorQuality.VALID,
                ),
            }

    def read_state(self, device_id: str) -> DeviceState:
        """读取设备状态快照。"""

        try:
            return self._states[device_id]
        except KeyError as exc:
            raise DeviceNotFoundError(f"Device is not registered: {device_id}") from exc

    def list_states(self) -> list[DeviceState]:
        """列出全部设备状态。"""

        return list(self._states.values())

    def list_sensor_readings(self, room: str | None = None) -> list[SensorReading]:
        """列出传感器读数，可按房间过滤。"""

        readings = list(self._sensors.values())
        if room is None:
            return readings
        return [reading for reading in readings if reading.room == room]

    def update_sensor_value(self, sensor_id: str, value: float) -> SensorReading:
        """更新模拟传感器读数（联调与测试用）。"""

        try:
            current = self._sensors[sensor_id]
        except KeyError as exc:
            raise DeviceNotFoundError(f"Sensor is not registered: {sensor_id}") from exc
        numeric_value = float(value)
        if not math.isfinite(numeric_value):
            raise ValueError("Sensor value must be a finite number")
        updated = SensorReading(
            **current.model_dump(exclude={"value", "recorded_at", "quality"}),
            value=numeric_value,
            recorded_at=datetime.now(timezone.utc),
            quality=SensorQuality.VALID,
        )
        self._sensors = {**self._sensors, sensor_id: updated}
        return updated

    def send_command(self, command: DeviceCommand) -> DeviceCommandResult:
        """执行固定设备动作并返回可审计回执。"""

        request_key = str(command.request_id)
        if request_key in self._results:
            return self._results[request_key]

        current = self.read_state(command.device_id)
        if not current.online:
            raise DeviceOfflineError(f"Device is offline: {command.device_id}")
        if command.expires_at is not None and command.expires_at <= datetime.now(timezone.utc):
            raise ExpiredCommandError(f"Command has expired: {command.request_id}")
        if command.action != _SET_STATE_ACTION:
            raise ValueError(f"Unsupported device action: {command.action}")

        acknowledged_at = datetime.now(timezone.utc)
        updated_state = DeviceState(
            **current.model_dump(exclude={"state", "updated_at", "last_request_id"}),
            state=command.state,
            updated_at=acknowledged_at,
            last_request_id=command.request_id,
        )
        result = DeviceCommandResult(
            request_id=command.request_id,
            device_id=command.device_id,
            accepted=True,
            state=command.state,
            acknowledged_at=acknowledged_at,
            message="Command acknowledged by simulated device",
        )
        self._states = {**self._states, command.device_id: updated_state}
        self._results = {**self._results, request_key: result}
        return result

    def execute_door_motion(
        self,
        device_id: str,
        action: DoorLockAction,
        *,
        request_id: UUID,
        expires_at: datetime | None,
    ) -> DoorActuatorResult:
        """模拟舵机开合并返回与 MQTT 一致的执行回执。"""

        request_key = str(request_id)
        if request_key in self._door_results:
            return self._door_results[request_key]
        current = self.read_state(device_id)
        if current.device_type is not DeviceType.DOOR_LOCK:
            raise ValueError(f"Device is not a door lock: {device_id}")
        if not current.online:
            raise DeviceOfflineError(f"Device is offline: {device_id}")
        if expires_at is not None and expires_at <= datetime.now(timezone.utc):
            raise ExpiredCommandError(f"Command has expired: {request_id}")
        if action not in (DoorLockAction.OPEN_DOOR, DoorLockAction.CLOSE_DOOR):
            raise ValueError(f"Unsupported door action: {action}")

        result = DoorActuatorResult(
            request_id=request_id,
            device_id=device_id,
            action=action,
            accepted=True,
            ack_status=DoorLockAckStatus.SUCCESS,
            message=f"Simulated servo acknowledged {action.value}",
        )
        self._door_results = {**self._door_results, request_key: result}
        return result
