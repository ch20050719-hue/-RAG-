"""智能家居领域文档与意图配置测试。"""

from app.chunkers.domain_detector import DomainDetector
from app.services.query_analyzer import QueryAnalyzer
from app.agent_framework.tools.tool_manager import ToolManager
from app.multi_agent_system.agents.intent_router_agent import IntentRouterAgent
from app.multi_agent_system.capability_loader import CapabilityLoader
from app.multi_agent_system.config.knowledge_loader import load_knowledge_base, load_risk_rules
from tests.unit.test_home_specialist import DummyHomeLLM


def test_home_document_filename_is_classified_as_smart_home():
    detector = DomainDetector()

    assert detector._detect_from_filename("智能家居设备说明书.pdf") == "smart_home"


def test_home_mode_loads_home_intent_prompt(monkeypatch):
    monkeypatch.setenv("HOME_DOMAIN_MODE", "1")

    agent = IntentRouterAgent(
        llm_adapter=DummyHomeLLM(),
        tool_manager=ToolManager(),
    )

    assert "智能家居" in agent.system_prompt


def test_home_rule_classifier_detects_device_switch(monkeypatch):
    monkeypatch.setenv("HOME_DOMAIN_MODE", "1")
    agent = IntentRouterAgent(
        llm_adapter=DummyHomeLLM(),
        tool_manager=ToolManager(),
    )

    result = agent._classify_intent_rule_based("打开书桌灯")

    assert result["intent"].value == "device_switch"


def test_query_analyzer_routes_home_queries_to_smart_home():
    assert QueryAnalyzer()._route_domain("打开书桌灯并查看房间温度") == "smart_home"


def test_smart_home_is_the_only_default_capability_domain(monkeypatch):
    monkeypatch.delenv("AGENT_CAPABILITIES_FILE", raising=False)
    monkeypatch.delenv("HOME_DOMAIN_MODE", raising=False)

    loader = CapabilityLoader()

    assert loader.config_path.name == "agent_home_capabilities.yaml"
    assert set(loader.load_from_file()["agents"]) == {
        "home_butler", "environment", "device_control", "comfort", "general"
    }


def test_legacy_domain_knowledge_and_risk_rules_are_not_available():
    for legacy_domain in ("finance", "tax", "legal"):
        assert load_knowledge_base(legacy_domain) == []
        assert load_risk_rules(legacy_domain) == []

    assert load_knowledge_base("device_control")
    assert load_risk_rules("device_control")
