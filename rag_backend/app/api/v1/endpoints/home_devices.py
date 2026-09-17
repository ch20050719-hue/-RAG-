"""智能家居设备查询与控制 API。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from starlette import status

from app.api import deps
from app.home_automation.device_models import (
    DeviceStateValue,
    DoorLockAction,
    HomeModeName,
    HomeScenarioName,
)
from app.home_automation.device_service import DeviceService
from app.home_automation.device_tools import get_device_service
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


class SetDeviceStateRequest(BaseModel):
    """设备开关控制请求。"""

    state: DeviceStateValue
    request_id: str | None = Field(default=None, max_length=64)


class ScenarioRequest(BaseModel):
    """场景执行请求。"""

    scenario: HomeScenarioName


class ModeRequest(BaseModel):
    """模式切换请求。"""

    mode: HomeModeName
    request_prefix: str | None = Field(default=None, max_length=64)


class DoorLockRequest(BaseModel):
    """门锁控制请求。"""

    request_id: str | None = Field(default=None, max_length=64)
    confirmed: bool = False


def _ensure_service() -> DeviceService:
    """获取设备服务（默认模拟适配器）。"""

    return get_device_service()


def _reading_payload(reading) -> dict[str, Any]:
    """序列化环境读数，统一返回质量与分级字段。"""

    return {
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


def _snapshot_payload(snapshot) -> dict[str, Any]:
    """序列化环境快照。"""

    return {
        "room": snapshot.room,
        "generated_at": snapshot.generated_at.isoformat(),
        "readings": [_reading_payload(reading) for reading in snapshot.readings],
    }


def _mode_payload(result, room: str) -> dict[str, Any]:
    """序列化模式切换结果，保留每一步 ack 回执。"""

    return {
        "room": room,
        "mode": result.mode.value,
        "previous_mode": result.previous_mode.value,
        "accepted": result.accepted,
        "overall_status": result.overall_status.value,
        "message": result.message,
        "actions": [
            {
                "name": action.name,
                "accepted": action.accepted,
                "message": action.message,
                "device_id": action.device_id,
                "command_result": (
                    {
                        "request_id": str(action.command_result.request_id),
                        "device_id": action.command_result.device_id,
                        "accepted": action.command_result.accepted,
                        "state": action.command_result.state.value,
                        "message": action.command_result.message,
                        "blocked_reason": action.command_result.blocked_reason,
                        "acknowledged_at": action.command_result.acknowledged_at.isoformat(),
                    }
                    if action.command_result is not None
                    else None
                ),
                "lock_result": (
                    action.lock_result.model_dump(mode="json")
                    if action.lock_result is not None
                    else None
                ),
            }
            for action in result.actions
        ],
    }


def _door_lock_state_payload(state) -> dict[str, Any]:
    """序列化门锁与门磁状态。"""

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


def _door_lock_result_payload(result) -> dict[str, Any]:
    """序列化门锁命令回执。"""

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


@router.get("/devices")
async def list_devices(current_user: User = Depends(deps.get_current_user)) -> list[dict[str, Any]]:
    """列出智能家居设备状态。"""

    service = _ensure_service()
    return [
        {
            "device_id": item.device_id,
            "room": item.room,
            "device_type": item.device_type.value,
            "state": item.state.value,
            "online": item.online,
            "updated_at": item.updated_at.isoformat(),
        }
        for item in service.list_devices()
    ]


@router.get("/devices/{device_id}")
async def get_device(
    device_id: str,
    current_user: User = Depends(deps.get_current_user),
) -> dict[str, Any]:
    """查询单个设备状态。"""

    service = _ensure_service()
    try:
        item = service.get_device(device_id)
    except Exception as exc:  # noqa: BLE001 - API boundary
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return {
        "device_id": item.device_id,
        "room": item.room,
        "device_type": item.device_type.value,
        "state": item.state.value,
        "online": item.online,
        "updated_at": item.updated_at.isoformat(),
    }


@router.post("/devices/{device_id}/state")
async def set_device_state(
    device_id: str,
    request: SetDeviceStateRequest,
    current_user: User = Depends(deps.get_current_user),
) -> dict[str, Any]:
    """下发设备开关指令（经安全规则与设备回执）。"""

    service = _ensure_service()
    result = service.set_device_state(
        device_id=device_id,
        state=request.state,
        request_id=request.request_id,
    )
    return {
        "request_id": str(result.request_id),
        "device_id": result.device_id,
        "accepted": result.accepted,
        "state": result.state.value,
        "message": result.message,
        "blocked_reason": result.blocked_reason,
        "acknowledged_at": result.acknowledged_at.isoformat(),
    }


@router.get("/environment")
async def get_environment(
    room: str | None = None,
    current_user: User = Depends(deps.get_current_user),
) -> dict[str, Any]:
    """读取房间环境传感器数据。"""

    service = _ensure_service()
    snapshot = service.get_environment(room)
    return _snapshot_payload(snapshot)


@router.get("/environment/history")
async def get_environment_history(
    room: str | None = None,
    minutes: int = Query(default=10, ge=1, le=60),
    current_user: User = Depends(deps.get_current_user),
) -> dict[str, Any]:
    """读取最近时间窗口内的环境历史快照。"""

    service = _ensure_service()
    target_room = room or "study"
    snapshots = service.get_environment_history(target_room, minutes=minutes)
    return {
        "room": target_room,
        "minutes": minutes,
        "samples": [_snapshot_payload(snapshot) for snapshot in snapshots],
    }


@router.get("/alerts")
async def get_environment_alerts(
    room: str | None = None,
    active_only: bool = False,
    current_user: User = Depends(deps.get_current_user),
) -> list[dict[str, Any]]:
    """读取环境报警与传感器故障记录。"""

    service = _ensure_service()
    alerts = service.get_environment_alerts(room, active_only=active_only)
    return [alert.model_dump(mode="json") for alert in alerts]


@router.get("/mode")
async def get_home_mode(
    current_user: User = Depends(deps.get_current_user),
) -> dict[str, str]:
    """读取当前房间运行模式。"""

    service = _ensure_service()
    return {"room": "study", "mode": service.get_mode().value}


@router.post("/mode")
async def set_home_mode(
    request: ModeRequest,
    current_user: User = Depends(deps.get_current_user),
) -> dict[str, Any]:
    """切换正常、睡眠或离家模式并返回逐步执行结果。"""

    service = _ensure_service()
    result = service.set_mode(request.mode, request_prefix=request.request_prefix)
    return _mode_payload(result, room="study")


@router.get("/lock/status")
async def get_door_lock_status(
    current_user: User = Depends(deps.get_current_user),
) -> dict[str, Any]:
    """读取实验门锁状态。"""

    return _door_lock_state_payload(_ensure_service().get_door_lock())


@router.post("/lock/unlock")
async def unlock_door(
    request: DoorLockRequest,
    current_user: User = Depends(deps.get_current_user),
) -> dict[str, Any]:
    """在当前登录用户权限下远程解锁。"""

    result = _ensure_service().command_door_lock(
        DoorLockAction.UNLOCK,
        authorized=True,
        request_id=request.request_id,
    )
    return _door_lock_result_payload(result)


@router.post("/lock/lock")
async def lock_door(
    request: DoorLockRequest,
    current_user: User = Depends(deps.get_current_user),
) -> dict[str, Any]:
    """读取门磁并在门已关闭时远程锁门。"""

    result = _ensure_service().command_door_lock(
        DoorLockAction.LOCK,
        request_id=request.request_id,
    )
    return _door_lock_result_payload(result)


@router.post("/lock/deadbolt/engage")
async def engage_deadbolt(
    request: DoorLockRequest,
    current_user: User = Depends(deps.get_current_user),
) -> dict[str, Any]:
    """读取门磁并在门已关闭时执行反锁。"""

    result = _ensure_service().command_door_lock(
        DoorLockAction.ENGAGE_DEADBOLT,
        request_id=request.request_id,
    )
    return _door_lock_result_payload(result)


@router.post("/lock/deadbolt/release")
async def release_deadbolt(
    request: DoorLockRequest,
    current_user: User = Depends(deps.get_current_user),
) -> dict[str, Any]:
    """在当前登录用户权限下解除反锁。"""

    result = _ensure_service().command_door_lock(
        DoorLockAction.RELEASE_DEADBOLT,
        authorized=True,
        confirmed=request.confirmed,
        request_id=request.request_id,
    )
    return _door_lock_result_payload(result)


@router.post("/scenarios")
async def run_scenario(
    request: ScenarioRequest,
    current_user: User = Depends(deps.get_current_user),
) -> dict[str, Any]:
    """执行预置场景（sleep/away/movie）。"""

    service = _ensure_service()
    result = service.run_scenario(request.scenario)
    return {
        "scenario": result.scenario.value,
        "accepted": result.accepted,
        "message": result.message,
        "results": [
            {
                "request_id": str(item.request_id),
                "device_id": item.device_id,
                "accepted": item.accepted,
                "state": item.state.value,
                "message": item.message,
                "blocked_reason": item.blocked_reason,
            }
            for item in result.results
        ],
    }
