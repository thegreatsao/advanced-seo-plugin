"""Every remaining evidence script, run against a served page, through its own path.

`test_evidence.py` covers the seven scripts that decide the nineteen `critical`
items. This file covers the other 43 — 83 registry items — and the rule is the same
one: **each test asserts the field the registry actually reads**, named in the test,
so a script that quietly changes its output contract fails here instead of in a
client's report.

Why this was worth the trouble twice over: writing the first 34 found eighteen
assertions that had never fired, and writing the eight for `image_weight_audit.py`
found two items that failed sites for serving images the recommended way. One defect
per two or three tests, two releases running. That rate is the argument — not a
coverage percentage.

**The scripts are not stubbed and not imported.** Each runs as a subprocess with
`--json`, exactly as `checklist_runner.run_script` runs it, against a real origin on
loopback. A stub tests the seam you thought of; these scripts reach for HTTP through
four different seams, and their own redirect handling, content-type checks, robots
logic and pacing are all things a stub replaces with an assumption.

Two origins, because `robots.txt`, `llms.txt` and the sitemap belong to an *origin*
rather than a directory — one document root cannot be both present and absent, so a
single origin could only ever test those in one direction.

Every run happens once, in `setUpModule`, in parallel, and is cached: 40 scripts is
~80 process launches, and doing them per test method would make this file slower than
the rest of the suite put together.
"""
import json
import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "seo-checklist")
SCRIPTS = os.path.join(SKILL, "scripts")
REGISTRY = os.path.join(SKILL, "resources", "config", "checklist.json")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harness  # noqa: E402
from harness import served  # noqa: E402

from checklist_runner import NO_DATA, PASS, FAIL, WARN, evaluate  # noqa: E402

with open(REGISTRY, encoding="utf-8") as f:
    ITEMS = {i["id"]: i for i in json.load(f)["items"]}


def verdict(item_id: str, output: dict) -> str:
    """The item's real rule over a script's real output, graded as the runner grades.

    The rule is read from the registry rather than restated here. A test that
    hard-codes `{"path": "score", "gte": 70}` keeps passing after the registry stops
    asking for it, which is exactly how a check goes quiet.
    """
    check = ITEMS[item_id]["check"]
    ok, _ = evaluate(check["assert"], output)
    if ok is None:
        return NO_DATA
    if ok:
        return PASS
    warn = check.get("warn")
    if warn and evaluate(warn, output)[0]:
        return WARN
    return FAIL


# ---------------------------------------------------------------------------
# The pages
# ---------------------------------------------------------------------------

# Rewritten to whichever port the origin bound, the same way the fixture trees are,
# so canonicals, sitemap entries, hreflang targets and `Location` headers point at
# themselves. Getting this wrong is not subtle in its effects and is very subtle to
# read: the first version of this file replaced a string the bodies did not contain,
# so every absolute URL pointed at a host that does not exist — and the *symptoms*
# were six checks reporting plausible-looking failures about self-reference, orphans,
# duplicate canonicals and redirect hops. Half an hour of reading them as script bugs.
PLACEHOLDER = "PLACEHOLDER"

GOOD_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Sourdough starter care: feeding, reviving and storing</title>
<meta name="description" content="How to feed and revive a sourdough starter, with timings for warm and cold kitchens.">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="canonical" href="PLACEHOLDER/">
<link rel="icon" href="/favicon.ico">
<meta property="og:title" content="Sourdough starter care">
<meta property="og:description" content="Feeding and reviving a sourdough starter.">
<meta property="og:image" content="PLACEHOLDER/i/a.webp">
<meta property="og:url" content="PLACEHOLDER/">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Fixture Bakery">
<meta property="og:locale" content="en_GB">
<meta property="article:published_time" content="2026-07-01">
<meta name="twitter:site" content="@fixturebakery">
<meta name="twitter:image:alt" content="A round sourdough loaf">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Sourdough starter care">
<meta name="twitter:description" content="Feeding and reviving a starter.">
<meta name="twitter:image" content="PLACEHOLDER/i/a.webp">
<link rel="stylesheet" href="/s.min.css">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Article",
"headline":"Sourdough starter care: feeding, reviving and storing","datePublished":"2026-07-01",
"dateModified":"2026-07-20","author":{"@type":"Person","name":"A Baker","url":"PLACEHOLDER/about.html"},
"publisher":{"@type":"Organization","name":"Fixture Bakery","url":"PLACEHOLDER/",
"logo":{"@type":"ImageObject","url":"PLACEHOLDER/i/logo.png","width":600,"height":60}},
"image":"PLACEHOLDER/i/a.webp","description":"How to feed and revive a sourdough starter.",
"mainEntityOfPage":{"@type":"WebPage","@id":"PLACEHOLDER/"}}</script>
</head><body>
<header><nav><a href="/">Starter care</a> <a href="/about.html">Who we are</a>
<a href="/guide.html">Baking guide</a> <a href="/privacy.html">Privacy</a></nav></header>
<main><h1>Sourdough starter care</h1>
<p>A sourdough starter is flour and water kept alive by regular feeding. Last updated
20 July 2026 by A Baker, who has kept the same culture since 2019.</p>
<h2>How often should you feed a sourdough starter?</h2>
<p>Once a day at room temperature, or once a week in the refrigerator. A starter fed
on a schedule rises predictably, and predictability is the whole point of keeping one
rather than buying yeast. Acidity slows starch retrogradation, which is why a sour
loaf stales more slowly than a sweet one.</p>
<h2>What does it mean when a starter smells of acetone?</h2>
<p>It is hungry. The smell is ethanol and acetic acid accumulating because the
available starch has been consumed. Feed it twice at twelve-hour intervals and it
recovers; discard nothing but the excess.</p>
<h2>Can you revive a starter that has been neglected for months?</h2>
<p>Usually yes. Scrape off any dry crust, keep a spoonful of the wet centre, and feed
it every twelve hours for three days. Lactobacilli survive far longer than bakers
expect, and a culture that looks dead is generally only dormant.</p>
<h3>Storing a starter between bakes</h3>
<p>Refrigerate it in a jar with a loose lid. Cold slows fermentation without stopping
it, so a weekly feed is enough. Feed it twice at room temperature before you bake, and
give the second feed at least four hours so the culture is at its peak when it goes
into the dough rather than already falling back.</p>
<table><caption>Feeding schedule</caption>
<tr><th>Kitchen</th><th>Interval</th></tr>
<tr><td>Warm (24C)</td><td>Every 12 hours</td></tr>
<tr><td>Cold (18C)</td><td>Once a day</td></tr></table>
<ul><li>Feed by weight, not by volume.</li><li>Use unchlorinated water.</li>
<li>Keep the jar loosely covered.</li></ul>
<blockquote cite="https://en.wikipedia.org/wiki/Sourdough"><p>Sourdough fermentation
is driven by lactic acid bacteria and yeasts.</p></blockquote>
<p>Sources: <a href="https://en.wikipedia.org/wiki/Sourdough">Wikipedia on
sourdough</a>, and our own <a href="/about.html">editorial policy</a>.</p>
<figure><picture><source type="image/webp" srcset="/i/a.webp 1x, /i/a.webp 2x"
sizes="(max-width: 600px) 64px, 128px">
<img src="/i/a.png" alt="A round sourdough loaf, scored across the top"
width="64" height="64" fetchpriority="high" decoding="async"></picture>
<figcaption>A finished loaf.</figcaption></figure>
</main>
<footer><p>Fixture Bakery, 1 Fixture Street, Vilnius, Lithuania. Telephone
+370 600 00000. <a href="/privacy.html">Privacy policy</a> ·
<a href="/about.html#contact">Contact</a></p></footer>
<script src="/s.js" defer></script></body></html>"""

# Deliberately failing, and failing in ways a *page* can: the origin-level defects
# live on the second origin because robots.txt and llms.txt cannot be both there and
# not there behind one port.
BAD_PAGE = """<!doctype html><html><head>
<title>page</title>
<meta name="robots" content="noindex">
<link rel="canonical" href="https://elsewhere.example/other">
<script src="https://cdn.jsdelivr.net/npm/heavy/heavy.js"></script>
<script src="https://www.googletagmanager.com/gtag/js?id=G-DUPLICATE"></script>
<script src="https://www.googletagmanager.com/gtag/js?id=G-DUPLICATE"></script>
<link rel="stylesheet" href="/s.css">
<style>
  body { font-size : 9px ; color : #eeeeee ; background : #ffffff }
  /* a comment left in, and a great deal of pointless whitespace */
</style>
</head><body>
<h1>a</h1><h1>b</h1>
<p style="font-size:8px;color:#f0f0f0;background:#ffffff">short</p>
<img src="/i/missing.png"><img src="/i/a.png" alt="">
<a href="http://insecure.invalid/x">click here</a>
<a href="/gone">here</a> <a href="/thin-indexable.html">stub</a>
<a href="/shop?utm_source=s0&amp;SESSIONID=0&amp;color=c0&amp;size=z0&amp;sort=k0">Filter 0</a>
<a href="/shop?utm_source=s1&amp;SESSIONID=1&amp;color=c1&amp;size=z1&amp;sort=k1">Filter 1</a>
<a href="/shop?utm_source=s2&amp;SESSIONID=2&amp;color=c2&amp;size=z2&amp;sort=k2">Filter 2</a>
<a href="/shop?utm_source=s3&amp;SESSIONID=3&amp;color=c3&amp;size=z3&amp;sort=k3">Filter 3</a>
<a href="/shop?utm_source=s4&amp;SESSIONID=4&amp;color=c4&amp;size=z4&amp;sort=k4">Filter 4</a>
<a href="/shop?utm_source=s5&amp;SESSIONID=5&amp;color=c5&amp;size=z5&amp;sort=k5">Filter 5</a>
<script src="/s.js"></script></body></html>"""

# One page per shape a script needs and the two above do not have.
INTL_BROKEN = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Intl</title><link rel="canonical" href="PLACEHOLDER/intl-broken.html">
<link rel="alternate" hreflang="en-GB" href="http://PLACEHOLDER_HOST/intl-broken.html">
<link rel="alternate" hreflang="de-DE" href="PLACEHOLDER/de.html">
<link rel="alternate" hreflang="xx-YY" href="PLACEHOLDER/xx.html">
</head><body><h1>Intl</h1><p>No self-reference, no x-default, mixed protocol.</p>
</body></html>"""

INTL_GOOD = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Intl</title><link rel="canonical" href="PLACEHOLDER/intl.html">
<link rel="alternate" hreflang="en" href="PLACEHOLDER/intl.html">
<link rel="alternate" hreflang="de" href="PLACEHOLDER/de.html">
<link rel="alternate" hreflang="x-default" href="PLACEHOLDER/intl.html">
</head><body><h1>Intl</h1><p>Self-referencing, x-default present, one protocol.</p>
</body></html>"""

FAQ_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Questions</title><link rel="canonical" href="PLACEHOLDER/faq.html">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"FAQPage",
"mainEntity":[{"@type":"Question","name":"How often do you feed a starter?",
"acceptedAnswer":{"@type":"Answer","text":"Once a day at room temperature."}}]}</script>
</head><body><h1>Questions</h1>
<h2>How often do you feed a starter?</h2>
<p>Once a day if the jar sits at room temperature, and once a week if it lives in the
refrigerator. The interval matters more than the quantity: a starter fed on a schedule
rises predictably, and a predictable rise is the only reason to keep one rather than
opening a packet of yeast.</p>
<h2>What is a levain?</h2>
<p>A levain is a portion of starter built specifically for one bake, usually mixed the
night before. It lets you keep a small culture in the refrigerator and still produce
enough leaven for a large dough, and it means an error in the levain costs you one
loaf rather than the whole culture.</p>
<h2>Why does my loaf spread instead of rising?</h2>
<p>Almost always one of two things: gluten that was never developed enough to hold a
shape, or a dough left to prove until the structure gave out. Both look identical
coming out of the basket, and the way to tell them apart is to shorten the prove by an
hour and see whether the next loaf holds.</p>
<dl><dt>Levain</dt><dd>A portion of starter built for a single bake.</dd>
<dt>Autolyse</dt><dd>Flour and water rested before salt is added.</dd></dl>
<ol><li>Feed the starter.</li><li>Wait four hours.</li><li>Mix the dough.</li></ol>
</body></html>"""

BROKEN_SCHEMA_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Broken schema</title><link rel="canonical" href="PLACEHOLDER/schema-bad.html">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Product",
"name":"A loaf"}</script>
<script type="application/ld+json">{"@context":"https://schema.org",
"@type":"BreadcrumbList"}</script>
<script type="application/ld+json">{not valid json at all</script>
</head><body><h1>Broken schema</h1><p>Product with no offers, breadcrumb with no
items, and one block that is not JSON.</p></body></html>"""

VIDEO_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Video</title><link rel="canonical" href="PLACEHOLDER/video.html">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"VideoObject",
"name":"Shaping a boule","description":"How to shape a round loaf.",
"thumbnailUrl":"PLACEHOLDER/i/a.webp","uploadDate":"2026-07-01","duration":"PT4M30S",
"contentUrl":"PLACEHOLDER/v/shape.mp4"}</script>
</head><body><h1>Video</h1>
<iframe src="https://www.youtube.com/embed/xyz" title="Shaping a boule"></iframe>
</body></html>"""

def page(slug: str, title: str, heading: str, body: str) -> str:
    """A page in the good site's shape, with its own content.

    Distinct bodies are load-bearing rather than tidy: serving one document at four
    paths makes them exact duplicates, and `duplicate_content.py` is right to say so —
    the first version of this file did exactly that and read four correct `Critical`
    duplicate findings as a bug in the script.
    """
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{title}</title>
<meta name="description" content="{heading} — Fixture Bakery, Vilnius.">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="canonical" href="PLACEHOLDER/{slug}">
<link rel="stylesheet" href="/s.min.css">
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"Article",
"headline":"{title}","datePublished":"2026-06-02","dateModified":"2026-07-19",
"author":{{"@type":"Person","name":"A Baker","url":"PLACEHOLDER/about.html"}},
"publisher":{{"@type":"Organization","name":"Fixture Bakery","url":"PLACEHOLDER/"}},
"mainEntityOfPage":{{"@type":"WebPage","@id":"PLACEHOLDER/{slug}"}}}}</script>
</head><body>
<header><nav><a href="/">Starter care</a> <a href="/about.html">Who we are</a>
<a href="/guide.html">Baking guide</a> <a href="/privacy.html">Privacy</a></nav></header>
<main><h1>{heading}</h1>
{body}
</main>
<footer><p>Fixture Bakery, 1 Fixture Street, Vilnius, Lithuania. Telephone
+370 600 00000. <a href="/privacy.html">Privacy policy</a></p></footer>
</body></html>"""


ABOUT_PAGE = page(
    "about.html", "About Fixture Bakery and who writes these guides",
    "About the bakery",
    """<p>Fixture Bakery has been open since 2019 on Fixture Street in Vilnius. We bake
