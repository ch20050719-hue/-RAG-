"""智能家居工具路由配置。

保留原有工具路由接口，但只暴露知识检索、环境读取、设备控制和场景执行。
底层 MQTT Topic/GPIO 不作为 Agent 工具开放。
"""

from enum import Enum
from typing import Dict, List, Optional


class ToolCategory(Enum):
    LOCAL = "local"
    MCP = "mcp"
    COMPUTATION = "computation"


TOOL_ROUTING_CONFIG: Dict[str, Dict] = {
    "search_enterprise_knowledge": {"category": ToolCategory.LOCAL, "description": "检索智能家居设备、场景和安全规则知识", "fallback": None, "retry": True},
    "list_home_devices": {"category": ToolCategory.LOCAL, "description": "列出当前租户已注册的智能家居设备", "fallback": None, "retry": True},
    "get_device_status": {"category": ToolCategory.LOCAL, "description": "读取指定设备的在线状态和当前状态", "fallback": None, "retry": True},
    "read_home_environment": {"category": ToolCategory.LOCAL, "description": "读取房间温度、湿度、光照和人体感知数据", "fallback": None, "retry": True},
    "set_light_state": {"category": ToolCategory.LOCAL, "description": "经过安全校验后控制灯具开关", "fallback": None, "retry": False},
    "set_fan_state": {"category": ToolCategory.LOCAL, "description": "经过安全校验后控制风扇开关", "fallback": None, "retry": False},
    "run_home_scenario": {"category": ToolCategory.LOCAL, "description": "执行预定义智能家居场景，并返回逐设备结果", "fallback": None, "retry": False},
    "publish_mqtt_command": {"category": ToolCategory.MCP, "description": "通过受控 MQTT 适配器发布已验证的设备命令", "fallback": None, "retry": False},
}


def get_local_tools() -> List[str]:
    return [name for name, config in TOOL_ROUTING_CONFIG.items() if config["category"] == ToolCategory.LOCAL]


def get_mcp_tools() -> List[str]:
    return [name for name, config in TOOL_ROUTING_CONFIG.items() if config["category"] == ToolCategory.MCP]


def get_tool_config(tool_name: str) -> Optional[Dict]:
    return TOOL_ROUTING_CONFIG.get(tool_name)


def is_mcp_tool(tool_name: str) -> bool:
    config = get_tool_config(tool_name)
    return bool(config and config["category"] == ToolCategory.MCP)


def is_local_tool(tool_name: str) -> bool:
    config = get_tool_config(tool_name)
    return bool(config and config["category"] == ToolCategory.LOCAL)


def get_tools_by_category(category: ToolCategory) -> Dict[str, Dict]:
    return {name: config for name, config in TOOL_ROUTING_CONFIG.items() if config["category"] == category}


def get_tool_system_instruction() -> str:
    local_desc = "\n".join(f"  - {name}: {TOOL_ROUTING_CONFIG[name]['description']}" for name in get_local_tools())
    mcp_desc = "\n".join(f"  - {name}: {TOOL_ROUTING_CONFIG[name]['description']}" for name in get_mcp_tools())
    return f"""
## 智能家居工具使用策略

### 本地工具
{local_desc}

### 受控通信工具
{mcp_desc}

### 调用原则
1. 查询先检索知识库或读取设备状态。
2. 控制前必须确认设备身份、设备类型、目标状态和安全规则。
3. 场景只能调用预定义动作；失败时停止后续动作并返回回执。
4. 不得直接生成 MQTT Topic、GPIO 或任意底层指令。
"""
