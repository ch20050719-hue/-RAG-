import pytest

from app.security.tool_authorization import ToolAuthorizationError, authorize_tool_call


def test_unknown_tool_is_rejected():
    with pytest.raises(ToolAuthorizationError):
        authorize_tool_call("run_shell", {}, tenant_id="t1", user_id="u1")


def test_tenant_argument_must_match_server_context():
    with pytest.raises(ToolAuthorizationError):
        authorize_tool_call(
            "extract_contract_clauses",
            {"tenant_id": "other", "report_id": "r1", "clause_category": "risk"},
            tenant_id="t1",
            user_id="u1",
        )


def test_local_tool_requires_principal_context():
    with pytest.raises(ToolAuthorizationError):
        authorize_tool_call("search_enterprise_knowledge", {}, tenant_id="", user_id="")


def test_declared_mcp_parameters_are_allowlisted():
    with pytest.raises(ToolAuthorizationError):
        authorize_tool_call(
            "calculate_tax_vat",
            {"taxable_amount": 100, "tax_rate": 0.13, "shell": "id"},
            tenant_id="t1",
            user_id="u1",
        )
