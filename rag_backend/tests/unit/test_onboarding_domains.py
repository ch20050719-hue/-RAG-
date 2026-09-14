import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest


BACKEND = Path(__file__).resolve().parents[2]
CHUNKERS = BACKEND / "app" / "chunkers"


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Load the pure domain modules without importing app.chunkers.__init__, which
# eagerly imports optional database/LLM integrations.
app_package = types.ModuleType("app")
app_package.__path__ = [str(BACKEND / "app")]
chunkers_package = types.ModuleType("app.chunkers")
chunkers_package.__path__ = [str(CHUNKERS)]
sys.modules.setdefault("app", app_package)
sys.modules.setdefault("app.chunkers", chunkers_package)

domains = _load_module("app.chunkers.domains", CHUNKERS / "domains.py")
detector_module = _load_module(
    "app.chunkers.domain_detector", CHUNKERS / "domain_detector.py"
)


class FakeGeneralChunker:
    def __init__(self, domain="general"):
        self.domain = domain


fake_general = types.ModuleType("app.chunkers.general_chunker")
fake_general.GeneralChunker = FakeGeneralChunker
sys.modules["app.chunkers.general_chunker"] = fake_general
factory_module = _load_module(
    "app.chunkers.domain_chunker_factory", CHUNKERS / "domain_chunker_factory.py"
)

ONBOARDING_DOMAINS = domains.ONBOARDING_DOMAINS
DomainDetector = detector_module.DomainDetector
DomainChunkerFactory = factory_module.DomainChunkerFactory


@pytest.mark.parametrize("domain", ONBOARDING_DOMAINS)
def test_explicit_onboarding_category_is_preserved(domain):
    result = asyncio.run(DomainDetector().detect("培训资料.md", kb_category=domain))

    assert result == domain


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("员工手册与考勤制度.pdf", "hr_policy"),
        ("新人开发环境搭建指南.md", "it_engineering"),
        ("产品业务流程SOP.md", "business_product"),
    ],
)
def test_onboarding_filename_routes_to_domain(filename, expected):
    result = asyncio.run(DomainDetector().detect(filename))

    assert result == expected


def test_unknown_document_falls_back_to_general():
    result = asyncio.run(DomainDetector().detect("杂项资料.txt"))

    assert result == "general"


def test_onboarding_domains_use_general_chunking_without_losing_domain():
    for domain in ONBOARDING_DOMAINS:
        chunker = DomainChunkerFactory.get_chunker(domain)
        assert chunker.domain == domain


def test_factory_lists_onboarding_domains():
    supported = DomainChunkerFactory.get_supported_domains()

    assert set(ONBOARDING_DOMAINS).issubset(supported)
