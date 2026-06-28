# Worked Examples

These are hand-authored reference examples. They serve two purposes:

1. **Few-shot anchors for the prompt.** The model patterns on these. Sloppy examples here will produce sloppy findings forever — every example in this folder must be exemplary.
2. **Seed entries for the eval golden set.** Each example is a vulnerable code snippet paired with the finding(s) we expect the tool to produce. As the golden set grows, these become regression-test fixtures.

Each example shows a small, plausible vulnerable code excerpt and the expected JSON finding output. Together the four files cover the four v1 scope domains and exercise the schema's distinctive features (conditional `exploitation_path` requirement, `related_locations` for multi-file findings, `cvss` for CVE-tied findings, `owasp_mapping` cross-references).

## Envelope skeleton

Examples below show only the `finding` object. In a real scan, each finding sits inside an envelope of this shape:

```json
{
  "schema_version": "0.1",
  "scan": {
    "timestamp": "2026-05-23T14:00:00Z",
    "model": "claude-opus-4-7",
    "prompt_version": "0.1"
  },
  "project": {
    "name": "demo-app",
    "files_scanned": 47,
    "size_budget_status": "within",
    "commit_hash": "a1b2c3d4..."
  },
  "summary": {
    "scorecard": { "code": "C", "dependencies": "D", "secrets_and_config": "F", "architecture": "F", "overall": "F" },
    "counts_by_severity": { "critical": 1, "high": 2, "medium": 0, "low": 1, "info": 0 },
    "counts_by_confidence": { "high": 3, "medium": 1, "low": 0 }
  },
  "findings": [ /* finding objects from the examples below */ ],
  "notes": []
}
```

## Quality bar (anchors for the model)

Every finding in this folder satisfies the following bar. Findings the model produces should clear the same bar; the prompt enforces these in language, the schema enforces them structurally.

- **Title is specific and quotable.** Not "SQL injection vulnerability" but "SQL injection via unescaped `user_id` in `/users/<id>` route."
- **`evidence.quote` is verbatim.** No paraphrasing; no ellipses except where the omitted portion is obviously irrelevant. Lines exactly match `line_start`–`line_end`.
- **`exploitation_path` is concrete.** Names the attacker, the input vector, and the observable harm. Not "this could be exploited" but "any unauthenticated HTTP caller can supply `?user_id=1 OR 1=1 --` and dump the users table."
- **`remediation` is actionable.** Names the fix (parameterized query, specific decorator, specific config setting) — not a category of fix.
- **`id` is derived deterministically.** Short SHA-1 of `category|evidence.file|evidence.line_start` (first 8 hex chars). Title is excluded so the same finding location gets the same ID regardless of how the model phrased the title across runs.
- **`owasp_mapping` is populated when there's a clear correspondence.** Omitted when forced.

## ID derivation snippet

```python
import hashlib
def finding_id(category: str, file: str, line_start: int) -> str:
    raw = f"{category}|{file}|{line_start}"
    return hashlib.sha1(raw.encode()).hexdigest()[:8]
```

## Index

| # | File | Category | Severity | Demonstrates |
|---|---|---|---|---|
| 01 | [01-code-injection.md](01-code-injection.md) | `CODE_injection` | high | Classic CODE_* finding, single-location evidence, owasp_mapping |
| 02 | [02-secret-hardcoded.md](02-secret-hardcoded.md) | `SECRET_hardcoded` | critical | High-severity finding with exploitation_path enforcement; contrast with what is NOT a secret |
| 03 | [03-arch-missing-authz.md](03-arch-missing-authz.md) | `ARCH_missing_authz` | critical | The multi-file killer-feature case: `related_locations` array, ARCH_* exploitation_path bar |
| 04 | [04-dep-known-cve.md](04-dep-known-cve.md) | `DEP_known_cve` | high | `cvss` field populated from upstream NVD data (not authored by model); CVE in `references` |
