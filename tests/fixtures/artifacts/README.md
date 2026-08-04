# Measured-elsewhere artifacts, for the fixture pair

Eight registry items are decided from a file rather than from a request:
`cwv_metrics.py` reads Core Web Vitals from a browser performance trace, and
`rendered_audit.py` reads font size, link distinctness, overlays and tap targets
from a rendered page. Both exist because those numbers are *computed* values — a
subprocess cannot obtain them, and a model reading HTML has not measured them.

Which means the contract audit could not exercise those eight at all. Without a
file they report NO_DATA, correctly, on both sites — so for eight items,
including two `high` ones, the good/broken comparison was measuring nothing. One
of the two `high` items is "Avoid Intrusive Interstitials", which is the check
most likely to matter to a real reader and was the least exercised.

**These numbers are written by hand, and every file says so in its own `source`
field.** No browser runs in CI. That is a real limitation and it is not hidden:
`source` is printed by the script, carried into the results, and shown in the
report, so a file that came from a text editor rather than a trace announces it
everywhere it goes.

What the fixtures then verify is precise, and it is not "the site is fast":

- the thresholds face the right way — 5200 ms fails LCP and 820 ms passes it,
  which is exactly the direction the CrUX rating bug had backwards in 0.5.0;
- `mobile_overlays_covering_content` derives from the general overlay count when
  the viewport is a phone, and the derivation is exercised rather than assumed;
- eight assertions that had never once produced a verdict now produce two.

Both files record a 390px viewport, because `rendered_audit.py` refuses to
answer tap-target and mobile-interstitial questions from a desktop render — a
desktop fixture would leave MB-094 and MB-103 NO_DATA and two of the eight
unexercised.

`http://127.0.0.1:8000` is a placeholder, rewritten by `tests/harness.py` to the
port each site actually bound, the same way the served fixtures are. It has to
be: the runner now refuses an artifact that describes a different page than the
one being audited, so an artifact pointing at the wrong port would be rejected
instead of read — which is itself asserted, in
`ArtifactsMustDescribeTheAuditedPage`.
