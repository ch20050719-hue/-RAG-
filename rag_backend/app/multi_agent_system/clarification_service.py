"""智能家居场景的澄清服务。"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ClarificationType(str, Enum):
    INTENT_CLARIFICATION = "intent_clarification"
    ENTITY_COMPLETION = "entity_completion"
    SCOPE_DEFINITION = "scope_definition"
    CONTEXT_PROVISION = "context_provision"
    AMBIGUOUS_KEYWORD = "ambiguous_keyword"


class ClarificationRequest(BaseModel):
    type: ClarificationType = Field(..., description="追问类型")
    question: str
    suggestions: List[str] = Field(default_factory=list)
    reason: str
    required: bool = True
    placeholder: Optional[str] = None

    model_config = {"use_enum_values": True}


class ClarificationService:
    """只针对设备、环境、模式和安全操作生成追问。"""

    KEYWORD_INTENT_MAP: Dict[str, List[str]] = {
        "灯": ["device_switch"],
        "风扇": ["device_switch"],
        "设备": ["device_status", "device_switch"],
        "状态": ["device_status"],
        "温度": ["sensor_reading", "comfort_assessment"],
        "湿度": ["sensor_reading", "comfort_assessment"],
        "环境": ["sensor_reading", "comfort_assessment"],
        "自动模式": ["home_control"],
        "手动模式": ["home_control"],
        "阈值": ["sensor_reading"],
    }

    INTENT_SUGGESTIONS: Dict[str, List[str]] = {
        "device_switch": ["打开或关闭设备", "控制书桌台灯", "控制桌面风扇"],
        "device_status": ["查看设备列表", "查询设备在线状态", "查看设备当前状态"],
        "sensor_reading": ["读取温湿度", "查看烟雾和火焰状态", "查看书房环境"],
        "comfort_assessment": ["查看当前报警", "检查自动联动条件", "查看有人状态"],
    }

    def __init__(self, min_query_length: int = 5, confidence_threshold: float = 0.6, enable_clarification: bool = True):
        self.min_query_length = min_query_length
        self.confidence_threshold = confidence_threshold
        self.enable_clarification = enable_clarification

    async def detect_ambiguous_input(
        self, query: str, intent: str, confidence: float, entities: List[Dict[str, Any]], routing_strategy: str = None
    ) -> Optional[ClarificationRequest]:
        if not self.enable_clarification:
            return None
        query = (query or "").strip()
        if len(query) < self.min_query_length:
            return self._handle_short_input(query)
        if confidence < self.confidence_threshold:
            return self._handle_low_confidence(query)
        if intent in {"unknown", "complex_task"}:
            return self._handle_ambiguous_intent(query)
        return None

    def _matched_keywords(self, query: str) -> List[str]:
        return [key for key in self.KEYWORD_INTENT_MAP if key in query]

    def _suggestions(self, query: str) -> List[str]:
        values: List[str] = []
        for keyword in self._matched_keywords(query):
            for intent in self.KEYWORD_INTENT_MAP[keyword]:
                values.extend(self.INTENT_SUGGESTIONS.get(intent, []))
        return list(dict.fromkeys(values))[:4]

    def _handle_short_input(self, query: str) -> ClarificationRequest:
        suggestions = self._suggestions(query) or ["查看设备状态", "读取环境数据", "切换自动模式", "咨询设备安全规则"]
        return ClarificationRequest(
            type=ClarificationType.AMBIGUOUS_KEYWORD if suggestions else ClarificationType.INTENT_CLARIFICATION,
            question="请说明要查询或控制哪台设备，或选择手动/自动模式。",
            suggestions=suggestions,
            reason="输入较短，无法安全确定设备和操作范围",
            placeholder="例如：打开书房台灯，或查看当前温度",
        )

    def _handle_low_confidence(self, query: str) -> ClarificationRequest:
        return ClarificationRequest(
            type=ClarificationType.INTENT_CLARIFICATION,
            question="您是想查询设备、读取环境，还是切换手动/自动模式？",
            suggestions=self._suggestions(query) or ["设备状态", "环境数据", "设备控制", "自动模式"],
            reason="系统无法可靠判断请求意图，为避免误控设备需要确认",
            required=False,
        )

    def _handle_ambiguous_intent(self, query: str) -> ClarificationRequest:
        return ClarificationRequest(
            type=ClarificationType.SCOPE_DEFINITION,
            question="请明确房间、设备和期望动作；如果是自动联动，请说明需要调整的阈值。",
            suggestions=self._suggestions(query) or ["查看设备状态", "读取环境数据", "切换自动模式", "调整烟雾阈值"],
            reason="请求范围不明确，控制操作必须先确认目标",
        )

    def _check_critical_entities(self, intent: str, entities: List[Dict[str, Any]]) -> List[str]:
        if intent in {"device_switch", "device_status"} and not entities:
            return ["设备"]
        return []

    def should_clarify(self, query: str, intent: str, confidence: float, entities: List[Dict[str, Any]]) -> bool:
        return bool(self.enable_clarification and ((len((query or "").strip()) < self.min_query_length) or confidence < self.confidence_threshold or intent in {"unknown", "complex_task"}))
