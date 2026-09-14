"""Agent 可调用的智能家居固定工具。"""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.tools import tool

from .default_devices import DEFAULT_DEVICE_REGISTRATIONS, DEFAULT_SENSOR_REGISTRATIONS
from .device_models import DeviceStateValue, DeviceType, HomeScenarioName
from .device_service import DeviceService
from .simulated_device import SimulatedDeviceAdapter

logger = logging.getLogger(__name__)

_service: DeviceService | None = None


def get_device_service() -> DeviceService:
    """获取进程内设备服务单例（默认模拟适配器）。"""

    global _service
    if _service is None:
        _service = create_device_service()
    return _service


def set_device_service(service: DeviceService | None) -> None:
    """注入或清理设备服务（测试与运行时切换适配器）。"""

    global _service
    _service = service


def create_device_service(
    *,
    mode: str | None = None,
    mqtt_host: str | None = None,
    mqtt_port: int | None = None,
    mqtt_username: str | None = None,
    mqtt_password: str | None = None,
    mqtt_ack_timeout: float | None = None,
    mqtt_client_id: str | None = None,
) -> DeviceService:
    """按配置创建设备服务；默认使用无硬件模拟适配器。"""

    selected_mode = (mode or os.getenv("HOME_DEVICE_ADAPTER", "simulated")).strip().lower()
    if selected_mode == "simulated":
        adapter = SimulatedDeviceAdapter(
            registrations=list(DEFAULT_DEVICE_REGISTRATIONS),
            sensor_registrations=list(DEFAULT_SENSOR_REGISTRATIONS),
        )
        return DeviceService(adapter=adapter)
    if selected_mode != "mqtt":
        raise ValueError("HOME_DEVICE_ADAPTER must be simulated or mqtt")

    from .mqtt_adapter import MqttDeviceAdapter

    adapter = MqttDeviceAdapter(
        registrations=list(DEFAULT_DEVICE_REGISTRATIONS),
        sensor_registrations=list(DEFAULT_SENSOR_REGISTRATIONS),
        host=mqtt_host or os.getenv("MQTT_HOST", "127.0.0.1"),
        port=mqtt_port or int(os.getenv("MQTT_PORT", "1883")),
        username=mqtt_username if mqtt_username is not None else os.getenv("MQTT_USERNAME") or None,
        password=mqtt_password if mqtt_password is not None else os.getenv("MQTT_PASSWORD") or None,
        ack_timeout=mqtt_ack_timeout or float(os.getenv("MQTT_ACK_TIMEOUT_SECONDS", "5")),
        client_id=mqtt_client_id or os.getenv("MQTT_CLIENT_ID", "home-backend"),
    )
    adapter.connect()
    return DeviceService(adapter=adapter)


def initialize_device_service(**kwargs: Any) -> DeviceService:
    """创建并注册进程级设备服务，供 FastAPI 生命周期使用。"""

    service = create_device_service(**kwargs)
    set_device_service(service)
    return service


def close_device_service() -> None:
    """关闭 MQTT 传输并清理进程级服务。"""

    global _service
    if _service is not None:
        adapter = getattr(_service, "_adapter", None)
        disconnect = getattr(adapter, "disconnect", None)
        if disconnect is not None:
            disconnect()
    _service = None


def _state_payload(state) -> dict[str, Any]:
    return {
        "device_id": state.device_id,
        "room": state.room,
        "device_type": state.device_type.value,
        "state": state.state.value,
        "online": state.online,
        "updated_at": state.updated_at.isoformat(),
    }


def _result_payload(result) -> dict[str, Any]:
    return {
        "request_id": str(result.request_id),
        "device_id": result.device_id,
        "accepted": result.accepted,
        "state": result.state.value,
        "message": result.message,
        "blocked_reason": result.blocked_reason,
        "acknowledged_at": result.acknowledged_at.isoformat(),
    }


@tool("get_device_status")
def get_device_status(device_id: str) -> str:
    """查询单个智能家居设备的当前状态。device_id 例如 desk_light、desk_fan。"""

    service = get_device_service()
    try:
        state = service.get_device(device_id)
    except Exception as exc:  # noqa: BLE001 - tool boundary
        return f"查询失败: {exc}"
    import json

    return json.dumps(_state_payload(state), ensure_ascii=False)


@tool("list_home_devices")
def list_home_devices() -> str:
    """列出当前已注册的智能家居设备及其状态。"""

    import json

    service = get_device_service()
    return json.dumps([_state_payload(item) for item in service.list_devices()], ensure_ascii=False)


@tool("read_home_environment")
def read_home_environment(room: str = "study") -> str:
    """读取指定房间的环境传感器数据（温度、湿度、光照、人体）。默认房间 study。"""

    import json

    service = get_device_service()
    snapshot = service.get_environment(room)
    payload = {
        "room": snapshot.room,
        "generated_at": snapshot.generated_at.isoformat(),
        "readings": [
            {
                "sensor_id": reading.sensor_id,
                "kind": reading.kind.value,
                "value": reading.value,
                "unit": reading.unit,
                "online": reading.online,
                "recorded_at": reading.recorded_at.isoformat(),
                "source": reading.source,
            }
            for reading in snapshot.readings
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


@tool("set_light_state")
def set_light_state(device_id: str, state: str, request_id: str = "") -> str:
    """打开或关闭灯。state 只能是 on 或 off。device_id 例如 desk_light。"""

    import json

    service = get_device_service()
    try:
        target = DeviceStateValue(state)
    except ValueError:
        return json.dumps(
            {"accepted": False, "blocked_reason": f"state must be on/off, got: {state}"},
            ensure_ascii=False,
        )
    result = service.set_device_state(
        device_id=device_id,
        state=target,
        request_id=request_id or None,
        expected_device_type=DeviceType.LIGHT,
    )
    return json.dumps(_result_payload(result), ensure_ascii=False)


@tool("set_fan_state")
def set_fan_state(device_id: str, state: str, request_id: str = "") -> str:
    """打开或关闭风扇。state 只能是 on 或 off。device_id 例如 desk_fan。"""

    import json

    service = get_device_service()
    try:
        target = DeviceStateValue(state)
    except ValueError:
        return json.dumps(
            {"accepted": False, "blocked_reason": f"state must be on/off, got: {state}"},
            ensure_ascii=False,
        )
    result = service.set_device_state(
        device_id=device_id,
        state=target,
        request_id=request_id or None,
        expected_device_type=DeviceType.FAN,
    )
    return json.dumps(_result_payload(result), ensure_ascii=False)


@tool("run_home_scenario")
def run_home_scenario(scenario: str) -> str:
    """执行智能家居场景。scenario 支持 sleep、away、movie。睡眠模式会关闭灯和风扇。"""

    import json

    service = get_device_service()
    try:
        name = HomeScenarioName(scenario)
    except ValueError:
        return json.dumps(
            {"accepted": False, "message": f"Unsupported scenario: {scenario}"},
            ensure_ascii=False,
        )
    result = service.run_scenario(name)
    payload = {
        "scenario": result.scenario.value,
        "accepted": result.accepted,
        "message": result.message,
        "results": [_result_payload(item) for item in result.results],
    }
    return json.dumps(payload, ensure_ascii=False)


def get_home_tools():
    """返回可注册到 Agent 的家居工具列表。"""

    return [
        get_device_status,
        list_home_devices,
        read_home_environment,
        set_light_state,
        set_fan_state,
        run_home_scenario,
    ]
