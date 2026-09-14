"""智能家居专家使用的轻量状态与风险发现模型。"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict
import uuid


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    INFO = "info"


@dataclass(frozen=True)
class Finding:
    id: str
    agent_name: str
    category: str
    description: str
    risk_level: RiskLevel
    risk_score: float
    confidence: float
    evidence: List[str]
    legal_basis: Optional[List[str]] = None
    recommendations: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "category": self.category,
            "description": self.description,
            "risk_level": self.risk_level.value,
            "risk_score": self.risk_score,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "legal_basis": list(self.legal_basis or []),
            "recommendations": list(self.recommendations or []),
        }


class HomeState(TypedDict, total=False):
    task_id: str
    tenant_id: str
    user_id: str
    user_query: str
    devices: List[Dict[str, Any]]
    environment: Dict[str, Any]
    findings: List[Dict[str, Any]]
    messages: List[Dict[str, Any]]
    created_at: str
    updated_at: str


def create_initial_state(task_id: str, tenant_id: str, user_id: str, user_query: str, documents: Optional[List[Dict[str, Any]]] = None) -> HomeState:
    now = datetime.utcnow().isoformat()
    return HomeState(task_id=task_id, tenant_id=tenant_id, user_id=user_id, user_query=user_query, devices=[], environment={}, findings=[], messages=[], created_at=now, updated_at=now)
