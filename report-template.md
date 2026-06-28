# Report Template

This document specifies how a findings envelope (matching `schema.json`) renders to a human-readable markdown report. It is **content**, not a runnable renderer — in v1 the model produces both the JSON envelope and the rendered markdown directly, as part of the pure-prompt onramp. A scripted renderer is a candidate for the skill form factor, but it must produce identical output to what this spec describes.

## 1. Production model

The model emits two artifacts per scan: the JSON envelope (the durable contract) and a markdown report (the human view). The markdown is derived from the JSON — it never contains information not in the JSON, and the JSON is always authoritative. If the model would change a fact in the markdown, it changes it in the JSON first.

## 2. Top-of-report block

```
# Security Review — {project.name}

Scanned {project.files_scanned} files at {scan.timestamp} using {scan.model} (prompt v{scan.prompt_version}).
{commit hash line if project.commit_hash present}
{branch line if project.branch present}
{size budget line if project.size_budget_status == "exceeded"}
{stack packs line if project.stack_packs_loaded non-empty}
```

The size budget line is only rendered if status is `exceeded` — silence on this line means the scan was within budget. If exceeded, the line reads: `**Note:** project exceeds the published size budget; results are partial.`

## 3. System map (DFD)

The DFD section is the **first content section** in the rendered report — before Data Profile, before Scorecard, before Findings. The reader gets "here is your system as an attacker sees it" before anything else.

In the markdown report, emit the Mermaid source in a fenced block. In the HTML report, `render.py` wraps it for mermaid.js rendering.

```
## System Map

```mermaid
{threat_model.dfd.mermaid verbatim}
```

{dfd notes line — omit if threat_model.dfd.notes is absent}
> ⚠️ **Note:** {threat_model.dfd.notes}
```

The notes line (if present) is rendered as a blockquote immediately after the diagram.

If `threat_model.dfd.mermaid` is empty or absent (should not happen per schema, but handle defensively): emit a paragraph `*System map not available for this scan.*` and continue.

## 4. Data Profile

The Data Profile section is rendered **before** the Scorecard. It is the risk multiplier — a `C` grade in a `minimal`-tier app is very different from a `C` grade in a `high`-tier app, and the reader needs this context before seeing grades.

The sensitivity tier label uses ALL CAPS. The tier is followed by a horizontal dividing line, then the `context_note` if present, then the categories table, then the regulatory scope table.

```
## Data Profile

**Sensitivity tier: {SENSITIVITY_TIER}**

{context_note — omit this line if context_note is absent}

| Data category | Evidence | Confidence |
|---|---|---|
| {human-readable category name} | {evidence_summary} | {confidence} |
(one row per entry in data_profile.categories; omit table entirely if categories is empty)

**Regulatory scope**

| Regulation | Applicability | Basis |
|---|---|---|
| {regulation} | {applicability} | {rationale} |
(one row per entry in data_profile.regulatory_flags; omit rows where applicability is "unlikely" UNLESS all flags are unlikely, in which case show them all)
```

**Human-readable category names** (use these in the table, not the enum values):

| Enum value | Rendered as |
|---|---|
| `identity_basic` | Basic identity (name, email, username) |
| `contact_info` | Contact information (phone, address) |
| `auth_credentials` | Authentication credentials |
| `financial_payment` | Payment card data |
| `financial_account` | Financial account data |
| `government_id` | Government-issued ID |
| `health_phi` | Protected health information (PHI) |
| `biometric` | Biometric data |
| `location` | Precise location / movement data |
| `childrens_data` | Children's data (under 13) |
| `gdpr_special_category` | GDPR special-category data |
| `other_sensitive` | Other sensitive data |

**Applicability rendering:**

| Enum value | Rendered as |
|---|---|
| `likely` | Likely applicable |
| `possibly` | Possibly applicable |
| `unlikely` | Unlikely applicable |

**Sensitivity tier rendering** (bold label + short phrase):

| Tier | Rendered header |
|---|---|
| `minimal` | **Sensitivity tier: MINIMAL** |
| `standard` | **Sensitivity tier: STANDARD** |
| `elevated` | **Sensitivity tier: ELEVATED** |
| `high` | **Sensitivity tier: HIGH** |
| `critical` | **Sensitivity tier: CRITICAL** |

## 5. Scorecard

A table with one row per bucket plus an `Overall` row. Grades use the closed enum `A | B | C | D | F | N/A`.