four kinds of sourdough, and everything on this site is written by the people who do
the baking rather than by an agency. This page exists so a reader can tell who is
making a claim before deciding whether to trust it.</p>
<h2>Who writes here</h2>
<p>A Baker keeps the culture, runs the ovens six mornings a week, and writes the
guides. Before the bakery there were eleven years in restaurant kitchens, four of
them in bread specifically. Nothing here is theoretical: every timing published on
this site is one we work to, and when a timing changes we change the page and note
the date at the top of it.</p>
<h2>How we test what we publish</h2>
<p>A method reaches this site after we have used it for at least two months in
production. Flour behaves differently between harvests, so a schedule that worked one
autumn may need adjusting the next, and we would rather publish a range than a false
precision. Where a claim depends on temperature we give the temperature. Where it
depends on a specific flour we name the flour.</p>
<h2>Corrections</h2>
<p>If something here is wrong, write to the address in the footer and we will correct
the page and say what changed. Two corrections have been made this year: a
hydration figure that was quoted for a different flour, and a proofing time that
assumed a warmer kitchen than most people have. Both are noted on the pages
themselves.</p>
<h2>Where to find us</h2>
<p>The shop is at 1 Fixture Street, Vilnius, open from seven in the morning until the
bread runs out, which in practice means early afternoon. The telephone number in the
footer reaches the counter rather than a call centre.</p>""")

GUIDE_PAGE = page(
    "guide.html", "A baking guide: mixing, folding, shaping and scoring",
    "Baking guide",
    """<p>This guide covers the four things that decide whether a loaf works: how the
dough is mixed, how it is folded, how it is shaped and how it is scored. It assumes
you already have an active starter — feeding one is covered on the starter care
page.</p>
<h2>Mixing</h2>
<p>Mix flour and water first and leave them for forty minutes before adding salt or
levain. The rest lets the flour hydrate fully, which makes the dough easier to handle
and shortens the kneading you will need afterwards. Weigh everything. Volume
measurement of flour varies by a fifth depending on how the cup was filled, and a
fifth is the difference between a slack dough and a stiff one.</p>
<h2>Folding</h2>
<p>Fold every forty minutes for the first two hours, then leave the dough alone.
Folding builds structure without tearing the gluten the way sustained kneading can,
and the interval matters more than the technique: dough that is folded on a schedule
develops predictably, and predictability is what lets you plan a bake around the
rest of your day.</p>
<h2>Shaping</h2>
<p>Shape in two stages with a twenty-minute rest between them. The first stage
gathers the dough into a rough round and the second tightens it. Attempting both at
once tears the surface, and a torn surface spreads in the oven however carefully it
was proofed.</p>
<h2>Scoring</h2>
<p>Score once, deeply, just before the loaf goes in. A single confident cut opens
better than several shallow ones, and a blade held at an angle produces the ear that
people associate with a good bake. None of this affects the taste.</p>""")

PRIVACY_PAGE = page(
    "privacy.html", "Privacy policy: what this site collects and why",
    "Privacy policy",
    """<p>This page explains what data this site collects, why it collects it, how long
it is kept and how to ask for it to be deleted. It was last reviewed on 19 July 2026.
If anything here is unclear, the address in the footer reaches a person.</p>
<h2>What we collect</h2>
<p>The web server keeps an access log containing the requested page, the time, the
browser's user agent and a truncated IP address. The log exists to find broken pages
and to tell a search engine crawler from a visitor. It is kept for thirty days and
then deleted automatically.</p>
<h2>Cookies</h2>
<p>This site sets no cookies of its own and loads no analytics or advertising
scripts, so there is nothing to consent to and no banner asking you to. If that
changes, this page will change first and the date above will move.</p>
<h2>Ordering bread</h2>
<p>Orders taken by telephone are written on paper at the counter and thrown away
once the order has been collected. We do not keep a customer list and we do not send
marketing of any kind, because we bake a fixed amount each morning and it sells.</p>
<h2>Your rights</h2>
<p>Under the GDPR you can ask what we hold about you, ask for it to be corrected, or
ask for it to be deleted. Given the above the answer is usually that we hold
nothing, but ask and we will check the access log for the period you name and tell
you what is in it. Requests are answered within a week.</p>
<h2>Data protection contact</h2>
<p>Write to the address in the footer, marked for the attention of the data
protection contact, who is the same person who does the baking.</p>""")

# Every anchor identical and pointing at one target, which is what BL-081 counts.
# Neither of the two main pages can carry this: varied navigation is what a good site
# has, and the bad page's links are varied for other reasons.
SPAMMY_ANCHORS = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Links</title><link rel="canonical" href="PLACEHOLDER/spammy.html"></head><body>
<h1>Links</h1>
<p>Buy <a href="/shop.html">cheap sourdough bread</a> today.</p>
<p>We sell <a href="/shop.html">cheap sourdough bread</a> daily.</p>
<p>Order <a href="/shop.html">cheap sourdough bread</a> online.</p>
<p>Try our <a href="/shop.html">cheap sourdough bread</a> now.</p>
<p>More <a href="/shop.html">cheap sourdough bread</a> here.</p>
</body></html>"""

