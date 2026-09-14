from pathlib import Path

import pytest

from app.security.rule_repository import load_rules
from app.security.interaction_safety import InteractionSafetyGuard, RiskLevel


def test_loads_current_governance_cards_with_auditable_snapshot():
    root = Path(__file__).parents[2] / "data" / "security" / "rules"
    snapshot = load_rules(root, version="test-version")

    assert snapshot.version == "test-version"
    assert snapshot.rule_count > 0
    assert snapshot.file_count == 4
    assert len(snapshot.sha256) == 64


def test_rejects_duplicate_rule_ids(tmp_path):
    (tmp_path / "rules.jsonl").write_text(
        '{"rule_id":"R-1","domain":"test","category":"test","severity":"high","trigger":"x","risk":"x","detection":"x","prevention":"x","emergency":"x"}\n'
        '{"rule_id":"R-1","domain":"test","category":"test","severity":"P1","trigger":"x","risk":"x","detection":"x","prevention":"x","emergency":"x"}\n',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="invalid security rule"):
        load_rules(tmp_path)


def test_compiles_explicit_regex_only(tmp_path):
    (tmp_path / "rules.jsonl").write_text(
        '{"rule_id":"R-1","risk_category":"test","risk_subtype":"test","severity":"P1","keywords_regex":"secret","trigger_condition":"x","safe_reply_template":"x","action":"BLOCK","priority":1}\n',
        encoding="utf-8",
    )

    snapshot = load_rules(tmp_path)
    assert snapshot.regex_rule_count == 1
    assert snapshot.rules[0].pattern.search("SECRET")


def test_explicit_regex_is_used_by_existing_interaction_guard(tmp_path):
    (tmp_path / "rules.jsonl").write_text(
        '{"rule_id":"R-1","risk_category":"test","risk_subtype":"test","severity":"P1","keywords_regex":"exfiltrate","trigger_condition":"x","safe_reply_template":"x","action":"BLOCK","priority":1}\n',
        encoding="utf-8",
    )
    snapshot = load_rules(tmp_path)
    guard = InteractionSafetyGuard()
    guard.configure_rules(snapshot.rules, version=snapshot.version, sha256=snapshot.sha256)

    decision = guard.assess("please EXFILTRATE this")

    assert not decision.allowed
    assert decision.level >= RiskLevel.HIGH
    assert decision.signals[0].rule_id == "R-1"