```
## Scorecard

| Domain | Grade |
|---|---|
| Code | {summary.scorecard.code} |
| Dependencies | {summary.scorecard.dependencies} |
| Secrets & Config | {summary.scorecard.secrets_and_config} |
| Architecture | {summary.scorecard.architecture} |
| **Overall** | **{summary.scorecard.overall}** |

**Counts:** {critical} critical, {high} high, {medium} medium, {low} low, {info} info — high-confidence: {hc_count}, medium: {mc_count}, low: {lc_count}.
```

If `low_count > 0`, append: `({low_count} low-confidence findings are present in the JSON envelope but suppressed from this report.)`

## 6. Notes section

If `notes` is empty, omit this section. Otherwise:

```
## Notes

- {note 1}
- {note 2}
...
```

These are scan limitations and caveats the reader needs to interpret the report correctly (files skipped, timeouts, assumptions).

## 7. Findings

Findings are grouped by severity descending: Critical, High, Medium, Low. Within each severity tier, findings are ordered by `confidence` descending (high before medium before low), then by `id` for stable ordering across runs. `info` findings are rendered last, in a single section.

`confidence: low` findings are **suppressed from the rendered report by default** (the JSON still carries them). The scorecard summary line discloses their count so the reader knows they exist.

Severity headings:

```
## Critical findings ({n})
## High findings ({n})
## Medium findings ({n})
## Info findings ({n})
```

Skip any severity tier with zero rendered findings.

## 8. Per-finding rendering

Each finding renders as a level-3 heading with the finding title (verbatim from JSON), followed by a metadata block and structured sub-sections. Optional sections are omitted entirely if not present in the JSON — no `n/a` placeholders.

```
### {title}

| Field | Value |
|---|---|
| Severity | `{severity}` |
| Confidence | `{confidence}` |
| Category | `{category}` |
| Domain | {derived from category-to-scorecard mapping in rubric §7} |
| OWASP | {owasp_mapping joined as "A01, A05" if present} |
| Finding ID | `{id}` |

**Evidence** — `{evidence.file}:{evidence.line_start}-{evidence.line_end}`

```
{evidence.quote}
```

**Related locations** *(present only if related_locations non-empty)*

- `{loc.file}:{loc.line_start}-{loc.line_end}`
  ```
  {loc.quote}
  ```
- (repeat per location)

**Exploitation path.** *(present only if exploitation_path is set)*
{exploitation_path}

**Remediation.**
{remediation}

**References** *(present only if references non-empty)*
- {ref 1}
- {ref 2}

**CVSS** *(present only if cvss is set)* — v{cvss.version} `{cvss.vector}` (score {cvss.score})
```

Use horizontal rules (`---`) between findings within a section.

## 9. Suppression rules (summary)

