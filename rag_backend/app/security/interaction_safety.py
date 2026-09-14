"""交互安全守门器：风险扫描、资源预算、紧急终止与审计。

该模块不依赖数据库或模型服务，保证在依赖异常时仍可执行 fail-closed 的本地安全决策。
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import re
import time
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Awaitable, Callable, Deque, Dict, Iterable, Optional

logger = logging.getLogger(__name__)


class RiskLevel(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


class SafetyAbort(RuntimeError):
    """安全策略拒绝或终止交互。"""

    def __init__(self, decision: "SafetyDecision") -> None:
        super().__init__(decision.reason)
        self.decision = decision


@dataclass(frozen=True)
class SafetyConfig:
    max_query_chars: int = 12_000
    max_history_items: int = 50
    max_active_total: int = 100
    max_active_per_principal: int = 3
    max_requests_per_minute: int = 30
    max_runtime_seconds: float = 240.0
    max_events: int = 2_000
    max_output_chars: int = 80_000
    max_cleanup_seconds: float = 2.0
    audit_capacity: int = 2_000


@dataclass(frozen=True)
class RiskSignal:
    rule_id: str
    level: RiskLevel
    score: int
    reason: str


@dataclass(frozen=True)
class SafetyDecision:
    allowed: bool
    level: RiskLevel
    score: int
    reason: str
    signals: tuple[RiskSignal, ...] = ()


@dataclass
class InteractionHandle:
    interaction_id: str
    principal_id: str
    tenant_id: str
    started_at: float
    event_count: int = 0
    output_chars: int = 0
    terminated: bool = False
    termination_reason: Optional[str] = None
    task: Optional[asyncio.Task] = None
    cleanup_callbacks: list[Callable[[], Any]] = field(default_factory=list)


AuditSink = Callable[[Dict[str, Any]], Awaitable[None] | None]


class InteractionSafetyGuard:
    """低开销、fail-closed 的交互安全控制器。

    规则扫描只使用规范化文本和预编译正则，不调用 LLM，不依赖 Redis；
    因此可以放在模型、检索和工具调用之前，并在服务降级时继续工作。
    """

    _RULES: tuple[tuple[str, RiskLevel, int, re.Pattern[str], str], ...] = (
        ("prompt_override", RiskLevel.HIGH, 4,
         re.compile(r"(?:忽略|无视|忘记).{0,12}(?:之前|系统|安全|规则|指令)|ignore\s+(?:all|previous|system)\s+instructions?", re.I),
         "疑似提示注入或规则覆盖"),
        ("secret_exfiltration", RiskLevel.CRITICAL, 8,
         re.compile(r"(?:输出|泄露|显示|打印).{0,16}(?:系统提示|system\s*prompt|密钥|token|密码|环境变量)|show\s+(?:me\s+)?(?:the\s+)?(?:system\s+prompt|secrets?)", re.I),
         "疑似敏感信息提取"),
        ("tool_escape", RiskLevel.CRITICAL, 8,
         re.compile(r"(?:直接|任意|绕过).{0,16}(?:调用工具|执行命令|访问内网|mqtt|gpio)|(?:execute|run|call).{0,20}(?:shell|command|mqtt|gpio|internal\s+network)", re.I),
         "疑似工具越权或外部系统攻击"),
        ("network_target", RiskLevel.HIGH, 5,
         re.compile(r"(?:https?://)?(?:localhost|127\.0\.0\.1|0\.0\.0\.0|169\.254\.|10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)", re.I),
         "疑似内网或本机地址访问"),
        ("path_traversal", RiskLevel.HIGH, 5,
         re.compile(r"(?:\.\.[/\\])|(?:[/\\]etc[/\\]passwd)|(?:读取|下载|覆盖).{0,12}(?:任意文件|配置文件)", re.I),
         "疑似路径穿越或任意文件访问"),
        ("dangerous_markup", RiskLevel.HIGH, 4,
         re.compile(r"(?:<script|javascript:|onerror\s*=|data:text/html)", re.I),
         "疑似危险 HTML 或脚本输出"),
    )

    def __init__(self, config: Optional[SafetyConfig] = None, audit_sink: Optional[AuditSink] = None) -> None:
        self.config = config or SafetyConfig()
        self.audit_sink = audit_sink
        self._active: Dict[str, InteractionHandle] = {}
        self._principal_windows: Dict[str, Deque[float]] = {}
        self._audit: Deque[Dict[str, Any]] = deque(maxlen=self.config.audit_capacity)
        self._lock = asyncio.Lock()
        self._external_rules: tuple[Any, ...] = ()
        self._rules_version = "builtin"
        self._rules_sha256 = ""

    def configure_rules(self, rules: Iterable[Any], *, version: str, sha256: str) -> None:
        """原子替换进程内规则快照；规则对象由 rule_repository 提供。"""
        self._external_rules = tuple(rules)
        self._rules_version = version
        self._rules_sha256 = sha256

    @staticmethod
    def normalize_text(value: str) -> str:
        text = unicodedata.normalize("NFKC", value or "")
        return "".join(char for char in text if unicodedata.category(char) not in {"Cf", "Cc"} or char in "\n\t")

    def assess(self, query: str, history_items: int = 0, metadata: Optional[Dict[str, Any]] = None) -> SafetyDecision:
        normalized = self.normalize_text(query)
        signals: list[RiskSignal] = []
        if len(normalized) > self.config.max_query_chars:
            signals.append(RiskSignal("query_size", RiskLevel.HIGH, 6, "输入超过最大字符数"))
        if history_items > self.config.max_history_items:
            signals.append(RiskSignal("history_size", RiskLevel.HIGH, 5, "历史消息数量超过上限"))
        if normalized and len(set(normalized)) <= 3 and len(normalized) >= 512:
            signals.append(RiskSignal("repetition_flood", RiskLevel.HIGH, 5, "检测到异常重复输入"))
        for rule_id, level, score, pattern, reason in self._RULES:
            if pattern.search(normalized):
                signals.append(RiskSignal(rule_id, level, score, reason))
        for rule in self._external_rules:
            if rule.pattern is not None and rule.pattern.search(normalized):
                level = self._external_level(rule.severity)
                signals.append(RiskSignal(rule.rule_id, level, max(1, 8 - rule.priority), "生产安全规则命中"))
        if metadata and metadata.get("external_tool") and signals:
            signals.append(RiskSignal("tool_risk_amplification", RiskLevel.CRITICAL, 8, "风险输入试图进入外部工具链"))
        total = min(sum(signal.score for signal in signals), 100)
        level = max((signal.level for signal in signals), default=RiskLevel.LOW)
        if total >= 8:
            level = max(level, RiskLevel.CRITICAL)
        elif total >= 5:
            level = max(level, RiskLevel.HIGH)
        allowed = not signals
        reason = "; ".join(signal.reason for signal in signals) or "通过本地安全预检"
        return SafetyDecision(allowed, level, total, reason, tuple(signals))

    @staticmethod
    def _external_level(severity: str) -> RiskLevel:
        return {"P0": RiskLevel.CRITICAL, "CRITICAL": RiskLevel.CRITICAL,
                "P1": RiskLevel.HIGH, "HIGH": RiskLevel.HIGH,
                "P2": RiskLevel.MEDIUM, "MEDIUM": RiskLevel.MEDIUM,
                "P3": RiskLevel.LOW, "LOW": RiskLevel.LOW}.get(severity, RiskLevel.HIGH)

    async def start(
        self,
        interaction_id: str,
        principal_id: str,
        tenant_id: str,
        query: str,
        *,
        history_items: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> InteractionHandle:
        decision = self.assess(query, history_items, metadata)
        if not decision.allowed:
            await self._record("blocked", interaction_id, principal_id, tenant_id, decision)
            raise SafetyAbort(decision)
        now = time.monotonic()
        rejection: Optional[SafetyDecision] = None
        handle: Optional[InteractionHandle] = None
        async with self._lock:
            self._prune_windows(now)
            window = self._principal_windows.setdefault(principal_id, deque())
            if interaction_id in self._active:
                rejection = SafetyDecision(False, RiskLevel.HIGH, 6, "同一交互正在运行")
            elif (
                len(self._active) >= self.config.max_active_total
                or sum(1 for _ in window) >= self.config.max_requests_per_minute
                or sum(1 for item in self._active.values() if item.principal_id == principal_id)
                    >= self.config.max_active_per_principal
            ):
                rejection = SafetyDecision(False, RiskLevel.HIGH, 6, "交互并发预算已用尽")
            else:
                window.append(now)
                handle = InteractionHandle(interaction_id, principal_id, tenant_id, now)
                self._active[interaction_id] = handle
        if rejection:
            await self._record("blocked", interaction_id, principal_id, tenant_id, rejection)
            raise SafetyAbort(rejection)
        assert handle is not None
        await self._record("started", interaction_id, principal_id, tenant_id, decision)
        return handle

    async def attach_task(self, interaction_id: str, task: asyncio.Task) -> None:
        async with self._lock:
            handle = self._active.get(interaction_id)
            if handle and not handle.terminated:
                handle.task = task

    async def add_cleanup(self, interaction_id: str, callback: Callable[[], Any]) -> None:
        async with self._lock:
            handle = self._active.get(interaction_id)
            if handle and not handle.terminated:
                handle.cleanup_callbacks.append(callback)

    async def checkpoint(self, interaction_id: str, *, output_delta: int = 0, text: Optional[str] = None) -> None:
        async with self._lock:
            handle = self._active.get(interaction_id)
            if handle is None:
                return
            handle.event_count += 1
            handle.output_chars += max(output_delta, 0)
            reason = self._budget_reason(handle)
        if text:
            decision = self.assess(text)
            if not decision.allowed:
                reason = decision.reason
        if reason:
            decision = SafetyDecision(False, RiskLevel.HIGH, 6, reason)
            await self.terminate(interaction_id, decision)
            raise SafetyAbort(decision)

    async def terminate(self, interaction_id: str, decision: SafetyDecision) -> bool:
        async with self._lock:
            handle = self._active.get(interaction_id)
            if not handle or handle.terminated:
                return False
            handle.terminated = True
            handle.termination_reason = decision.reason
            task = handle.task
            callbacks = tuple(handle.cleanup_callbacks)
        if task and task is not asyncio.current_task() and not task.done():
            task.cancel()
        await self._run_cleanup(callbacks)
        await self._record("terminated", handle.interaction_id, handle.principal_id, handle.tenant_id, decision)
        return True

    async def finish(self, interaction_id: str, status: str = "completed") -> None:
        async with self._lock:
            handle = self._active.pop(interaction_id, None)
        if handle:
            await self._record(status, handle.interaction_id, handle.principal_id, handle.tenant_id, None)

    def metrics(self) -> Dict[str, int]:
        return {"active": len(self._active), "audit_events": len(self._audit), "principals": len(self._principal_windows)}

    def audit_snapshot(self) -> tuple[Dict[str, Any], ...]:
        return tuple(self._audit)

    def _budget_reason(self, handle: InteractionHandle) -> Optional[str]:
        elapsed = time.monotonic() - handle.started_at
        if elapsed > self.config.max_runtime_seconds:
            return "交互超过最大运行时间"
        if handle.event_count > self.config.max_events:
            return "交互事件数量超过上限"
        if handle.output_chars > self.config.max_output_chars:
            return "交互输出量超过上限"
        return None

    def _prune_windows(self, now: float) -> None:
        for principal, window in tuple(self._principal_windows.items()):
            while window and now - window[0] > 60:
                window.popleft()
            if not window:
                self._principal_windows.pop(principal, None)

    async def _run_cleanup(self, callbacks: Iterable[Callable[[], Any]]) -> None:
        for callback in callbacks:
            try:
                result = callback()
                if inspect.isawaitable(result):
                    await asyncio.wait_for(result, timeout=self.config.max_cleanup_seconds)
            except Exception as exc:
                logger.warning("交互安全清理失败: %s", exc)

    async def _record(
        self,
        event: str,
        interaction_id: str,
        principal_id: str,
        tenant_id: str,
        decision: Optional[SafetyDecision],
    ) -> None:
        payload: Dict[str, Any] = {
            "event": event,
            "interaction_id": interaction_id,
            "principal_id": principal_id,
            "tenant_id": tenant_id,
            "timestamp": time.time(),
        }
        if decision:
            payload.update({"allowed": decision.allowed, "risk_level": decision.level.name.lower(), "score": decision.score, "reason": decision.reason, "rules": [signal.rule_id for signal in decision.signals], "rules_version": self._rules_version, "rules_sha256": self._rules_sha256})
        self._audit.append(payload)
        logger.warning("interaction_safety %s", payload) if event in {"blocked", "terminated"} else logger.info("interaction_safety %s", payload)
        if self.audit_sink:
            try:
                result = self.audit_sink(payload)
                if inspect.isawaitable(result):
                    await asyncio.wait_for(result, timeout=self.config.max_cleanup_seconds)
            except Exception as exc:
                logger.warning("交互安全审计写入失败: %s", exc)


interaction_guard = InteractionSafetyGuard()