# The hero image lazy-loaded, which delays the largest paint by a round trip. CN-054
# reads `summary.lazy_lcp_candidates`, and a page has to have exactly this shape for
# the count to be anything but zero.
LAZY_HERO = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Lazy hero</title><link rel="canonical" href="PLACEHOLDER/lazy.html"></head><body>
<h1>Lazy hero</h1>
<img src="/i/a.png" alt="A round sourdough loaf" width="800" height="400" loading="lazy">
<p>The first and largest image on the page, told to wait.</p></body></html>"""

CSS_MIN = "body{color:#222}h1{font-size:2rem}a{color:#06c}"
CSS_FAT = "\n".join(f"  .rule-{n} {{ color : #222222 ;  margin : 0 auto ; }} "
                    f"/* rule number {n}, with a comment nobody needed */"
                    for n in range(120))

SITEMAP_GOOD = ('<?xml version="1.0" encoding="UTF-8"?>'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                '<url><loc>PLACEHOLDER/</loc><lastmod>2026-07-20</lastmod></url>'
                '<url><loc>PLACEHOLDER/about.html</loc><lastmod>2026-07-18</lastmod></url>'
                '<url><loc>PLACEHOLDER/guide.html</loc><lastmod>2026-07-11</lastmod></url>'
                '</urlset>')

SITEMAP_BAD = ('<?xml version="1.0" encoding="UTF-8"?>'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
               '<url><loc>PLACEHOLDER/</loc></url>'
               '<url><loc>PLACEHOLDER/gone</loc></url>'
               '<url><loc>PLACEHOLDER/also-gone</loc></url>'
               '<url><loc>PLACEHOLDER/unlinked-a.html</loc></url>'
               '<url><loc>PLACEHOLDER/unlinked-b.html</loc></url>'
               '<url><loc>http://insecure.invalid/x</loc></url>'
               '</urlset>')

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 900
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\0" * 600

TEXT = {"Content-Type": "text/plain; charset=utf-8"}
XML = {"Content-Type": "application/xml"}
CSS = {"Content-Type": "text/css"}
JS = {"Content-Type": "application/javascript"}

GOOD_ROUTES = {
    "/": GOOD_PAGE,
    "/about.html": ABOUT_PAGE,
    "/guide.html": GUIDE_PAGE,
    "/privacy.html": PRIVACY_PAGE,
    "/intl.html": INTL_GOOD,
    "/intl-broken.html": INTL_BROKEN,
    "/de.html": INTL_GOOD,
    "/xx.html": INTL_GOOD,
    "/faq.html": FAQ_PAGE,
    "/schema-bad.html": BROKEN_SCHEMA_PAGE,
    "/video.html": VIDEO_PAGE,
    "/thin.html": BAD_PAGE,
    "/spammy.html": SPAMMY_ANCHORS,
    "/lazy.html": LAZY_HERO,
    "/shop.html": ABOUT_PAGE,
    "/robots.txt": (200, TEXT, "User-agent: *\nAllow: /\nDisallow: /private/\n"
                               "User-agent: GPTBot\nAllow: /\n"
                               "Sitemap: PLACEHOLDER/sitemap.xml\n"),
    "/a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6.txt": (200, TEXT, "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"),
    "/llms.txt": (200, TEXT, "# Fixture Bakery\n\n> Sourdough guides and recipes.\n\n"
                             "## Guides\n- [Starter care](PLACEHOLDER/): feeding and "
                             "reviving a starter\n- [About](PLACEHOLDER/about.html): "
                             "who writes this\n\n## Optional\n"
                             "- [Privacy](PLACEHOLDER/privacy.html): the policy\n"),
    "/sitemap.xml": (200, XML, SITEMAP_GOOD),
    "/s.min.css": (200, CSS, CSS_MIN),
    "/s.css": (200, CSS, CSS_FAT),
    "/s.js": (200, JS, "console.log(1);"),
    "/i/a.png": (200, {"Content-Type": "image/png"}, PNG),
    "/i/a.webp": (200, {"Content-Type": "image/webp"}, WEBP),
    "/i/logo.png": (200, {"Content-Type": "image/png"}, PNG),
    "/favicon.ico": (200, {"Content-Type": "image/x-icon"}, b"\0" * 40),
    # Redirects, which a static file server cannot express and three items need.
    "/hop1": (301, {"Location": "PLACEHOLDER/hop2"}, ""),
    "/hop2": (302, {"Location": "PLACEHOLDER/hop3"}, ""),
    "/hop3": (301, {"Location": "PLACEHOLDER/"}, ""),
    "/loop1": (301, {"Location": "PLACEHOLDER/loop2"}, ""),
    "/loop2": (301, {"Location": "PLACEHOLDER/loop1"}, ""),
}

# No robots.txt, no llms.txt, a sitemap full of problems, and the bad page at the
# root. Origin-level absence is only expressible as a second origin.
BAD_ROUTES = {
    "/": BAD_PAGE,
    "/shop": BAD_PAGE,
    "/thin-indexable.html": ("<!doctype html><html lang=en><head>"
                             "<title>Stub</title></head><body><h1>Stub</h1>"
                             "<p>Twenty words of nothing much, published "
                             "with no thought and no reason for anyone to "
                             "read it at all.</p></body></html>"),
    "/unlinked-a.html": BAD_PAGE,
    "/unlinked-b.html": BAD_PAGE,
    "/i/a.png": (200, {"Content-Type": "image/png"}, PNG),
    "/s.css": (200, CSS, CSS_FAT),
    "/s.js": (200, JS, "console.log(1);"),
    "/sitemap.xml": (200, XML, SITEMAP_BAD),
}


# ---------------------------------------------------------------------------
# Running them
# ---------------------------------------------------------------------------

GOOD = BAD = None
OUT: dict = {}

# (key, script, argv template). `{good}` and `{bad}` are the two origins' roots.
# One entry per (script, page) pair the assertions below need — each runs once.
RUNS = [
    ("a11y", "a11y_seo_checker.py", ["{good}"]),
    ("a11y_bad", "a11y_seo_checker.py", ["{bad}"]),
    ("aicrawl", "ai_crawler_policy_matrix.py", ["{good}"]),
    ("aicrawl_bad", "ai_crawler_policy_matrix.py", ["{bad}"]),
    ("anchor", "anchor_text_audit.py", ["{good}"]),
    ("anchor_spam", "anchor_text_audit.py", ["{good}spammy.html"]),
    ("answers", "answer_block_scanner.py", ["{good}faq.html"]),
    ("answers_bad", "answer_block_scanner.py", ["{bad}"]),
    ("article", "article_seo.py", ["{good}", "--no-autocomplete"]),
    ("article_bad", "article_seo.py", ["{bad}", "--no-autocomplete"]),
    ("broken", "broken_links.py", ["{good}"]),
    ("broken_bad", "broken_links.py", ["{bad}"]),
    ("cache", "cache_compression_checker.py", ["{good}"]),
    ("citation", "citation_readiness.py", ["{good}"]),
    ("citation_bad", "citation_readiness.py", ["{bad}"]),
    ("collection", "collection_page_checker.py", ["{good}"]),
    ("collection_bad", "collection_page_checker.py", ["{bad}"]),
    ("chain", "critical_request_chain.py", ["{good}"]),
    ("cssmin", "css_minify_check.py", ["{good}"]),
    ("cssmin_bad", "css_minify_check.py", ["{bad}"]),
    ("dupes", "duplicate_content.py", ["{good}"]),
    ("dupes_bad", "duplicate_content.py", ["{bad}"]),
    ("eeat", "eeat_signal_checker.py", ["{good}"]),
    ("eeat_bad", "eeat_signal_checker.py", ["{bad}"]),
    ("entity", "entity_checker.py", ["{good}"]),
    ("extlinks", "external_link_quality.py", ["{good}"]),
    ("extlinks_bad", "external_link_quality.py", ["{bad}"]),
    ("facets", "faceted_nav_audit.py", ["{good}", "--from-page"]),
    ("facets_bad", "faceted_nav_audit.py", ["{bad}", "--from-page"]),
    ("fonts", "font_audit.py", ["{good}"]),
    ("fresh", "freshness_checker.py", ["{good}"]),
    ("fresh_bad", "freshness_checker.py", ["{bad}"]),
    ("ga4", "ga4_tag_checker.py", ["{good}"]),
    ("ga4_bad", "ga4_tag_checker.py", ["{bad}"]),
    ("hreflang", "hreflang_checker.py", ["{good}intl.html"]),
    ("hreflang_bad", "hreflang_checker.py", ["{good}intl-broken.html"]),
    ("hreflang_none", "hreflang_checker.py", ["{good}"]),
    ("images", "image_inventory.py", ["{good}"]),
    ("images_bad", "image_inventory.py", ["{bad}"]),
    ("images_lazy", "image_inventory.py", ["{good}lazy.html"]),
    ("intlinks", "internal_links.py", ["{good}"]),
    ("orphans", "orphan_pages_from_sitemap.py", ["{good}"]),
    ("orphans_bad", "orphan_pages_from_sitemap.py", ["{bad}"]),
    ("crawl", "site_crawl.py", ["{good}"]),
    ("crawl_bad", "site_crawl.py", ["{bad}"]),
    ("jsrender", "javascript_render_audit.py", ["{good}"]),
    ("jsrender_bad", "javascript_render_audit.py", ["{bad}"]),
    ("lcp", "lcp_subparts.py", ["{good}"]),
    ("profile", "link_profile.py", ["{good}"]),
    ("profile_bad", "link_profile.py", ["{bad}"]),
    ("indexnow", "indexnow_checker.py", ["{good}", "--key", "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"]),
    ("indexnow_bad", "indexnow_checker.py", ["{bad}", "--key", "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"]),
    ("llms", "llms_txt_checker.py", ["{good}"]),
    ("llms_bad", "llms_txt_checker.py", ["{bad}"]),
    ("mobile", "mobile_render_checker.py", ["{good}"]),
    ("mobile_bad", "mobile_render_checker.py", ["{bad}"]),
    ("redirect", "redirect_checker.py", ["{good}"]),
    ("redirect_hops", "redirect_checker.py", ["{good}hop1"]),
    ("redirect_loop", "redirect_checker.py", ["{good}loop1"]),
    ("rich", "rich_results_guard.py", ["{good}"]),
    ("rich_bad", "rich_results_guard.py", ["{good}schema-bad.html"]),
    ("robots", "robots_checker.py", ["{good}"]),
    ("robots_bad", "robots_checker.py", ["{bad}"]),
    ("props", "schema_required_props.py", ["{good}faq.html"]),
    ("props_bad", "schema_required_props.py", ["{good}schema-bad.html"]),
    ("sitemap", "sitemap_checker.py", ["{good}"]),
    ("sitemap_bad", "sitemap_checker.py", ["{bad}"]),
    ("sitemap_urls", "sitemap_checker.py", ["{good}", "--fetch-urls", "--max-urls", "25"]),
    ("sitemap_urls_bad", "sitemap_checker.py", ["{bad}", "--fetch-urls", "--max-urls", "25"]),
    ("social", "social_meta.py", ["{good}"]),
    ("social_bad", "social_meta.py", ["{bad}"]),
    ("thirdparty", "third_party_script_audit.py", ["{good}"]),
    ("thirdparty_bad", "third_party_script_audit.py", ["{bad}"]),
    ("clusters", "topical_cluster_mapper.py", ["{good}"]),
    ("urls", "url_quality.py", ["{good}"]),
    ("urls_bad", "url_quality.py", ["{bad}shop?utm_source=a&SESSIONID=1&color=red&size=xl&sort=price"]),
    ("video", "video_schema_checker.py", ["{good}video.html"]),
    ("video_bad", "video_schema_checker.py", ["{good}"]),
    # `server_log_audit.py` reads files and makes no request, so these are the only
    # runs here with no origin in them. `{logs}` and `{artifacts}` are directories in
    # the checkout rather than temp copies: the logs carry fixed dates, because the
    # script refuses to report never-crawled URLs from a window under a week, and a
    # fixture generated relative to today would make that refusal fire or not
    # depending on which day the suite ran.
    ("log_good", "server_log_audit.py", ["{artifacts}good/access.log"]),
    ("log_waste", "server_log_audit.py", ["{artifacts}broken/access.log"]),
    ("log_common", "server_log_audit.py", ["{logs}common.log"]),
    ("log_json", "server_log_audit.py", ["{logs}nginx-json.log"]),
    ("log_gz", "server_log_audit.py", ["{logs}rotated.log.gz"]),
    ("log_junk", "server_log_audit.py", ["{logs}unparsable.log"]),
    ("log_absent", "server_log_audit.py", ["{logs}no-such-file.log"]),
]


def script_env() -> dict:
    """Loopback permitted, pacing off, every credential cleared.

    The credentials matter: a developer machine with a Search Console key must not
    make these tests do something a CI runner cannot, and a Safe Browsing key would
    turn an offline test into a paid API call.
    """
    env = dict(os.environ)
    env.update({"SEO_ALLOW_PRIVATE": "1", "SEO_MAX_RPS": "0", "PYTHONPATH": SCRIPTS})
    for key in ("GSC_CREDENTIALS_PATH", "GV_SA_KEY", "GOOGLE_SAFE_BROWSING_KEY",
                "PAGESPEED_API_KEY", "INDEXNOW_KEY"):
        env.pop(key, None)
    return env


def setUpModule():
    global GOOD, BAD
    GOOD, BAD = served(GOOD_ROUTES), served(BAD_ROUTES)
    for site in (GOOD, BAD):
        # `PLACEHOLDER_HOST` first: it is a substring of nothing, but the full
        # placeholder contains the scheme, so rewriting that one first would leave
        # `http://http://127.0.0.1:PORT/...` behind.
        site.rewrite("PLACEHOLDER_HOST", site.base.split("//", 1)[1])
        site.rewrite(PLACEHOLDER)
    env = script_env()

    def run(spec):
        key, script, template = spec
        fixtures = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "fixtures")
        argv = [a.replace("{good}", GOOD.url).replace("{bad}", BAD.url)
                .replace("{logs}", os.path.join(fixtures, "logs") + os.sep)
                .replace("{artifacts}", os.path.join(fixtures, "artifacts") + os.sep)
                for a in template]
        # `cwd` is deliberately not passed: it would put the child back on CPython's
        # `fork` path, which macOS kills outright once Network.framework has been
        # initialised in this process. See `harness.spawn`. Both paths below are
        # absolute, so nothing needed the working directory anyway.
        proc = harness.spawn(
            [sys.executable, os.path.join(SCRIPTS, script)] + argv + ["--json"],
            env=env, timeout=180)
        # A non-zero exit carrying JSON is an answer, not a crash. With `--json`
        # these scripts put a refusal in the payload and still exit 1 so a shell
        # notices, and treating that as a failure would hide exactly the cases worth
        # asserting: a log with no User-Agent field, a file that is not a log at all.
        if not proc.stdout.strip():
            return key, {"__failed__": f"exit {proc.returncode}: "
                                       f"{(proc.stderr or '')[-400:]}"}
        try:
            return key, json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            return key, {"__failed__": f"not JSON: {exc}: {proc.stdout[:200]}"}

    with ThreadPoolExecutor(max_workers=8) as pool:
        for key, payload in pool.map(run, RUNS):
            OUT[key] = payload


def tearDownModule():
    for site in (GOOD, BAD):
        if site:
            site.stop()


def out(key: str) -> dict:
    payload = OUT[key]
    if "__failed__" in payload:
        raise AssertionError(f"{key}: {payload['__failed__']}")
    return payload


class EveryScriptRan(unittest.TestCase):
    """Before any verdict is asserted: did the scripts run at all?

    A script that exits non-zero produces `{}` from the runner's point of view, and an
    empty dict satisfies a surprising number of assertions — that combination once
    scored a host that does not resolve at 61/100. If this test fails, every failure
    below it is noise.
    """

    def test_no_script_crashed_or_returned_unusable_output(self):
        failed = {k: v["__failed__"] for k, v in OUT.items() if "__failed__" in v}
        self.assertEqual(failed, {}, "\n".join(f"  {k}: {v}"
                                               for k, v in failed.items()))

    def test_every_run_is_asserted_on_somewhere_in_this_file(self):
        """An unused run is a script nobody checked, hiding behind a green suite."""
        with open(os.path.abspath(__file__), encoding="utf-8") as f:
            source = f.read()
        unused = [key for key, _, _ in RUNS
                  if source.count(f'"{key}"') < 2]
        self.assertEqual(unused, [], f"runs nothing asserts on: {unused}")


class ServerLogs(unittest.TestCase):
    """CI-018, the one item no request could ever answer.

    Its evidence is in the past, so the tests that matter here are not about
    arithmetic. They are about the four ways this script could report a confident
    number about nothing: a log that records no crawler, a window too short for
    absence to mean anything, a file that is not a log, and a `304` counted as waste.
    """

    def test_a_clean_crawl_produces_no_findings(self):
        """The good fixture's log: every sitemap URL fetched, then revalidated.
        Nothing here should be reported, or the item accuses every healthy site."""
        d = out("log_good")
        self.assertEqual(d["error"], None)
        self.assertEqual([i for i in d["issues"]
                          if i["severity"] in ("high", "medium")], [])

    def test_revalidation_is_not_waste(self):
        """A `304` is the cheapest exchange there is: the crawler kept its copy and
        the server sent no body. Counting it against the site would penalise exactly
        what `cache_compression_checker.py` asks for two items away."""
        d = out("log_good")
        self.assertGreater(d["summary"]["not_modified_requests"], 0,
                           "the fixture stopped exercising 304s")
        self.assertEqual(d["summary"]["wasted_requests"], 0)
        self.assertEqual(d["summary"]["wasted_pct"], 0.0)

    def test_a_wasted_crawl_budget_is_reported_as_high(self):
        d = out("log_waste")
        types = {i["type"]: i["severity"] for i in d["issues"]}
        self.assertEqual(types.get("crawl_budget_wasted"), "high", types)
        self.assertEqual(types.get("server_errors_to_crawlers"), "high", types)
        self.assertIn("parameter_crawl", types)
        self.assertGreater(d["summary"]["wasted_pct"], 20)
        # And it says which URLs, because "44% wasted" is not an action.
        self.assertTrue(d["top_wasted"])
        self.assertTrue(all(row["status"] >= 400 for row in d["top_wasted"]))

    def test_ai_crawlers_are_counted_apart_from_crawl_budget(self):
        """An AI crawler pulling pages is not Google's crawl budget, and folding the
        two together would put two claims in one number."""
        d = out("log_waste")
        self.assertGreater(d["summary"]["ai_bot_requests"], 0)
        self.assertIn("GPTBot", d["bots"])
        self.assertEqual(d["bots"]["GPTBot"]["kind"], "ai")
        self.assertEqual(d["bots"]["Googlebot"]["kind"], "search")
        self.assertNotIn("GPTBot", [k for k, v in d["bots"].items()
                                    if v["kind"] == "search"])

    def test_a_log_with_no_user_agent_refuses_to_answer(self):
        """Common Log Format records no User-Agent, so every question here is
        unanswerable. "No crawler visited" and "this file cannot say which crawlers
        visited" are opposite findings, and reporting the second as the first is the
        one thing this tool exists to refuse."""
        d = out("log_common")
        self.assertIs(d["user_agent_recorded"], False)
        self.assertEqual(d["format"], "common")
        self.assertIn("no User-Agent", d["error"])
        # No zeros left lying around for a rule to read as a pass.
        self.assertEqual(d["summary"], {})
        self.assertEqual(d["bots"], {})

    def test_json_lines_are_read_with_nginx_key_names(self):
        d = out("log_json")
        self.assertEqual(d["format"], "json")
        self.assertEqual(d["error"], None)
        self.assertEqual(d["summary"]["search_bot_requests"], 63)
        # 1 July to 21 July is a 20-day span, not 21 days of entries.
        self.assertEqual(d["window"]["days"], 20)

    def test_a_rotated_log_reads_the_same_as_a_plain_one(self):
        """Not merely that gzip did not crash: the same bytes must give the same
        answer, because a log worth analysing has usually been rotated."""
        plain, rotated = out("log_good"), out("log_gz")
        for field in ("lines_parsed", "search", "by_status_class"):
            self.assertEqual(rotated[field], plain[field], field)
        self.assertEqual(rotated["summary"]["search_bot_requests"],
                         plain["summary"]["search_bot_requests"])

    def test_a_file_that_is_not_a_log_says_so(self):
        d = out("log_junk")
        self.assertIn("parsed as an access log", d["error"])
        self.assertEqual(d["summary"], {})

    def test_a_missing_file_says_so(self):
        d = out("log_absent")
        self.assertIn("no such log file", d["error"])

    def test_coverage_findings_need_an_inventory_and_are_absent_without_one(self):
        """`None`, not `[]`. An empty list reads as "we looked and found none", and
        these two questions cannot be asked of a log alone at all."""
        d = out("log_good")
        self.assertIsNone(d["never_crawled"])
        self.assertIsNone(d["crawled_not_offered"])

    def test_the_user_agent_is_reported_as_a_claim(self):
        """It is a lookup table over a string the client chose. Anything that reads
        this output has to know that, so the caveat is a field rather than a comment
        in the source."""
        self.assertIn("not verified", out("log_good")["bot_identity"])

    def test_no_robots_only_token_is_treated_as_a_user_agent(self):
        """`Google-Extended` and `Applebot-Extended` are robots.txt tokens that
        nothing ever sends. Matching them would define a crawler that cannot appear
        and then report zero visits from it forever."""
        import server_log_audit as sla
        for token in sla.NOT_USER_AGENTS:
            self.assertNotIn(token, sla.AI_BOTS)
            self.assertNotIn(token, sla.SEARCH_BOTS)
            # `applebot-extended` contains `applebot`, so substring matching read it as
            # Apple's search crawler and therefore search crawl budget. What matters
            # is not which bucket it lands in but that it is neither of the two that
            # decide anything.
            self.assertNotIn(sla.classify_agent(token)[0], ("search", "ai"),
                             f"{token} is counted as a real crawler")


class CrawlerAddressesAreConfirmed(unittest.TestCase):
    """CI-018's `bot_identity`, and the reason `--verify-bots` exists.

    Classification is a lookup over a string the client chose, so a scraper announcing
    itself as Googlebot was counted as Googlebot — and the direction of that error was
    always towards *over*-reporting the crawl, because nobody forges a User-Agent to
    look less important. Every test here hands in a resolver, so the suite stays
    offline: the whole feature is one network call, and the seam that lets it be tested
    is what makes adding it acceptable at all.
    """

    REAL = "66.249.66.1"
    FAKE = "203.0.113.9"

    UA = ("Mozilla/5.0 (compatible; Googlebot/2.1; "
          "+http://www.google.com/bot.html)")

    def _log(self) -> str:
        """Three requests from Google's address, five 404s from somewhere else — both
        announcing themselves as Googlebot. Built in a method rather than a class
        attribute because a comprehension in a class body cannot see the class's own
        names."""
        rows = [f'{self.REAL} - - [01/Jul/2026:00:0{i}:00 +0000] "GET /p{i} HTTP/1.1" '
                f'200 12 "-" "{self.UA}"' for i in range(3)]
        rows += [f'{self.FAKE} - - [01/Jul/2026:01:0{i}:00 +0000] "GET /admin{i} '
                 f'HTTP/1.1" 404 9 "-" "{self.UA}"' for i in range(5)]
        return "\n".join(rows) + "\n"

    class Resolver:
        """Reverse and forward answers written down, plus a record of the questions
        asked — so a test can assert that one address costs one lookup."""

        def __init__(self, reverse_map, forward_map=None, fail=()):
            self.reverse_map, self.fail = reverse_map, set(fail)
            self.forward_map = forward_map or {}
            self.asked = []

        def reverse(self, ip):
            self.asked.append(ip)
            if ip in self.fail:
                raise OSError("no PTR record")
            return self.reverse_map[ip]

        def forward(self, host):
            return self.forward_map.get(host, [])

    def _audit(self, resolver, budget=64):
        import tempfile

        import server_log_audit as sla
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as fh:
            fh.write(self._log())
            path = fh.name
        try:
            return sla.audit(path, checker=sla.AddressCheck(resolver, budget))
        finally:
            os.unlink(path)

    def _both_ways(self):
        return self.Resolver(
            {self.REAL: "crawl-66-249-66-1.googlebot.com",
             self.FAKE: "host9.cheap-vps.example.com"},
            {"crawl-66-249-66-1.googlebot.com": [self.REAL]})

    def test_a_forged_googlebot_leaves_the_crawl_budget_figures(self):
        """The finding underneath the feature. Five 404s from an address that is not
        Google used to be five 404s of Google's crawl budget wasted — the exact number
        the item reports, inflated by whoever pointed a scraper at the site."""
        result = self._audit(self._both_ways())
        self.assertEqual(result["address_checks"]["Googlebot"],
                         {"verified": 3, "forged": 5})
        self.assertEqual(result["bots"]["Googlebot"]["requests"], 3)
        self.assertEqual(
            result["bots"]["Googlebot (address not confirmed)"]["kind"], "other")
        self.assertEqual(result["summary"]["search_bot_requests"], 3)
        self.assertIn("forged_crawler", [i.get("type") for i in result["issues"]])

    def test_a_reverse_lookup_alone_is_not_enough(self):
        """The half of the rule that is easy to skip and does the work. A PTR record is
        controlled by whoever owns the address, so anyone with a rented block can name
        it `crawl-….googlebot.com`. Only the forward zone is Google's, so a name that
        does not resolve back to the address is forged."""
        lying = self.Resolver(
            {self.REAL: "crawl-66-249-66-1.googlebot.com",
             self.FAKE: "crawl-203-0-113-9.googlebot.com"},        # says the words
            {"crawl-66-249-66-1.googlebot.com": [self.REAL],
             "crawl-203-0-113-9.googlebot.com": ["8.8.8.8"]})      # resolves elsewhere
        result = self._audit(lying)
        self.assertEqual(result["address_checks"]["Googlebot"],
                         {"verified": 3, "forged": 5})

    def test_a_hostname_that_merely_ends_in_the_domain_is_forged(self):
        """`notgooglebot.com` ends with the string "googlebot.com". The suffix has to
        match on a label boundary — the same class of bug as the robots.txt token that
        was read as Apple's crawler by substring."""
        import server_log_audit as sla
        check = sla.AddressCheck(self.Resolver(
            {self.FAKE: "www.notgooglebot.com"},
            {"www.notgooglebot.com": [self.FAKE]}))
        self.assertEqual(check.status("Googlebot", self.FAKE), "forged")

    def test_a_resolver_that_is_down_does_not_make_every_crawler_an_impostor(self):
        """The failure this feature could easily have introduced. Reading "DNS did not
        answer" as "not Googlebot" would turn one outage on the auditing machine into a
        report telling a client their whole crawl is fraudulent — the same shape as a
        busy W3C validator becoming "your HTML has errors"."""
        result = self._audit(self.Resolver({}, fail=(self.REAL, self.FAKE)))
        self.assertEqual(result["address_checks"]["Googlebot"], {"unresolved": 8})
        self.assertEqual(result["bots"]["Googlebot"]["requests"], 8)
        self.assertNotIn("forged_crawler", [i.get("type") for i in result["issues"]])

    def test_one_address_costs_one_lookup_however_many_requests_it_made(self):
        """Eight requests, two addresses, two questions. A log is millions of lines and
        a crawler reuses its addresses; asking DNS per line would be the fan-out the
        response cache and the shared crawl exist to remove."""
        resolver = self._both_ways()
        self._audit(resolver)
        self.assertEqual(sorted(resolver.asked), sorted([self.REAL, self.FAKE]))

    def test_beyond_the_budget_an_address_is_unchecked_and_not_assumed(self):
        """A bounded feature has to say where it stopped. `not_checked` is handled like
        `unresolved`: the requests stay attributed to the crawler that claimed them,
        because a budget running out is not evidence about anybody."""
        result = self._audit(self._both_ways(), budget=1)
        self.assertEqual(result["address_checks"]["Googlebot"],
                         {"verified": 3, "not_checked": 5})
        self.assertEqual(result["bots"]["Googlebot"]["requests"], 8)

    def test_a_crawler_with_no_published_rule_is_left_as_a_claim(self):
        """DuckDuckBot, SeznamBot and PetalBot publish address ranges rather than a DNS
        convention. Inventing a rule for them would report every one of their visits as
        forged, which is worse than the claim it replaces."""
        import server_log_audit as sla
        check = sla.AddressCheck(self.Resolver({}))
        for name in ("DuckDuckBot", "SeznamBot", "PetalBot"):
            self.assertNotIn(name, sla.CRAWLER_DOMAINS)
            self.assertEqual(check.status(name, self.FAKE), "no_published_rule")

    def test_nothing_asks_dns_unless_the_operator_asked_for_it(self):
        """The default has to stay a file read, and the audit of the good fixture is
        the one that proves it: no checker, no `address_checks`, and the identity field
        still says the word "claim" out loud."""
        self.assertEqual(out("log_good")["address_checks"], {})
        self.assertIn("not verified", out("log_good")["bot_identity"])


