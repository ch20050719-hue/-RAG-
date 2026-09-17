"""智能家居专家 Agent：总管家 / 环境感知 / 设备控制 / 舒适度。"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, List, Optional, TYPE_CHECKING

from app.agent_framework.llm.base_adapter import BaseLLMAdapter
from app.agent_framework.tools.tool_manager import ToolManager
from app.home_automation.device_models import (
    DeviceStateValue,
    DeviceType,
    HomeModeName,
    HomeScenarioName,
)
from app.home_automation.device_service import DeviceService
from app.home_automation.device_tools import get_device_service

from .base_specialist import BaseSpecialistAgent
from ..state import HomeState, Finding

if TYPE_CHECKING:
    from app.skills.skill_registry import SkillRegistry

logger = logging.getLogger(__name__)

_HOME_SPECIALTIES = frozenset({"home_butler", "environment", "device_control", "comfort"})


class HomeSpecialistAgent(BaseSpecialistAgent):
    """面向智能家居控制场景的轻量专家。"""

    def __init__(
        self,
        specialty: str,
        llm_adapter: BaseLLMAdapter,
        tool_manager: ToolManager,
        system_prompt: str = "",
        max_iterations: int = 8,
        timeout: float = 120.0,
        skill_registry: Optional["SkillRegistry"] = None,
        device_service: DeviceService | None = None,
    ) -> None:
        if specialty not in _HOME_SPECIALTIES:
            raise ValueError(f"Unsupported home specialty: {specialty}")
        if not system_prompt:
            system_prompt = _default_prompt(specialty)
        super().__init__(
            specialty=specialty,
            llm_adapter=llm_adapter,
            tool_manager=tool_manager,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            timeout=timeout,
            skill_registry=skill_registry,
        )
        self._device_service = device_service

    @property
    def device_service(self) -> DeviceService:
        """设备服务（可注入，便于测试）。"""

        if self._device_service is None:
            self._device_service = get_device_service()
        return self._device_service

    def snapshot_environment(self, room: str = "study") -> dict[str, Any]:
        """返回环境快照，供工具调用与调试使用。"""

        snapshot = self.device_service.get_environment(room)
        return {
            "room": snapshot.room,
            "generated_at": snapshot.generated_at.isoformat(),
            "readings": [reading.model_dump(mode="json") for reading in snapshot.readings],
        }

    def control_light(self, device_id: str, state: str, request_id: str | None = None) -> dict[str, Any]:
        """控制灯开关。"""

        return self._set_state(device_id, state, request_id, DeviceType.LIGHT)

    def control_fan(self, device_id: str, state: str, request_id: str | None = None) -> dict[str, Any]:
        """控制风扇开关。"""

        return self._set_state(device_id, state, request_id, DeviceType.FAN)

    def run_sleep_mode(self) -> dict[str, Any]:
        """执行睡眠模式。"""

        result = self.device_service.set_mode(HomeModeName.SLEEP)
        return result.model_dump(mode="json")

    async def run(self, user_input: str, history: List[dict] | None = None, **kwargs: Any) -> str:
        """执行家居请求；确定性设备动作经过固定工具，其他问题交给 LLM。"""

        self._reset_state()
        query = user_input.strip()
        state = _state_from_query(query)
        if state and _contains_any(query, ("灯", "light")):
            return await self._call_home_tool(
                "set_light_state",
                device_id="desk_light",
                state=state,
            )
        if state and _contains_any(query, ("风扇", "fan")):
            return await self._call_home_tool(
                "set_fan_state",
                device_id="desk_fan",
                state=state,
            )
        if _contains_any(query, ("正常模式", "日常模式")):
            return await self._call_home_tool("set_home_mode", mode="normal")
        if _contains_any(query, ("睡眠模式", "睡觉")):
            return await self._call_home_tool("set_home_mode", mode="sleep")
        if _contains_any(query, ("离家", "出门", "节能")):
            return await self._call_home_tool("set_home_mode", mode="away")
        if _contains_any(query, ("解除反锁", "释放反锁")):
            return await self._call_home_tool("release_deadbolt", authorized=False)
        if _contains_any(query, ("远程开锁", "远程开门")):
            return await self._call_home_tool("unlock_door", authorized=True)
        if _contains_any(query, ("远程锁门", "锁住房门")):
            return await self._call_home_tool("lock_door")
        if _contains_any(query, ("反锁房门", "室内反锁")):
            return await self._call_home_tool("engage_deadbolt")
        if _contains_any(query, ("门锁状态", "门磁", "门锁")):
            return await self._call_home_tool("get_door_lock_status", room="study")
        if _contains_any(query, ("温度", "湿度", "光照", "人体", "CO2", "二氧化碳", "环境")):
            return await self._call_home_tool("read_home_environment", room="study")
        if _contains_any(query, ("设备状态", "设备列表", "有哪些设备")):
            return await self._call_home_tool("list_home_devices")

        response = await self.llm_adapter.generate(self.build_prompt(query, history or []))
        return response.content

    async def stream_run(
        self, user_input: str, history: List[dict] | None = None, **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """保持基座流式 Agent 接口；家居工具结果作为一个完整事件返回。"""

        yield await self.run(user_input, history, **kwargs)

    async def audit(self, state: HomeState, documents: List[dict[str, Any]]) -> List[Finding]:
        """审查家居文档中的明显越权控制描述。"""

        findings: list[Finding] = []
        content = "\n".join(str(item.get("content", "")) for item in documents)
        if _contains_any(content, ("任意 GPIO", "任意Topic", "绕过安全")):
            findings.append(
                self.create_finding(
                    category="设备控制安全",
                    description="文档包含绕过固定设备工具的控制方式",
                    evidence=["文档命中禁止的底层控制描述"],
                    recommendations=["仅允许调用注册设备工具并执行设备类型、状态和回执校验"],
                )
            )
        return findings

    async def _call_home_tool(self, tool_name: str, **kwargs: Any) -> str:
        """通过 ToolManager 执行已注册的家居工具。"""

        if self._device_service is None:
            result = await self.call_tool(tool_name, **kwargs)
        else:
            result = self._call_injected_tool(tool_name, kwargs)
        await self._log_step("observation", result, tool_name=tool_name, tool_input=kwargs, tool_output=result)
        return result

    def _call_injected_tool(self, tool_name: str, kwargs: dict[str, Any]) -> str:
        """在注入服务时直接走同一设备服务，避免测试/嵌入场景依赖全局单例。"""

        if tool_name == "set_light_state":
            return json.dumps(self.control_light(**kwargs), ensure_ascii=False)
        if tool_name == "set_fan_state":
            return json.dumps(self.control_fan(**kwargs), ensure_ascii=False)
        if tool_name == "run_home_scenario":
            return json.dumps(
                self.device_service.run_scenario(HomeScenarioName(kwargs["scenario"])).model_dump(mode="json"),
                ensure_ascii=False,
            )
        if tool_name == "set_home_mode":
            return json.dumps(
                self.device_service.set_mode(
                    HomeModeName(kwargs["mode"]),
                    request_prefix=kwargs.get("request_prefix"),
                ).model_dump(mode="json"),
                ensure_ascii=False,
            )
        if tool_name == "get_home_mode":
            return json.dumps(
                {"room": kwargs.get("room", "study"), "mode": self.device_service.get_mode().value},
                ensure_ascii=False,
            )
        if tool_name == "get_door_lock_status":
            return json.dumps(self.device_service.get_door_lock().model_dump(mode="json"), ensure_ascii=False)
        if tool_name in {"unlock_door", "lock_door", "engage_deadbolt", "release_deadbolt"}:
            action_by_tool = {
                "unlock_door": "unlock",
                "lock_door": "lock",
                "engage_deadbolt": "engage_deadbolt",
                "release_deadbolt": "release_deadbolt",
            }
            return json.dumps(
                self.device_service.command_door_lock(
                    action_by_tool[tool_name],
                    authorized=bool(kwargs.get("authorized", False)),
                    request_id=kwargs.get("request_id"),
                ).model_dump(mode="json"),
                ensure_ascii=False,
            )
        if tool_name == "list_home_devices":
            return json.dumps(
                [item.model_dump(mode="json") for item in self.device_service.list_devices()],
                ensure_ascii=False,
            )
        if tool_name == "read_home_environment":
            snapshot = self.device_service.get_environment(kwargs.get("room", "study"))
            return json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False)
        if tool_name == "get_device_status":
            return json.dumps(
                self.device_service.get_device(kwargs["device_id"]).model_dump(mode="json"),
                ensure_ascii=False,
            )
        raise ValueError(f"Unsupported home tool: {tool_name}")

    def _set_state(
        self,
        device_id: str,
        state: str,
        request_id: str | None,
        expected_type: DeviceType,
    ) -> dict[str, Any]:
        try:
            target = DeviceStateValue(state)
        except ValueError as exc:
            return {
                "accepted": False,
                "blocked_reason": f"state must be on/off, got: {state}",
                "error": str(exc),
            }
        result = self.device_service.set_device_state(
            device_id=device_id,
            state=target,
            request_id=request_id,
            expected_device_type=expected_type,
        )
        return json.loads(result.model_dump_json())


def _contains_any(value: str, choices: tuple[str, ...]) -> bool:
    return any(choice.lower() in value.lower() for choice in choices)


def _state_from_query(query: str) -> str | None:
    if _contains_any(query, ("关闭", "关掉", "关上", "off")):
        return "off"
    if _contains_any(query, ("打开", "开启", "开灯", "开风扇", "on")):
        return "on"
    return None


def _default_prompt(specialty: str) -> str:
    """按角色生成默认系统提示词。"""

    shared = (
        "你是智能家居助手。只调用后端注册的固定设备工具，"
        "不得输出 MQTT Topic、GPIO 或任意底层指令。"
        "控制失败、设备离线或安全拦截时必须向用户说明原因。"
    )
    role = {
        "home_butler": "你是总管家，负责理解自然语言并协调环境与设备动作。",
        "environment": "你是环境感知专家，负责读取温湿度、光照与人体状态并给出舒适判断。",
        "device_control": "你是设备控制专家，负责安全地控制灯、风扇、模式和实验门锁，并回报设备状态。",
        "comfort": "你是舒适度专家，负责睡眠、离家等场景建议与执行。",
    }.get(specialty, "你是智能家居助手。")
    return f"{role}\n{shared}"


def create_home_specialist(
    specialty: str,
    llm_adapter: BaseLLMAdapter,
    tool_manager: ToolManager,
    **kwargs: Any,
) -> HomeSpecialistAgent:
    """工厂方法：创建家居专家。"""

    return HomeSpecialistAgent(
        specialty=specialty,
        llm_adapter=llm_adapter,
        tool_manager=tool_manager,
        **kwargs,
    )
