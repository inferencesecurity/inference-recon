# Example 04 — DEP_known_cve (Vulnerable dependency with CVSS)

**Demonstrates:** `cvss` field populated from upstream authoritative source (NOT authored by the model), CVE reference satisfying the schema's `cvss`-requires-CVE-in-references conditional rule, OWASP A06 cross-reference, high severity.

This example also shows the discipline of the schema: the model is allowed to *report* CVSS values for CVE-tied findings, but it gets them from `references`, not from its own judgment.

## Vulnerable code

`requirements.txt`:

```
# requirements.txt
flask==2.2.3
requests==2.31.0
PyYAML==5.3.1
SQLAlchemy==2.0.4
```

`app/services/config_loader.py` (relevant because it shows the library is actually used in a dangerous way, which raises confidence):

```python
# app/services/config_loader.py
import yaml


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.load(f, Loader=yaml.FullLoader)
```

## Expected finding

```json
{
  "id": "4c17d8be",
  "category": "DEP_known_cve",
  "owasp_mapping": ["A06"],
  "severity": "high",
  "confidence": "high",
  "title": "PyYAML 5.3.1 vulnerable to arbitrary code execution (CVE-2020-14343)",
  "evidence": {
    "file": "requirements.txt",
    "line_start": 4,
    "line_end": 4,
    "quote": "PyYAML==5.3.1"
  },
  "related_locations": [
    {
      "file": "app/services/config_loader.py",
      "line_start": 6,
      "line_end": 7,
      "quote": "    with open(path) as f:\n        return yaml.load(f, Loader=yaml.FullLoader)"
    }
  ],
  "exploitation_path": "PyYAML versions before 5.4 allow arbitrary code execution when untrusted YAML is processed with yaml.load() under the default or FullLoader, via Python tag constructors. In this project, config_loader.py calls yaml.load(f, Loader=yaml.FullLoader) on a caller-supplied path. If any flow allows user-controlled YAML to reach load_config() — even indirectly, e.g., via a config-upload endpoint, a tenant-supplied config file, or a CI step that ingests artifact metadata — an attacker can execute arbitrary Python in the process. The use of FullLoader (rather than SafeLoader) confirms the project is exposed to the patched-but-still-present vulnerability that 5.4 closes.",
  "remediation": "1) Upgrade PyYAML to >=6.0 (5.4 is the patch boundary, but pin to the current minor). 2) Switch yaml.load(..., Loader=yaml.FullLoader) to yaml.safe_load(...) in app/services/config_loader.py — this is the correct API for untrusted input and removes the vulnerable code path regardless of library version. 3) Add a dependency policy that flags PyYAML versions <5.4 in CI.",
  "references": [
    "CVE-2020-14343",
    "https://nvd.nist.gov/vuln/detail/CVE-2020-14343",
    "https://github.com/yaml/pyyaml/issues/420"
  ],
  "cvss": {
    "version": "3.1",
    "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    "score": 9.8
  }
}
```

## What makes this a quality finding

The `evidence` is the lockfile pin, which is the actionable artifact (upgrade this line). The `related_locations` array shows *why* this finding deserves high confidence rather than just "you have an old package" — the project's code actively uses `yaml.load(FullLoader)`, the specific dangerous pattern. Without that confirmation the finding would warrant lower confidence ("vulnerable version installed, but usage pattern unclear") and lower severity. Tying the dependency finding to the call site is the kind of context the LLM is well suited to provide.

The `cvss` object carries the authoritative NVD score (9.8 critical) and the vector string. Per D11, the model does not author these — it copies them from the cited reference. The schema enforces that `cvss` is only valid when `references` contains a CVE ID matching `CVE-\d{4}-\d+`. The `cvss.score` being 9.8 (critical) and the finding's `severity` being `high` (not critical) is intentional: the model's severity reflects *project-specific* impact (which is high but not critical because the call site is internal-only in this app), while the CVSS reflects the generic upstream worst-case. The two scores are allowed to diverge; they answer different questions.

The `remediation` lists both the version bump and the API change (`safe_load` instead of `FullLoader`) — the second matters because it removes the vulnerability *class* from the code, not just the current incarnation, so the next time the dependency drifts the call site is still safe.

## What is NOT a finding in this code

The other dependencies in `requirements.txt` are NOT findings by virtue of being pinned to specific versions. Pinning is the *correct* practice; the model should not flag "this dependency could have a CVE" as a finding without identifying a specific CVE. (A separate `DEP_supply_chain_risk` finding could surface if the lockfile *did* float versions — e.g., `flask>=2.2` — but that's a different category.)

If the project had `PyYAML==5.3.1` in requirements.txt but no actual use of `yaml.load` anywhere in the codebase (only `yaml.safe_load`), this would still be a finding, but at `confidence: medium` or `low` — vulnerable package present, but no exposed call path identified. Be explicit about that distinction in the model's reasoning.
