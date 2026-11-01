"""出站 HTTP URL 的轻量 SSRF 边界。"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from typing import Iterable
from urllib.parse import SplitResult, urlsplit


class OutboundURLPolicyError(ValueError):
    """URL 不满足出站访问策略。"""


def _normalize_host(host: str) -> str:
    host = host.rstrip(".").lower()
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise OutboundURLPolicyError("invalid hostname") from exc


def _allowed_host_set(hosts: Iterable[str] | None) -> frozenset[str]:
    return frozenset(_normalize_host(str(host).strip()) for host in (hosts or ()) if str(host).strip())


def _is_public_ip(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_global
    except ValueError:
        return True


def validate_outbound_url(
    url: str,
    *,
    allowed_hosts: Iterable[str] | None = None,
    allow_private: bool = False,
) -> SplitResult:
    """校验协议、凭据、主机白名单和字面 IP；不执行网络请求。"""
    if not isinstance(url, str) or not url.strip():
        raise OutboundURLPolicyError("URL is required")

    parsed = urlsplit(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise OutboundURLPolicyError("only absolute http/https URLs are allowed")
    if parsed.username is not None or parsed.password is not None:
        raise OutboundURLPolicyError("credentials in URLs are forbidden")

    try:
        _ = parsed.port
    except ValueError as exc:
        raise OutboundURLPolicyError("invalid URL port") from exc

    hostname = _normalize_host(parsed.hostname)
    allowed = _allowed_host_set(allowed_hosts)
    if allowed and hostname not in allowed:
        raise OutboundURLPolicyError("host is not in the outbound allowlist")
    if not allow_private and not _is_public_ip(hostname):
        raise OutboundURLPolicyError("non-public IP targets are blocked")
    if hostname == "localhost" and not allow_private:
        raise OutboundURLPolicyError("non-public host targets are blocked")

    return parsed


def validate_configured_service_url(
    url: str,
    *,
    allowed_hosts: Iterable[str],
    private_hosts: Iterable[str] = (),
) -> SplitResult:
    """校验管理员配置的服务地址；私网主机必须同时出现在专用白名单中。"""
    parsed = validate_outbound_url(url, allowed_hosts=allowed_hosts, allow_private=True)
    private = _allowed_host_set(private_hosts)
    hostname = _normalize_host(parsed.hostname or "")
    return validate_outbound_url(
        url,
        allowed_hosts=allowed_hosts,
        allow_private=hostname in private,
    )


async def validate_resolved_outbound_url(
    url: str,
    *,
    allowed_hosts: Iterable[str] | None = None,
    allow_private: bool = False,
) -> SplitResult:
    """解析域名并拒绝任何非公网地址，减少常见 SSRF 绕过。"""
    parsed = validate_outbound_url(
        url,
        allowed_hosts=allowed_hosts,
        allow_private=allow_private,
    )
    if allow_private:
        return parsed

    try:
        addresses = await asyncio.to_thread(
            socket.getaddrinfo,
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            0,
            socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise OutboundURLPolicyError("hostname could not be resolved") from exc

    if not addresses:
        raise OutboundURLPolicyError("hostname did not resolve to an address")
    for address in addresses:
        if not _is_public_ip(address[4][0]):
            raise OutboundURLPolicyError("non-public resolved IP targets are blocked")
    return parsed
