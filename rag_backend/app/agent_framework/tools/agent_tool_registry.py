"""
Agent 工具注册器

统一采用 MCP 装饰器（@local_tool/@cloud_tool）注册工具，并为智能家居设备工具保留
稳定的 ToolManager 接口。控制类工具必须通过安全校验和设备服务执行。
"""

import logging

from app.agent_framework.tools.tool_manager import ToolManager

logger = logging.getLogger(__name__)


async def register_tools(
    tool_manager: ToolManager,
    include_mcp: bool = True,
    include_local: bool = True
) -> dict:
    """
    注册所有 MCP 工具到 ToolManager。

    Returns:
        注册结果统计 dict
    """
    result = {
        "local_tools": [],
        "cloud_tools": [],
        "total_count": 0
    }

    logger.info("🔧 注册 MCP 工具...")

    from app.mcp import get_unified_tools
    unified = get_unified_tools()

    if include_local:
        for tool_func in unified["local"]:
            try:
                tool_manager.register_langchain_tool(tool_func)
                result["local_tools"].append(tool_func.name)
                logger.debug(f"✅ 注册本地工具: {tool_func.name}")
            except Exception as e:
                logger.error(f"❌ 注册本地工具失败: {tool_func.name} - {e}")

    if include_mcp:
        for tool_func in unified["cloud"]:
            try:
                tool_manager.register_langchain_tool(tool_func)
                result["cloud_tools"].append(tool_func.name)
                logger.debug(f"✅ 注册云端工具: {tool_func.name}")
            except Exception as e:
                logger.error(f"❌ 注册云端工具失败: {tool_func.name} - {e}")

    result["total_count"] = len(result["local_tools"]) + len(result["cloud_tools"])
    logger.info(
        f"✅ MCP 工具注册完成：本地 {len(result['local_tools'])} + "
        f"云端 {len(result['cloud_tools'])} = {result['total_count']} 个"
    )
    return result


async def initialize_tool_manager(
    tool_manager: ToolManager,
    include_mcp: bool = True,
    include_local: bool = True,
    tenant_id: str = "default"
) -> dict:
    """
    初始化工具管理器：通用 RAG/MCP 工具、智能家居工具和代码解释器。
    """
    result = await register_tools(
        tool_manager,
        include_mcp=include_mcp,
        include_local=include_local
    )

    # 领域控制工具统一由 home_automation.device_tools 提供；不再注册旧领域 ToolBase。
    toolbase_registered: list = []

    # ── 注册代码解释器（execute_python）──
    # code_interpreter.py 使用 @auto_register_tool，但该装饰器挂载在模块级全局列表上，
    # 必须显式导入模块触发装饰器，再手动把函数注册进 ToolManager。
    code_registered: list = []
    try:
        from app.agent_framework.tools.code_interpreter import execute_python
        from app.agent_framework.tools.decorators import get_auto_registered_tools

        for meta in get_auto_registered_tools():
            if meta.get("name") == "execute_python":
                tool_manager.register_function(
                    name="execute_python",
                    func=execute_python,
                    description=meta.get("description", "在沙箱中执行 Python 代码，支持 math/json/re/datetime 等安全模块"),
                )
                code_registered.append("execute_python")
                logger.info("✅ 代码解释器工具 execute_python 注册完成")
                break
    except Exception as e:
        logger.warning(f"[工具注册] execute_python 注册失败（非致命）: {e}")

    result["toolbase_tools"] = toolbase_registered
    result["code_tools"] = code_registered

    # 智能家居工具与既有通用 MCP 共存，保持 ToolManager 接口不变。
    home_registered: list = []
    try:
        from app.home_automation.device_tools import get_home_tools

        for home_tool in get_home_tools():
            tool_manager.register_langchain_tool(home_tool)
            home_registered.append(home_tool.name)
        logger.info("✅ 智能家居工具注册完成：%s 个", len(home_registered))
    except Exception as e:
        logger.warning("[工具注册] 智能家居工具注册失败（非致命）: %s", e)

    result["home_tools"] = home_registered
    result["total_count"] = (
        result.get("total_count", 0)
        + len(toolbase_registered)
        + len(code_registered)
        + len(home_registered)
    )
    return result


def get_receptionist_tools_config() -> dict:
    """接待智能体工具配置。"""
    return {
        "mcp_tools": [],
        "local_tools": ["list_home_devices", "get_device_status", "read_home_environment"],
    }


def get_specialist_tools_config(specialty: str = "general") -> dict:
    """
    各智能家居 Agent 可用工具列表（用于 _build_openai_tools 过滤）。
    """
    specialty_aliases = {
        "总管家": "home_butler", "home": "home_butler", "home_butler": "home_butler",
        "环境": "environment", "environment": "environment",
        "设备": "device_control", "device_control": "device_control",
        "舒适": "comfort", "comfort": "comfort",
        "通用": "general", "general": "general",
    }
    specialty_key = specialty_aliases.get((specialty or "general").lower(), specialty or "general")

    home_tools = [
        "list_home_devices", "get_device_status", "read_home_environment",
        "get_environment_thresholds", "get_automation_mode", "set_automation_mode",
        "set_environment_threshold", "set_light_state", "set_fan_state",
        "set_sprinkler_pump_state", "set_alarm_buzzer_state",
    ]
    mapping = {
        "home_butler": {"mcp_tools": [], "local_tools": home_tools},
        "environment": {"mcp_tools": [], "local_tools": ["list_home_devices", "get_device_status", "read_home_environment", "get_environment_thresholds"]},
        "device_control": {"mcp_tools": [], "local_tools": ["get_device_status", "set_light_state", "set_fan_state", "set_sprinkler_pump_state", "set_alarm_buzzer_state", "get_automation_mode", "set_automation_mode", "set_environment_threshold"]},
        "comfort": {"mcp_tools": [], "local_tools": home_tools},
    }

    if specialty_key.lower() == "general":
        # 通用智能体：全量工具，LLM 自行决策
        return {"mcp_tools": ["*"], "local_tools": ["*"]}

    return mapping.get(specialty_key.lower(), {"mcp_tools": [], "local_tools": []})
