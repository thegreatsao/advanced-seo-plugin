#!/usr/bin/env python3
"""Small shared helpers for standalone SEO CLI scripts."""

from __future__ import annotations

import gzip
import json
import re
import sys
import xml.etree.ElementTree as ET
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlunparse

try:
    import requests
except ImportError:  # pragma: no cover - exercised by users without deps
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - exercised by users without deps
    BeautifulSoup = None

try:
    from lib.safe_http import (AGENTIC_SEO_USER_AGENT, RobotsDisallowed,
                               safe_request)
except ImportError:
    from scripts.lib.safe_http import (AGENTIC_SEO_USER_AGENT, RobotsDisallowed,
                                       safe_request)


USER_AGENT = AGENTIC_SEO_USER_AGENT
HTML_CTYPES = ("text/html", "application/xhtml+xml")
XML_CTYPES = ("xml", "text/plain", "application/octet-stream")


def require_requests() -> None:
    if requests is None:
        print("Error: requests library required. Install with: pip install requests", file=sys.stderr)
        sys.exit(1)


def require_bs4() -> None:
    if BeautifulSoup is None:
        print("Error: beautifulsoup4 required. Install with: pip install beautifulsoup4", file=sys.stderr)
        sys.exit(1)


def normalize_url(url: str, base: str | None = None, default_scheme: str = "https") -> str:
    url = (url or "").strip()
    if base:
        url = urljoin(base, url)
    parsed = urlparse(url)
    if not parsed.scheme and not base:
        url = f"{default_scheme}://{url}"
        parsed = urlparse(url)
    if parsed.scheme in ("http", "https"):
        path = parsed.path or "/"
        parsed = parsed._replace(fragment="", path=path)
        return urlunparse(parsed)
    return url


def is_responsive_fill_image(img) -> bool:
    if img.get("data-nimg") == "fill":
        return True
    style = re.sub(r"\s+", "", (img.get("style") or "").lower())
    return "position:absolute" in style and "width:100%" in style and "height:100%" in style


# `srcset` is a comma-separated candidate list where each entry is a URL plus an
# optional descriptor: "logo.avif 1x, logo@2x.avif 2x". Only the URL carries the
# format, so the descriptor has to be dropped before an extension means anything.
def srcset_urls(srcset: str, base_url: str = "") -> list[str]:
    out = []
    for candidate in (srcset or "").split(","):
        url = candidate.strip().split()[0] if candidate.strip() else ""
        if url:
            out.append(normalize_url(url, base_url) if base_url else url)
    return out


def picture_sources(img, base_url: str = "") -> list[dict]:
    """The `<source>` alternatives a `<picture>` offers for this `<img>`.

    Empty for an `img` that stands alone, which is most of them. It has to be a
    `<picture>` specifically: `<source>` also appears inside `<video>` and
    `<audio>`, where it means something else entirely, and the `img` is the only
    thing tying a set of sources to a still image.

    **Any ancestor, not the parent.** libxml2 — which is what `lxml` is, and lxml
    is the parser this module prefers — predates `<picture>` and does not know
    `<source>` is void, so it nests the `<img>` *inside* the first `<source>`
    instead of beside it. Under `html.parser` the same markup gives the `img` the
    `<picture>` as its parent. Walking up finds the same element either way, which
    is the only reason this function does not silently return nothing in production
    while passing its tests. See KNOWN-ISSUES.md — the divergence is wider than
    this function and nothing else structural relies on it yet.
    """
    picture = img.find_parent("picture") if hasattr(img, "find_parent") else None
    if picture is None:
        return []
    out = []
    # Recursive on purpose: under lxml the second `<source>` is a child of the
    # first rather than its sibling, so a non-recursive scan would find one.
    for source in picture.find_all("source"):
        srcset = source.get("srcset") or ""
        out.append({
            "type": (source.get("type") or "").strip().lower() or None,
            "media": source.get("media"),
            "srcset": srcset or None,
            "sizes": source.get("sizes"),
            "urls": srcset_urls(srcset, base_url),
        })
    return out


