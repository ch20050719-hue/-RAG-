"""租户隔离的智能家居 RAG 检索器。

保留原有的租户隔离、缓存、限流和检索上下文接口，移除旧业务增强器。
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class TenantRateLimiter:
    """租户级滑动窗口限流器。"""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = Lock()

    def check_rate_limit(self, tenant_id: str) -> Tuple[bool, Dict[str, Any]]:
        now = time.time()
        with self._lock:
            valid = [item for item in self._requests[tenant_id] if item > now - self.window_seconds]
            allowed = len(valid) < self.max_requests
            updated = [*valid, now] if allowed else valid
            self._requests[tenant_id] = updated
            reset_at = min(updated) + self.window_seconds if updated else now + self.window_seconds
            return allowed, {
                "allowed": allowed,
                "remaining": max(0, self.max_requests - len(valid)),
                "reset_at": reset_at,
                "limit": self.max_requests,
                "window_seconds": self.window_seconds,
            }

    def get_usage(self, tenant_id: str) -> Dict[str, Any]:
        now = time.time()
        with self._lock:
            valid = [item for item in self._requests[tenant_id] if item > now - self.window_seconds]
            return {
                "total_requests": len(valid),
                "max_requests": self.max_requests,
                "window_seconds": self.window_seconds,
                "usage_percent": len(valid) / self.max_requests * 100,
            }


class TenantAccessValidator:
    """验证租户标识并阻止跨租户检索。"""

    def __init__(self):
        self._validated_tenants: Set[str] = set()
        self._lock = Lock()

    def validate_tenant_id(self, tenant_id: str) -> Tuple[bool, str]:
        if not isinstance(tenant_id, str) or not tenant_id:
            return False, "租户ID不能为空且必须为字符串"
        if not 8 <= len(tenant_id) <= 128:
            return False, "租户ID长度无效"
        return True, ""

    def validate_access(self, tenant_id: str, document_tenant_id: str) -> Tuple[bool, str]:
        valid, error = self.validate_tenant_id(tenant_id)
        if not valid:
            return False, f"租户验证失败: {error}"
        if tenant_id != document_tenant_id:
            logger.warning("跨租户知识检索被阻止")
            return False, "禁止跨租户访问"
        return True, ""

    def mark_validated(self, tenant_id: str) -> None:
        with self._lock:
            self._validated_tenants.add(tenant_id)

    def is_validated(self, tenant_id: str) -> bool:
        with self._lock:
            return tenant_id in self._validated_tenants


class RAGDocType(str, Enum):
    DEVICE_MANUAL = "device_manual"
    SENSOR_GUIDE = "sensor_guide"
    SCENARIO_DEFINITION = "scenario_definition"
    SAFETY_RULE = "safety_rule"
    GENERAL = "general"


@dataclass(frozen=True)
class RAGRetrievalResult:
    content: str
    source: str
    doc_type: RAGDocType
    confidence: float
    metadata: Dict[str, Any]
    relevance_score: float


@dataclass(frozen=True)
class RAGRetrievalContext:
    query: str
    results: List[RAGRetrievalResult]
    total_results: int
    retrieval_time_ms: float
    tenant_id: str
    filters_applied: Dict[str, Any]


class RetrievalCache:
    """按租户隔离的 TTL 缓存。"""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[RAGRetrievalContext, float]] = {}
        self._lock = Lock()

    def _make_key(self, tenant_id: str, query: str) -> str:
        return hashlib.sha256(f"{tenant_id}:{query.strip().lower()}".encode()).hexdigest()

    def get(self, tenant_id: str, query: str) -> Optional[RAGRetrievalContext]:
        key = self._make_key(tenant_id, query)
        now = time.time()
        with self._lock:
            item = self._cache.get(key)
            if not item:
                return None
            result, created_at = item
            if now - created_at >= self.ttl_seconds:
                self._cache.pop(key, None)
                return None
            return result

    def set(self, tenant_id: str, query: str, result: RAGRetrievalContext) -> None:
        key = self._make_key(tenant_id, query)
        with self._lock:
            if len(self._cache) >= self.max_size:
                oldest = min(self._cache, key=lambda item: self._cache[item][1])
                self._cache.pop(oldest, None)
            self._cache[key] = (result, time.time())

    def clear(self, tenant_id: Optional[str] = None) -> None:
        with self._lock:
            if tenant_id is None:
                self._cache.clear()
                return
            # Keys are intentionally opaque; clear one tenant by checking the cached context.
            self._cache = {
                key: value for key, value in self._cache.items()
                if value[0].tenant_id != tenant_id
            }


_global_rate_limiter = TenantRateLimiter()
_global_access_validator = TenantAccessValidator()
_global_retrieval_cache = RetrievalCache()


class TenantIsolatedRAGRetriever:
    """智能家居知识检索入口，兼容既有 Agent 编排接口。"""

    def __init__(self, qdrant_client=None, embedding_service=None, enable_audit: bool = True, search_service=None):
        self.qdrant_client = qdrant_client
        self.embedding_service = embedding_service
        self.enable_audit = enable_audit
        self.search_service = search_service
        self.use_rate_limiter = True
        self.use_cache = True

    async def retrieve(
        self,
        query: str,
        tenant_id: str,
        top_k: int = 3,
        doc_types: Optional[List[RAGDocType]] = None,
        require_public: bool = True,
        min_relevance_score: float = 0.5,
        bypass_cache: bool = False,
    ) -> RAGRetrievalContext:
        started = time.time()
        valid, error = _global_access_validator.validate_tenant_id(tenant_id)
        if not valid:
            raise ValueError(f"租户ID验证失败: {error}")
        if self.use_rate_limiter:
            allowed, info = _global_rate_limiter.check_rate_limit(tenant_id)
            if not allowed:
                raise PermissionError(f"检索请求过于频繁，请在 {max(0, int(info['reset_at'] - time.time()))} 秒后重试")
        if self.use_cache and not bypass_cache:
            cached = _global_retrieval_cache.get(tenant_id, query)
            if cached:
                return cached

        filters = self._build_tenant_isolated_filters(tenant_id, require_public, doc_types)
        embedding = await self._get_query_embedding(query)
        raw_results = [] if not embedding or all(value == 0.0 for value in embedding) else await self._search_vectors(
            embedding, filters, max(1, top_k) * 2
        )
        selected = [item for item in raw_results if item.get("score", 0) >= min_relevance_score]
        selected.sort(key=lambda item: item.get("score", 0), reverse=True)
        results = [self._to_result(item) for item in selected[:top_k]]
        context = RAGRetrievalContext(
            query=query,
            results=results,
            total_results=len(results),
            retrieval_time_ms=(time.time() - started) * 1000,
            tenant_id=tenant_id,
            filters_applied=filters,
        )
        if self.use_cache and not bypass_cache:
            _global_retrieval_cache.set(tenant_id, query, context)
        if self.enable_audit:
            logger.info("智能家居知识检索完成 tenant=%s results=%s", tenant_id, len(results))
        return context

    def _build_tenant_isolated_filters(self, tenant_id: str, require_public: bool = True, doc_types=None) -> Dict[str, Any]:
        conditions = [{"key": "tenant_id", "match": {"value": tenant_id}}]
        if require_public:
            conditions.append({"key": "is_public", "match": {"value": True}})
        if doc_types:
            conditions.append({"key": "doc_type", "match": {"any": [item.value for item in doc_types]}})
        return {"must": conditions}

    async def _get_query_embedding(self, query: str) -> List[float]:
        if not self.embedding_service:
            return []
        return await self.embedding_service.get_embedding(query)

    async def _search_vectors(self, query_embedding: List[float], filters: Dict[str, Any], top_k: int) -> List[Dict[str, Any]]:
        tenant_id = filters["must"][0]["match"]["value"]
        if self.search_service and hasattr(self.search_service, "search_with_vector"):
            results = await self.search_service.search_with_vector(
                query_vector=query_embedding, top_k=top_k, score_threshold=0.0, tenant_id=tenant_id
            )
            return [{"id": item.chunk_id, "score": item.score, "payload": {
                "content": item.content, "source": item.source_file, "doc_type": "general"
            }} for item in results]
        if self.qdrant_client:
            results = self.qdrant_client.search(
                collection_name="smart_home_knowledge", query_vector=query_embedding, query_filter=filters, limit=top_k
            )
            return [{"id": item.id, "score": item.score, "payload": item.payload} for item in results]
        return []

    def _to_result(self, item: Dict[str, Any]) -> RAGRetrievalResult:
        payload = item.get("payload", {})
        try:
            doc_type = RAGDocType(payload.get("doc_type", RAGDocType.GENERAL.value))
        except ValueError:
            doc_type = RAGDocType.GENERAL
        score = float(item.get("score", 0.0))
        return RAGRetrievalResult(
            content=payload.get("content", payload.get("page_content", "")),
            source=payload.get("source", payload.get("filename", "unknown")),
            doc_type=doc_type,
            confidence=score,
            metadata={"doc_id": item.get("id"), **payload},
            relevance_score=score,
        )

    def get_tenant_usage(self, tenant_id: str) -> Dict[str, Any]:
        return {"tenant_id": tenant_id, "rate_limit": _global_rate_limiter.get_usage(tenant_id),
                "cache_enabled": self.use_cache, "rate_limiter_enabled": self.use_rate_limiter}

    def clear_tenant_cache(self, tenant_id: str) -> None:
        _global_retrieval_cache.clear(tenant_id)

    def enable_caching(self, enabled: bool = True) -> None:
        self.use_cache = enabled

    def enable_rate_limiting(self, enabled: bool = True) -> None:
        self.use_rate_limiter = enabled


class HomeRAGOrchestrator:
    """按家居角色提供统一 RAG 入口，避免领域分叉。"""

    def __init__(self, tenant_id: str, retriever: Optional[TenantIsolatedRAGRetriever] = None):
        self.tenant_id = tenant_id
        self.rag_retriever = retriever or TenantIsolatedRAGRetriever()

    async def retrieve_for_home_agent(self, query: str, specialist: str = "home_butler") -> RAGRetrievalContext:
        return await self.rag_retriever.retrieve(query=query, tenant_id=self.tenant_id, top_k=5)

    @staticmethod
    def format_rag_context_for_prompt(context: RAGRetrievalContext) -> str:
        if not context.results:
            return "未检索到相关智能家居知识。"
        return "\n\n".join(f"[{item.source}] {item.content}" for item in context.results)
