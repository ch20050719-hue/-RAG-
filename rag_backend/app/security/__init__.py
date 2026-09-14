"""
安全模块

提供多租户安全保护，包括：
1. Cypher AST 验证 - 防止 Cypher 注入攻击
2. 租户隔离机制 - 确保数据隔离
3. 权限控制 - 细粒度的权限管理
"""

from app.security.cypher_validator import (
    CypherValidator,
    ValidationResult,
    ValidationLevel,
    get_cypher_validator,
)

from app.security.tenant_isolation import (
    TenantContext,
    TenantIsolation,
    TenantIsolationLevel,
    get_tenant_context,
    get_tenant_isolation,
    set_tenant_context,
)

from app.security.permission import (
    Permission,
    PermissionType,
    Role,
    RoleType,
    PermissionChecker,
    PermissionDenied,
    get_permission_checker,
)

from app.security.interaction_safety import (
    InteractionSafetyGuard,
    InteractionHandle,
    RiskLevel,
    SafetyAbort,
    SafetyConfig,
    SafetyDecision,
    interaction_guard,
)
from app.security.tool_authorization import ToolAuthorizationError, authorize_tool_call
from app.security.session_access import can_access_session
from app.security.outbound_url import (
    OutboundURLPolicyError,
    validate_outbound_url,
    validate_configured_service_url,
    validate_resolved_outbound_url,
)

__all__ = [
    "CypherValidator",
    "ValidationResult",
    "ValidationLevel",
    "get_cypher_validator",
    "TenantContext",
    "TenantIsolation",
    "TenantIsolationLevel",
    "get_tenant_context",
    "get_tenant_isolation",
    "set_tenant_context",
    "Permission",
    "PermissionType",
    "Role",
    "RoleType",
    "PermissionChecker",
    "PermissionDenied",
    "get_permission_checker",
    "InteractionSafetyGuard",
    "InteractionHandle",
    "RiskLevel",
    "SafetyAbort",
    "SafetyConfig",
    "SafetyDecision",
    "interaction_guard",
    "ToolAuthorizationError",
    "authorize_tool_call",
    "can_access_session",
    "OutboundURLPolicyError",
    "validate_outbound_url",
    "validate_configured_service_url",
    "validate_resolved_outbound_url",
]
