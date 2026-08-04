# The fixture site

Six pages, a sitemap, a robots.txt and two assets — enough for the live path to
have something to crawl, sample, follow and refuse.

It exists because the SSRF guard used to have no escape hatch, so the only way to
exercise `checklist_runner.py` in `live` mode was to point it at somebody else's
website. Every test in this suite passed while a slot-file bug crashed 36 of 56
evidence scripts in a real run, and nothing offline could have caught it: a single
process writing to a fresh pacing file never appends twice. `--allow-private` and
this directory are what make that reproducible.

Serve it and audit it:

```bash
python3 -m http.server 8000 --directory tests/fixtures/site &
python3 skills/seo-checklist/scripts/checklist_runner.py http://127.0.0.1:8000/ \
    --allow-private --sample 3 --max-rps 50 --no-history --no-prompt
```

The site is deliberately **not** clean. It is a fixture for the machinery, not a
model of good SEO, and a page that passes everything would exercise none of the
failure paths:

| On purpose | So that |
|---|---|
| `/orphan.html` is in `sitemap.xml` and linked from nowhere | the orphan check has a real orphan |
| `/private/secret.html` is in the sitemap **and** disallowed in `robots.txt` | the sitemap/robots conflict is reported as itself, and our own politeness is not counted as the site's defect |
| `/blog/second-post.html` is linked everywhere and absent from the sitemap | the reverse of an orphan, which the orphan check must not report |
| the two blog posts share a meta description | `duplicate_content.py` has a duplicate |
| `/about.html` has a one-word title | a sampled page disagrees with the entry page, so aggregation is exercised rather than assumed |

One planted defect was removed in 0.9.0: `/blog/first-post.html` used to link to
`/gone.html` so `broken_links.py` had a 404 to find. That predates the good/broken
pair, and it was invisible while TE-168 checked only the entry page's links. One
shared crawl made the check site-wide, it found the dead link immediately, and the
fixture the pair calls *good* started warning about broken links — which weakens
every claim the pair makes. Planted defects belong in `../broken/`, which has its own
dead link. This side has to be able to pass.

The URLs inside `sitemap.xml` and the canonicals are hard-coded to
`http://127.0.0.1:8000`, so serve it on that port or the canonical and sitemap
checks will report a real mismatch — a correct verdict about a wrongly served
fixture, which is a confusing way to spend an afternoon.
