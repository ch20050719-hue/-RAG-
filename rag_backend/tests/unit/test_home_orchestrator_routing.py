"""LangGraph 主编排器的智能家居路由契约测试。"""

from app.multi_agent_system.orchestrator import AgentOrchestrator


def test_home_device_intent_routes_to_home_specialist_node():
    state = {
        "intent": "device_switch",
        "routing_strategy": "single_specialist",
        "specialists_needed": ["device_control"],
    }

    assert AgentOrchestrator.route_after_intent(state) == "home_specialist"