# ---------------------------------------------------------------------------
# Crawling and indexing
# ---------------------------------------------------------------------------

class Robots(unittest.TestCase):
    """AR-151 `status`, AR-152 `user_agents`, CI-006 `sitemaps`."""

    def test_a_present_robots_txt_is_parsed_into_rules_and_a_sitemap(self):
        good = out("robots")
        self.assertEqual(verdict("AR-151", good), PASS)
        self.assertEqual(good["user_agents"]["*"]["disallow"], ["/private/"])
        self.assertEqual(verdict("AR-152", good), PASS)
        self.assertEqual(len(good["sitemaps"]), 1)
        self.assertEqual(verdict("CI-006", good), PASS)

    def test_an_absent_robots_txt_is_a_404_and_no_rules(self):
        """Two origins is what makes this testable at all: robots.txt belongs to an
        origin, so one document root cannot be both present and absent."""
        bad = out("robots_bad")
        self.assertEqual(bad["status"], 404)
        self.assertEqual(verdict("AR-151", bad), FAIL)
        self.assertEqual(bad["user_agents"], {})
        self.assertEqual(verdict("AR-152", bad), FAIL)
        self.assertEqual(verdict("CI-006", bad), FAIL)


class Sitemap(unittest.TestCase):
    """CI-002 `summary.urls`, GO-136 `issues`, GO-138 `issues` (with --fetch-urls)."""

    def test_a_clean_sitemap_reports_its_urls_and_no_serious_issue(self):
        good = out("sitemap")
        self.assertEqual(good["summary"]["urls"], 3)
        self.assertEqual(verdict("CI-002", good), PASS)
        self.assertEqual(verdict("GO-136", good), PASS)

    def test_a_probed_path_that_does_not_exist_is_not_an_issue(self):
        """The bug that made GO-136 and GO-138 fail on every clean site ever audited.

        Discovery tries `/sitemap.xml`, `/sitemap_index.xml` and `/sitemap-index.xml`.
        Those are alternatives, not a set, so a site with one sitemap produced two
        404s — and both were reported as errors. Only the declared one counts.
        """
        good = out("sitemap")
        self.assertEqual([i for i in good["issues"] if "404" in i.get("message", "")], [])
        self.assertGreaterEqual(good["summary"].get("probed_absent", 0), 1)

    def test_a_sitemap_of_dead_and_insecure_urls_is_reported(self):
        bad = out("sitemap_urls_bad")
        self.assertIn(verdict("GO-136", bad), (FAIL, WARN))
        self.assertEqual(verdict("GO-138", bad), FAIL)
        self.assertRegex(json.dumps(bad["issues"]), "(?i)404")

    def test_fetching_a_clean_sitemap_finds_nothing_to_report(self):
        """The other direction for `--fetch-urls`: the flag has to be capable of
        producing a pass, or GO-138 has merely moved from never-failing to
        never-passing."""
        self.assertEqual(verdict("GO-138", out("sitemap_urls")), PASS)

    def test_go_138_needs_the_urls_fetched_to_find_anything(self):
        """It could only ever pass without `--fetch-urls`, which the registry did not
        pass until 0.6.0: 404/redirect/noindex issues are produced by fetching the
        listed URLs, so a run that never fetched them had nothing to match.

        The first assertion below failed once on CI, on 3.10, and passed on a re-run
        of the same commit — 0 failures in 15 local runs of the full suite and of this
        module alone. Reading the script settles what it *cannot* be: every issue
        whose text can match `404|redirect|noindex` is inside the `if fetch_urls`
        branch, and this run does not pass the flag. So the payload is the whole
        question, and guessing at it twice has already cost more than printing it
        once. The message carries the issues verbatim rather than a boolean, because
        a diagnostic that names the wrong cause is worse than no diagnostic — which
        is the standing lesson of 0.15.0."""
        self.assertIn("--fetch-urls", ITEMS["GO-138"]["check"]["args"])
        unfetched = out("sitemap_bad")
        self.assertEqual(verdict("GO-138", unfetched), PASS,
                         "without fetching, the dead URLs are invisible; the issues "
                         "this run actually produced were "
                         + json.dumps(unfetched.get("issues"), ensure_ascii=False))
        self.assertEqual(verdict("GO-138", out("sitemap_urls_bad")), FAIL)


