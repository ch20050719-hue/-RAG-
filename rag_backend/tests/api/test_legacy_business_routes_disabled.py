"""验证旧财税业务入口已从默认 FastAPI 应用中移除。"""

from app.main import app


def test_legacy_business_routes_are_not_registered():
    paths = {route.path for route in app.routes}

    assert "/api/v1/policy" not in paths
    assert "/api/v1/tax-reports" not in paths
    assert "/api/v1/financial-health/monitor" not in paths
    assert "/api/v1/financial-data" not in paths
    assert "/api/v1/contract-review" not in paths
    assert "/api/v1/enterprise" not in paths


def test_core_rag_routes_remain_registered():
    paths = {route.path for route in app.routes}

    assert "/api/v1/documents/" in paths
    assert "/api/v1/search/query" in paths
    assert "/api/v1/chat/completions" in paths
    assert "/api/v1/knowledge/bases" in paths