# Below this many declared pixels an image is not what the Largest Contentful Paint
# measures — it is an icon. A threshold, not a law: 100×100 is the smallest thing that
# could plausibly be the largest paint on a page with any content at all, and Chrome's
# own LCP heuristics discard low-entropy images for the same reason. Written down here
# because it is one of the numbers KNOWN-ISSUES §2 is about.
LCP_MIN_AREA = 100 * 100


def _declared_area(img: dict) -> int | None:
    """Pixels the markup claims, or None when it does not say."""
    try:
        width, height = int(str(img.get("width"))), int(str(img.get("height")))
    except (TypeError, ValueError):
        return None
    return width * height if width > 0 and height > 0 else None


def likely_lcp_candidate(img: dict, index: int) -> bool:
    """Whether this image could be the Largest Contentful Paint.

    One definition, because there were two: `image_inventory.py` and
    `image_weight_audit.py` each held `index == 0 or fetchpriority == "high" or
    loading == "eager"`, and two copies of a heuristic drift.

    Document order is the signal available without a browser, and it is a weak one —
    the first `<img>` in the source is often a logo. So an image that *declares* a
    size too small to be the largest paint is excluded: the good fixture is a page
    whose only image is a 64px loaf mark inside a `<figure>` halfway down, correctly
    lazy-loaded, and two items reported it as a lazy-loaded LCP image. A real
    measurement is `cwv_metrics.py`'s job and it names the element; this is the
    fallback for a run with no browser trace.
    """
    area = _declared_area(img)
    if area is not None and area < LCP_MIN_AREA:
        return False
    return (index == 0
            or img.get("fetchpriority") == "high"
            or img.get("loading") == "eager")


def origin(url: str) -> str:
    parsed = urlparse(normalize_url(url))
    return f"{parsed.scheme}://{parsed.netloc}"


def clean_url(url: str) -> str:
    parsed = urlparse(normalize_url(url))
    return urlunparse(parsed._replace(fragment=""))


def same_host(a: str, b: str, include_www_variant: bool = True) -> bool:
    host_a = urlparse(normalize_url(a)).netloc.lower()
    host_b = urlparse(normalize_url(b)).netloc.lower()
    if include_www_variant:
        host_a = host_a[4:] if host_a.startswith("www.") else host_a
        host_b = host_b[4:] if host_b.startswith("www.") else host_b
    return host_a == host_b


def fetch_url(
    url: str,
    method: str = "GET",
    timeout: int = 15,
    allow_redirects: bool = True,
    max_bytes: int = 2_000_000,
    extra_headers: dict | None = None,
    respect_robots: bool = False,
) -> dict:
    """Fetch a URL through the shared safe, paced HTTP path.

    Pass `respect_robots=True` for a URL found by crawling, never for the one the
    operator asked about — see `lib.safe_http.safe_request` for why the asymmetry
    matters. A refusal arrives as `result["error"]` naming robots.txt, and
    `result["robots_blocked"]` is True. A caller that counts errors as site defects
    **must** separate those out: a page we politely declined to fetch is not a page
    the site got wrong.
    """
    require_requests()
    url = normalize_url(url)
    parsed = urlparse(url)
    result = {
        "input_url": url,
        "url": url,
        "status": None,
        "headers": {},
        "text": "",
        "bytes": 0,
        "redirect_chain": [],
        "error": None,
        "robots_blocked": False,
    }
    if parsed.scheme not in ("http", "https"):
        result["error"] = f"Unsupported URL scheme: {parsed.scheme}"
        return result

    # No Accept of its own any more. It used to send one differing from
    # `default_headers()` by a single media type, and two spellings of one header
    # made every audited page two requests instead of one — invisible until the
    # response cache made it countable. DEFAULT_HEADERS now carries the union, so
    # nothing here advertises less than it did.
    headers = dict(extra_headers) if extra_headers else {}

    try:
        response = safe_request(
            method,
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=allow_redirects,
            max_response_bytes=max_bytes,
            respect_robots=respect_robots,
        )
        result["url"] = response.url
        result["status"] = response.status_code
        result["headers"] = {str(k).lower(): v for k, v in response.headers.items()}
        result["redirect_chain"] = [r.url for r in response.history]

        if method.upper() != "HEAD":
            result["bytes"] = len(response.content)
            result["text"] = response.text
    except RobotsDisallowed as exc:
        # Flagged, not merely errored. Callers that turn "not fetched" into a site
        # defect have to be able to tell our restraint from the site's problem.
        result["error"] = str(exc)
        result["robots_blocked"] = True
    except requests.exceptions.RequestException as exc:
        result["error"] = str(exc)
    return result


