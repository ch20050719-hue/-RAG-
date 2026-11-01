"""Agent 可调用的智能家居固定工具。"""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.tools import tool

from .default_devices import DEFAULT_DEVICE_REGISTRATIONS, DEFAULT_SENSOR_REGISTRATIONS
from .device_models import (
    AutomationMode,
    DeviceStateValue,
    DeviceType,
    DoorLockAction,
    HomeScenarioName,
    ThresholdName,
)
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
    """读取指定房间的环境传感器数据（温度、湿度、烟雾、火焰和有人状态）。默认房间 study。"""

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
                "quality": reading.quality.value,
                "level": reading.level.value,
            }
            for reading in snapshot.readings
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


@tool("get_environment_history")
def get_environment_history(room: str = "study", minutes: int = 10) -> str:
    """读取指定房间最近一段时间的环境历史快照，默认返回最近 10 分钟。"""

    import json

    service = get_device_service()
    try:
        snapshots = service.get_environment_history(room, minutes=minutes)
    except ValueError as exc:
        return json.dumps({"accepted": False, "message": str(exc)}, ensure_ascii=False)
    return json.dumps(
        {
            "room": room,
            "minutes": minutes,
            "samples": [
                {
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
                            "quality": reading.quality.value,
                            "level": reading.level.value,
                        }
                        for reading in snapshot.readings
                    ],
                }
                for snapshot in snapshots
            ],
        },
        ensure_ascii=False,
    )


@tool("get_home_alerts")
def get_home_alerts(room: str = "study", active_only: bool = False) -> str:
    """读取指定房间的环境报警与传感器故障记录。"""

    import json

    service = get_device_service()
    alerts = service.get_environment_alerts(room, active_only=active_only)
    return json.dumps(
        [alert.model_dump(mode="json") for alert in alerts],
        ensure_ascii=False,
    )


@tool("get_automation_mode")
def get_automation_mode(room: str = "study") -> str:
    """读取版本三手动/自动设备主控制模式。"""

    import json

    return json.dumps(
        {"room": room, "automation_mode": get_device_service().get_automation_mode().value},
        ensure_ascii=False,
    )


@tool("set_automation_mode")
def set_automation_mode(mode: str, room: str = "study") -> str:
    """切换 manual/automatic；自动模式允许阈值规则执行固定联动。"""

    import json

    try:
        target = AutomationMode(mode)
    except ValueError:
        return json.dumps({"accepted": False, "message": "mode must be manual or automatic"}, ensure_ascii=False)
    try:
        selected = get_device_service().set_automation_mode(target)
    except ValueError as exc:
        return json.dumps({"accepted": False, "message": str(exc)}, ensure_ascii=False)
    return json.dumps({"accepted": True, "room": room, "automation_mode": selected.value}, ensure_ascii=False)


@tool("run_home_scenario")
def run_home_scenario(scenario: str, room: str = "study", request_id: str = "") -> str:
    """执行 normal/sleep/away 固定场景预设，返回逐动作回执。"""

    import json

    try:
        target = HomeScenarioName(scenario)
    except ValueError:
        return json.dumps(
            {"accepted": False, "message": "scenario must be normal, sleep, or away"},
            ensure_ascii=False,
        )
    result = get_device_service().run_scenario(target, request_id=request_id or None)
    payload = result.model_dump(mode="json")
    payload["room"] = result.room
    return json.dumps(payload, ensure_ascii=False)


@tool("get_environment_thresholds")
def get_environment_thresholds(room: str = "study") -> str:
    """读取温度上限、湿度上限和实验烟雾上限。"""

    import json

    return json.dumps(
        {"room": room, "thresholds": get_device_service().get_thresholds().model_dump()},
        ensure_ascii=False,
    )


@tool("set_environment_threshold")
def set_environment_threshold(name: str, value: float, room: str = "study") -> str:
    """更新一个固定版本三阈值，名称不接受任意寄存器或底层参数。"""

    import json

    try:
        threshold_name = ThresholdName(name)
        thresholds = get_device_service().set_threshold(threshold_name, value)
    except (ValueError, TypeError) as exc:
        return json.dumps({"accepted": False, "message": str(exc)}, ensure_ascii=False)
    return json.dumps(
        {"accepted": True, "room": room, "thresholds": thresholds.model_dump()},
        ensure_ascii=False,
    )


def _door_lock_result_payload(result) -> dict[str, Any]:
    return {
        "request_id": str(result.request_id),
        "device_id": result.device_id,
        "room": result.room,
        "action": result.action.value,
        "accepted": result.accepted,
        "ack_status": result.ack_status.value,
        "message": result.message,
        "blocked_reason": result.blocked_reason,
        "door_state": result.door_state.value,
        "latch_state": result.latch_state.value,
        "deadbolt_state": result.deadbolt_state.value,
        "battery_level": result.battery_level,
        "expires_at": result.expires_at.isoformat() if result.expires_at else None,
        "acknowledged_at": result.acknowledged_at.isoformat(),
    }