class Redirects(unittest.TestCase):
    """CI-014 `has_loop`, AR-150 `total_hops`.

    A static file server cannot express a redirect, which is why the contract pair
    exempts both items — `served()` can, so this is the only place either is
    exercised against a real 301.
    """

    def test_no_redirect_is_no_hops_and_no_loop(self):
        direct = out("redirect")
        self.assertEqual(direct["total_hops"], 0)
        self.assertEqual(verdict("AR-150", direct), PASS)
        self.assertEqual(verdict("CI-014", direct), PASS)

    def test_a_three_hop_chain_exceeds_the_budget(self):
        hops = out("redirect_hops")
        self.assertEqual(hops["total_hops"], 3)
        self.assertEqual(verdict("AR-150", hops), FAIL)

    def test_a_loop_is_reported_as_a_loop(self):
        loop = out("redirect_loop")
        self.assertIs(loop["has_loop"], True)
        self.assertEqual(verdict("CI-014", loop), WARN)


class UrlQuality(unittest.TestCase):
    """CI-012 `rows.0.score`, AR-147 `rows.0.param_count`, AR-155 `rows.0.flags`."""

    def test_a_clean_root_url_scores_and_carries_no_flags(self):
        good = out("urls")
        for item_id in ("CI-012", "AR-147", "AR-155"):
            self.assertEqual(verdict(item_id, good), PASS, item_id)

    def test_a_url_full_of_tracking_and_session_parameters_fails(self):
        bad = out("urls_bad")
        self.assertGreater(bad["rows"][0]["param_count"], 2)
        self.assertEqual(verdict("AR-147", bad), FAIL)
        self.assertNotEqual(bad["rows"][0]["flags"], [])
        self.assertEqual(verdict("AR-155", bad), FAIL)
        self.assertIn(verdict("CI-012", bad), (FAIL, WARN))


class Indexability(unittest.TestCase):
    """AI crawler alignment, GEO-003 `rows` with a `field`-scoped value map."""

    def test_a_documented_policy_aligns_and_an_undocumented_one_does_not(self):
        self.assertEqual(verdict("GEO-003", out("aicrawl")), PASS)
        self.assertEqual(verdict("GEO-003", out("aicrawl_bad")), FAIL)

    def test_the_verdict_comes_from_the_alignment_field_of_each_row(self):
        """`value_map` with `field` is the operator that replaced matching prose. It
        reads one named key per row, so a row growing a new key cannot change the
        verdict by accident."""
        rows = out("aicrawl")["rows"]
        self.assertTrue(rows)
        self.assertTrue(all("alignment" in row for row in rows))


class LlmsTxt(unittest.TestCase):
    """GEO-001 `exists`, GEO-002 `quality.score`."""

    def test_a_structured_llms_txt_exists_and_scores(self):
        good = out("llms")
        self.assertIs(good["exists"], True)
        self.assertEqual(verdict("GEO-001", good), PASS)
        self.assertGreaterEqual(good["quality"]["score"], 60)
        self.assertEqual(verdict("GEO-002", good), PASS)

    def test_an_absent_llms_txt_is_absent_rather_than_undecided(self):
        """`exists: false` and not a missing key: the difference between "this site
        does not have one" and "we could not tell" is the whole coverage metric."""
        bad = out("llms_bad")
        self.assertIs(bad["exists"], False)
        self.assertEqual(verdict("GEO-001", bad), FAIL)
        self.assertEqual(verdict("GEO-002", bad), FAIL)


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

class DuplicateAndThinContent(unittest.TestCase):
    """MS-022 `exact_duplicates`, MS-029 and CN-041 `summary.exact_duplicate_groups`,
    CN-039 `summary.thin_pages`."""

    def test_four_distinct_pages_are_not_duplicates_of_each_other(self):
        good = out("dupes")
        self.assertEqual(good["exact_duplicates"], [])
        for item_id in ("MS-022", "MS-029", "CN-041"):
            self.assertEqual(verdict(item_id, good), PASS, item_id)

    def test_the_home_page_is_not_its_own_duplicate(self):
        """It was, on every site with a `href="/"` in its navigation — which is every
        site. The trailing slash was stripped unconditionally, so `example.com/` and
        `example.com` were crawled as two URLs, returned identical bytes, and the
        hash comparison reported the home page as **Critical** duplicate content.
        """
        good = out("dupes")
        home = [u for group in good["exact_duplicates"] for u in group.get("urls", [])
                if u.rstrip("/") == GOOD.base]
        self.assertEqual(home, [])

    def test_two_paths_serving_one_document_are_found(self):
        bad = out("dupes_bad")
        self.assertEqual(bad["summary"]["exact_duplicate_groups"], 1)
        for item_id in ("MS-022", "MS-029", "CN-041"):
            self.assertEqual(verdict(item_id, bad), FAIL, item_id)

    def test_an_indexable_thin_page_is_counted(self):
        thin = {p["url"]: p for p in out("dupes_bad").get("thin_content") or []}
        stub = f"{BAD.base}/thin-indexable.html"
        self.assertIn(stub, thin, f"the 20-word page was not called thin: {list(thin)}")
        self.assertLess(thin[stub]["word_count"], thin[stub]["threshold"])
        self.assertIn(verdict("CN-039", out("dupes_bad")), (FAIL, WARN))

    def test_a_noindex_page_is_not_a_thin_content_problem(self):
        """Deliberate, and worth pinning: a page kept out of the index is not
        competing for anything, so asking somebody to write 300 words for it is a fix
        list entry that should not exist."""
        thin = {p["url"] for p in out("dupes_bad").get("thin_content") or []}
        self.assertNotIn(BAD.url, thin)
        self.assertNotIn(f"{BAD.base}/shop", thin)

    def test_a_404_page_is_not_analysed_as_content(self):
        """It was. An error page is HTML, so a site with one dead internal link
        collected a `Critical` thin-content finding telling somebody to expand a page
        that does not exist — and it counted against CN-039. A broken link is
        `broken_links.py`'s finding, and it should be made once.
        """
        analysed = {p["url"] for p in out("dupes_bad").get("thin_content") or []}
        self.assertNotIn(f"{BAD.base}/gone", analysed)