def read_urls(values: list[str] | None = None, file_path: str | None = None) -> list[str]:
    urls: list[str] = []
    for value in values or []:
        if value:
            urls.append(value.strip())
    if file_path:
        with open(file_path, "r", encoding="utf-8") as fh:
            urls.extend(line.strip() for line in fh if line.strip() and not line.lstrip().startswith("#"))
    seen = set()
    normalized = []
    for url in urls:
        nurl = normalize_url(url)
        if nurl not in seen:
            seen.add(nurl)
            normalized.append(nurl)
    return normalized


def load_html(source: str, timeout: int = 15) -> tuple[str, str, dict]:
    if re.match(r"^https?://", source, re.I) or "." in source and "/" not in source:
        fetched = fetch_url(source, timeout=timeout)
        return fetched.get("text") or "", fetched.get("url") or normalize_url(source), fetched
    with open(source, "r", encoding="utf-8") as fh:
        html = fh.read()
    return html, "", {"url": source, "status": None, "headers": {}, "error": None}


def parse_html(html: str, base_url: str = "") -> dict:
    require_bs4()
    soup = BeautifulSoup(html or "", "lxml" if "lxml" in sys.modules else "html.parser")

    def text_or_none(tag):
        return tag.get_text(" ", strip=True) if tag else None

    title = text_or_none(soup.find("title"))
    meta = {}
    for tag in soup.find_all("meta"):
        key = (tag.get("name") or tag.get("property") or tag.get("http-equiv") or "").strip().lower()
        if key:
            meta[key] = tag.get("content", "")

    canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    canonical = canonical_tag.get("href") if canonical_tag else None
    if canonical and base_url:
        canonical = normalize_url(canonical, base_url)

    links = []
    for tag in soup.find_all("a", href=True):
        href = tag.get("href", "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            continue
        abs_url = normalize_url(href, base_url) if base_url else href
        links.append({
            "href": abs_url,
            "text": tag.get_text(" ", strip=True)[:160],
            "rel": tag.get("rel") or [],
        })

    images = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if src and base_url:
            src = normalize_url(src, base_url)
        is_responsive_fill = is_responsive_fill_image(img)
        images.append({
            "src": src,
            "alt": img.get("alt"),
            "width": img.get("width"),
            "height": img.get("height"),
            "is_responsive_fill": is_responsive_fill,
            "loading": img.get("loading"),
            "srcset": img.get("srcset"),
            "sizes": img.get("sizes"),
            "fetchpriority": img.get("fetchpriority"),
            "decoding": img.get("decoding"),
            # What the browser may pick *instead* of `src`. Reading only the `img`
            # made a site doing this right look like a site doing nothing: the
            # recommended way to serve webp is a `<picture>` whose `<source>`
            # offers the modern format and whose `<img>` keeps a png fallback for
            # old browsers — so the fallback was the only thing the audit ever
            # saw, and MB-096/MB-097 failed the pattern they exist to encourage.
            "picture_sources": picture_sources(img, base_url),
        })

    schema = []
    for script in soup.find_all("script", type=lambda v: v and "ld+json" in v):
        raw = script.string or script.get_text() or ""
        try:
            data = json.loads(raw)
            schema.append(data)
        except json.JSONDecodeError:
            schema.append({"error": "invalid_json", "snippet": raw[:160]})

    for element in soup(["script", "style", "noscript", "template"]):
        element.decompose()
    body_text = soup.get_text(" ", strip=True)
    words = re.findall(r"\b[\w'-]+\b", body_text)

    return {
        "title": title,
        "meta_description": meta.get("description"),
        "meta_robots": meta.get("robots"),
        "viewport": meta.get("viewport"),
        "canonical": canonical,
        "lang": (soup.html.get("lang") if soup.html else None),
        "headings": {f"h{i}": [h.get_text(" ", strip=True) for h in soup.find_all(f"h{i}") if h.get_text(strip=True)] for i in range(1, 7)},
        "links": links,
        "images": images,
        "schema": schema,
        "word_count": len(words),
        "body_text": body_text,
        "forms": len(soup.find_all("form")),
        "landmarks": {
            "main": len(soup.find_all("main")),
            "nav": len(soup.find_all("nav")),
            "header": len(soup.find_all("header")),
            "footer": len(soup.find_all("footer")),
        },
        "labels": len(soup.find_all("label")),
        "inputs": len(soup.find_all(["input", "select", "textarea"])),
        "buttons": len(soup.find_all(["button"])) + len(soup.find_all("a", role="button")),
        "soup": soup,
    }


def issue(severity: str, message: str, url: str | None = None, evidence: str | None = None) -> dict:
    return {"severity": severity, "message": message, "url": url, "evidence": evidence}


def parse_robots_txt(content: str) -> dict:
    groups: list[dict] = []
    current: dict | None = None
    sitemaps: list[str] = []
    crawl_delays: dict[str, float] = {}
    for raw_line in (content or "").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        name, value = line.split(":", 1)
        name = name.strip().lower()
        value = value.strip()
        if name == "user-agent":
            if current is None or current.get("rules"):
                current = {"agents": [], "rules": []}
                groups.append(current)
            current["agents"].append(value.lower())
        elif name in ("allow", "disallow") and current is not None:
            current["rules"].append((name, value))
        elif name == "sitemap":
            sitemaps.append(value)
        elif name == "crawl-delay" and current is not None:
            try:
                delay = float(value)
            except ValueError:
                continue
            for agent in current["agents"]:
                crawl_delays[agent] = delay
    return {"groups": groups, "sitemaps": sitemaps, "crawl_delays": crawl_delays}


def _robots_pattern_to_regex(pattern: str) -> re.Pattern:
    escaped = re.escape(pattern).replace("\\*", ".*")
    if escaped.endswith("\\$"):
        escaped = escaped[:-2] + "$"
    return re.compile("^" + escaped)


def robots_allowed(parsed_robots: dict | None, url: str, user_agent: str = "*") -> tuple[bool, str]:
    if not parsed_robots:
        return True, "no robots.txt"
    path = urlparse(normalize_url(url)).path or "/"
    ua = user_agent.lower()
    matches: list[tuple[int, str, str]] = []
    for group in parsed_robots.get("groups", []):
        agents = group.get("agents", [])
        if not any(agent == "*" or agent in ua or ua in agent for agent in agents):
            continue
        for directive, pattern in group.get("rules", []):
            if directive == "disallow" and pattern == "":
                continue
            if _robots_pattern_to_regex(pattern).search(path):
                matches.append((len(pattern), directive, pattern))
    if not matches:
        return True, "no matching rule"
    matches.sort(key=lambda item: (item[0], item[1] == "allow"), reverse=True)
    _, directive, pattern = matches[0]
    return directive == "allow", f"{directive}: {pattern}"


def fetch_robots(site_url: str, timeout: int = 15) -> dict:
    robots_url = origin(site_url) + "/robots.txt"
    fetched = fetch_url(robots_url, timeout=timeout, max_bytes=500_000)
    parsed = parse_robots_txt(fetched.get("text") or "") if fetched.get("status") == 200 else None
    return {"url": robots_url, "fetch": fetched, "parsed": parsed}


# Conventional filenames worth trying when nothing declares a sitemap. They are
# guesses, and a guess that misses says nothing about the site — see
# `discover_sitemap_urls`.
CONVENTIONAL_SITEMAP_PATHS = ("/sitemap.xml", "/sitemap_index.xml",
                              "/sitemap-index.xml")


def discover_sitemap_urls(site_url: str, timeout: int = 15,
                          with_source: bool = False):
    """Sitemap URLs to try, declared ones first.

    With `with_source=True`, yields `(url, source)` where source is `"declared"`
    (named in robots.txt, or passed in by the caller) or `"probed"` (a conventional
    filename we guessed at).

    **The distinction decides whether a 404 is a finding.** A declared sitemap that
    does not load is a real defect: the site says it is there. A probed filename
    that 404s means only that this site does not use that name — which is true of
    almost every site, since these three names are alternatives, not a set. Treating
    the miss as an error made `sitemap_checker` report two errors against every site
    that has exactly one sitemap, and those errors failed GO-136 (`none_severity`)
    and GO-138 (whose pattern matches the literal "404" in the message). A clean
    sitemap could not pass either item.
    """
    base = origin(site_url)
    robots = fetch_robots(site_url, timeout=timeout)
    declared = list((robots.get("parsed") or {}).get("sitemaps", []))
    pairs, seen = [], set()
    for candidate, source in ([(c, "declared") for c in declared]
                              + [(base + p, "probed")
                                 for p in CONVENTIONAL_SITEMAP_PATHS]):
        url = normalize_url(candidate, base)
        if url not in seen:
            seen.add(url)
            pairs.append((url, source))
    return pairs if with_source else [url for url, _ in pairs]


def parse_sitemap_xml(xml_text: str, sitemap_url: str = "") -> dict:
    text = xml_text or ""
    if text[:2] == "\x1f\x8b":
        text = gzip.decompress(text.encode("latin1")).decode("utf-8", errors="replace")
    try:
        root = ET.fromstring(text.encode("utf-8"))
    except ET.ParseError as exc:
        return {"type": "invalid", "urls": [], "sitemaps": [], "error": str(exc)}

    def local(tag: str) -> str:
        return tag.split("}", 1)[-1]

    urls = []
    children = list(root)
    if local(root.tag) == "sitemapindex":
        for sm in root:
            loc = sm.findtext("{*}loc") or sm.findtext("loc")
            if loc:
                urls.append({"loc": normalize_url(loc, sitemap_url), "lastmod": sm.findtext("{*}lastmod") or sm.findtext("lastmod")})
        return {"type": "sitemapindex", "urls": [], "sitemaps": urls, "error": None}

    if local(root.tag) == "urlset" or any(local(child.tag) == "url" for child in children):
        for node in root.findall("{*}url") or root.findall("url"):
            loc = node.findtext("{*}loc") or node.findtext("loc")
            if not loc:
                continue
            urls.append({
                "loc": normalize_url(loc, sitemap_url),
                "lastmod": node.findtext("{*}lastmod") or node.findtext("lastmod"),
                "changefreq": node.findtext("{*}changefreq") or node.findtext("changefreq"),
                "priority": node.findtext("{*}priority") or node.findtext("priority"),
            })
        return {"type": "urlset", "urls": urls, "sitemaps": [], "error": None}

    return {"type": "unknown", "urls": [], "sitemaps": [], "error": f"Unknown root element: {root.tag}"}


def extract_directives(value: str | None) -> set[str]:
    if not value:
        return set()
    cleaned = value.lower().replace(";", ",")
    return {part.strip() for part in cleaned.split(",") if part.strip()}


def print_json_or_text(result: dict, as_json: bool, text_lines: Iterable[str]) -> None:
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=False))
    else:
        for line in text_lines:
            print(line)
