# Demo Output

This folder contains a captured scan output produced by running `prompt.md` against `../demo-project/`. It exists to show what a real scan looks like. The three files follow the v0.7 filename convention (`<project>-security-review-<YYYY-MM-DD>T<HHMM>.<ext>`) and are the same three artifacts the tool produces in a live session:

- `demo-project-security-review-2026-05-23T1500.json` — the JSON findings envelope (authoritative).
- `demo-project-security-review-2026-05-23T1500.md` — the markdown report rendered from the envelope.
- `demo-project-security-review-2026-05-23T1500.html` — the self-contained HTML report produced by `render.py`. Double-click to view in a browser.

**A note on the divergence between this scan and the current demo-project.** The Stripe-key finding (id `efa49c68`) was captured when `demo-project/app/services/payments.py` contained a real-shaped Stripe live key on line 7. For safe public commit, that line has been replaced with an obvious placeholder (`sk_live_PLACEHOLDER_DO_NOT_USE_DEMO_FIXTURE_VALUE_X`). Re-running the prompt against the current `demo-project/` will not reproduce this exact finding — the rubric's negative anchors instruct the model not to flag placeholder values at high confidence. The captured scan in this folder is preserved as a reference for what the output looks like when the input does contain a real-shaped credential.

The other three findings (`c77f6ce8`, `4fab2d2f`, `85934c06`) are unaffected by the sanitization and will reproduce on a fresh scan.

To regenerate the HTML from the JSON envelope (e.g., after iterating on `render.py`):

```
python ../render.py demo-project-security-review-2026-05-23T1500.json
```

Run `python ../eval/sanity_check.py demo-project-security-review-2026-05-23T1500.json` (when that script exists) to verify this envelope is internally consistent.