class EeatSignals(unittest.TestCase):
    """CN-040 `signals.privacy_links`, CN-044 `signals.trust_links`,
    CN-057 `signals.authors`, CN-068 `score`."""

    def test_the_three_signal_families_are_found_separately(self):
        """Separately is the point. CN-040 is about a *privacy* policy and used to read
        `policy_links`, which this script fills with editorial policy — fact-checking,
        corrections, ethics. A site with a normal privacy policy failed unless it also
        published editorial standards, and a site with an ethics page and no privacy
        policy passed. The check answered a different question in both directions.
        """
        good = out("eeat")
        self.assertTrue(good["signals"]["privacy_links"])
        self.assertTrue(good["signals"]["trust_links"])
        self.assertTrue(good["signals"]["authors"])
        self.assertIsNot(good["signals"]["privacy_links"],
                         good["signals"].get("policy_links"))
        for item_id in ("CN-040", "CN-044", "CN-057"):
            self.assertEqual(verdict(item_id, good), PASS, item_id)

    def test_a_page_with_no_author_policy_or_contact_fails_all_three(self):
        bad = out("eeat_bad")
        for item_id in ("CN-040", "CN-044", "CN-057"):
            self.assertEqual(verdict(item_id, bad), FAIL, item_id)

    def test_the_score_separates_the_two_pages(self):
        """Asserted as a direction rather than a threshold: CN-068 wants 60 and the
        good fixture reaches 52, because a page cannot earn the rest of the score
        without things a fixture has no business inventing — an author page with a
        real byline history, an organisation with verifiable sameAs targets."""
        self.assertGreater(out("eeat")["score"], out("eeat_bad")["score"] + 30)


class Freshness(unittest.TestCase):
    """CN-038 `score`, CN-056 `dates`."""

    def test_a_dated_article_is_fresh_and_its_dates_are_found(self):
        good = out("fresh")
        self.assertTrue(good["dates"])
        self.assertEqual(verdict("CN-056", good), PASS)
        self.assertEqual(verdict("CN-038", good), PASS)

    def test_a_page_with_no_date_anywhere_reports_no_dates(self):
        bad = out("fresh_bad")
        self.assertEqual(bad["dates"], [])
        self.assertEqual(verdict("CN-056", bad), FAIL)
        self.assertEqual(verdict("CN-038", bad), FAIL)


class AnswerBlocks(unittest.TestCase):
    """GO-144 and GEO-004, both `score`."""

    def test_questions_with_snippet_length_answers_score(self):
        """A "direct answer" is a paragraph of 20 to 70 words immediately after a
        question heading, which is roughly what a featured snippet takes. A page
        answering in eight words scores nothing — correctly, and it is worth knowing
        that is the rule rather than discovering it in a client's report."""
        good = out("answers")
        self.assertTrue(good["direct_answers"])
        self.assertEqual(verdict("GO-144", good), PASS)
        self.assertEqual(verdict("GEO-004", good), PASS)

    def test_a_page_with_no_questions_scores_zero(self):
        bad = out("answers_bad")
        self.assertEqual(bad["score"], 0)
        self.assertEqual(verdict("GEO-004", bad), FAIL)


class CitationReadiness(unittest.TestCase):
    """GO-145 and GEO-005, both `score`."""

    def test_cited_claims_and_named_sources_score(self):
        self.assertEqual(verdict("GO-145", out("citation")), PASS)
        self.assertEqual(verdict("GEO-005", out("citation")), PASS)

    def test_a_page_with_no_sources_or_dates_does_not(self):
        self.assertEqual(verdict("GEO-005", out("citation_bad")), FAIL)


class ArticleKeyword(unittest.TestCase):
    """KW-076 `target_keyword`."""

    def test_a_keyword_is_inferred_from_the_prose(self):
        """`--no-autocomplete` because the script otherwise asks Google for related
        terms, and this suite does not leave loopback."""
        self.assertTrue(out("article")["target_keyword"])
        self.assertEqual(verdict("KW-076", out("article")), PASS)

    def test_a_page_with_almost_no_prose_yields_none(self):
        """The contract pair exempts this item on the grounds that the script "finds
        one on any page with prose". Measured, that holds only for a page with enough
        of it: nineteen words extract nothing."""
        self.assertEqual(out("article_bad")["target_keyword"], "")
        self.assertEqual(verdict("KW-076", out("article_bad")), FAIL)


class TopicalClusters(unittest.TestCase):
    """AR-153 `score`."""

    def test_a_single_topic_site_scores_as_coherent(self):
        self.assertEqual(verdict("AR-153", out("clusters")), PASS)


class CollectionPage(unittest.TestCase):
    """AR-154 `issues`, read by severity rather than by wording."""

    def test_a_page_with_copy_raises_nothing_serious(self):
        self.assertEqual(verdict("AR-154", out("collection")), PASS)

    def test_a_thin_collection_page_warns(self):
        bad = out("collection_bad")
        self.assertEqual(verdict("AR-154", bad), WARN)
        self.assertIn("warning", [i["severity"] for i in bad["issues"]])


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------

class ImageInventory(unittest.TestCase):
    """CI-016 and MD-186 `missing_alt`, CN-054 `summary.lazy_lcp_candidates`,
    MD-184 `count`."""

    def test_images_with_alt_text_pass_both_alt_items(self):
        good = out("images")
        self.assertEqual(good["missing_alt"], 0)
        for item_id in ("CI-016", "MD-186"):
            self.assertEqual(verdict(item_id, good), PASS, item_id)

    def test_a_missing_and_an_empty_alt_are_both_counted(self):
        """`alt=""` is correct for a decorative image and wrong for a content one, and
        this script counts both — which is why the item is `high` rather than
        `critical`: the reader has to look."""
        bad = out("images_bad")
        self.assertEqual(bad["missing_alt"], 2)
        for item_id in ("CI-016", "MD-186"):
            self.assertEqual(verdict(item_id, bad), FAIL, item_id)

    def test_a_lazy_loaded_hero_image_is_the_one_thing_cn_054_looks_for(self):
        self.assertEqual(verdict("CN-054", out("images")), PASS)
        self.assertEqual(out("images_lazy")["summary"]["lazy_lcp_candidates"], 1)
        self.assertEqual(verdict("CN-054", out("images_lazy")), FAIL)

    def test_the_image_count_is_the_count(self):
        self.assertEqual(verdict("MD-184", out("images")), PASS)
        self.assertEqual(out("images_bad")["count"], 2)


class VideoSchema(unittest.TestCase):
    """MD-188, MD-190 and MB-102, all `issues` by severity."""

    def test_a_videoobject_missing_publisher_warns_rather_than_passing(self):
        video = out("video")
        self.assertIn("warning", [i["severity"] for i in video["issues"]])
        self.assertEqual(verdict("MD-190", video), WARN)

    def test_a_page_with_no_video_raises_nothing(self):
        self.assertEqual(verdict("MD-190", out("video_bad")), PASS)


# ---------------------------------------------------------------------------
# Structured data
# ---------------------------------------------------------------------------

class SchemaRequiredProps(unittest.TestCase):
    """MS-032 `summary.errors`, AR-158 and GO-143 `issues` by pattern."""

    def test_complete_schema_produces_no_errors(self):
        good = out("props")
        self.assertEqual(good["summary"]["errors"], 0)
        self.assertEqual(verdict("MS-032", good), PASS)

    def test_a_missing_required_property_and_unparsable_json_are_errors(self):
        bad = out("props_bad")
        self.assertGreaterEqual(bad["summary"]["errors"], 2)
        self.assertEqual(verdict("MS-032", bad), FAIL)

    def test_ar_158_matches_the_breadcrumb_finding_specifically(self):
        """A pattern assertion, and the family that produced fifteen checks which
        could never fire. This one can: the finding it looks for exists."""
        self.assertEqual(verdict("AR-158", out("props")), PASS)
        self.assertEqual(verdict("AR-158", out("props_bad")), FAIL)
        self.assertRegex(json.dumps(out("props_bad")["issues"]), "(?i)BreadcrumbList")


class RichResults(unittest.TestCase):
    """TE-172 `summary.errors`, TECH-001 `summary.warnings`."""

    def test_valid_schema_has_no_errors(self):
        self.assertEqual(verdict("TE-172", out("rich")), PASS)

    def test_broken_schema_blocks_rich_results(self):
        bad = out("rich_bad")
        self.assertGreaterEqual(bad["summary"]["errors"], 1)
        self.assertEqual(verdict("TE-172", bad), FAIL)


class Entities(unittest.TestCase):
    """GEO-006 `summary.sameas_missing_critical`."""

    def test_an_organisation_with_no_sameas_targets_is_unresolvable(self):
        """The contract pair exempts this item because verifying `sameAs` means
        fetching Wikidata, and this suite does not leave loopback. The *absence*
        side needs no egress, and that is what is asserted here."""
        entity = out("entity")
        self.assertGreater(entity["summary"]["sameas_missing_critical"], 0)
        self.assertEqual(verdict("GEO-006", entity), FAIL)


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------

class BrokenLinks(unittest.TestCase):
    """TE-168 `summary.broken`."""

    def test_a_site_whose_links_all_resolve_passes(self):
        self.assertEqual(verdict("TE-168", out("broken")), PASS)

    def test_a_dead_internal_link_and_a_dead_host_are_both_found(self):
        bad = out("broken_bad")
        self.assertGreaterEqual(bad["summary"]["broken"], 1)
        self.assertEqual(verdict("TE-168", bad), WARN)

    def test_the_cap_is_declared_in_the_output(self):
        """It had none until 0.3.0, so a page with 4,000 links produced 4,000
        requests. `truncated` exists so a capped run cannot be read as a complete
        one."""
        self.assertIn("truncated", out("broken"))


class ExternalLinks(unittest.TestCase):
    """BL-083 `summary.broken_links`."""

    def test_links_that_resolve_are_not_broken(self):
        self.assertEqual(verdict("BL-083", out("extlinks")), PASS)

    def test_a_host_that_does_not_resolve_counts_as_broken(self):
        """The gap this closed. The test was `status >= 400`, and a dead domain
        produces no status at all — so the *ordinary* form of external link rot was
        the one form this check could not see, and a page of links to expired domains
        reported zero broken links.
        """
        bad = out("extlinks_bad")
        self.assertGreaterEqual(bad["summary"]["unreachable_links"], 1)
        self.assertEqual(verdict("BL-083", bad), FAIL)

    def test_a_timeout_is_not_called_broken(self):
        """It is a fact about this run, not about the link. Kept in its own count so
        a slow host does not arrive in a fix list as a dead one."""
        self.assertIn("unchecked_links", out("extlinks")["summary"])


