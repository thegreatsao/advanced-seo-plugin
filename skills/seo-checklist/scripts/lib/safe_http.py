#!/usr/bin/env python3
"""Safe HTTP helpers shared by network-facing SEO scripts."""

from __future__ import annotations

import fcntl
import hashlib
import ipaddress
import os
import socket
import tempfile
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse, urlunparse

try:
    import requests
    _REQUESTS_ERROR = ""
except ImportError:  # pragma: no cover - environment guard
    # Deferred, not fatal. This module is imported transitively by the checklist
    # runner, so exiting here killed `--archive` — a mode that makes no network
    # calls at all and has no business needing an HTTP library installed. The
    # failure now happens when something actually tries to make a request.
    requests = None
    _REQUESTS_ERROR = ("requests library required for network access. "
                       "Install with: pip install requests")


def _require_requests() -> None:
    if requests is None:
        raise RuntimeError(_REQUESTS_ERROR)


AGENTIC_SEO_USER_AGENT = (
    "Mozilla/5.0 (compatible; AgenticSEOSkill/1.0; "
    "+https://github.com/Bhanunamikaze/Agentic-SEO-Skill)"
)
DEFAULT_TIMEOUT = 15
DEFAULT_MAX_REDIRECTS = 5
DEFAULT_MAX_RESPONSE_BYTES = 5 * 1024 * 1024

DEFAULT_HEADERS = {
    "User-Agent": AGENTIC_SEO_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}


class SafeHTTPError(requests.exceptions.RequestException if requests else Exception):
    """Raised when a request is blocked by safe HTTP policy.

    Subclasses RequestException so callers can catch either; without requests
    installed there is nothing to subclass and nothing to catch it from."""


def default_headers(extra: dict | None = None) -> dict:
    """Return request headers with the shared Agentic SEO User-Agent."""
    headers = dict(DEFAULT_HEADERS)
    if extra:
        headers.update(extra)
    headers["User-Agent"] = AGENTIC_SEO_USER_AGENT
    return headers


def normalize_url(url: str, default_scheme: str = "https") -> str:
    """Normalize a user-supplied URL, adding https:// when no scheme exists."""
    if not url:
        raise SafeHTTPError("URL is required")
    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"{default_scheme}://{url}"
        parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SafeHTTPError(f"Invalid URL scheme: {parsed.scheme}")
    if not parsed.hostname:
        raise SafeHTTPError("URL must include a hostname")
    return urlunparse(parsed)


# ---------------------------------------------------------------------------
# Politeness
# ---------------------------------------------------------------------------

# An audit is a burst by construction: the runner launches its evidence scripts
# concurrently, and several of them walk a sitemap or a link list inside their own
# process. Nothing paced any of it, so a small site could take a few hundred
# requests in a couple of seconds from one machine — indistinguishable from
# something worth blocking, and rude regardless of whether anyone notices.
#
# The pacing has to be shared, because the scripts are separate processes and an
# in-process limiter would just let eight of them go at once. The state is a file
# per host holding the last request time, guarded by a lock: cheap, no daemon, and
# it survives a script crashing mid-audit.
DEFAULT_MAX_RPS = 4.0
RATE_LIMIT_DIR = os.path.join(tempfile.gettempdir(), "seo-checklist-rate")
# A server that says "come back in an hour" is not worth waiting for inside an
# audit; past this the request fails and the item reports NO_DATA with the reason,
# which is more useful than a run that appears to hang.
MAX_RETRY_AFTER_WAIT = 30.0


def max_rps() -> float:
    """Requests per second per host. `SEO_MAX_RPS=0` switches pacing off."""
    raw = os.environ.get("SEO_MAX_RPS", "")
    if not raw:
        return DEFAULT_MAX_RPS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_MAX_RPS
    return max(value, 0.0)


def _slot_path(host: str) -> str:
    # The host is not a safe filename (ports, IDN, path-like garbage from a
    # malformed URL), so it is hashed rather than sanitised.
    digest = hashlib.sha256(host.encode("utf-8", "replace")).hexdigest()[:32]
    return os.path.join(RATE_LIMIT_DIR, f"{digest}.slot")


def pace(host: str, rps: float | None = None) -> float:
    """Wait until this process may hit `host` again. Returns the seconds waited.

    Coordinated through a lock file so that concurrent evidence scripts queue
    behind each other instead of each pacing itself. A failure to read or write
    that file is never fatal: being unable to co-ordinate is a reason to slow down
    on our own, not to abandon the request.
    """
    limit = max_rps() if rps is None else rps
    if limit <= 0 or not host:
        return 0.0
    interval = 1.0 / limit
    try:
        os.makedirs(RATE_LIMIT_DIR, exist_ok=True)
        path = _slot_path(host)
        with open(path, "a+") as slot:
            fcntl.flock(slot.fileno(), fcntl.LOCK_EX)
            try:
                slot.seek(0)
                raw = slot.read().strip()
                last = float(raw) if raw else 0.0
                now = time.monotonic()
                # A stale slot from a previous run — or a clock that moved — must
                # not park the audit. monotonic() is per-boot, so a value in the
                # future means the file outlived a reboot.
                if last > now or now - last > 3600:
                    last = 0.0
                waited = max(0.0, last + interval - now)
                if waited:
                    time.sleep(waited)
                slot.seek(0)
                slot.truncate()
                slot.write(str(time.monotonic()))
                return waited
            finally:
                fcntl.flock(slot.fileno(), fcntl.LOCK_UN)
    except OSError:
        time.sleep(interval)
        return interval


