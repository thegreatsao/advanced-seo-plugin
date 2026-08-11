# Fixture oracle triage

Measured on 11 August 2026 from the 12 stage-one differences. Bucket meanings are
those in `GVM-ORACLE-TRIAGE-CODEX.md`: A is a checker defect, B is an incorrect
declaration, C is a fixture that cannot exercise the item, and D is a deferred
registry decision.

| Item | Fixture | Expected | Actual | Bucket | Reasoning |
|---|---|---:|---:|:---:|---|
| AR-158 | good | FAIL | PASS | D | The rule validates only `BreadcrumbList` schema errors and never the visible “UI” required by “Implement Breadcrumbs (UI + Schema)”; defer to `REGISTRY-DECISIONS.md` item 1. |
| MB-096 | good | PASS | FAIL | A | “Use Responsive Images” is satisfied on the only page containing an image, but image-free sampled pages emit `responsive_count=0` and falsely fail the site. |
| MB-097 | good | PASS | FAIL | A | “Optimize Image Formats & Compression” is satisfied by the served WebP `<source>` plus tiny PNG fallback, but image-free sampled pages emit `modern_format_count=0` and falsely fail the site. |
| TE-174 | good | FAIL | PASS | B | The title's words “Minify & Optimize CSS” make PASS appropriate for a 340-byte stylesheet below the checker's 2 KB actionability floor; formatting exists, but there is no meaningful optimization target. |
| CI-019 | good | N/A | PASS | B | “Noindex System & Search Pages” is satisfied when those pages do not exist, and the deliberate robots exclusions confirm that policy, so PASS—not N/A—is the settled verdict. |
| GO-138 | good | FAIL | PASS | B | The title says “Invalid URLs”; `/private/secret.html` exists and returns 200, while a robots `Disallow` conflict does not itself make the URL invalid (and is already reported separately). |
| TECH-001 | broken | FAIL | PASS | C | The only `HowTo` is inside unparseable JSON-LD, so the guard never receives a HowTo/FAQ node; the fixture needs a parseable `HowTo` or `FAQPage` block. |
| BL-081 | broken | FAIL | WARN | B | Five repeated exact-match links violate “Natural and Varied,” but they create one overused target—the rule's explicit warning band—not the more than ten targets required for FAIL. |
| LO-200 | broken | FAIL | WARN | C | No `LocalBusiness` node creates only the rule's warning condition; to exercise FAIL, the fixture needs a parseable LocalBusiness node missing `name`, `address`, or `telephone`, which emits an error-band issue. |
| MD-185 | broken | FAIL | WARN | B | “Optimize Images” calls for an optimization finding, and the constructed lazy LCP candidate is a medium issue, so WARN is the rule's correct verdict for what it actually measures. |
| TE-168 | broken | FAIL | WARN | D | The rule counts one broken target in its warning band and ignores the “Redirected” half of “Fix Broken & Redirected Links”; defer to `REGISTRY-DECISIONS.md` item 2. |
| CN-054 | broken | PASS | FAIL | A | “Ensure Lazy-Loaded Content Is Discoverable” is satisfied by native `loading=lazy` with an ordinary `src`; the checker wrongly substitutes deferred-LCP performance for crawl discoverability. |

## Counts

- A — checker defect: 3
- B — declaration correction: 5
- C — fixture indeterminate: 2
- D — deferred registry decision: 2

## Measurement notes

The MB-096/MB-097 failure is not the old `<picture>` parsing regression. Through the
fixture harness, `/assets/logo@2x.webp` returns HTTP 200 and 34 bytes; the PNG fallback
is 64×64 and 136 bytes. The entry page reports `responsive_count=1` and
`modern_format_count=1`. The two sampled pages with no images each report zero for
both counts, and those inapplicable zeroes decide the site-wide failure.