class AnchorText(unittest.TestCase):
    """BL-081 `summary.overused_exact_match_targets`."""

    def test_varied_navigation_anchors_are_not_overused(self):
        self.assertEqual(verdict("BL-081", out("anchor")), PASS)

    def test_five_identical_anchors_to_one_target_are(self):
        spam = out("anchor_spam")
        self.assertGreaterEqual(spam["summary"]["overused_exact_match_targets"], 1)
        self.assertEqual(verdict("BL-081", spam), WARN)


class InternalLinks(unittest.TestCase):
    """AR-149 `pages`."""

    def test_the_crawl_reports_incoming_and_outgoing_counts_per_page(self):
        pages = out("intlinks")["pages"]
        self.assertTrue(pages)
        self.assertEqual(verdict("AR-149", out("intlinks")), PASS)
        first = next(iter(pages.values()))
        self.assertIn("incoming_links", first)
        self.assertIn("outgoing_links", first)


class LinkProfile(unittest.TestCase):
    """CI-008 `orphan_pages.count`, AR-162 `issues`."""

    def test_a_site_whose_pages_all_link_to_each_other_has_no_orphans(self):
        good = out("profile")
        self.assertEqual(good["orphan_pages"]["count"], 0)
        self.assertEqual(verdict("CI-008", good), PASS)
        self.assertEqual(verdict("AR-162", good), PASS)

    def test_sitemap_pages_nothing_links_to_are_orphans(self):
        bad = out("profile_bad")
        self.assertGreaterEqual(bad["orphan_pages"]["count"], 1)
        self.assertEqual(verdict("CI-008", bad), FAIL)
        self.assertEqual(verdict("AR-162", bad), FAIL)


class FacetedNavigation(unittest.TestCase):
    """AR-163 `issues`."""

    def test_a_site_with_no_parameter_urls_raises_nothing(self):
        self.assertEqual(verdict("AR-163", out("facets")), PASS)

    def test_six_parameter_variants_on_one_path_are_a_crawl_trap(self):
        """And the item could not fail until the registry passed `--from-page`. A trap
        is a property of a *set* of URLs — five variants sharing a path, or one
        parameter recurring three times — and the registry handed the script the entry
        URL alone, which supplies one of each.
        """
        self.assertIn("--from-page", ITEMS["AR-163"]["check"]["args"])
        bad = out("facets_bad")
        self.assertEqual(verdict("AR-163", bad), WARN)
        self.assertRegex(json.dumps(bad["issues"]), "(?i)parameter")


# ---------------------------------------------------------------------------
# Speed, mobile, technical
# ---------------------------------------------------------------------------

class CacheAndCompression(unittest.TestCase):
    """TE-170 `issues`."""

    def test_an_uncompressed_response_warns_with_the_reason(self):
        """One direction only: `http.server` sends no `Content-Encoding` and no cache
        headers, and nothing in this harness can make it. The value is that the
        vocabulary maps — the script says `warning`, the rule asks about `medium`, and
        0.5.0 is where those two stopped being unable to intersect."""
        cache = out("cache")
        self.assertEqual(verdict("TE-170", cache), WARN)
        self.assertRegex(json.dumps(cache["issues"]), "(?i)gzip|brotli|encod")


class CriticalChain(unittest.TestCase):
    """SP-110 `issues`."""

    def test_a_stylesheet_in_the_head_is_render_blocking(self):
        chain = out("chain")
        self.assertEqual(verdict("SP-110", chain), WARN)
        self.assertRegex(json.dumps(chain["issues"]), "(?i)render-blocking")


class ThirdPartyScripts(unittest.TestCase):
    """SP-109 `blocking_third_party_count`."""

    def test_a_page_loading_only_its_own_scripts_has_none(self):
        self.assertEqual(out("thirdparty")["blocking_third_party_count"], 0)
        self.assertEqual(verdict("SP-109", out("thirdparty")), PASS)

    def test_synchronous_third_party_scripts_are_counted(self):
        bad = out("thirdparty_bad")
        self.assertGreaterEqual(bad["blocking_third_party_count"], 1)
        self.assertEqual(verdict("SP-109", bad), FAIL)


class CssMinification(unittest.TestCase):
    """TE-174 `unminified_count`."""

    def test_a_minified_stylesheet_is_not_counted(self):
        self.assertEqual(verdict("TE-174", out("cssmin")), PASS)

    def test_a_stylesheet_full_of_whitespace_and_comments_is(self):
        bad = out("cssmin_bad")
        self.assertEqual(bad["unminified_count"], 1)
        self.assertEqual(verdict("TE-174", bad), FAIL)
        self.assertGreater(bad["wasted_bytes"], 0)


class FontLoading(unittest.TestCase):
    """TECH-002 `issues`."""

    def test_a_page_loading_no_web_font_raises_nothing(self):
        """One direction, and the honest reason: a fixture cannot serve a real font
        file without committing a binary to the repository for one `low` item."""
        self.assertEqual(verdict("TECH-002", out("fonts")), PASS)
        self.assertEqual(out("fonts")["font_face_count"], 0)


class LcpSubparts(unittest.TestCase):
    """TECH-003 `subparts.ttfb_ms`."""

    def test_ttfb_is_measured_as_a_number_of_milliseconds(self):
        """Loopback answers in about a millisecond, so this can only ever pass here.
        What it does prove is that the field is measured rather than defaulted — a
        hard-coded 0 would make TECH-003 unable to fail on any site."""
        lcp = out("lcp")
        self.assertIsInstance(lcp["subparts"]["ttfb_ms"], (int, float))
        self.assertEqual(verdict("TECH-003", lcp), PASS)


class MobileRender(unittest.TestCase):
    """MB-100 `issues`."""

    def test_a_page_with_a_viewport_raises_nothing_serious(self):
        self.assertEqual(verdict("MB-100", out("mobile")), PASS)

    def test_a_missing_viewport_is_critical(self):
        bad = out("mobile_bad")
        self.assertIn("critical", [i["severity"] for i in bad["issues"]])
        self.assertEqual(verdict("MB-100", bad), FAIL)


class Accessibility(unittest.TestCase):
    """TE-180 `score`, CN-036 `checks.inline_contrast_candidates`."""

    def test_a_page_with_landmarks_alt_text_and_labels_scores(self):
        self.assertEqual(verdict("TE-180", out("a11y")), PASS)

    def test_the_contrast_check_reads_inline_styles_only_and_says_so(self):
        """Deliberately narrow: computing the cascade would mean rendering the page,
        and this script does not. So it counts inline styles that set both a colour
        and a background — which means a site whose contrast problem lives in a
        stylesheet is not covered, and `rendered_audit.py` is the answer to that."""
        self.assertEqual(out("a11y")["checks"]["inline_contrast_candidates"], 0)
        self.assertEqual(verdict("CN-036", out("a11y")), PASS)
        self.assertEqual(out("a11y_bad")["checks"]["inline_contrast_candidates"], 1)
        self.assertEqual(verdict("CN-036", out("a11y_bad")), FAIL)


class JavascriptRender(unittest.TestCase):
    """CN-053 `raw.word_count`, TE-169 `raw.internal_link_count`,
    TE-177 `raw.title`, MB-105 `diffs`."""

    def test_the_raw_html_carries_the_content(self):
        good = out("jsrender")
        self.assertGreaterEqual(good["raw"]["word_count"], 300)
        for item_id in ("CN-053", "TE-169", "TE-177"):
            self.assertEqual(verdict(item_id, good), PASS, item_id)

    def test_a_nineteen_word_page_fails_the_depth_check(self):
        self.assertEqual(verdict("CN-053", out("jsrender_bad")), FAIL)

    def test_static_html_shows_no_rendered_difference(self):
        """MB-105 can only fail a site that needs JavaScript to produce its content,
        which no fixture here is — recorded rather than left as a silent pass."""
        self.assertEqual(out("jsrender")["diffs"], [])
        self.assertEqual(verdict("MB-105", out("jsrender")), PASS)


class Hreflang(unittest.TestCase):
    """IN-121 `checks.x_default.passed`, IN-127 `checks.protocol_consistency.passed`,
    IN-128 `checks.self_reference.passed`, IN-122 `summary.critical`."""

    def test_correct_hreflang_passes_each_named_check(self):
        good = out("hreflang")
        for item_id in ("IN-121", "IN-127", "IN-128", "IN-122"):
            self.assertEqual(verdict(item_id, good), PASS, item_id)

    def test_a_missing_x_default_fails_the_item_that_reads_it(self):
        self.assertIs(out("hreflang_bad")["checks"]["x_default"]["passed"], False)
        self.assertEqual(verdict("IN-121", out("hreflang_bad")), FAIL)

    def test_a_monolingual_page_is_undecided_rather_than_failed(self):
        """The distinction the whole coverage metric rests on. A single-language site
        has nothing to get wrong, so the script returns early and the three `checks.*`
        keys are absent — which the runner reads as NO_DATA. Reporting FAIL would
        invent a defect; reporting PASS would claim a check nobody ran."""
        none = out("hreflang_none")
        self.assertNotIn("x_default", none["checks"])
        self.assertIn("hreflang_present", none["checks"])
        for item_id in ("IN-121", "IN-127", "IN-128"):
            self.assertEqual(verdict(item_id, none), NO_DATA, item_id)


class Ga4(unittest.TestCase):
    """GO-131 `measurement_ids`, GO-132 `duplicates`."""

    def test_a_page_with_no_analytics_reports_no_measurement_id(self):
        self.assertEqual(out("ga4")["measurement_ids"], [])
        self.assertEqual(verdict("GO-131", out("ga4")), FAIL)

    def test_one_id_loaded_twice_is_a_duplicate(self):
        """The verdict this could not produce. `duplicates` counted only
        `gtag('config', …)` calls, and the ordinary way GA4 ends up installed twice is
        two copies of the *loader* — a theme and a plugin, or a hand-added tag beside
        GTM. So GO-132 "Prevent GA4 Tag Duplication" passed the exact situation it
        exists to catch, while the script's own `issues` list said "gtag.js loaded 2x"
        one field away.
        """
        bad = out("ga4_bad")
        self.assertEqual(verdict("GO-131", bad), PASS)
        self.assertEqual([d["kind"] for d in bad["duplicates"]], ["gtag_loader"])
        self.assertEqual(verdict("GO-132", bad), FAIL)


class SocialMeta(unittest.TestCase):
    """MS-033 `score`."""

    def test_a_full_open_graph_and_twitter_card_scores(self):
        self.assertEqual(verdict("MS-033", out("social")), PASS)

    def test_a_page_with_no_social_tags_scores_zero(self):
        self.assertEqual(out("social_bad")["score"], 0)
        self.assertEqual(verdict("MS-033", out("social_bad")), FAIL)


