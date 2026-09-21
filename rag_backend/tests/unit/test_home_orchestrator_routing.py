"""单房间智能家居主编排器和路由契约测试。"""

import asyncio
from types import SimpleNamespace

from app.langgraph.conditional import route_by_intent
from app.langgraph.state import AgentState
from app.multi_agent_system.orchestrator import AgentOrchestrator
from app.multi_agent_system.routing.unified_router import route_by_intent_result


def test_home_device_intent_routes_to_home_specialist_node():
    state = {
        "intent": "device_switch",
        "routing_strategy": "single_specialist",
        "specialists_needed": ["device_control"],
    }

    assert AgentOrchestrator.route_after_intent(state) == "home_specialist"


def test_home_intent_does_not_follow_legacy_rag_routing_strategy():
    decision = route_by_intent_result(
        intent_value="device_switch",
        routing_strategy="rag_retrieval",
        requires_specialists=["device_control"],
        confidence=0.95,
    )

    assert decision is not None
    assert decision.target_nodes == ["home_specialist"]


def test_langgraph_home_intent_skips_rag_node():
    state = AgentState(
        user_query="打开书桌灯",
        intent="device_switch",
        intent_confidence=0.95,
        routing_strategy="rag_retrieval",
        target_specialists=["device_control"],
    )

    assert route_by_intent(state) == "home_specialist"


def test_home_orchestrator_skips_rag_and_runs_fixed_specialist_path():
    orchestrator = AgentOrchestrator(enable_rag=True)
    orchestrator.initialized = True
    orchestrator._intent_mapping = {"device_switch": "device_control"}

    class FakeIntentRouter:
        async def run(self, user_input):
            return SimpleNamespace(
                is_simple=False,
                intent_result=SimpleNamespace(
                    intent=SimpleNamespace(value="device_switch"),
                    requires_specialists=["device_control"],
                ),
                clarification_request=None,
            )

    calls = []

    class FakeHomeSpecialist:
        async def run(self, **kwargs):
            calls.append(kwargs)
            return "fixed-tool-result"

    orchestrator.intent_router = FakeIntentRouter()
    orchestrator.home_specialists = {"device_control": FakeHomeSpecialist()}

    async def fail_if_rag_is_called(*args, **kwargs):
        raise AssertionError("home requests must not call the RAG retriever")

    orchestrator._retrieve_home_knowledge = fail_if_rag_is_called

    result = asyncio.run(
        orchestrator.process_user_request(
            "打开书桌灯",
            metadata={"enable_reflection": False},
        )
    )

    assert orchestrator.enable_rag is False
    assert result.final_response == "fixed-tool-result"
    assert result.metadata["execution_path"] == [
        "receptionist",
        "intent_router",
        "home_specialist",
        "final",
    ]
    assert calls and "rag_context" not in calls[0]