def _door_lock_state_payload(state) -> dict[str, Any]:
    return {
        "device_id": state.device_id,
        "room": state.room,
        "door_state": state.door_state.value,
        "latch_state": (state.latch_state or state.lock_state).value,
        "lock_state": state.lock_state.value,
        "deadbolt_state": state.deadbolt_state.value,
        "online": state.online,
        "battery_level": state.battery_level,
        "battery_state": state.battery_state.value,
        "jammed": state.jammed,
        "tampered": state.tampered,
        "last_command": state.last_command,
        "ack_status": state.ack_status.value,
        "updated_at": state.updated_at.isoformat(),
    }


@tool("get_door_lock_status")
def get_door_lock_status(room: str = "study") -> str:
    """读取指定房间实验门锁、门磁和电量状态。"""

    import json

    return json.dumps(_door_lock_state_payload(get_device_service().get_door_lock()), ensure_ascii=False)


def _execute_door_lock_tool(
    action: DoorLockAction,
    *,
    authorized: bool = False,
    request_id: str = "",
) -> str:
    import json

    result = get_device_service().command_door_lock(
        action,
        authorized=authorized,
        request_id=request_id or None,
    )
    return json.dumps(_door_lock_result_payload(result), ensure_ascii=False)


@tool("unlock_door")
def unlock_home_door(authorized: bool = False, request_id: str = "") -> str:
    """远程解锁门舌；必须显式提供用户授权。"""

    return _execute_door_lock_tool(
        DoorLockAction.UNLOCK,
        authorized=authorized,
        request_id=request_id,
    )


@tool("open_door")
def open_home_door(authorized: bool = False, request_id: str = "") -> str:
    """通过舵机自动打开门体；必须显式提供用户授权。"""

    return _execute_door_lock_tool(
        DoorLockAction.OPEN_DOOR,
        authorized=authorized,
        request_id=request_id,
    )


@tool("close_door")
def close_home_door(authorized: bool = False, request_id: str = "") -> str:
    """通过舵机自动关闭门体；必须显式提供用户授权。"""

    return _execute_door_lock_tool(
        DoorLockAction.CLOSE_DOOR,
        authorized=authorized,
        request_id=request_id,
    )


@tool("lock_door")
def lock_home_door(request_id: str = "") -> str:
    """远程锁门；房门打开时会被门磁安全规则拒绝。"""

    return _execute_door_lock_tool(DoorLockAction.LOCK, request_id=request_id)


@tool("engage_deadbolt")
def engage_home_deadbolt(request_id: str = "") -> str:
    """执行室内反锁；房门打开时拒绝反锁。"""

    return _execute_door_lock_tool(DoorLockAction.ENGAGE_DEADBOLT, request_id=request_id)


@tool("release_deadbolt")
def release_home_deadbolt(
    authorized: bool = False,
    confirmed: bool = False,
    request_id: str = "",
) -> str:
    """解除室内反锁；必须显式提供用户授权和二次确认。"""

    return _execute_door_lock_tool(
        DoorLockAction.RELEASE_DEADBOLT,
        authorized=authorized,
        confirmed=confirmed,
        request_id=request_id,
    )


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


@tool("set_sprinkler_pump_state")
def set_sprinkler_pump_state(state: str, request_id: str = "") -> str:
    """控制模拟喷淋水泵。state 只能是 on 或 off。"""

    import json

    try:
        target = DeviceStateValue(state)
    except ValueError:
        return json.dumps(
            {"accepted": False, "blocked_reason": f"state must be on/off, got: {state}"},
            ensure_ascii=False,
        )
    result = get_device_service().set_pump_state(target, request_id=request_id or None)
    return json.dumps(_result_payload(result), ensure_ascii=False)


@tool("set_alarm_buzzer_state")
def set_alarm_buzzer_state(state: str, request_id: str = "") -> str:
    """控制报警蜂鸣器。state 只能是 on 或 off。"""

    import json

    try:
        target = DeviceStateValue(state)
    except ValueError:
        return json.dumps(
            {"accepted": False, "blocked_reason": f"state must be on/off, got: {state}"},
            ensure_ascii=False,
        )
    result = get_device_service().set_buzzer_state(target, request_id=request_id or None)
    return json.dumps(_result_payload(result), ensure_ascii=False)


def get_home_tools():
    """返回可注册到 Agent 的家居工具列表。"""

    return [
        get_device_status,
        list_home_devices,
        read_home_environment,
        get_environment_history,
        get_home_alerts,
        get_automation_mode,
        set_automation_mode,
        run_home_scenario,
        get_environment_thresholds,
        set_environment_threshold,
        get_door_lock_status,
        open_home_door,
        close_home_door,
        unlock_home_door,
        lock_home_door,
        engage_home_deadbolt,
        release_home_deadbolt,
        set_light_state,
        set_fan_state,
        set_sprinkler_pump_state,
        set_alarm_buzzer_state,
    ]
