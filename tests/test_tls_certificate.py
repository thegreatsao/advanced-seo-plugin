"""`tls_certificate.py`, the evidence behind SE-118.

The rule this file inherits from `test_evidence_scripts.py`: **assert the field the
registry actually reads**, named here, so a script that quietly changes its output
contract fails in this suite rather than in a client's report. SE-118 reads `valid`.

Why it is its own file rather than a case in `test_evidence_scripts.py`: every other
evidence script is answered by an origin over plain HTTP, and this one cannot be. It
needs a certificate, which is what `harness.tls_context()` exists for.

The defect this guards is not hypothetical. Until 0.20 SE-118 asserted `https ==
True` — SE-117's field, from SE-117's script — so two `critical` items shared one
assertion, SE-118 could not fail independently on any site, and a certificate that
expired yesterday passed it. The negative case below is the one that matters: a
verdict that can only be True is not a verdict.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from harness import offline_env, served, tls_env

SCRIPT = (Path(__file__).resolve().parent.parent
          / "skills/seo-checklist/scripts/tls_certificate.py")


def run(url: str, env: dict) -> dict:
    # `sys.executable` and `close_fds=False`, both required by the repo's own
    # posix_spawn rules (test_runner.AScriptTheOperatingSystemKilled), which scan this
    # directory too — the first draft of this file broke both. They are not bureaucracy
    # here: without `close_fds=False` CPython takes the fork path, and this child opens
    # a TLS connection, which is precisely the Network.framework case macOS kills with
    # -11. The four tests passed alone and segfaulted inside the full suite until this
    # line was right.
    proc = subprocess.run([sys.executable, str(SCRIPT), url, "--json"],
                          capture_output=True, text=True, env=env, timeout=60,
                          close_fds=False)
    assert proc.returncode == 0, f"exited {proc.returncode}: {proc.stderr[-400:]}"
    return json.loads(proc.stdout)


class TlsCertificate(unittest.TestCase):

    def test_a_trusted_certificate_sets_the_field_se_118_reads(self):
        """`valid` is True, and only after a handshake that verified."""
        with served({"/": "<html><body>ok</body></html>"}, tls=True) as site:
            out = run(site.url, tls_env())
        self.assertTrue(out["valid"], out)          # <- the field SE-118 asserts
        self.assertNotIn("verify_error", out)
        self.assertTrue(out["tls_version"].startswith("TLS"), out)
        self.assertIsInstance(out["not_after"], str)
        self.assertIsInstance(out["days_until_expiry"], int)

    def test_an_untrusted_certificate_fails_rather_than_passing_on_the_scheme(self):
        """The same origin, without the CA in the environment.

        This is the whole point of the item. The URL still begins `https`, so the
        pre-0.20 assertion passed here; a verifying handshake does not.
        """
        with served({"/": "<html><body>ok</body></html>"}, tls=True) as site:
            out = run(site.url, offline_env())
        self.assertFalse(out.get("valid"), out)
        self.assertIn("verify_error", out)
        self.assertTrue(any(i["severity"] == "critical" for i in out["issues"]), out)

    def test_a_host_that_speaks_no_tls_reports_an_error_and_not_a_verdict(self):
        """A refused handshake is not a bad certificate.

        `valid` must be absent, not False: 'we could not look' and 'we looked and it
        is invalid' are different claims, and `truthy` on a missing field is NO_DATA
        rather than FAIL — which is what the runner is supposed to report when the
        connection never got far enough to see a certificate.
        """
        with served({"/": "<html><body>ok</body></html>"}) as site:
            plain = site.url.replace("http://", "https://")
            out = run(plain, offline_env())
        self.assertNotIn("valid", out)
        self.assertIn("error", out)

    def test_an_http_url_is_not_a_certificate_failure(self):
        """The good fixture is served over plain HTTP, and both fixture sites are.

        The first draft opened TLS against the plaintext port anyway and reported
        `SSLError: WRONG_VERSION_NUMBER` — an error about our own request, dressed as
        a fact about the site, which the good-site sweep counted as a crashed script.
        SE-117 is the item that says a site is not on HTTPS; this one has nothing to
        look at and must say so without inventing a verdict.
        """
        with served({"/": "<html><body>ok</body></html>"}) as site:
            out = run(site.url, offline_env())
        self.assertNotIn("valid", out)
        self.assertNotIn("error", out)
        self.assertIs(out["https"], False)
        self.assertEqual(out["issues"], [])

    def test_a_url_with_no_host_is_refused_without_a_handshake(self):
        out = run("https:///nowhere", offline_env())
        self.assertNotIn("valid", out)
        self.assertTrue(any(i["severity"] == "critical" for i in out["issues"]), out)


if __name__ == "__main__":
    unittest.main()
