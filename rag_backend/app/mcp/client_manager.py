"""
MCP 客户端管理器 - HTTP 方式
使用简单的 HTTP API 调用远程 MCP 服务
"""

import httpx
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from app.core.config import settings
from app.security.outbound_url import validate_configured_service_url

logger = logging.getLogger(__name__)

TIMEOUT_MAP = {
    "quick": 10,
    "normal": 30,
    "slow": 60,
    "complex": 120
}


class MCPError(Exception):
    """MCP 基础错误"""
    pass


class MCPConnectionError(MCPError):
    """连接错误"""
    pass


class MCPTimeoutError(MCPError):
    """超时错误"""
    pass


@dataclass
class MCPToolInfo:
    """MCP 工具信息"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    category: str = "unknown"


class MCPClientManager:
    """
    MCP HTTP 客户端

    使用简单的 HTTP API 与远程 MCP 服务器通信
    """

    def __init__(
        self,
        server_url: str,
        api_key: str,
        timeout: int = 120
    ):
        self.server_url = validate_configured_service_url(
            server_url,
            allowed_hosts=settings.OUTBOUND_ALLOWED_HOSTS.split(","),
            private_hosts=settings.OUTBOUND_PRIVATE_HOSTS.split(","),
        ).geturl().rstrip("/")
        self.api_key = api_key
        self.default_timeout = timeout
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self._is_initialized = False
        self._tools: List[MCPToolInfo] = []

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                response = await client.get(f"{self.server_url}/health")
                return response.status_code == 200
        except (ValueError, KeyError) as e:
            logger.error(f"健康检查数据失败: {e}")
            return False
        except (OSError, IOError) as e:
            logger.error(f"健康检查IO失败: {e}")
            return False
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return False

    async def connect(self) -> None:
        """连接到 MCP 服务器"""
        if self._is_initialized:
            logger.warning("MCP Client 已连接，跳过重复 connect()")
            return

        logger.info(f"🔌 连接 MCP 服务器: {self.server_url}")

        try:
            if not await self.health_check():
                raise MCPConnectionError("MCP 服务器健康检查失败")
        except httpx.ConnectError as e:
            raise MCPConnectionError(f"无法连接到 MCP 服务器: {e}")

        await self._load_tools()
        self._is_initialized = True
        logger.info("🎉 MCP Client 初始化完成")

    async def _load_tools(self) -> None:
        """加载工具列表"""
        try:
            async with httpx.AsyncClient(timeout=self.default_timeout, follow_redirects=False) as client:
                response = await client.get(
                    f"{self.server_url}/tools",
                    headers=self._headers
                )
                response.raise_for_status()
                data = response.json()

                tools_list = data.get("tools", [])
                self._tools = [
                    MCPToolInfo(
                        name=tool.get("name", ""),
                        description=tool.get("description", ""),
                        input_schema=tool.get("input_schema", {}),
                        category=tool.get("category", "unknown")
                    )
                    for tool in tools_list
                ]
                logger.info(f"✅ 已加载 {len(self._tools)} 个云端工具")

        except httpx.TimeoutException as e:
            raise MCPTimeoutError(f"获取工具列表超时: {e}")
        except (ValueError, KeyError) as e:
            raise MCPError(f"获取工具列表数据失败: {e}")
        except (OSError, IOError) as e:
            raise MCPError(f"获取工具列表IO失败: {e}")
        except Exception as e:
            raise MCPError(f"获取工具列表失败: {e}")

    async def call_tool(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        调用远程工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果
        """
        if not self._is_initialized:
            await self.connect()

        if arguments is None:
            arguments = {}

        try:
            from app.security.tool_authorization import authorize_tool_call
            from app.tools.agent_tools import get_tool_tenant_id, get_tool_user_id
            authorize_tool_call(
                tool_name,
                arguments,
                tenant_id=get_tool_tenant_id(),
                user_id=get_tool_user_id(),
            )
        except PermissionError:
            logger.warning("MCP 工具调用未通过服务端授权: %s", tool_name)
            raise MCPError("工具调用未通过服务端安全校验")

        logger.info("📤 调用工具: %s, 参数键: %s", tool_name, sorted(arguments))

        try:
            async with httpx.AsyncClient(timeout=self.default_timeout, follow_redirects=False) as client:
                response = await client.post(
                    f"{self.server_url}/mcp/call",
                    headers=self._headers,
                    json={"tool_name": tool_name, "arguments": arguments}
                )
                response.raise_for_status()
                result = response.json()

                if "error" in result:
                    raise MCPError(f"工具执行错误: {result['error']}")

                return result.get("result", result)

        except httpx.TimeoutException as e:
            raise MCPTimeoutError(f"工具调用超时: {e}")
        except httpx.HTTPStatusError as e:
            raise MCPError(f"HTTP 错误: {e.response.status_code} - {e.response.text}")
        except (ValueError, KeyError) as e:
            raise MCPError(f"工具调用数据失败: {e}")
        except (OSError, IOError) as e:
            raise MCPError(f"工具调用IO失败: {e}")
        except Exception as e:
            raise MCPError(f"工具调用失败: {e}")

    def list_tools(self) -> List[MCPToolInfo]:
        """列出所有可用工具"""
        return self._tools

    async def disconnect(self) -> None:
        """断开连接"""
        self._is_initialized = False
        self._tools = []
        logger.info("👋 MCP Client 已断开")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