- `confidence: low` findings are not rendered in the report. Count is shown in the scorecard line.
- The `OWASP` row in the metadata table is omitted when `owasp_mapping` is empty.
- The `Related locations` block is omitted when `related_locations` is empty.
- The `Exploitation path` block is omitted when `exploitation_path` is unset (recall: it's required for severity high/critical and for ARCH_* findings, so omission is only possible at lower severities in non-ARCH categories).
- The `References` block is omitted when `references` is empty.
- The `CVSS` line is omitted when `cvss` is unset (it should only be set on findings citing a CVE).

## 10. Scorecard derivation algorithm (D20)

The scorecard letter grades are computed mechanically from the findings, not authored by the model. This eliminates drift between the narrative and the data.

**Per-finding score:**
```
severity_weight = { critical: 10, high: 5, medium: 2, low: 1, info: 0 }
confidence_weight = { high: 1.0, medium: 0.5, low: 0.2 }
finding_score = severity_weight[severity] * confidence_weight[confidence]
```

**Per-bucket grade:**
```
bucket_score = sum(finding_score for finding in bucket)
grade = F  if bucket_score >= 10
        D  if bucket_score >= 5
        C  if bucket_score >= 2
        B  if bucket_score >= 1
        A  if bucket_score < 1
        N/A if the bucket had nothing applicable to scan
```

`N/A` is reserved for cases where the bucket genuinely couldn't be assessed — e.g., the `dependencies` bucket on a project with no lockfile or manifest files. An empty bucket because nothing was found is grade `A`, not `N/A`.

**Overall grade:** the worst (lowest) grade among the four buckets, ignoring `N/A`. If all four buckets are `N/A`, overall is `N/A` (and the report's existence is questionable).

**Threshold rationale.** A score of 10 corresponds to one critical-high-confidence finding alone — that's enough to fail a bucket. A score of 5 corresponds to one high-high-confidence finding, sufficient for `D`. The thresholds are deliberately strict on the critical/high side; users who want a passing grade need to fix things, not argue about scoring.

**Derivation example** (the four findings from `examples/01`–`04`, one per bucket):
- `code` bucket: 1 finding × (5 × 1.0) = 5.0 → `D`
- `dependencies` bucket: 1 finding × (5 × 1.0) = 5.0 → `D`
- `secrets_and_config` bucket: 1 finding × (10 × 1.0) = 10.0 → `F`
- `architecture` bucket: 1 finding × (10 × 1.0) = 10.0 → `F`
- `overall`: worst non-N/A bucket = `F`

## 11. Envelope reference

`schema.json` is the authoritative contract for the findings envelope. `examples/01`–`04` show the four finding types at full fidelity, including all optional fields. The rendering rules in §2–§9 above are complete specifications; no separate worked rendering example is provided here.


## 12. Operator security checklist (static appendix)

This section is appended to **every** rendered report — always, unconditionally, after all findings. It is static content: it is not derived from the JSON envelope, does not vary based on findings, and does not appear in the JSON at all. Its purpose is a responsibility handoff — a prompt for the application owner to verify the operational security context that code review cannot assess.

The rationale: a code review covers what is visible in source. Real breaches regularly exploit the gap between clean code and insecure operations — lapsed certificates, publicly exposed database ports, MFA-less admin accounts, former employees with retained access. The checklist makes that gap visible and puts accountability for it with the owner.

The rendered section below is emitted verbatim. Do not omit, truncate, or modify it based on the findings in the report.

---

```markdown
---

## Operator Security Checklist

This review assessed what is visible in your source code. It cannot assess the environment your code runs in. The items below represent real attack vectors that have compromised otherwise well-coded applications — work through them before considering this review complete.

For each item: **✅ verified**, **⚠️ action needed**, or **— N/A** for your deployment. See `ops-checklist.md` for the reasoning behind each item.

### Infrastructure

- [ ] TLS certificate is valid, auto-renews, and enforces TLS 1.2+ (TLS 1.0/1.1 disabled)
- [ ] Server OS is patched and running a supported version
- [ ] SSH access requires key-based auth; password authentication is disabled
- [ ] Firewall exposes only required ports (80, 443); database and admin ports are not publicly reachable
- [ ] Database is not directly accessible from the public internet
- [ ] Database connections are encrypted in transit
- [ ] Data at rest is encrypted (host disk encryption and DB at-rest encryption enabled)
- [ ] Backups exist, are encrypted, are stored separately from production, and a restore has been tested

### Access & Secrets

- [ ] All privileged accounts (cloud provider, GitHub, domain registrar) use MFA
- [ ] Production SSH keys are attributed to named individuals; no shared or unattributed keys exist
- [ ] Secrets are in a secrets manager or vault — not in files on disk, chat history, or email
- [ ] Former team members' access is revoked; you can name every person with current production access
- [ ] Application API keys are scoped to least privilege

### Build Pipeline

- [ ] Main branch has push protection; direct force-push is disabled
- [ ] CI/CD secrets are stored as platform secrets, not hardcoded in workflow files
- [ ] CI/CD actions are pinned to specific reviewed versions (not `@latest` or `@main`)
- [ ] Dependency update PRs are reviewed before merge

### DNS & Domain

- [ ] Domain registrar has MFA enabled and transfer lock set
- [ ] No dangling DNS records pointing to decommissioned services (subdomain takeover risk)
- [ ] SSL certificate expiry is monitored with pre-expiry alerting
- [ ] If the domain sends email: SPF, DKIM, and DMARC are configured

### Monitoring & Response

- [ ] Access and error logs are collected and retained
- [ ] Alerting exists for repeated auth failures, traffic anomalies, and admin actions
- [ ] You can take the application offline quickly; the procedure is known and practiced
- [ ] You have a playbook for credential compromise: who rotates, how fast, who is notified
- [ ] You know how to reach your hosting provider's security team

### Third-Party Services

- [ ] Every third-party service receiving user data has been reviewed for its own security posture
- [ ] OAuth integrations request only the scopes actually needed
- [ ] Webhooks from third parties validate the request signature before processing
- [ ] You have a way to learn about breaches at providers you depend on

### Human Factors

- [ ] No shared credentials exist for production access
- [ ] SSH private keys on developer machines are passphrase-protected
- [ ] There is a formal offboarding checklist that revokes all production access when someone leaves
```
