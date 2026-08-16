"""Typed fetch failures stay machine-readable from transport to link verdict.

Every case raises at the HTTP seam. No test asks DNS or a socket what kind of
failure occurred, because the contract is precisely that callers do not infer it
from another library's prose.
"""
from __future__ import annotations

import os
import socket
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "seo-checklist", "scripts")
sys.path.insert(0, SCRIPTS)

import broken_links  # noqa: E402
import external_link_quality  # noqa: E402
import seo_common  # noqa: E402
from lib import safe_http  # noqa: E402


def raising(exc):
    def fail(*args, **kwargs):
        raise exc
    return fail


class FetchErrorKinds(unittest.TestCase):

    def fetched(self, exc):
        with mock.patch.object(seo_common, "safe_request", side_effect=exc):
            return seo_common.fetch_url("https://failure.example/")

    def test_the_closed_vocabulary_is_produced_from_exception_types(self):
        cases = (
            (safe_http.HostResolutionError("no address"), "unresolved"),
            (requests_error("ConnectionError", "refused"), "refused"),
            (requests_error("Timeout", "late"), "timeout"),
            (requests_error("SSLError", "certificate"), "tls"),
            (safe_http.SafeHTTPError("private address"), "blocked"),
            (safe_http.RobotsDisallowed("robots.txt"), "robots"),
            (requests_error("RequestException", "opaque"), "other"),
        )
        self.assertEqual(
            seo_common.FETCH_ERROR_KINDS,
            ("unresolved", "refused", "timeout", "tls", "blocked", "robots", "other"),
        )
        for exc, expected in cases:
            with self.subTest(expected=expected):
                result = self.fetched(exc)
                self.assertEqual(result["error"], str(exc))
                self.assertEqual(result["error_kind"], expected)

    def test_name_resolution_inside_a_connection_error_uses_the_typed_reason(self):
        wrapper = RuntimeError("wrapper prose is irrelevant")
        wrapper.reason = socket.gaierror(socket.EAI_NONAME, "also irrelevant")
        exc = seo_common.requests.exceptions.ConnectionError(wrapper)
        self.assertEqual(self.fetched(exc)["error_kind"], "unresolved")

    def test_other_survives_the_fetch_result_without_becoming_a_neighbour(self):
        exc = seo_common.requests.exceptions.RequestException("opaque failure")
        result = self.fetched(exc)
        self.assertEqual(result["error"], "opaque failure")
        self.assertEqual(result["error_kind"], "other")
        self.assertNotIn(result["error_kind"], seo_common.DEAD_FETCH_ERROR_KINDS)


def requests_error(name: str, message: str):
    return getattr(seo_common.requests.exceptions, name)(message)


class ExternalLinkKinds(unittest.TestCase):

    def audit_one(self, error_kind: str) -> dict:
        source = {
            "status": 200,
            "text": '<a href="https://target.example/path">target</a>',
            "url": "https://source.example/",
            "error": None,
            "error_kind": None,
        }
        failed = {
            "status": None,
            "url": "https://target.example/path",
            "redirect_chain": [],
            "error": "the wording is deliberately identical",
            "error_kind": error_kind,
        }
        # A failed HEAD takes the script's existing GET fallback, so both attempts
        # carry the same typed outcome.
        with mock.patch.object(external_link_quality, "fetch_url",
                               side_effect=(source, failed, failed)):
            return external_link_quality.audit_external_links(
                ["https://source.example/"], timeout=1)

    def test_unresolved_is_broken_and_blocked_is_unchecked(self):
        unresolved = self.audit_one("unresolved")
        blocked = self.audit_one("blocked")
        self.assertEqual(unresolved["summary"]["broken_links"], 1)
        self.assertEqual(unresolved["summary"]["unreachable_links"], 1)
        self.assertEqual(blocked["summary"]["broken_links"], 0)
        self.assertEqual(blocked["summary"]["unchecked_links"], 1)


class BrokenLinkKinds(unittest.TestCase):

    def check_one(self, exc) -> dict:
        page = SimpleNamespace(
            status_code=200,
            text='<a href="https://target.example/path">target</a>',
        )
        with mock.patch.object(broken_links, "safe_get", return_value=page), \
                mock.patch.object(broken_links, "safe_head", side_effect=exc):
            return broken_links.check_broken_links(
                "https://source.example/", max_workers=1, timeout=1)

    def test_unresolved_is_broken_and_robots_is_unchecked(self):
        unresolved = self.check_one(safe_http.HostResolutionError("no address"))
        robots = self.check_one(safe_http.RobotsDisallowed("robots.txt disallows it"))
        self.assertEqual(unresolved["summary"]["broken"], 1)
        self.assertEqual(unresolved["broken"][0]["error"], "no address")
        self.assertEqual(unresolved["broken"][0]["error_kind"], "unresolved")
        self.assertEqual(robots["summary"]["broken"], 0)
        self.assertEqual(robots["summary"]["unchecked"], 1)
        self.assertEqual(robots["unchecked"][0]["error_kind"], "robots")


if __name__ == "__main__":
    unittest.main()