def retry_after_seconds(response) -> float:
    """How long a 429/503 asked us to wait, 0 when it did not ask.

    Both forms of the header are accepted: delta-seconds and an HTTP date. An
    unparseable value returns 0 rather than a guess — waiting a made-up interval
    is not more polite than not waiting.
    """
    if getattr(response, "status_code", 0) not in (429, 503):
        return 0.0
    raw = ((getattr(response, "headers", {}) or {}).get("Retry-After") or "").strip()
    if not raw:
        return 0.0
    try:
        return max(0.0, float(raw))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return 0.0
    if when is None:
        return 0.0
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())


def _port_for(parsed) -> int:
    if parsed.port:
        return parsed.port
    return 443 if parsed.scheme == "https" else 80


def _is_blocked_ip(ip_text: str) -> bool:
    ip = ipaddress.ip_address(ip_text)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_reserved
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
    )


def assert_safe_url(url: str) -> str:
    """Validate URL scheme and reject hosts resolving to private/internal IPs."""
    normalized = normalize_url(url)
    parsed = urlparse(normalized)
    hostname = parsed.hostname

    try:
        if _is_blocked_ip(hostname):
            raise SafeHTTPError(f"Blocked: URL resolves to private/internal IP ({hostname})")
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(hostname, _port_for(parsed), type=socket.SOCK_STREAM)
    except socket.gaierror:
        return normalized

    resolved_ips = sorted({info[4][0] for info in infos})
    for ip_text in resolved_ips:
        try:
            if _is_blocked_ip(ip_text):
                raise SafeHTTPError(f"Blocked: URL resolves to private/internal IP ({ip_text})")
        except ValueError as exc:
            raise SafeHTTPError(f"Blocked: could not validate resolved IP ({ip_text})") from exc

    return normalized


def _consume_capped(response, max_response_bytes: int | None):
    if max_response_bytes is None:
        response._content = response.content
        return response

    chunks = []
    total = 0
    for chunk in response.iter_content(chunk_size=65536):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_response_bytes:
            response.close()
            raise SafeHTTPError(f"Response exceeded {max_response_bytes} byte safety limit")
        chunks.append(chunk)
    response._content = b"".join(chunks)
    response._content_consumed = True
    return response


def safe_request(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    timeout: int | float = DEFAULT_TIMEOUT,
    allow_redirects: bool = True,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    max_response_bytes: int | None = DEFAULT_MAX_RESPONSE_BYTES,
    stream: bool = False,
    session=None,
    **kwargs,
):
    """
    Execute an HTTP request with SSRF guards, redirect checks, TLS verification,
    timeouts, and a response-size cap.
    """
    _require_requests()
    current = assert_safe_url(url)
    request_headers = default_headers(headers)
    requester = session or requests.Session()
    history = []
    method = method.upper()
    kwargs["verify"] = True

    for _ in range(max_redirects + 1):
        response = _paced_request(requester, method, current, request_headers,
                                  timeout, kwargs)

        if not (allow_redirects and response.is_redirect):
            response.history = history
            if method == "HEAD":
                response.close()
                return response
            if stream:
                return response
            return _consume_capped(response, max_response_bytes)

        location = response.headers.get("Location")
        if not location:
            response.history = history
            if method == "HEAD":
                response.close()
                return response
            if stream:
                return response
            return _consume_capped(response, max_response_bytes)

        response.close()
        history.append(response)
        if len(history) > max_redirects:
            raise requests.exceptions.TooManyRedirects(f"Too many redirects (max {max_redirects})")

        next_url = assert_safe_url(urljoin(current, location))
        if response.status_code == 303 and method not in ("GET", "HEAD"):
            method = "GET"
            kwargs.pop("data", None)
            kwargs.pop("json", None)
        current = next_url

    raise requests.exceptions.TooManyRedirects(f"Too many redirects (max {max_redirects})")


def _paced_request(requester, method, url, headers, timeout, kwargs):
    """One request, paced before it goes out and retried once if asked to back off.

    The retry is deliberately single and bounded. A server that answers 429 has
    told us we are going too fast, and hammering it again — or waiting out an
    hour-long Retry-After inside an audit — are both worse than letting the item
    report NO_DATA with the reason attached.
    """
    pace(urlparse(url).hostname or "")
    response = requester.request(method, url, headers=headers, timeout=timeout,
                                 allow_redirects=False, stream=True, **kwargs)
    wait = retry_after_seconds(response)
    if 0 < wait <= MAX_RETRY_AFTER_WAIT:
        response.close()
        time.sleep(wait)
        pace(urlparse(url).hostname or "")
        response = requester.request(method, url, headers=headers, timeout=timeout,
                                     allow_redirects=False, stream=True, **kwargs)
    return response


def safe_get(url: str, **kwargs):
    return safe_request("GET", url, **kwargs)


def safe_head(url: str, **kwargs):
    return safe_request("HEAD", url, **kwargs)


def safe_post(url: str, **kwargs):
    return safe_request("POST", url, **kwargs)
