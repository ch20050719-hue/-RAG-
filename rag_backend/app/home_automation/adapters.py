"""设备适配器协议：模拟与 MQTT 实现共用同一契约。"""

from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from .device_models import (
    DoorActuatorResult,
    DeviceCommand,
    DeviceCommandResult,
    DeviceState,
    DoorLockAction,
    SensorReading,
)


@runtime_checkable
class DeviceAdapter(Protocol):
    """设备与传感器适配器最小接口。"""

    def read_state(self, device_id: str) -> DeviceState:
        """读取设备状态。"""

    def send_command(self, command: DeviceCommand) -> DeviceCommandResult:
        """发送固定动作命令并等待回执。"""

    def list_states(self) -> list[DeviceState]:
        """列出全部设备状态。"""

    def list_sensor_readings(self, room: str | None = None) -> list[SensorReading]:
        """列出传感器读数。"""


@runtime_checkable
class DoorActuator(Protocol):
    """门体舵机执行器的固定动作接口。"""

    def execute_door_motion(
        self,
        device_id: str,
        action: DoorLockAction,
        *,
        request_id: UUID,
        expires_at: datetime | None,
    ) -> DoorActuatorResult:
        """执行开门或关门并等待底层回执。"""
