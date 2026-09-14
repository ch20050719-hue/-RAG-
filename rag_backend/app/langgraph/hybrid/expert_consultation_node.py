"""智能家居专家会诊节点。

保留混合 LangGraph 的节点接口，所有会诊参与者限定为家居环境、设备、安全和舒适度角色。
"""

from typing import Any, Callable, Dict, Optional, TypedDict

from app.state.unified_state import UnifiedState


class ExpertConsultationState(TypedDict, total=False):
    query: str
    specialists: list[str]
    observations: list[dict[str, Any]]


class ExpertConsultationNode:
    """在黑板上下文中执行受控的智能家居专家协作。"""

    allowed_specialists = frozenset({"home_butler", "environment", "device_control", "comfort"})

    def __init__(
        self,
        blackboard: Any = None,
        max_rounds: int = 3,
        agent_factory: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self.blackboard = blackboard
        self.max_rounds = max(1, max_rounds)
        self.agent_factory = agent_factory

    async def invoke(self, state: UnifiedState) -> UnifiedState:
        requested = state.get("target_specialists", [])
        specialists = [name for name in requested if name in self.allowed_specialists]
        if not specialists:
            specialists = ["home_butler"]
        observations = list(state.get("debate_context", []))
        observations.append({"type": "home_consultation", "specialists": specialists, "round": 1})
        state["target_specialists"] = specialists
        state["debate_context"] = observations[-self.max_rounds :]
        state["current_phase"] = "home_consultation"
        return state


async def expert_consultation_node_func(state: UnifiedState, **kwargs: Any) -> UnifiedState:
    return await ExpertConsultationNode(**kwargs).invoke(state)