class OneCrawlForEveryoneWhoNeedsTheWholeSite(unittest.TestCase):
    """`site_crawl.py`, and GO-137 which reads it through the orphan check.

    The inventory is the one artifact this tool produces for itself rather than being
    handed, so unlike the browser traces it can be verified by re-running the thing
    that wrote it — which is what these do.
    """

    def test_the_crawl_records_a_status_for_every_page_it_reached(self):
        crawl = out("crawl")
        self.assertGreater(crawl["summary"]["pages_fetched"], 3)
        for key, row in crawl["pages"].items():
            self.assertIsNotNone(row["status"], key)
            self.assertIn("links", row)

    def test_the_request_count_is_reported_because_it_is_the_point(self):
        """Six scripts used to crawl independently — ~275 fetches, measured at 181
        against a seven-page fixture. A shared crawl that does not say what it cost
        cannot be checked against the thing it replaced."""
        crawl = out("crawl")
        self.assertGreater(crawl["summary"]["requests"], 0)
        self.assertLess(crawl["summary"]["requests"],
                        crawl["summary"]["pages_fetched"] + 10,
                        "the crawl is making requests it does not account for")

    def test_a_broken_page_is_named_with_the_pages_that_link_to_it(self):
        """The thing the report could never give anyone: which URL is broken, and
        which page to edit. A verdict about the site is not an address."""
        broken = out("crawl_bad")["broken"]
        self.assertTrue(broken, "the broken fixture's dead internal link was missed")
        dead = next(row for row in broken if row["url"].endswith("/gone"))
        self.assertEqual(dead["status"], 404)
        self.assertTrue(dead["linked_from"])

    def test_a_page_only_the_sitemap_mentions_is_not_reachable(self):
        """The distinction GO-137 is made of. The shared crawl *fetches* sitemap URLs,
        so "we got a status for it" cannot be what reachable means, or seeding from
        the sitemap would satisfy the orphan check by construction."""
        crawl = out("crawl_bad")
        orphan = f"{BAD.base}/unlinked-a.html"
        self.assertIn(orphan, crawl["pages"], "the sitemap URL was never fetched")
        self.assertNotIn(orphan, crawl["reachable"])
        self.assertGreaterEqual(out("orphans_bad")["summary"]["orphan_pages"], 1)
        self.assertEqual(verdict("GO-137", out("orphans_bad")), WARN)

    def test_a_site_whose_sitemap_matches_its_links_has_no_orphans(self):
        self.assertEqual(verdict("GO-137", out("orphans")), PASS)


class NothingIsUndecidedAboutASiteThatAnswered(unittest.TestCase):
    """The other direction, and it cost an item on every audit for a whole release.

    `NothingIsDecidedAboutASiteThatCannotBeRead` below made twelve scripts report
    "I read nothing" so the runner could turn that into NO_DATA. This asserts the
    converse: a script that *did* read a site must not say so. Get it backwards and
    the fix for a site scoring 61/100 while unreachable becomes an item that can
    never be decided about any site at all — which is what happened to AR-149.

    The reason 462 tests missed it is worth keeping in view: every other test in this
    file grades through `evaluate()`, which never looks at `fetch_error`. Only the
    runner's `grade()` reads it, so a spurious one is invisible to all of them. This
    test checks the field directly, over every run in `RUNS`, which is why it is four
    lines and covers 75 of them.
    """

    # No exemptions, deliberately. The first draft of this test excused the two
    # `sitemap_checker` runs against the broken fixture, on the assumption that a
    # site with no sitemap has nothing to read — and the exemption was wrong twice
    # over: a 404 *is* an answer, and `sitemap_checker` already distinguishes "no
    # sitemap here" from "no location responded". Both runs pass without it.
    #
    # The *scope* is narrowed, which is a different thing from an exemption and is
    # derived rather than listed: this asserts something about sites that answered,
    # so it covers the runs that address a site. Three `server_log_audit.py` runs
    # address a file chosen to be unreadable — no User-Agent field, not a log, not
    # there — and "I read nothing" is the correct and required answer for each. A
    # hand-written exemption list would have said the same thing while also excusing
    # whatever got added to it later.
    def test_no_script_reports_a_site_it_read_as_unread(self):
        from checklist_runner import unread_reason
        about_a_site = {key for key, _script, template in RUNS
                        if any("{good}" in a or "{bad}" in a for a in template)}
        self.assertGreater(len(about_a_site), 60,
                           "the scope filter matched almost nothing, so this test "
                           "would pass without checking anything")
        wrong = []
        for key, payload in OUT.items():
            if "__failed__" in payload or key not in about_a_site:
                continue
            reason = unread_reason(payload)
            if reason:
                wrong.append(f"{key} = {reason!r}")
        self.assertEqual(wrong, [],
                         "these runs read a served fixture and told the runner they "
                         "read nothing, so every item behind them is NO_DATA on "
                         "every site:\n" + "\n".join(f"  {w}" for w in wrong))

    def test_a_log_that_could_be_read_is_not_reported_as_unread(self):
        """The same guarantee for the runs the filter above excludes. Two of the
        seven log runs read their file fine, and those must reach the runner as
        evidence rather than as a refusal — otherwise CI-018 is NO_DATA whenever a
        log *is* supplied, which is the AR-149 failure in a new script."""
        from checklist_runner import unread_reason
        for key in ("log_good", "log_waste", "log_json", "log_gz"):
            self.assertEqual(unread_reason(out(key)), "", key)


class NothingIsDecidedAboutASiteThatCannotBeRead(unittest.TestCase):
    """The single most valuable test in this file, and the last one written.

    Every URL-taking script is pointed at a port where nothing is listening, and no
    item may come back PASS, FAIL or WARN. That covers a whole family at once rather
    than one script at a time, and the family is this tool's oldest and worst: a
    script that fetched nothing exits 0 with an empty result, and an empty result
    satisfies a surprising number of assertions. It is how a host that does not
    resolve was once scored 61/100.

    Writing it found three more instances, all in the scripts that talk to a third
    party — `None` pre-seeded into a field that `eq` and `truthy` read as a *failing
    value*, and an empty `issues` list that `none_severity` reads as "nothing wrong".
    Both are verdicts invented out of a service being unavailable, in opposite
    directions.

    **The script list comes from the registry, not from `RUNS`.** It came from `RUNS`
    for a release, and that is how it missed `orphan_pages_from_sitemap.py`: the one
    crawler with no entry in that hand-maintained table, and therefore the one script
    this sweep could not see. GO-137 reported "no orphan pages" about a host that
    refused every connection — `sitemap(∅) - reachable(∅)` is no orphans, and no
    orphans is a PASS. A sweep whose coverage is a list somebody maintains has the
    same blind spot as the thing it is checking.
    """

    DEAD = None

    @classmethod
    def url_taking_scripts(cls) -> set:
        """Every script the registry hands a URL as its first argument.

        Derived, so a script cannot be added to the registry and stay out of this
        sweep. Scripts whose first argument is an HTML file, a Search Console
        property or an artifact are excluded — they are not being asked about a
        host, so a dead host is not their subject.

        Scripts whose capability is `api` are left out too, and that is a constraint
        rather than a judgement: they ask a third party about the URL, so pointing
        them at a dead host makes this suite call `validator.w3.org` and a WHOIS
        server. The suite is offline — loopback only, no DNS, no keys — and staying
        offline outranks the extra coverage. Their "the third party did not answer"
        path is stubbed in test_evidence_apis.py, which is the part of it that can be
        tested without a network.
        """
        out = set()
        for item in ITEMS.values():
            check = item.get("check") or {}
            args = check.get("args") or []
            if not check.get("script") or not args or args[0] != "{url}":
                continue
            if check.get("requires") == "api":
                continue
            out.add(check["script"])
        return out

    @classmethod
    def setUpClass(cls):
        import socket
        # A port nobody is on: bound to find a free one, then released. The refusal
        # is instant, which is what makes running 40 scripts through this cheap.
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        cls.DEAD = f"http://127.0.0.1:{port}/"

        env = script_env()
        scripts = sorted(cls.url_taking_scripts())

        def run(script):
            proc = harness.spawn(
                [sys.executable, os.path.join(SCRIPTS, script), cls.DEAD, "--json"],
                env=env, timeout=120)
            if proc.returncode != 0 or not proc.stdout.strip():
                # A non-zero exit is fine here — the runner turns it into NO_DATA with
                # the reason. What must not happen is a *verdict*.
                return script, None
            try:
                return script, json.loads(proc.stdout)
            except json.JSONDecodeError:
                return script, None

        cls.dead_output = {}
        with ThreadPoolExecutor(max_workers=8) as pool:
            for script, payload in pool.map(run, scripts):
                cls.dead_output[script] = payload

    # Two scripts judge the URL *string* and fetch nothing to do it. A verdict from
    # them about an unreachable host is correct: whether `/shop?SESSIONID=1&sort=x` is
    # a clean URL does not depend on the server answering.
    URL_ONLY = {
        "url_quality.py": "judges the URL it was given, and does not fetch it",
        "faceted_nav_audit.py": "judges URL shape; the page fetch is --from-page only",
    }

    def graded_status(self, item, script, payload):
        """The item's status as the *runner* would report it.

        Through `grade()` rather than `evaluate()` alone, because the difference
        between them is the whole point: `evaluate` sees a dict of defaults and grades
        it, and `grade` is where a payload that says "I read nothing" has to become
        NO_DATA. Testing `evaluate` here would assert the bug.
        """
        from checklist_runner import grade
        key = (script, ())
        rows = grade([item], {key: [item["id"]]}, {key: payload}, {}, False)
        return rows[0]["status"]

    def test_no_item_gets_a_verdict_from_a_site_that_answered_nothing(self):
        decided = []
        for script, payload in self.dead_output.items():
            if payload is None or script in self.URL_ONLY:
                continue
            for item in ITEMS.values():
                if (item.get("check") or {}).get("script") != script:
                    continue
                got = self.graded_status(item, script, payload)
                if got in (PASS, FAIL, WARN):
                    decided.append(f"{item['id']} ({item['severity']}, {script}) "
                                   f"= {got}")
        self.assertEqual(decided, [],
                         "these items decided something about a site that refused "
                         "every connection:\n" + "\n".join(f"  {d}" for d in decided))

    def test_the_url_only_scripts_still_answer_and_that_is_correct(self):
        """The other side of the exemption, so it cannot quietly become a way to
        excuse a script that should have noticed."""
        for script, reason in self.URL_ONLY.items():
            payload = self.dead_output.get(script)
            self.assertIsNotNone(payload, f"{script} produced nothing: {reason}")
            items = [i for i in ITEMS.values()
                     if (i.get("check") or {}).get("script") == script]
            statuses = {self.graded_status(i, script, payload) for i in items}
            self.assertTrue(statuses & {PASS, FAIL, WARN},
                            f"{script} decided nothing, so the exemption is wrong: "
                            f"{reason}")

    def test_the_scripts_that_answered_said_why(self):
        """A script may legitimately return a result for an unreachable host — it just
        has to carry the reason, so the runner can report NO_DATA with something a
        reader can act on rather than a bare absence."""
        silent = [script for script, payload in self.dead_output.items()
                  if payload is not None and script not in self.URL_ONLY
                  and not any(str(payload.get(key) or "")
                              for key in ("error", "fetch_error", "fetch_errors"))]
        self.assertEqual(silent, [], f"no error recorded by: {silent}")


class IndexNow(unittest.TestCase):
    """GEO-007 `key_valid`.

    The last of the 55 evidence scripts to get a test, and the one that needed a
    secret to run at all — which is why the contract pair exempts it: an IndexNow key
    is a credential, not a fixture. A *fake* key is not a credential, though, and the
    protocol is entirely about whether the origin hosts `/{key}.txt`. That is
    servable, so there was no reason for this to stay uncovered.
    """

    KEY = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"

    def test_a_hosted_key_file_validates(self):
        good = out("indexnow")
        self.assertIs(good["checks"]["key_file"]["passed"], True)
        self.assertEqual(verdict("GEO-007", good), PASS)

    def test_an_origin_that_does_not_host_the_key_file_fails(self):
        """Which is the point of the protocol: anyone could claim a key, so the
        origin has to prove it owns one by serving it."""
        bad = out("indexnow_bad")
        self.assertIs(bad["checks"]["key_file"]["passed"], False)
        self.assertEqual(verdict("GEO-007", bad), FAIL)
