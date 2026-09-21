"""智能家居知识图谱查询分类器。"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from enum import Enum
from typing import Dict, List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)


class GraphQueryType(str, Enum):
    ENTITY_RELATION = "ENTITY_RELATION"
    ENTITY_ATTRIBUTE = "ENTITY_ATTRIBUTE"
    GRAPH_PATH = "GRAPH_PATH"
    NONE = "NONE"


class GraphQueryClassifier:
    """优先使用明确的家居关系规则，LLM 失败时安全回退为 RAG。"""

    GRAPH_STRONG_PATTERNS = [
        r"设备.*(连接|关联|绑定|控制)", r"传感器.*(关联|对应)",
        r"场景.*(包含|控制|触发)", r"(设备|场景).*(关系|拓扑|路径)",
        r"谁.*控制.*(灯|风扇|空调)",
    ]
    RAG_STRONG_PATTERNS = [
        r"是什么", r"怎么(做|用|设置)", r"教程", r"功能", r"解释",
        r"定义", r"原理", r"步骤", r"方法", r"代码", r"示例", r"文档", r"指南",
    ]
    GRAPH_KEYWORDS = ("连接", "关联", "绑定", "拓扑", "路径", "包含", "触发", "控制链路")
    CN_STOP_WORDS = frozenset("什么 怎么 如何 为什么 哪些 哪个 这个 那个 关系 情况 我们 他们 可以 需要 是否 使用 关于 方法 步骤 说明 介绍 描述 包括 功能 教程 代码 示例 原理 定义 解释".split())

    def __init__(self):
        self._compiled_graph_patterns: Optional[List[re.Pattern]] = None
        self._compiled_rag_patterns: Optional[List[re.Pattern]] = None
        self._mode = getattr(settings, "GRAPH_CLASSIFIER_MODE", "llm_first")
        self._cache_ttl = getattr(settings, "GRAPH_CLASSIFIER_CACHE_TTL", 300)
        self._cache: Dict[str, Tuple[bool, float]] = {}

    @property
    def graph_patterns(self) -> List[re.Pattern]:
        if self._compiled_graph_patterns is None:
            self._compiled_graph_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.GRAPH_STRONG_PATTERNS]
        return self._compiled_graph_patterns

    @property
    def rag_patterns(self) -> List[re.Pattern]:
        if self._compiled_rag_patterns is None:
            self._compiled_rag_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.RAG_STRONG_PATTERNS]
        return self._compiled_rag_patterns

    def _get_cache_key(self, query: str) -> str:
        return hashlib.md5(query.strip().lower().encode("utf-8")).hexdigest()

    def _get_cached(self, query: str) -> Optional[bool]:
        item = self._cache.get(self._get_cache_key(query))
        if not item:
            return None
        result, created_at = item
        if time.time() - created_at >= self._cache_ttl:
            self._cache.pop(self._get_cache_key(query), None)
            return None
        return result

    def _set_cache(self, query: str, result: bool) -> None:
        self._cache[self._get_cache_key(query)] = (result, time.time())
        if len(self._cache) > 1000:
            self._cache = dict(list(self._cache.items())[-500:])

    async def classify(self, query: str) -> Tuple[GraphQueryType, bool]:
        if not getattr(settings, "ENABLE_KNOWLEDGE_GRAPH", False) or not isinstance(query, str) or not query.strip():
            return GraphQueryType.NONE, False
        query = query.strip()
        try:
            if self._matches_rag_strong_patterns(query):
                return GraphQueryType.NONE, False
            cached = self._get_cached(query)
            if cached is not None:
                return (GraphQueryType.ENTITY_RELATION, True) if cached else (GraphQueryType.NONE, False)
            result = self._classify_keyword_only(query)[1]
            self._set_cache(query, result)
            return (GraphQueryType.ENTITY_RELATION, True) if result else (GraphQueryType.NONE, False)
        except Exception:
            logger.exception("家居图谱查询分类失败")
            return GraphQueryType.NONE, False

    def _classify_keyword_only(self, query: str) -> Tuple[GraphQueryType, bool]:
        needs_graph = self._matches_graph_strong_patterns(query) or (
            self._has_graph_keywords(query) and bool(self._extract_entities(query))
        )
        return (GraphQueryType.ENTITY_RELATION, True) if needs_graph else (GraphQueryType.NONE, False)

    async def _llm_classify_lightweight(self, query: str) -> Optional[bool]:
        """保留可选 LLM 接口；任何异常都回退到本地规则。"""
        try:
            from app.services.llm_service import llm_service
            answer = (await llm_service.get_answer(
                query=f"判断问题是否涉及智能家居设备、传感器、场景之间的关系。只回答 GRAPH 或 RAG。问题：{query}",
                context_chunks=[], history=[]
            )).strip().upper()
            return True if "GRAPH" in answer else False if "RAG" in answer else None
        except Exception as exc:
            logger.debug("家居图谱 LLM 分类不可用: %s", exc)
            return None

    def _matches_rag_strong_patterns(self, query: str) -> bool:
        return any(pattern.search(query) for pattern in self.rag_patterns)

    def _matches_graph_strong_patterns(self, query: str) -> bool:
        return any(pattern.search(query) for pattern in self.graph_patterns)

    def _extract_entities(self, query: str) -> List[str]:
        candidates = re.findall(r"(?:desk_light|desk_fan|sprinkler_pump|alarm_buzzer|esp8266|书桌灯|台灯|风扇|水泵|蜂鸣器|传感器|手动模式|自动模式|书房|客厅|卧室)", query, re.IGNORECASE)
        return list(dict.fromkeys(item for item in candidates if item not in self.CN_STOP_WORDS))

    def _has_graph_keywords(self, query: str) -> bool:
        return any(keyword in query for keyword in self.GRAPH_KEYWORDS)


graph_query_classifier = GraphQueryClassifier()
