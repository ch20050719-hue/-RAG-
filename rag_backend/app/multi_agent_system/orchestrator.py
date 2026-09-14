"""智能家居多智能体编排器。

对外保留原有 ``AgentOrchestrator``、``OrchestrationContext`` 和流式接口，
内部统一调度家居总管家、环境感知、设备控制和舒适度专家。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, List, Optional

from app.agent_framework.llm.factory import LLMAdapterFactory
from app.agent_framework.tools.tool_manager import ToolManager
from app.core.config import settings
from app.memory_system.memory_manager import MemoryManager
from app.multi_agent_system.agents.home_specialist import HomeSpecialistAgent, create_home_specialist
from app.multi_agent_system.agents.intent_router_agent import (
    IntentAnalysisResult,
    IntentCategory,
    IntentRouterAgent,
)
from app.multi_agent_system.rag_retriever import TenantIsolatedRAGRetriever
from app.prompts.llm_functions import review_quality

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationContext:
    """跨请求会话上下文，字段保持与既有 API 兼容。"""

    session_id: str
    tenant_id: str
    user_id: str
    user_query: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    enable_reflection: bool = True
    enable_rag: bool = True
    enable_report_generation: bool = False
    confidence_threshold: float = 0.7
    max_specialists: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    intent_result: Optional[IntentAnalysisResult] = None
    specialist_results: List[Dict[str, Any]] = field(default_factory=list)
    reflection_result: Optional[Dict[str, Any]] = None
    final_response: Optional[str] = None
    needs_human_review: bool = False
    needs_clarification: bool = False
    clarification_request: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentOrchestrator:
    """智能家居领域的 RAG + Agent + 多轮会话编排入口。"""

    HOME_SPECIALTIES = ("home_butler", "environment", "device_control", "comfort")

    def __init__(
        self,
        tenant_id: str = "default_tenant",
        user_id: str = "default",
        enable_reflection: bool = True,
        enable_rag: bool = True,
        max_parallel_agents: int = 3,
        timeout: float = 120.0,
        context: Optional[OrchestrationContext] = None,
    ) -> None:
        source = context
        self.tenant_id = source.tenant_id if source else tenant_id
        self.user_id = source.user_id if source else user_id
        self.enable_reflection = source.enable_reflection if source else enable_reflection
        self.enable_rag = source.enable_rag if source else enable_rag
        self.max_parallel_agents = source.max_specialists if source else max_parallel_agents
        self.timeout = timeout
        self.context = source
        self.initialized = False
        self.llm_adapter = None
        self.tool_manager: Optional[ToolManager] = None
        self.intent_router: Optional[IntentRouterAgent] = None
        self.home_specialists: Dict[str, HomeSpecialistAgent] = {}
        self.rag_retriever: Optional[TenantIsolatedRAGRetriever] = None
        self.memory_manager: Optional[MemoryManager] = None
        self._capability_config: Dict[str, Any] = {}
        self._specialist_descriptions = ""
        self._intent_mapping: Dict[str, str] = {}

    async def initialize(self) -> None:
        if self.initialized:
            return
        from app.agent_framework.tools.agent_tool_registry import initialize_tool_manager
        from app.skills.skill_registry import SkillRegistry
        from app.multi_agent_system.capability_loader import get_capability_loader

        provider = settings.get_llm_provider_for_agent("receptionist")
        self.llm_adapter = LLMAdapterFactory.create_adapter(provider)
        self.tool_manager = ToolManager()
        await initialize_tool_manager(
            self.tool_manager, include_mcp=True, include_local=True, tenant_id=self.tenant_id
        )
        loader = get_capability_loader()
        self._capability_config = loader.load_from_file()
        self._intent_mapping = loader.get_intent_mapping()
        self._specialist_descriptions = self._describe_capabilities()
        self.intent_router = IntentRouterAgent(
            llm_adapter=self.llm_adapter,
            tool_manager=self.tool_manager,
            confidence_threshold=0.7,
            timeout=30.0,
            specialist_descriptions=self._specialist_descriptions,
            intent_mapping=self._intent_mapping,
            skill_registry=SkillRegistry,
        )
        for specialty in self.HOME_SPECIALTIES:
            specialist = create_home_specialist(
                specialty=specialty,
                llm_adapter=self.llm_adapter,
                tool_manager=self.tool_manager,
                skill_registry=SkillRegistry,
            )
            specialist._orchestrator_ref = self
            self.home_specialists[specialty] = specialist
        if self.enable_rag:
            await self._initialize_rag()
        self.memory_manager = MemoryManager(
            session_id=f"home_{self.tenant_id}_{uuid.uuid4().hex[:8]}", user_id=self.user_id
        )
        self.initialized = True

    async def _initialize_rag(self) -> None:
        try:
            from app.services.embedding_service import EmbeddingService
            from app.services.search_service import SearchService
            self.rag_retriever = TenantIsolatedRAGRetriever(
                embedding_service=EmbeddingService(),
                search_service=SearchService(),
                enable_audit=True,
            )
        except Exception as exc:
            logger.warning("智能家居 RAG 初始化失败，继续使用 Agent: %s", exc)
            self.rag_retriever = None

    def _describe_capabilities(self) -> str:
        agents = self._capability_config.get("agents", {})
        return "\n".join(
            f"{name}: {config.get('agent_name', name)}"
            for name, config in agents.items()
            if config.get("enabled", True) and name in self.HOME_SPECIALTIES + ("general",)
        )

    @staticmethod
    def route_after_intent(state: Dict[str, Any]) -> str | List[str]:
        """兼容 LangGraph 条件边的家居路由函数。"""
        if state.get("needs_clarification"):
            return "final"
        strategy = str(state.get("routing_strategy", ""))
        if strategy in {"direct_answer", "greeting"} or state.get("intent") in {"greeting", "chit_chat"}:
            return "final"
        specialists = [item for item in state.get("specialists_needed", []) if item in AgentOrchestrator.HOME_SPECIALTIES]
        # 节点名保持稳定，具体家居角色由 home_specialist 节点内部调度。
        return "home_specialist" if specialists or state.get("intent") else "final"

    def _create_initial_state(
        self, user_input: str, session_id: str, history: Optional[List[Dict[str, str]]], metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        return {
            "session_id": session_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "user_query": user_input,
            "history": list(history or []),
            "metadata": dict(metadata or {}),
        }

    async def process_user_request(
        self,
        user_input: str,
        session_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None,
    ) -> OrchestrationContext:
        if not isinstance(user_input, str) or not user_input.strip():
            raise ValueError("user_input 不能为空")
        await self.initialize()
        session_id = session_id or str(uuid.uuid4())
        request_metadata = dict(metadata or {})
        context = OrchestrationContext(
            session_id=session_id, tenant_id=self.tenant_id, user_id=self.user_id,
            user_query=user_input, context={"history": list(history or []), **request_metadata},
            enable_reflection=request_metadata.get("enable_reflection", self.enable_reflection),
            enable_rag=self.enable_rag,
        )
        try:
            await self._progress(progress_callback, "receptionist", {"status": "received"})
            routed = await self.intent_router.run(user_input=user_input)
            if routed.is_simple:
                context.final_response = routed.simple_response or self._home_greeting(user_input)
                context.metadata["execution_path"] = ["receptionist", "intent_router", "final"]
                return context
            context.intent_result = routed.intent_result
            context.needs_clarification = bool(routed.clarification_request)
            context.clarification_request = routed.clarification_request
            if context.needs_clarification:
                context.final_response = self._clarification_text(routed.clarification_request)
                context.metadata["execution_path"] = ["receptionist", "intent_router", "final"]
                return context

            await self._progress(progress_callback, "intent_router", {"intent": context.intent_result.intent.value})
            rag_context = await self._retrieve_home_knowledge(user_input) if self.enable_rag else []
            await self._progress(progress_callback, "rag_retrieval", {"count": len(rag_context)})
            specialties = self._resolve_specialists(context.intent_result)
            results = await self._run_specialists(user_input, history, rag_context, specialties)
            context.specialist_results = results
            await self._progress(progress_callback, "home_specialist", {"count": len(results), "specialists": specialties})
            response = self._combine_results(results, rag_context)
            if context.enable_reflection and results:
                context.reflection_result = await self._reflect(user_input, response)
                context.needs_human_review = bool(context.reflection_result.get("needs_human_review"))
                await self._progress(progress_callback, "reflection", context.reflection_result)
            context.final_response = response
            context.metadata["execution_path"] = ["receptionist", "intent_router", "rag_retrieval", "home_specialist", "final"]
            return context
        except Exception as exc:
            logger.exception("智能家居编排失败")
            context.metadata["error"] = str(exc)
            context.final_response = "智能家居请求处理失败，请稍后重试。"
            return context

    async def _progress(self, callback, stage: str, state: Dict[str, Any]) -> None:
        if callback:
            await callback(stage, state)

    def _resolve_specialists(self, intent_result: Optional[IntentAnalysisResult]) -> List[str]:
        if not intent_result:
            return ["home_butler"]
        mapped = self._intent_mapping.get(intent_result.intent.value)
        candidates = [mapped] if mapped else list(intent_result.requires_specialists)
        selected = [item for item in candidates if item in self.HOME_SPECIALTIES]
        return list(dict.fromkeys(selected))[: max(1, self.max_parallel_agents)] or ["home_butler"]

    async def _retrieve_home_knowledge(self, query: str) -> List[Dict[str, Any]]:
        if not self.rag_retriever:
            return []
        try:
            tenant_id = self.tenant_id if len(self.tenant_id) >= 8 else "default_tenant"
            result = await self.rag_retriever.retrieve(query=query, tenant_id=tenant_id, top_k=5)
            return [{"content": item.content, "source": item.source, "score": item.relevance_score} for item in result.results]
        except Exception as exc:
            logger.warning("智能家居 RAG 检索失败: %s", exc)
            return []

    async def _run_specialists(self, query, history, rag_context, specialties) -> List[Dict[str, Any]]:
        async def execute(name: str) -> Dict[str, Any]:
            specialist = self.home_specialists[name]
            response = await asyncio.wait_for(
                specialist.run(user_input=query, history=history or [], context={"tenant_id": self.tenant_id}, rag_context={"documents": rag_context}),
                timeout=self.timeout,
            )
            content = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
            return {"specialist_type": name, "source": name, "content": content, "response": content, "confidence": 0.9, "success": True}

        results = await asyncio.gather(*(execute(name) for name in specialties), return_exceptions=True)
        output = []
        for name, result in zip(specialties, results):
            if isinstance(result, Exception):
                output.append({"specialist_type": name, "source": name, "content": "设备服务暂时不可用。", "confidence": 0.0, "success": False, "error": str(result)})
            else:
                output.append(result)
        return output

    def _combine_results(self, results: List[Dict[str, Any]], rag_context: List[Dict[str, Any]]) -> str:
        successful = [item for item in results if item.get("success", True) and item.get("content")]
        if successful:
            return "\n\n".join(str(item["content"]) for item in successful)
        if rag_context:
            return "\n\n".join(str(item["content"]) for item in rag_context[:3])
        return "未找到可用的智能家居设备或知识，请检查设备注册状态和问题描述。"

    async def _reflect(self, query: str, response: str) -> Dict[str, Any]:
        try:
            result = await review_quality(user_question=query, ai_answer=response, data_source_info="智能家居设备工具与知识库")
            score = float(result.get("scores", {}).get("overall", result.get("score", 0.8)))
            return {"score": score, "acceptable": score >= 0.7, "needs_human_review": score < 0.5, "issues": result.get("issues", [])}
        except Exception as exc:
            return {"score": 0.7, "acceptable": True, "skipped": True, "issues": [str(exc)[:120]]}

    async def process(self, context: OrchestrationContext) -> OrchestrationContext:
        return await self.process_user_request(
            user_input=context.user_query or "",
            session_id=context.session_id,
            history=(context.context or {}).get("history", []),
            metadata={"enable_reflection": context.enable_reflection, **(context.context or {})},
        )

    async def process_context(self, context: OrchestrationContext) -> OrchestrationContext:
        return await self.process(context)

    async def stream_process_context(self, context: OrchestrationContext) -> AsyncGenerator[str, None]:
        yield json.dumps({"type": "ttft", "stage": "received", "timestamp": datetime.now().isoformat()}, ensure_ascii=False)
        result = await self.process(context)
        if result.needs_clarification:
            yield json.dumps({"type": "clarification", "data": self._clarification_payload(result.clarification_request)}, ensure_ascii=False)
        elif result.final_response:
            for chunk in _chunks(result.final_response, 100):
                yield json.dumps({"type": "text", "content": chunk}, ensure_ascii=False)
        yield json.dumps({"type": "done", "metadata": result.metadata}, ensure_ascii=False)

    async def stream_process(self, user_input: str, session_id: Optional[str] = None, history: Optional[List[Dict[str, str]]] = None) -> AsyncGenerator[str, None]:
        context = OrchestrationContext(
            session_id=session_id or str(uuid.uuid4()), tenant_id=self.tenant_id, user_id=self.user_id,
            user_query=user_input, context={"history": history or []}, enable_reflection=self.enable_reflection, enable_rag=self.enable_rag,
        )
        async for event in self.stream_process_context(context):
            yield event

    def get_available_tools(self) -> List[str]:
        return ["search_enterprise_knowledge", "list_home_devices", "get_device_status", "read_home_environment", "set_light_state", "set_fan_state", "run_home_scenario", "publish_mqtt_command"]

    async def execute_orchestrator_workflow(self, *args, **kwargs) -> Dict[str, Any]:
        query = kwargs.get("user_input") or kwargs.get("query") or (args[0] if args else "")
        result = await self.process_user_request(query, session_id=kwargs.get("session_id"))
        return {"status": "success", "answer": result.final_response, "specialist_results": result.specialist_results, "metadata": result.metadata}

    async def breakdown_task_to_blackboard(self, user_input: str, **kwargs: Any) -> Dict[str, Any]:
        return {"status": "success", "domain": "smart_home", "tasks": [{"id": "home_1", "type": "home_control", "description": user_input, "dependencies": []}]}

    async def summarize_final_report(self, user_input: str, results: Any = None, **kwargs: Any) -> Dict[str, Any]:
        return {"status": "success", "domain": "smart_home", "summary": self._combine_results(results or [], [])}

    @staticmethod
    def _home_greeting(query: str) -> str:
        return "你好！我是智能家居助手，可以查询设备状态、读取环境、执行安全控制和场景联动。"

    @staticmethod
    def _clarification_text(request: Any) -> str:
        if hasattr(request, "question"):
            return request.question
        if isinstance(request, dict):
            return request.get("question", "请补充设备名称或房间信息。")
        return "请补充设备名称或房间信息。"

    @staticmethod
    def _clarification_payload(request: Any) -> Dict[str, Any]:
        if hasattr(request, "model_dump"):
            return request.model_dump(mode="json")
        return request if isinstance(request, dict) else {"question": str(request)}


def _chunks(text: str, size: int) -> List[str]:
    return [text[index:index + size] for index in range(0, len(text), size)] or [""]
