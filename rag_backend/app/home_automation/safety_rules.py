"""设备操作安全规则：白名单、参数范围与风险分级。"""

from datetime import datetime, timezone
from typing import Final

from pydantic import BaseModel, ConfigDict

from .device_models import DeviceAction, DeviceCommand, DeviceRegistration, DeviceState, DeviceStateValue, DeviceType


class SafetyDecision(BaseModel):
    """安全校验结果。"""

    model_config = ConfigDict(frozen=True)

    allowed: bool
    reason: str = ""
    risk_level: str = "low"
    requires_human_confirmation: bool = False


_ALLOWED_ACTIONS: Final[frozenset[str]] = frozenset({action.value for action in DeviceAction})
_ALLOWED_STATES: Final[frozenset[str]] = frozenset({state.value for state in DeviceStateValue})
_ALLOWED_DEVICE_TYPES: Final[frozenset[str]] = frozenset({dtype.value for dtype in DeviceType})
_HIGH_RISK_ACTIONS: Final[frozenset[str]] = frozenset()


def is_supported_action(action: str) -> bool:
    """动作是否在白名单内。"""

    return action in _ALLOWED_ACTIONS


def validate_command_shape(command: DeviceCommand) -> SafetyDecision:
    """校验命令字段是否符合固定契约。"""

    if command.action not in _ALLOWED_ACTIONS:
        return SafetyDecision(
            allowed=False,
            reason=f"Unsupported action: {command.action}",
            risk_level="high",
        )
    if command.state.value not in _ALLOWED_STATES:
        return SafetyDecision(
            allowed=False,
            reason=f"Unsupported state: {command.state}",
            risk_level="high",
        )
    if command.expires_at is not None and command.expires_at <= datetime.now(timezone.utc):
        return SafetyDecision(allowed=False, reason="Command expired", risk_level="medium")
    return SafetyDecision(allowed=True, reason="Command shape accepted")


def validate_device_registration(registration: DeviceRegistration) -> SafetyDecision:
    """注册设备是否允许进入控制域。"""

    if registration.device_type.value not in _ALLOWED_DEVICE_TYPES:
        return SafetyDecision(
            allowed=False,
            reason=f"Device type not allowed: {registration.device_type}",
            risk_level="high",
        )
    if not registration.device_id or not registration.room:
        return SafetyDecision(allowed=False, reason="Device id and room are required", risk_level="medium")
    return SafetyDecision(allowed=True, reason="Registration accepted")


def validate_expected_device_type(
    registration: DeviceRegistration | DeviceState,
    expected_type: DeviceType,
) -> SafetyDecision:
    """校验固定工具声明的设备类型与注册类型一致。"""

    actual_type = getattr(registration, "device_type", None)
    if actual_type is None or actual_type is not expected_type:
        actual_value = getattr(actual_type, "value", actual_type or "unknown")
        return SafetyDecision(
            allowed=False,
            reason=f"Device type mismatch: expected {expected_type.value}, got {actual_value}",
            risk_level="high",
        )
    return SafetyDecision(allowed=True, reason="Device type accepted")


def evaluate_control_risk(command: DeviceCommand) -> SafetyDecision:
    """评估控制命令风险等级与是否需要人工确认。"""

    shape = validate_command_shape(command)
    if not shape.allowed:
        return shape

    requires_confirmation = command.action in _HIGH_RISK_ACTIONS
    risk_level = "medium" if requires_confirmation else "low"
    if requires_confirmation:
        return SafetyDecision(
            allowed=False,
            reason="High-risk action requires human confirmation",
            risk_level=risk_level,
            requires_human_confirmation=True,
        )
    return SafetyDecision(allowed=True, reason="Control allowed", risk_level=risk_level)


def reject_reason_for_unregistered(device_id: str) -> str:
    """未注册设备的标准拒绝文案。"""

    return f"Device is not registered: {device_id}"


def reject_reason_for_offline(device_id: str) -> str:
    """离线设备的标准拒绝文案。"""

    return f"Device is offline: {device_id}"
