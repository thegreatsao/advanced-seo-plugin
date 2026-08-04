"""A served fixture site, so an evidence script can be tested through its real path.

Every test written before this one had to stub HTTP by hand, and the seven scripts
covered in 0.5.0 needed four different stubs between them: some fetch through
`seo_common.fetch_url`, some through `lib.safe_http.safe_get`, one posts to Safe
Browsing with `requests.post`, one asks `fetch_robots`. Reproducing that per script
would have made the remaining 44 mostly copied scaffolding — and a stub tests the
seam you thought of, not the request the script makes.

So the fixture is served over real HTTP on loopback instead. The scripts run
unmodified: their own pacing, redirect handling, robots logic and content-type checks
are all in the path, which is the half a stub cannot reach. `--allow-private` (0.4.0)
is what makes this possible at all; before it the SSRF guard refused loopback and
there was nowhere to serve a fixture.

**Still offline.** Loopback only, no egress, no API key, no DNS. A test that needs a
third-party service stubs that one call and says so.

Two sites, so every check can be exercised in both directions:

    good/   a site that satisfies as much of the registry as a static site can
    broken/ the same site with as many checks as possible deliberately failing

A check that only ever sees one of the two is not verified — it is observed agreeing
with the only input it was given, which is how thirty-three assertions in this
registry's history passed forever without being able to fail.

**Each site gets its own port, and that is not incidental.** `robots.txt`, the
sitemap and `llms.txt` live at the root of an *origin*, not inside a directory, so
two roots behind one port would have to share them — and every origin-level check
would then give both sites the same answer. Two origins is what makes `robots_checker`
and `sitemap_checker` testable in both directions at all.

Fixture URLs are written with the literal `http://127.0.0.1:8000`, which is also what
CI serves the good site on. The harness copies each tree to a temp directory and
rewrites that string to the port it actually bound, so nothing depends on a fixed
port being free and the two sites' canonicals point at themselves.
"""
from __future__ import annotations

import http.server
import os
import shutil
import socketserver
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
PLACEHOLDER = "http://127.0.0.1:8000"

# The *other* fixture origin, so a page can carry a genuinely external link without
# the suite touching the network. Several checks — outbound citations, external link
# health, cross-host detection — only have something to look at when a link leaves
# the origin, and `broken_links.py` requests every link it finds, so a real
# `https://en.wikipedia.org/...` in a fixture would quietly make this suite online.
# Each site's neighbour is external by host and still on loopback.
PLACEHOLDER_EXTERNAL = "http://127.0.0.1:8001"

TEXTUAL = (".html", ".xml", ".txt", ".css", ".json", ".md")

# Files the operator measures in a browser and hands to the run, rather than
# anything the tool fetches: a performance trace and a rendered-page measurement.
# They live outside both document roots on purpose — an artifact is an input to
# the audit, not a page of the site, and serving one would put it in the crawl.
ARTIFACTS = "artifacts"


def substitute(root: str, needle: str, replacement: str) -> None:
    """Rewrite `needle` in every textual file under `root`."""
    for folder, _dirs, files in os.walk(root):
        for name in files:
            if not name.endswith(TEXTUAL):
                continue
            path = os.path.join(folder, name)
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
            if needle in text:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text.replace(needle, replacement))


