"""
MCP 统一入口

所有智能体工具统一通过 MCP 协议提供
使用 @local_tool/@cloud_tool 装饰器标记工具类型

架构：
- @local_tool: 本地 STDIO MCP（访问本地数据库）
- @cloud_tool: 云端 MCP HTTP（访问外部 API）
- 云端连接失败自动回退到本地实现
"""

import logging

from app.mcp.decorators import (
    local_tool,
    cloud_tool,
    ToolSource,
    get_registry,
    get_tool_metadata,
    get_tool_source,
    clear_registry,
)

logger = logging.getLogger(__name__)

__all__ = [
    "local_tool",
    "cloud_tool",
    "ToolSource",
    "get_registry",
    "get_tool_metadata",
    "get_tool_source",
    "clear_registry",
    "create_database_tools",
    "create_foundation_tools",
    "get_all_local_tools",
    "get_all_cloud_tools",
    "get_unified_tools",
]


def create_database_tools():
    """创建数据库工具"""
    from app.mcp.database_tools import create_database_tools as _create
    return _create()


def create_foundation_tools():
    """创建基础设施工具（时间锚点和派单印章）"""
    from app.mcp.foundation_tools import create_foundation_tools as _create
    return _create()


def get_all_local_tools():
    """获取所有本地工具"""
    tools = []
    tools.extend(create_database_tools())
    tools.extend(create_foundation_tools())
    try:
        from app.services.custom_tool_service import get_published_custom_tool_callables

        tools.extend(get_published_custom_tool_callables())
    except Exception as e:
        logger.warning(f"Failed to load published custom tools: {e}")
    logger.info(f"📦 本地 MCP 工具: {len(tools)} 个")
    return tools


def get_all_cloud_tools():
    """获取所有云端工具。

    领域云工具已移除；智能家居设备通信由受控 MQTT 适配器负责。
    """
    logger.info("☁️ 云端 MCP 工具: 0 个")
    return []


def get_unified_tools():
    """获取所有工具"""
    local = get_all_local_tools()
    cloud = get_all_cloud_tools()
    logger.info(f"🔧 统一 MCP: 本地 {len(local)} + 云端 {len(cloud)} = {len(local) + len(cloud)} 个")
    return {
        "local": local,
        "cloud": cloud,
        "all": local + cloud
    }
