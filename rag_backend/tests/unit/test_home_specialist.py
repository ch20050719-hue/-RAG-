"""智能家居专家 Agent 的可实例化与工具闭环测试。"""

from collections.abc import AsyncGenerator

from app.agent_framework.llm.base_adapter import BaseLLMAdapter, LLMResponse
from app.agent_framework.tools.tool_manager import ToolManager
from app.home_automation.default_devices import DEFAULT_DEVICE_REGISTRATIONS
from app.home_automation.device_service import DeviceService
from app.home_automation.device_tools import get_home_tools
from app.home_automation.simulated_device import SimulatedDeviceAdapter
from app.multi_agent_system.agents.home_specialist import HomeSpecialistAgent


class DummyHomeLLM(BaseLLMAdapter):
    async def _chat(self, messages, temperature=0.1, max_tokens=None, **kwargs) -> LLMResponse:
        return LLMResponse(content="已完成智能家居处理")

    async def generate(self, prompt: str, temperature: float = 0.1, max_tokens=None, **kwargs) -> LLMResponse:
        return LLMResponse(content="已完成智能家居处理")

    async def stream_generate(
        self, prompt: str, temperature: float = 0.1, max_tokens=None, **kwargs
    ) -> AsyncGenerator[dict, None]:
        yield {"type": "delta", "content": "已完成智能家居处理"}


def _home_service() -> DeviceService:
    return DeviceService(
        SimulatedDeviceAdapter(registrations=list(DEFAULT_DEVICE_REGISTRATIONS))
    )


def test_home_specialist_runs_a_light_control_request():
    service = _home_service()
    tools = ToolManager()
    for home_tool in get_home_tools():
        tools.register_langchain_tool(home_tool)

    agent = HomeSpecialistAgent(
        specialty="device_control",
        llm_adapter=DummyHomeLLM(),
        tool_manager=tools,
        device_service=service,
    )

    result = __import__("asyncio").run(agent.run("打开书桌灯"))

    assert "desk_light" in result
    assert service.get_device("desk_light").state.value == "on"


def test_home_specialist_routes_mode_and_lock_queries_to_fixed_tools():
    service = _home_service()
    tools = ToolManager()
    for home_tool in get_home_tools():
        tools.register_langchain_tool(home_tool)

    agent = HomeSpecialistAgent(
        specialty="home_butler",
        llm_adapter=DummyHomeLLM(),
        tool_manager=tools,
        device_service=service,
    )

    import asyncio

    mode_result = asyncio.run(agent.run("切换睡眠模式"))
    lock_result = asyncio.run(agent.run("查看门锁状态"))

    assert '"mode": "sleep"' in mode_result
    assert '"device_id": "door_lock"' in lock_result


def test_home_specialist_does_not_bypass_deadbolt_authorization():
    service = _home_service()
    tools = ToolManager()
    for home_tool in get_home_tools():
        tools.register_langchain_tool(home_tool)

    agent = HomeSpecialistAgent(
        specialty="device_control",
        llm_adapter=DummyHomeLLM(),
        tool_manager=tools,
        device_service=service,
    )

    import asyncio

    result = asyncio.run(agent.run("解除反锁"))

    assert "authorization" in result.lower()


def test_home_specialist_routes_servo_open_and_close_actions():
    service = _home_service()
    tools = ToolManager()
    for home_tool in get_home_tools():
        tools.register_langchain_tool(home_tool)

    agent = HomeSpecialistAgent(
        specialty="device_control",
        llm_adapter=DummyHomeLLM(),
        tool_manager=tools,
        device_service=service,
    )

    import asyncio

    open_result = asyncio.run(agent.run("自动打开房门"))
    close_result = asyncio.run(agent.run("自动关闭房门"))

    assert '"action": "open_door"' in open_result
    assert '"door_state": "open"' in open_result
    assert '"action": "close_door"' in close_result
    assert '"door_state": "closed"' in close_result
