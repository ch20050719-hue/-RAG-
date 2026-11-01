"""只读加载生产安全规则。

规则目录中的治理卡片可能只描述检测策略，不一定包含本地正则；只有显式
提供 ``keywords_regex`` 的规则才参与进程内扫描。其余字段仍会被严格校验，
并纳入版本与哈希，供审计和回滚使用。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_SEVERITIES = {"P0", "P1", "P2", "P3", "CRITICAL", "HIGH", "MEDIUM", "LOW"}
_ACTIONS = {"REWRITE", "BLOCK", "REVIEW", "CONTINUE", "RESUME"}
_CARD_FIELDS = {"domain", "category", "severity", "trigger", "risk", "detection", "prevention", "emergency"}
_COMPILED_FIELDS = {"risk_category", "risk_subtype", "severity", "keywords_regex", "trigger_condition", "safe_reply_template", "action", "priority"}


@dataclass(frozen=True)
class CompiledRule:
    rule_id: str
    category: str
    severity: str
    priority: int
    pattern: re.Pattern[str] | None
    template: str
    action: str


@dataclass(frozen=True)
class SecurityRuleSnapshot:
    rules: tuple[CompiledRule, ...]
    version: str
    sha256: str
    file_count: int
    rule_count: int
    regex_rule_count: int


def _severity(value: Any) -> str:
    normalized = str(value).strip().upper()
    if normalized not in _SEVERITIES:
        raise ValueError(f"invalid severity: {value}")
    return normalized


def _action(value: Any, severity: str) -> str:
    if value is None:
        return "BLOCK" if severity in {"P0", "P1", "CRITICAL", "HIGH"} else "REVIEW"
    normalized = str(value).strip().upper()
    if normalized not in _ACTIONS:
        raise ValueError(f"invalid action: {value}")
    return normalized


def load_rules(root: Path, *, version: str = "") -> SecurityRuleSnapshot:
    """加载并校验规则，任何坏行、重复 ID 或空目录都失败。"""
    root = root.expanduser().resolve()
    paths = tuple(sorted(root.glob("*.jsonl"))) if root.is_dir() else ()
    if not paths:
        raise RuntimeError(f"empty security rule set: {root}")

    seen: set[str] = set()
    loaded: list[CompiledRule] = []
    digest = hashlib.sha256()
    for path in paths:
        raw_bytes = path.read_bytes()
        digest.update(path.name.encode("utf-8"))
        digest.update(raw_bytes)
        for line_no, line in enumerate(raw_bytes.decode("utf-8-sig").splitlines(), 1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
                if not isinstance(raw, dict) or "rule_id" not in raw:
                    raise ValueError("missing required fields")
                schema_fields = _COMPILED_FIELDS if "keywords_regex" in raw else _CARD_FIELDS
                if not schema_fields.issubset(raw):
                    raise ValueError("missing required fields")
                rule_id = str(raw["rule_id"]).strip()
                if not rule_id or rule_id in seen:
                    raise ValueError(f"duplicate or empty rule_id: {rule_id}")
                severity = _severity(raw["severity"])
                pattern_text = raw.get("keywords_regex")
                pattern = re.compile(str(pattern_text), re.IGNORECASE) if pattern_text else None
                loaded.append(CompiledRule(
                    rule_id=rule_id,
                    category=str(raw.get("risk_category") or raw.get("category") or "unknown"),
                    severity=severity,
                    priority=int(raw.get("priority", 5)),
                    pattern=pattern,
                    template=str(raw.get("safe_reply_template") or raw.get("prevention") or ""),
                    action=_action(raw.get("action"), severity),
                ))
                seen.add(rule_id)
            except (UnicodeDecodeError, KeyError, TypeError, ValueError, json.JSONDecodeError, re.error) as exc:
                raise RuntimeError(f"invalid security rule {path}:{line_no}") from exc
    if not loaded:
        raise RuntimeError(f"empty security rule set: {root}")
    ordered = tuple(sorted(loaded, key=lambda item: (item.priority, item.rule_id)))
    return SecurityRuleSnapshot(
        rules=ordered,
        version=version or digest.hexdigest()[:12],
        sha256=digest.hexdigest(),
        file_count=len(paths),
        rule_count=len(ordered),
        regex_rule_count=sum(rule.pattern is not None for rule in ordered),
    )
