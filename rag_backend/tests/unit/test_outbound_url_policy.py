import asyncio
import socket

import pytest

import app.security.outbound_url as outbound_module
from app.security.outbound_url import (
    OutboundURLPolicyError,
    validate_configured_service_url,
    validate_outbound_url,
    validate_resolved_outbound_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://user:password@example.com/data",
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/admin",
    ],
)
def test_outbound_url_rejects_unsafe_protocol_credentials_and_ips(url):
    with pytest.raises(OutboundURLPolicyError):
        validate_outbound_url(url)


def test_allowed_host_matching_is_exact_and_can_explicitly_allow_local_service():
    assert validate_outbound_url(
        "http://127.0.0.1:8001/health",
        allowed_hosts={"127.0.0.1"},
        allow_private=True,
    ).hostname == "127.0.0.1"

    with pytest.raises(OutboundURLPolicyError):
        validate_outbound_url(
            "https://trusted.example.evil/path",
            allowed_hosts={"trusted.example"},
        )


def test_dns_resolution_rejects_private_target(monkeypatch):
    monkeypatch.setattr(
        outbound_module.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", 443))
        ],
    )

    with pytest.raises(OutboundURLPolicyError, match="non-public"):
        asyncio.run(validate_resolved_outbound_url("https://example.com/data"))


def test_dns_resolution_accepts_public_target(monkeypatch):
    monkeypatch.setattr(
        outbound_module.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )

    parsed = asyncio.run(validate_resolved_outbound_url("https://example.com/data"))

    assert parsed.hostname == "example.com"


def test_configured_private_service_requires_private_host_allowlist():
    with pytest.raises(OutboundURLPolicyError):
        validate_configured_service_url(
            "http://127.0.0.1:8001",
            allowed_hosts={"127.0.0.1"},
            private_hosts=set(),
        )

    parsed = validate_configured_service_url(
        "http://127.0.0.1:8001",
        allowed_hosts={"127.0.0.1"},
        private_hosts={"127.0.0.1"},
    )
    assert parsed.port == 8001
