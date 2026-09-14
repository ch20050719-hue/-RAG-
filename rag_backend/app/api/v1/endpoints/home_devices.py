"""智能家居设备查询与控制 API。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from starlette import status

from app.api import deps
from app.home_automation.device_models import DeviceStateValue, HomeScenarioName
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


def _ensure_service() -> DeviceService:
    """获取设备服务（默认模拟适配器）。"""

    return get_device_service()


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
    return {
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
