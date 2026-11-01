"""工具调用边界校验：工具名、参数白名单和租户上下文。"""

from __future__ import annotations

from typing import Any, Mapping

from app.agent_framework.tools.tool_router import get_tool_config


class ToolAuthorizationError(PermissionError):
    """工具调用不满足服务端安全边界。"""


def authorize_tool_call(
    tool_name: str,
    arguments: Mapping[str, Any] | None = None,
    *,
    tenant_id: str = "",
    user_id: str = "",
) -> None:
    """在实际执行工具前拒绝未知工具和越权租户参数。"""
    name = str(tool_name or "").strip()
    config = get_tool_config(name)
    if not name or config is None:
        raise ToolAuthorizationError("工具未被服务端 allowlist 授权")

    args = dict(arguments or {})
    declared = config.get("input_params")
    if declared:
        unknown = set(args).difference(declared)
        if unknown:
            raise ToolAuthorizationError("工具参数不在 allowlist 中")

    requested_tenant = args.get("tenant_id")
    if requested_tenant is not None:
        if not tenant_id or str(requested_tenant) != str(tenant_id):
            raise ToolAuthorizationError("工具租户参数与服务端上下文不一致")

    # 带租户数据访问能力的工具必须有服务端主体上下文。
    category = config.get("category")
    category_value = getattr(category, "value", category)
    if category_value == "local" and (not tenant_id or not user_id):
        raise ToolAuthorizationError("本地数据工具缺少租户或用户上下文")