class _Quiet(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with a fixed document root and no access log."""

    root = ""

    def translate_path(self, path):
        rel = path.split("?", 1)[0].split("#", 1)[0].lstrip("/")
        return os.path.join(self.root,
                            *[p for p in rel.split("/") if p not in ("", ".", "..")])

    def log_message(self, *args):  # noqa: D102 - silence the access log
        pass


class _Site:
    """One served fixture tree on its own port.

    Rewriting happens in two passes because the second placeholder needs a port that
    does not exist until the *other* site has bound one: `_rewrite()` fixes this
    site's own URLs at construction, and `link_external()` is called by `FixtureSite`
    once both ports are known.
    """

    def __init__(self, source: str, into: str):
        self.dir = shutil.copytree(source, into)
        socketserver.ThreadingTCPServer.allow_reuse_address = True
        # Threading: several evidence scripts fetch concurrently, and a
        # single-threaded server deadlocks the moment one of them holds a connection
        # open while asking for the next page.
        handler = type("Handler", (_Quiet,), {"root": self.dir})
        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.base = f"http://127.0.0.1:{self.port}"
        self._rewrite()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def _rewrite(self) -> None:
        """Point every absolute URL in this tree at the port we actually got."""
        substitute(self.dir, PLACEHOLDER, self.base)

    def link_external(self, other_base: str) -> None:
        """Point this tree's external-link placeholder at the neighbouring origin."""
        substitute(self.dir, PLACEHOLDER_EXTERNAL, other_base)

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class FixtureSite:
    """The two fixture sites, each on its own origin.

    `good` and `broken` are absolute URLs ending in `/`. Use as a context manager or
    call `start()`/`stop()`.
    """

    def __init__(self, source: str = FIXTURES):
        self.source = source
        self.dir = ""
        self._sites: dict[str, _Site] = {}
        self._artifacts: dict[str, str] = {}

    def start(self) -> "FixtureSite":
        self.dir = tempfile.mkdtemp(prefix="seo-fixture-")
        for name in ("good", "broken"):
            src = os.path.join(self.source, name)
            if os.path.isdir(src):
                self._sites[name] = _Site(src, os.path.join(self.dir, name))
                self._copy_artifacts(name)
        # Each site's external links point at the other, once both ports are known.
        # A site served alone keeps pointing at the unbound placeholder, which fails
        # loudly rather than silently reaching the internet.
        if len(self._sites) == 2:
            good, broken = self._sites["good"], self._sites["broken"]
            good.link_external(broken.base)
            broken.link_external(good.base)
        return self

    def _copy_artifacts(self, name: str) -> None:
        """Stage this site's browser-measured artifacts, outside its document root.

        The `url` inside each one is rewritten to the port the site actually bound,
        and that is load-bearing rather than tidy: the runner refuses an artifact
        describing a different page than the one being audited, so an unrewritten
        file would arrive as NO_DATA with a reason instead of as evidence.
        """
        src = os.path.join(self.source, ARTIFACTS, name)
        if not os.path.isdir(src):
            return
        dest = shutil.copytree(src, os.path.join(self.dir, f"{ARTIFACTS}-{name}"))
        substitute(dest, PLACEHOLDER, self._sites[name].base)
        self._artifacts[name] = dest

    def artifact(self, name: str, filename: str) -> str:
        """Path to one staged artifact, or "" when this fixture has none."""
        folder = self._artifacts.get(name, "")
        path = os.path.join(folder, filename) if folder else ""
        return path if path and os.path.exists(path) else ""

    def origin(self, name: str) -> str:
        return self._sites[name].base

    @property
    def good(self) -> str:
        return self._sites["good"].base + "/"

    @property
    def broken(self) -> str:
        return self._sites["broken"].base + "/"

    def stop(self) -> None:
        for site in self._sites.values():
            site.stop()
        self._sites.clear()
        shutil.rmtree(self.dir, ignore_errors=True)

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()


def offline_env(**extra) -> dict:
    """The environment an evidence script gets in these tests.

    `SEO_ALLOW_PRIVATE` because the fixture is on loopback and the guard is doing its
    job. `SEO_MAX_RPS=0` because pacing is a courtesy to somebody else's server and
    there is nobody else here — four requests a second would make the suite take
    minutes to be polite to itself. Every credential is cleared: a machine that
    happens to have a Search Console key must not make these tests do something a
    CI runner cannot.
    """
    env = dict(os.environ)
    env.update({
        "SEO_ALLOW_PRIVATE": "1",
        "SEO_MAX_RPS": "0",
        "PYTHONPATH": os.path.join(os.path.dirname(HERE), "skills", "seo-checklist",
                                   "scripts"),
    })
    for key in ("GSC_CREDENTIALS_PATH", "GV_SA_KEY", "GOOGLE_SAFE_BROWSING_KEY",
                "PAGESPEED_API_KEY", "INDEXNOW_KEY"):
        env.pop(key, None)
    env.update(extra)
    return env
