"""设备适配器协议：模拟与 MQTT 实现共用同一契约。"""

from typing import Protocol, runtime_checkable

from .device_models import (
    DeviceCommand,
    DeviceCommandResult,
    DeviceState,
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
