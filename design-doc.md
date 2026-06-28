# Inference Recon — Design Doc

**Status:** Draft v1.7 — rule packs + corpus pivot
**Last updated:** 2026-05-25
**Owner:** Mark
**Purpose:** Capture the architectural commitments made during the v1 precheck so we don't violate them by accident later. Living document — update the decision log as choices are revisited.

---

## 1. Context

An AI-driven security review tool. Background motivation: the author has an information-security background and wants a tool that can do a fast, broad security pass over a project and produce a credible report. The bet is that an LLM can meaningfully contribute to security review — particularly on architectural and contextual issues that existing static scanners miss — provided the tool is disciplined about evidence and false positives.

The starting form factor is intentionally minimal: a prompt the user pastes into Claude, Codex, Cursor, or a similar assistant. The architecture is designed so this same artifact can be promoted to a Claude skill (and eventually a CI integration) without rewriting from scratch.

---

## 2. Product definition

The dominant model of automated security analysis is rule-based static scanning: a tool fires when code matches a pattern, and stays silent otherwise. The silence is treated as safety. This achieves its apparent certainty through a commitment to incompleteness — it only asserts what it can prove mechanically, which is a small fraction of the actual vulnerability space. The vulnerabilities that get organizations breached — architectural gaps, trust boundary violations, authorization failures that require understanding the data model — live outside that space. They are invisible to rule-based tools by design.

This tool works from the other direction. It applies contextual security reasoning — the kind a senior engineer brings to a code review — across the full surface area of a project: code-level vulnerabilities, dependencies and supply chain, secrets and configuration, architecture and threat modeling. Where the reasoning is certain, it says so. Where it isn't, it says that too, explicitly, in the confidence tier. A `confidence: medium` finding is more useful than a Semgrep clean run — the clean run hid its uncertainty; the finding names it. Repeated scans and cross-tool corroboration convert that honest uncertainty into calibrated signal over time.

The first-class user is a solo developer or small team doing self-assessment. Output is structured JSON with confidence tiers and evidence, rendered as a human-readable scorecard report. The tool is structured to grow into a Claude skill that can optionally incorporate existing scanners to ground specific finding categories — an enhancement to this foundation, not the foundation itself.

---

## 3. Goals (v1)

A credible, paste-anywhere prompt that produces useful findings on small-to-medium projects without any execution environment. Findings that come with file/line evidence and an explicit confidence tier, so a security-literate reader can triage quickly. A JSON output schema strong enough that downstream consumers (report templates, future CI integrations, eval harnesses) can rely on it. Repo structure such that promoting v1 to a Claude skill is a wrapping exercise, not a rewrite.

---

## 4. Non-goals (v1)

**Not a replacement for Semgrep / Snyk / GitHub Advanced Security.** Existing scanners have years of rule curation, CVE databases, and false-positive tuning behind them. This tool complements them by reasoning about architectural and contextual issues they don't see. It does not try to match their rule coverage.

**Not a pentesting tool.** Static review of code and configuration only. No DAST, no network probing, no exploit execution.

**Not a remediation autopilot.** The tool identifies and explains. It does not auto-patch, open PRs, or apply fixes. This is a deliberate blast-radius limit on LLM hallucination risk.

**Open question on compliance:** explicitly *not* called out as anti-scope. v1 will not produce SOC2/PCI/HIPAA audit artifacts, but the finding category taxonomy will be designed to map cleanly onto OWASP Top 10 / CWE so compliance-style reporting is buildable later without retrofitting.

---

## 5. Decision log

| # | Decision | Choice | Rationale |
|---|---|---|---|
| D1 | Scope of security domains for v1 | All four: code vulns, deps/supply chain, secrets/config, architecture/threat modeling | Architectural and threat-modeling reasoning is the differentiator — pure code-vuln scanning is a crowded space. Cost: prompt depth-vs-breadth tradeoff (see R1). |
| D2 | Analysis engine | Hybrid: LLM-native, with optional tool orchestration | Preserves the paste-into-Claude onramp. Tool orchestration becomes available when the skill form factor is built, without changing the prompt's core contract. |
| D3 | v1 primary user | Solo developer / small team self-audit | Highest tolerance for false positives during early iteration. Natural fit for the pure-prompt form factor. Security-pro and CI personas stack on top once finding quality is proven. |
| D4 | Output format | Structured JSON + rendered human-readable report on top | JSON is the durable contract; report is a view. Lets multiple personas be served (scorecard view for devs, terse view for sec pros, machine view for CI) without divergent code paths. |
| D5 | Context-window strategy for v1 | Declare an honest size budget; no map-reduce yet | Map-reduce requires orchestration that breaks the pure-prompt onramp. v1 publishes a "works best on projects under N files" budget and exits cleanly when exceeded. |
| D6 | False-positive discipline | Confidence tiers + evidence requirements, enforced by schema | Findings without `file`, `line`, `evidence_quote`, and `confidence` are structurally invalid. Low-confidence findings allowed in JSON but suppressed from the rendered report by default. |
| D7 | v1 distribution artifact | Prompt-first, skill-ready structure | Ship paste-able markdown today. Repo structure separates content (rubric, schema, rule packs) from orchestration (the prompt), so promotion to a skill is a wrapping exercise. |
| D8 | Language / stack scope | Stack-agnostic in v1, with prompt designed for stack-pluggability | Defers the stack focus question while keeping the door open. Rule packs live as discrete files under `rules/` so a stack-specific pack can be appended without modifying the main prompt. |
| D9 | Eval strategy | Phased: vibes-check now → curated golden set → comparison against existing scanners | Forces the data model to be eval-ready from day one (stable finding IDs, closed category enum), even though formal eval doesn't run until later. |
| D10 | Evidence shape | Primary `evidence` location object + optional `related_locations` array | Keeps the common single-location case clean while accommodating multi-file ARCH_* findings without splitting them artificially. |
| D11 | Severity model | Five buckets primary; optional `cvss` object only for findings tied to a published CVE | The model assigns buckets consistently; CVSS scores come from authoritative upstream sources (NVD, vendor advisories), never authored by the LLM. Schema enforces that `cvss` requires a CVE in `references`. |
| D12 | Reproducibility metadata | Envelope carries `scan.timestamp`, `scan.model`, `scan.prompt_version`, `project.commit_hash`, `project.branch` | Eval/regression tracking requires all of these. `prompt_version` is separate from `schema_version` so prompt iteration can be measured against a stable schema. |
| D13 | `exploitation_path` required-when | Required when severity ∈ {critical, high} OR category begins with `ARCH_` | Impact-based + category-based. ARCH_* carry the highest hallucination risk (per R5) so they get forced grounding regardless of severity. Enforced by `if/then` rules in the schema, not by exhortation in the prompt. |
| D14 | Category taxonomy structure | Hybrid: domain buckets primary (CODE_*, DEP_*, SECRET_*, CONFIG_*, ARCH_*) plus named buckets for OWASP categories without a clean domain equivalent (AUTHN_failure, AUTHZ_failure, INSECURE_DESIGN, INTEGRITY_failure) | Avoids the overlap problem of the v0.1 OWASP+domain mix while preserving access to OWASP semantics. Disambiguation rule: prefer the most specific applicable category. |
| D15 | OWASP cross-reference | Optional `owasp_mapping` array on each finding | Lets compliance-style grouping be built later without retrofitting every finding. Field omitted by default; populated when there's a clear OWASP correspondence. |
| D16 | Severity vs. CVSS semantics | `severity` reflects project-specific impact; `cvss.score` reflects upstream worst-case. They are allowed to diverge. | Surfaced while writing example 04 (PyYAML CVE): the upstream NVD score is 9.8 (critical) but the project-specific impact is `high` because the call site is internal-only. Conflating the two destroys signal in both directions. The prompt instructs the model to compute project-specific severity considering reachability, exposure, and contextual exploitability. |
| D17 | Confidence definitions | high = directly evidenced reachable/exploitable in this codebase. medium = pattern match but exploitability in context uncertain. low = heuristic match, may be FP, surfaced for completeness. | Without this calibration the model conflates the three tiers and the report-mode suppression of low-confidence findings (per R2 mitigation) becomes meaningless. The prompt must define each tier in these terms. |
| D18 | Category-to-scorecard mapping | Authoritative mapping in `rubric.md` §7. Each of the 22 categories belongs to exactly one bucket (`code`, `dependencies`, `secrets_and_config`, `architecture`). `OTHER` defaults to `architecture`. | Required for deterministic scorecard derivation. Validated: every schema-enum category appears in the mapping table; no duplicates; no orphans. The `OTHER` → `architecture` default is debatable (findings that don't fit anywhere else are often architectural in nature, but not always); revisit if real scans produce noisy `OTHER` findings. |
| D19 | Order of analysis | Dependencies → Secrets & Config → Code → Architecture | Architecture goes last because it consumes context from earlier domains (an architectural finding's exploitation path may cite a vulnerability discovered in §3). Dependencies and Secrets/Config go first because they're cheap pattern matches that establish baseline context. The model does not revise earlier findings as later context emerges — it cross-references via `related_locations` instead. |
| D20 | Scorecard derivation algorithm | `finding_score = severity_weight × confidence_weight` summed per bucket; thresholds 10/5/2/1 → F/D/C/B/A; overall = worst non-N/A bucket. Authoritative spec in `report-template.md` §10. | Mechanical and deterministic — derivable from JSON without model judgment, eliminating drift between the narrative grades and the underlying findings. Strict on the critical/high side intentionally (one critical-high-conf = F). Enables an automated envelope sanity checker (see new open question). |
| D21 | Report production model | Model emits JSON envelope AND rendered markdown in pure-prompt mode. The JSON is authoritative; the markdown is a derived view. | Required by the pure-prompt onramp commitment (D2/§6): a scripted renderer would break the "paste prompt into Claude" form factor. The skill form factor MAY later add a scripted renderer, but it must produce output identical to what `report-template.md` specifies. |
| D22 | Low-confidence suppression | `confidence: low` findings are not rendered in the markdown report. Count is disclosed in the scorecard summary line. Findings remain in the JSON. | Implements the R2 mitigation (trust death from FPs). The user sees the high/medium-confidence picture by default; the JSON preserves complete data for power users and for the eval golden set. |
| D23 | Size budget thresholds (v1) | ≤150 source files AND ≤10k source lines AND no single source file >2k lines → within. Above any of these → exceeded. | Closes the "what is small project" open question with concrete numbers. Calibrated to fit comfortably in current frontier model context windows for thorough single-pass review. Honest threshold — the prompt explicitly tells the user when exceeded and what was skipped, rather than silently degrading. |
| D24 | In-prompt self-consistency check | `prompt.md` Step 9 instructs the model to verify ID derivation, count consistency, scorecard derivation, and conditional schema requirements before emitting. | Interim implementation of the envelope sanity checker (open question carried since v0.5). Operates in pure-prompt mode where no external script can run. The standalone `eval/sanity_check.py` artifact remains the v2 design — it provides offline regression testing independent of the model. |
| D25 | Distribution & runtime flow | One-paste CTA into Claude Code. User pastes a natural-language instruction; Claude clones the tool repo to `~/.inference-recon/`, reads `prompt.md` (which loads the companion files), and executes the scan against the cwd. | Optimizes for the dominant target persona (Claude Code users). One paste, one approval, no path math. The dotdir clone location is persistent, predictable, self-documenting, and survives across sessions — `/tmp/*` was rejected as both ephemeral and signaling "throwaway hack." README's quick-start is just the one-paste block. |
| D26 | Persona positioning (runtime UX) | Optimize all runtime affordances for the person *running* the scan, not for hypothetical downstream audiences. | Surfaced while deciding timestamp formats. The primary persona is a solo dev or small-team member running scans on their own project; downstream audiences (CTO, auditor) read filenames at the freshness-sniff-test resolution, not at minute precision. This guides multiple decisions: local time over UTC in filenames (D29), file-system outputs they can double-click (D27), chat summary readable inline. Future UX decisions should apply this lens. |
| D27 | Output artifacts | Three files written to disk per scan: `findings.json` (machine-readable source of truth), `report.md` (IDE / grep / paste), `report.html` (self-contained, double-clickable). Plus a markdown summary emitted to chat for immediate consumption. | Three real consumers, three formats; none redundant. Files-on-disk because reports are read carefully on couches and shared with stakeholders — chat-only output is ephemeral and dev-biased. Markdown summary in chat is the "you don't have to leave Claude Code to see what happened" affordance. |
| D28 | Output filesystem layout | Flat: all artifacts land directly in `./security-review/` under the audited project's cwd. No timestamp subdirectories. | Filenames are uniquely timestamped (D29), so the disambiguation work the subdir used to do is no longer needed. One less click for the noob to find the HTML. Users add `security-review/` to their project's `.gitignore`; README mentions this. |
| D29 | Filename convention | `<project>-security-review-<YYYY-MM-DD>T<HHMM>.<ext>`. Local time, minute precision, ISO `T` separator, no offset suffix. Project slug: lowercase, hyphens for whitespace/underscores, strip non-alphanumeric-or-hyphen, fallback `project`. | The filename is the only context that survives the file leaving its directory. Encodes the three things a future reader needs: what project, when, what kind of artifact. Project-first for alphabetical grouping; ISO date for sort correctness. Local time per D26 (the runner reads "T1500" as "3pm" immediately). Always-include-time was chosen over auto-increment or conditional-time because predictability beats brevity — the caller can derive the filename from inputs they know. |
| D30 | JSON envelope `scan.timestamp` format | ISO 8601 with explicit offset: `2026-05-24T15:00:00-07:00`. | The JSON envelope is the artifact that survives furthest into automation and archival. Embedding the offset preserves "what local time was this, where" forever, with no information loss. Filename stays clean for the runner per D26; JSON stays robust for archival. Different jobs, different conventions, no mixed messaging because the surfaces serve different audiences. |
| D31 | HTML renderer | Bundled Python script (`render.py`) in the tool repo. Reads `findings.json`, writes `report.html` alongside it. v1: static HTML, inlined CSS, stdlib only. **Exception (D37):** mermaid.js loaded from jsDelivr CDN for DFD rendering; graceful `<noscript>` fallback (raw source + mermaid.live deep link) preserves self-contained usability offline. | Renderer-as-script keeps HTML quality deterministic (no LLM creativity in output) and lets the HTML template iterate independently of the prompt. Static + inlined CSS hits the "self-contained, double-clickable, no broken assets" requirement. Python/stdlib only for the one-paste CTA. The mermaid.js CDN exception is narrow and recoverable — noscript fallback means the report doesn't break without a network connection. Future v2: collapsibles via `<details>`, severity-filter chips, etc. — additive, no LLM dependency. |
| D36 | DFD as first-class envelope field | `threat_model.dfd` is a required top-level object in the findings envelope (v0.3+). Model derives a Level 1 DFD from source inventory and emits Mermaid source; optional `dfd.notes` captures inferences. Optional `dfd_element` field on each finding references a node ID in the diagram, reserved for future diagram-to-finding cross-referencing. | The DFD is the tool's highest-impact wow moment for the target audience — seeing their own system architecture materialized directly from their code. Required, not optional, so the model cannot skip it; it must reason and commit. First-class JSON means it can be rendered, validated, queried, and evolved independently of the report template. `dfd_element` is a forward-looking hook: set now, used later for HTML interactivity without a schema break. |
| D37 | DFD format and rendering | Mermaid flowchart syntax emitted as a string in the JSON envelope. HTML report renders via mermaid.js from jsDelivr CDN (`mermaid@11`), initialized with `startOnLoad: true`. Markdown report wraps source in a ` ```mermaid ` fenced block. Noscript fallback: raw source displayed + base64-encoded mermaid.live deep link for offline viewing. | Mermaid is the only diagram-as-code format with widespread IDE rendering support, a browser-side JS library, and no local toolchain requirement. jsDelivr CDN is the intentional, narrow deviation from D31's stdlib-only constraint — DFD rendering in HTML requires JS; there is no stdlib equivalent. The noscript fallback preserves the self-contained guarantee where it matters most. Mermaid.live link means offline users still get a rendered diagram, just one click away. |
| D38 | DFD scope: Level 1, one diagram per scan | One Level 1 DFD per scan. Level 1 = external actors, processes, data stores, labeled data flows, trust boundaries. No Level 0 (too abstract to be useful), no Level 2 (too detailed for the target audience). STRIDE annotations explicitly deferred. Max 15–20 nodes recommended; simplify ruthlessly. | Target audience is solo devs and small teams who have likely never seen a DFD before — Level 1 is the "aha" layer. One diagram forces the model to reason about what matters at system level rather than enumerating every code path. Level 2 would require per-process decomposition, multiplying diagram complexity and token cost. STRIDE deferred: adding six threat categories per node would overwhelm first-time viewers; architecture diagram and STRIDE threat table are separable features that can ship in separate schema versions. |
| D39 | Two-layer finding model in the eval / Pro data layer | `run_findings` (one row per finding per scan — immutable record of a tool's output) + `canonical_findings` (one row per unique vulnerability per project, deduplicated across all runs and tools). New runs are ingested by matching each finding against canonicals via the finding ID hash; unmatched findings create new canonical records. | The eval table and the Pro persistent-tracking feature have different primary keys. `run_findings` answers "what did Tool X find on Date Y?" (run-centric). `canonical_findings` answers "does this vulnerability exist in this project, and when was it first seen?" (finding-centric). Conflating them into one table forces a choice between these two query patterns. The two-layer structure also enables cross-tool corroboration as a confidence signal (D42) and finding lifecycle tracking without schema surgery later. |
| D40 | Projects as a first-class entity | The eval DB has a `projects` table: repo URL, owner, name, primary language, primary framework, sensitivity tier, first/last scanned, scan count. `scans` has a `project_id` FK. Currently project is just a string inside a scan record — promoting it to an entity costs almost nothing now and is required for benchmarking queries later. | Benchmarking / peer comparison (a Pro feature) requires grouping scans by project and comparing project-level aggregates across the corpus. This is only possible if project is a persistent entity with stable identity, not a string field. Stack classification and sensitivity tier — both already produced by every scan — become the dimensions for percentile segmentation. Captured now because adding a FK later requires a migration; capturing it from the first ingestion is free. |
| D41 | SQLite for eval, Postgres for Pro — same schema, connection string swap | The eval data layer is SQLite. The Pro backend is Postgres. No SQLite-specific idioms (no AUTOINCREMENT in place of standard SERIAL, no SQLite-only JSON functions) in the table definitions. | The canonical migration path for this class of project is: SQLite during development/eval → Postgres in production. If the schema is clean, the migration is `pg_dump`-style import and a changed connection string. If it isn't, it's a schema redesign under live data. Designing it right once at eval scale is essentially free. |
| D43 | Two-repo distribution strategy | Private development repo (this repo) + separate public release repo. No git relationship between them — no shared history, no branches in common, no submodules. The public repo is a release artifact populated by `scripts/release.sh`. The public file manifest is maintained in `RELEASE.md` and enforced by the script. | A GitHub fork maintains a link back to the source, exposing the private repo's existence. A `public` branch shares history and makes private commits reachable via git. Two independent repos is the only clean separation. The release script eliminates the manual copy-paste error surface while keeping the deployment model simple: clone public, overwrite files, commit, tag, push. |
| D42 | Cross-tool finding corroboration as primary confidence signal at scale | When multiple tools (Claude Code, Cursor, Codex, etc.) independently produce the same `finding_id` for the same project, that corroboration is treated as strong evidence the finding is real — a higher-confidence proxy for ground truth than any single tool's output. The canonical_findings record tracks how many distinct tools and runs have linked to it. | Manual ground truth annotation does not scale to hundreds of repos. Static analysis tools are noisy proxies. The most scalable signal available without human annotation is whether independent AI tools agree. The finding ID hash (sha1 of category + file + line_start — see D44) was designed to be deterministic and stable precisely so this deduplication is possible. Two or more independent tools agreeing on the same finding_id is meaningfully different from one tool flagging it — both as a quality signal and as a basis for confident disclosure decisions. |
| D47 | Two-track eval: Real World + Academic | Corpus is structured as two explicit tracks. **Real World** (primary): real open-source Next.js + Supabase / Stripe / AI projects — the Tier 1 vibe coder SaaS stack. Ground truth via rule-pack predictions → scan → triage. Tests what the tool can find that rule-based scanners cannot. **Academic** (calibration): intentionally vulnerable apps with pre-given documented ground truth — the same benchmarks the security research community uses. Tests whether classical vulnerability patterns are handled correctly; enables direct comparison against existing tools. Neither track alone is sufficient: Academic-only is undifferentiated (every scanner scores on these); Real World-only is unverifiable (anecdotal). Together they produce a reproducible credibility claim: we match established scanners on recognized standards *and* find things in production-adjacent codebases that no academic benchmark was designed to test — e.g., a missing Stripe webhook signature check in a widely-forked Next.js starter, flagged as critical with file/line evidence. | Credibility requires both rigor (academic track, comparable to prior work) and relevance (real world track, the actual target use case). The combination maps directly to §15's stochasticity argument: the academic track proves calibration on known patterns; the real-world track proves reasoning over novel patterns that no rule set covers. |
| D46 | Rule pack content strategy | Packs target the vibe coder SaaS power law: the top two or three stacks account for ~80% of the addressable market, and LLM-generated code within each stack produces highly predictable failure patterns. Pack content is derived by inverting the LLM build model — identifying what AI coding assistants routinely generate and where those patterns are insecure. This produces high-signal, low-noise rules with concrete positive anchors and explicit false positive suppressors. Bar for a new pack: (1) stack must be in the top distribution tiers, (2) at least three rules with documented real-world LLM-generation occurrence, (3) validated against at least one real project. Packs are additive — they do not replace the stack-agnostic rubric. | First pack (`nextjs-supabase`) covers the canonical vibe coder SaaS stack and the majority of LLM-generated web app output. 13 rules across Supabase, Next.js, Stripe, AI integrations, and general multi-tenant patterns. Product implication: the tool can tell a Next.js + Supabase founder "your service role key is exposed and your webhook handler has no signature check" on first run — that is the product. |
| D45 | Dependency bar for this codebase | High. Official vendor SDKs and well-understood infrastructure libraries only. No intermediary abstraction layers, aggregator services, or convenience wrappers in any path that touches user code, API keys, or scan output. When a library sits between our code and a provider, it sees everything — source code, credentials, findings. A security tool with a compromised dependency is worse than no tool. Prefer a one-time build of 60 lines of owned code over a maintained third-party wrapper. Every new dependency requires an explicit justification: what does it do, who maintains it, what does it see at runtime? | LiteLLM was the immediate trigger: legitimate library, but it sits in the API call path and sees all source code passed to the scanner. Replaced with direct vendor SDK calls (~60 lines). The principle generalises: supply chain risk is especially acute here because the tool processes codebases that may contain real credentials and proprietary code. Being compromised via our own toolchain would be the sharpest possible irony. |
| D44 | Finding ID stability: drop `title` from hash | Finding `id` is derived from `sha1(category + "\|" + evidence.file + "\|" + str(evidence.line_start))[:8]`. Title is excluded. | The model phrases finding titles differently across runs and models — "SQL injection in user_id param" vs "Unsanitised user_id enables SQL injection." Including title in the hash means the same vulnerability gets a different ID each time it's reworded, breaking canonical deduplication (D39) and corroboration counting (D42). Category + file + line is the minimal stable identity: same vulnerability in the same place, regardless of how the model chose to express it. Collision risk is low for well-scoped findings — two different vulnerabilities at the same file+line in the same category would be a degenerate case. See §15 for the broader stochasticity context that motivated this decision. |

---

## 6. Architectural commitments

These are the implications of the decisions above. Violating any of them means rewriting something.

**The prompt cannot assume tool execution.** Per D2, the hybrid engine starts as pure-prompt. The main prompt must be entirely doable by a model reading text. Tool orchestration (running Semgrep, etc.) lives in a separate layer that may or may not be present at runtime. A prompt that says "run `npm audit` and analyze the output" breaks this.

**Content is separate from orchestration.** Per D7, the rubric, schema, examples, and rule packs are standalone files. The prompt references them. When v2 promotes this to a skill, the skill wraps the orchestration; the content files travel along unchanged. If content gets baked into the prompt body, this commitment is broken.

**The JSON schema is the spine.** Per D4 and D6, every output flows from the schema. The report template renders from JSON, not the other way around. The eval harness reads JSON. CI integrations consume JSON. The schema is the artifact most expensive to change later — design it first, before writing the prompt.

**Category taxonomy is a closed enum.** Per D9, eval recall/precision can only be measured if findings categorize consistently. v1 ships with a fixed enum (proposed: the OWASP Top 10 categories plus a small set of additions for architecture/threat-modeling findings — see §8). The prompt must constrain the model to this enum; free-form category strings will sabotage eval down the line.

**Rule packs are discrete files.** Per D8, stack-specific guidance lives in `rules/python-web.md`, `rules/node-web.md`, etc. The main prompt has a defined slot for loading one or more rule packs. v1 ships with no rule packs (or one demonstrative one); the structure exists so packs can be added without surgery on the prompt body.

**Size budget is published, honest, and enforced.** Per D5, the README states the supported project size. The prompt's preflight step checks the size budget and tells the user when the project exceeds it, rather than silently producing degraded output.

**Runtime UX is optimized for the scan runner, not downstream readers.** Per D26, when a UX decision involves trading off between the convenience of the person executing the scan and the convenience of a hypothetical recipient, prefer the runner. The runner is the user we have today and the user we are explicitly building for; downstream readers will adapt or won't, but they aren't in the primary loop. Concrete instances: local time in filenames (not UTC), files on disk where they're easy to find (not buried), one-paste CTA (not a multi-command setup script). Future UX decisions apply this lens.

---

## 7. Data model

**JSON schema locked at v0.3.** The canonical per-scan contract lives in `schema.json` (JSON Schema Draft 2020-12) alongside this doc. The summary below is descriptive; the schema is authoritative.

**Eval / Pro database schema.** The eval DB is a separate layer from `schema.json` — it ingests `findings.json` envelopes and stores them in a relational form optimised for cross-run queries. Tables: `projects`, `scans`, `run_findings`, `canonical_findings`, `scorecards`, `data_profiles`, `ground_truth`. Two-layer finding model per D39. Projects as first-class entity per D40. Schema is SQLite-compatible but free of SQLite-specific idioms per D41. See `eval/db/schema.sql` when built.

**Finding object — required fields:** `id`, `category`, `severity`, `confidence`, `title`, `evidence`, `remediation`. **Optional fields:** `owasp_mapping`, `related_locations`, `exploitation_path` (conditionally required — see D13), `references`, `cvss`.

**Envelope structure.** Top-level keys: `schema_version` (const `"0.1"`), `scan` (timestamp, model, prompt_version, optional duration), `project` (name, files_scanned, size_budget_status, optional commit_hash and branch and stack_packs_loaded), `summary` (scorecard, counts_by_severity, counts_by_confidence), `findings`, optional `notes`.

**Schema-enforced discipline:** `exploitation_path` is structurally required when severity is critical/high OR category begins with `ARCH_` (per D13). The `cvss` object is only valid when `references` contains a string matching `CVE-\d{4}-\d+` (per D11) — preventing the model from authoring CVSS scores for non-CVE findings.

**Scorecard derivation:** Letter grades are computed from findings, not authored separately by the model. This avoids drift between narrative and data. (Algorithm to be defined when the prompt is written — likely a function of count-and-severity-weighted findings per domain.)

**ID stability:** `id` is derived as `sha1(category + "|" + evidence.file + "|" + evidence.line_start)[:8]`. Title is intentionally excluded (D44) — title phrasing varies across runs and model versions, which would break canonical deduplication (D39) and corroboration counting (D42). Category + file + line is the minimal stable identity: same vulnerability type, same location. The prompt specifies this construction so it is deterministic across model invocations and tool implementations.

---

## 8. Category taxonomy (locked v0.1)

22 categories. Hybrid structure per D14: domain-prefixed buckets are the primary spine; the four non-prefixed entries cover OWASP categories that don't have a clean domain equivalent. `OTHER` is the escape hatch and requires a `notes` entry on the envelope explaining why nothing else fit.

**Disambiguation rule.** When multiple categories could apply, pick the most specific. Domain-prefixed categories (CODE_*, DEP_*, SECRET_*, CONFIG_*, ARCH_*) take precedence over the named OWASP-aligned buckets. The `owasp_mapping` array exists for cross-referencing — a finding categorized as `ARCH_missing_authz` can still map to OWASP A01.

**Code-level (CODE_*)** — vulnerabilities at the level of specific code constructs.
- `CODE_injection` — SQL injection, command injection, XSS, template injection, etc.
- `CODE_crypto_failure` — weak algorithms, hardcoded keys, weak randomness, improper key management.
- `CODE_input_validation` — missing or insufficient validation/sanitization of untrusted input.
- `CODE_unsafe_api_use` — dangerous APIs used insecurely (unsafe deserialization, path traversal, race conditions, etc. — catch-all for code-level misuse).

**OWASP-aligned (non-prefixed)** — categories without a clean domain equivalent.
- `AUTHN_failure` — broken authentication mechanism at code level (weak password handling, broken session management, MFA bypass).
- `AUTHZ_failure` — broken authorization at code level (missing check at a specific point, role confusion).
- `INSECURE_DESIGN` — OWASP A04. Design-level flaws that aren't best described as architectural (e.g., business logic flaws).
- `INTEGRITY_failure` — OWASP A08. Software/data integrity failures (unsigned updates, untrusted plugin loading).

**Dependencies & supply chain (DEP_*)**
- `DEP_known_cve` — dependency has a published CVE.
- `DEP_supply_chain_risk` — typosquatting concerns, outdated/unpinned deps, suspicious package metadata.

**Secrets (SECRET_*)**
- `SECRET_hardcoded` — credential/key embedded in source.
- `SECRET_committed_history` — credential present in git history (even if removed from current code).
- `SECRET_logged` — credential leaked via logs or error messages.

**Configuration (CONFIG_*)**
- `CONFIG_insecure_default` — framework/runtime/cloud default left at an insecure setting.
- `CONFIG_excessive_permission` — IAM, file, process, or service permissions broader than necessary.
- `CONFIG_iac_misconfig` — Terraform/CloudFormation/Kubernetes/etc. manifest with insecure settings.

**Architecture & threat modeling (ARCH_*)** — the v1 differentiator. These trigger the higher evidence bar (required `exploitation_path`) per D13.
- `ARCH_trust_boundary` — trust boundary crossed without adequate validation/sanitization at the crossing.
- `ARCH_missing_authz` — endpoint class or whole subsystem lacks an authorization layer (distinct from `AUTHZ_failure` which is a code-level missed check).
- `ARCH_data_flow_risk` — sensitive data traversing an insecure path or persisted insecurely.
- `ARCH_attack_surface` — unnecessary attack surface exposed (debug endpoints in prod, internal-only services bound to public interfaces, etc.).
- `ARCH_logging_gap` — security-relevant events not logged, making detection and forensics impossible.

**Escape hatch**
- `OTHER` — for findings that genuinely don't fit; requires explanation in envelope `notes`.

---

## 9. v1 repo layout

```
inference-recon/
├── README.md                  # one-paste CTA + what this is, size budget, anti-scope
├── prompt.md                  # the orchestration — what Claude follows
├── rubric.md                  # the four domains, what to look for in each
├── schema.json                # JSON Schema for the findings envelope
├── report-template.md         # how JSON renders to markdown
├── render.py                  # findings.json → report.html (stdlib only)
├── examples/                  # worked examples (input snippet + expected output)
│   ├── 01-sql-injection.md
│   ├── 02-exposed-secret.md
│   ├── 03-missing-authz.md    # ARCH_* category example
│   └── 04-vulnerable-dep.md
├── demo-project/              # intentionally-broken Flask app for testing the tool
├── demo-output/               # captured scan of demo-project
├── rules/                     # stack-specific rule packs (empty or 1 starter in v1)
│   └── README.md              # how rule packs are structured
└── eval/                      # eval pipeline
    ├── batch_scan.py          # batch scanner: clone → collect → API → ingest
    ├── providers.py           # vendor SDK adapters: Anthropic / OpenAI / Google
    ├── ingest.py              # findings.json → Postgres (idempotent)
    ├── requirements.txt       # eval Python dependencies
    ├── Dockerfile             # shared image for ui + scanner services
    ├── corpus.md              # 12-app test corpus with per-run tracking tables
    ├── corpus/
    │   ├── repos.txt          # target repo list (one URL per line)
    │   ├── repos/             # clone cache (gitignored)
    │   └── findings/          # raw findings.json output (gitignored)
    ├── db/
    │   └── schema.sql         # Postgres schema — projects, scans, run_findings,
    │                          #   canonical_findings, scorecards, data_profiles
    ├── ui/                    # FastAPI web UI (7 views)
    │   ├── main.py
    │   ├── db.py              # read-only query helpers (Postgres + SQLite)
    │   ├── templates/         # Jinja2 templates
    │   └── static/
    └── sanity_check.py        # envelope self-consistency validator (planned)
```

The README states honestly: size budget, anti-scope, that this is a complement to and not a replacement for existing scanners, and the trust posture (model output is advisory and labeled with confidence; treat as a triage aid, not ground truth).

**Runtime output layout** (in the audited project, not in this repo):

```
<audited-project>/
└── security-review/
    ├── <project>-security-review-<YYYY-MM-DD>T<HHMM>.json
    ├── <project>-security-review-<YYYY-MM-DD>T<HHMM>.md
    └── <project>-security-review-<YYYY-MM-DD>T<HHMM>.html
```

Per D27/D28/D29. Users add `security-review/` to their project's `.gitignore`.

---

## 10. Risks

**R1 — Four-domain scope may produce shallow output per domain.** Asking a model to do SAST, supply chain, secrets, and threat modeling in one pass risks each being thinner than a focused pass would be. Mitigation: section the prompt into four sub-analyses, possibly serialized within a single prompt run, so each domain gets dedicated attention. Pilot whether one-pass or four-pass produces better findings before locking in.

**R2 — Trust death from false positives.** The self-audit persona is forgiving but not infinitely so. A first run that produces 40 findings of which 30 are noise will end the user's trust permanently. Mitigation: the confidence tier discipline (D6) must include a default report mode that suppresses low-confidence findings from the rendered output. Keep them in the JSON for power users; hide them by default.

**R3 — Size budget caps usefulness on real codebases.** Real-world projects routinely exceed any reasonable single-context budget. Today the answer is "out of scope." If feedback shows this is the dominant blocker, the response is map-reduce orchestration, which requires the skill form factor. Don't paper over with file truncation in the prompt — that produces silently degraded output, which is worse than a clean "too big" error.

**R4 — Stack-agnostic findings drift toward generic advice.** "Validate user input" is not a useful finding. The defense is the schema's evidence requirement (must quote actual code) and the few-shot examples. If early outputs trend generic, the answer is stack packs, not prompt tweaking.

**R5 — Architectural findings are the differentiator and the hardest to validate.** `ARCH_*` findings are where the LLM might genuinely add value over Semgrep — and also where hallucination risk is highest, because there's no static check to corroborate. Mitigation: `ARCH_*` findings carry a higher evidence bar (must describe a concrete data flow or trust boundary, not just "consider reviewing authn"). The exploitation_path field is non-negotiable for these.

**R6 — Model variation across Claude / Codex / Cursor / etc.** The prompt's promise is to work on any of these. They have different context windows, different instruction-following habits, and different JSON-mode capabilities. Mitigation: test on at least Claude and one other before declaring v1 done. Document any per-model adjustments needed.

---

## 11. Open questions

These are decisions deferred from the precheck conversation. Resolve before or during v1 build.

- [ ] **`scan.tool` field (schema v0.4).** `schema.json` captures `scan.model` and `scan.prompt_version` but has no field for which tool/environment produced the run. Without it, a Claude Code run and a Cursor run of the same project at the same prompt version are indistinguishable in the eval DB — multi-tool comparison queries are impossible. Add as an optional string field to `scan` in schema v0.4 alongside STRIDE. Proposed values: `claude-code`, `cursor`, `codex`, `windsurf`, `aider`, `copilot-agent`, `gemini-cli`, `ai-studio`, `other`.
- [ ] **Compliance posture.** Is OWASP / CWE mapping a v1 feature, or just a v1 architectural readiness (taxonomy aligned but no compliance-styled output)? Affects report template content but not schema.
- [x] ~~**Size budget magnitude.**~~ Resolved in D23. ≤150 files, ≤10k lines, ≤2k single file.
- [ ] **Target LLM(s) for v1.** Claude only, or also Codex / Cursor / others? Influences prompt length budget and which JSON-mode features can be relied on.
- [x] **Name.** Inference Recon. Rename sweep complete 2026-05-25.
- [ ] **License & distribution.** Public repo? MIT? Private until first eval pass is done?
- [ ] **One-pass or four-pass per scan.** Does the prompt execute the four domains in one go, or sequentially with explicit handoffs? Pilot before committing.
- [x] ~~**Severity vs. confidence in the scorecard.**~~ Resolved in D20. Both, multiplicatively (`severity_weight × confidence_weight`).
- [x] ~~**Scorecard derivation algorithm.**~~ Resolved in D20. Severity × confidence weighting with deterministic thresholds.
- [ ] **"Considered and dismissed" reasoning.** Should the envelope include an optional array showing what the model considered but chose not to flag (the "what is NOT a finding" content from the worked examples)? Pro: surfaces the model's negative reasoning, which is auditable. Con: schema surface + token cost. Possibly v0.2 of the schema.
- [ ] **Quality-bar document.** The worked examples currently double as quality anchors. As the example set grows, the "what makes this a quality finding" guidance probably belongs in a dedicated `QUALITY_BAR.md` file rather than repeated across examples.
- [ ] **`INTEGRITY_failure` scorecard bucket.** Placed in `code` per D18 because real examples are usually code-level (pickle.load on untrusted input, unsigned update download in code). But OWASP A08 framing is more architectural. If real scans surface findings where the placement feels wrong, move to `architecture` and update D18.
- [ ] **`OTHER` bucket default.** Currently rolls up to `architecture`. Defensible but not principled. Consider: should `OTHER` not count toward any specific bucket (only `overall`)? Or should the model be asked to nominate a bucket per finding when using `OTHER`?
- [ ] **Envelope sanity checker (eval artifact).** D20 made the scorecard derivable from the findings. A ~30-line script can verify any envelope's internal consistency: derived grades match asserted grades, counts match, IDs are derived correctly, conditional schema rules pass. Worth building as `eval/sanity_check.py` once the project repo materializes. Catches model drift between findings and summary cheaply.
- [ ] **Severity vs. confidence weighting in scorecard.** Already partly addressed by D20 (multiplicative). Open sub-question: do we want a separate "high-severity-only" sub-score? Some readers will want a "how bad is the worst thing" number alongside the bucket roll-up.
- [ ] **FP/FN comparison piece vs. Semgrep.** The FP and FN profiles of this tool and Semgrep are qualitatively different, not just quantitatively — worth writing up properly once corpus data exists to back it with numbers. The two-track corpus (D47) is designed to generate exactly this data: the Academic track enables direct comparison on recognized benchmarks (what did Semgrep find on NodeGoat vs. what did we find?); the Real World track shows class-specific gaps (Semgrep is silent on STR-01 / NJS-02 / SUP-02 by design — no rule covers contextual auth reasoning). Key analytical points: (1) Semgrep's FNs are structurally invisible and concentrated in exactly the vulnerability classes that cause breaches; this tool's FNs are probabilistic and distributed. (2) This tool's FPs come with auditable reasoning (exploitation_path, confidence tier); Semgrep's don't. (3) A Semgrep clean run creates false confidence by hiding its coverage gaps; this tool's uncertainty is always explicit. (4) This tool's FN rate decreases with corroboration; Semgrep's FP/FN profile is fixed at rule-write time. Analytically true, not just marketing — the corpus data will make it falsifiable and publishable.

---

## 12. Next moves (suggested order)

1. ~~**Ratify the JSON schema.**~~ ✓ Done. `schema.json` v0.1 locked. See D10–D15.
2. ~~**Write 2–3 worked examples by hand.**~~ ✓ Done. Four examples in `examples/` covering all four domains. All four findings validate against `schema.json`. No schema gaps surfaced; two new principles codified (D16 severity-vs-CVSS, D17 confidence calibration) and four new open questions added.
3. ~~**Draft the rubric.**~~ ✓ Done. `rubric.md` covers all 22 schema categories across the four domains, with cross-cutting principles, negative anchors per domain, and an authoritative category-to-scorecard mapping. Coverage check passes (every category mentioned in prose; every category mapped to exactly one bucket; no orphans, no duplicates). Two new decisions captured (D18 mapping, D19 order of analysis); two new open questions added.
4. ~~**Draft the report template.**~~ ✓ Done. `report-template.md` specifies rendering rules + the D20 scorecard derivation algorithm + a fully worked example (the four example findings rendered to markdown). Worked envelope validates against schema; derived grades match asserted grades; counts match. Three decisions captured (D20 scorecard algorithm, D21 production model — model emits both JSON and markdown, D22 low-confidence suppression in rendered report). Two open questions closed (scorecard algorithm, severity-confidence weighting).
5. ~~**Write the prompt.**~~ ✓ Done. `prompt.md` is the orchestration document (Steps 0–9, cross-cutting discipline, what-not-to-do directives, output contract). Stays cleanly separated from content per the §6 architectural commitment. Also wrote project `README.md`. Two decisions captured (D23 size budget thresholds, D24 in-prompt self-consistency check). One open question closed (size budget magnitude). **v1 scaffold is now complete** — 11 files matching the §9 repo layout exactly.

The remaining items are no longer scaffold authoring; they require running the tool on real code and iterating on quality. Treat as a separate work phase.

6. **Vibes-check on 2–3 of Mark's own projects.** Iterate.
7. **Curate a small golden set (5–10 small repos, mix of intentional-vuln and real).** Run, measure recall and precision, start a quality baseline.
8. **Compare against Semgrep on the same set.** Identify the differentiation in concrete terms.

---

## 14. Ops checklist automation horizon

The operator security checklist (`ops-checklist.md`) was deliberately positioned as a "responsibility handoff" — things a code review cannot assess. But "cannot assess today" and "cannot assess ever" are different claims. This section maps each checklist item to its automation horizon: what would need to exist to move it from a manual question to a verifiable check.

Four tiers, defined:

- **T1 — Current architecture.** Assessable today by the existing prompt reading source files. Already overlaps with existing finding categories (IaC, config, workflow files in repo) or can be added as new rubric entries without architectural changes.
- **T2 — Future skill + external tools.** Requires network queries, external API calls, or lightweight tooling (DNS lookup, GitHub API, cert check) but no server access. Buildable as a skill-form-factor enhancement alongside the existing code review.
- **T3 — Different app, different architecture.** Requires persistent agent access to live infrastructure: SSH to a server, cloud provider API with appropriate IAM, or active network scanning. This is a materially different product than a code reviewer — a continuous compliance agent or infra audit tool.
- **T4 — Meatspace only.** Requires organizational knowledge, human testimony, or physical verification. Logically or literally airgapped from any automated system. These items can be prompted but never verified programmatically.

### Infrastructure

| Checklist item | Tier | Mechanism / blocker |
|---|---|---|
| TLS enforces TLS 1.2+; TLS 1.0/1.1 disabled | T1 (partial), T2 (live) | **T1:** If server config is in-repo (nginx.conf, Caddyfile, Apache vhost) — detectable as `CONFIG_insecure_default`. **T2:** Live endpoint → ssllabs API or `testssl.sh`; objective pass/fail. |
| Server OS is patched and on a supported version | T3 | SSH + `uname -r`, `cat /etc/os-release`, `apt list --upgradeable`. Requires authenticated server access. |
| SSH: key-based auth only; password auth disabled | T1 (partial), T3 (live) | **T1:** If `sshd_config` is in-repo or in Ansible/Chef config — readable now. **T3:** SSH + `grep PasswordAuthentication /etc/ssh/sshd_config` on live server. |
| Firewall: only 80/443 public; DB ports closed | T1 (partial), T2/T3 | **T1:** IaC security groups already in `CONFIG_iac_misconfig` scope. **T2:** Cloud provider API can enumerate security group rules without server access. **T3:** Active port scan. |
| Database not publicly accessible | T1 (partial), T2 | **T1:** `publicly_accessible = true` in Terraform RDS → `CONFIG_iac_misconfig`. **T2:** Cloud API (RDS `PubliclyAccessible` attribute). |
| Database connections encrypted in transit | T1 | Connection strings in code often expose `sslmode=` / `ssl:` flags. Lack of `sslmode=require` on a Postgres connection string is findable today → `ARCH_data_flow_risk`. |
| Data at rest encrypted | T1 (partial), T2 | **T1:** `encrypted = false` on Terraform EBS/RDS → `CONFIG_iac_misconfig`. **T2:** Cloud API (`DescribeVolumes`, `DescribeDBInstances`). |
| Backups exist, encrypted, separate, restore tested | T1 (existence only), T4 (tested) | **T1:** Backup config blocks in IaC (e.g., `backup_retention_period`) are readable. **T4:** Whether a restore has actually been executed and validated is a human act — no automated proxy exists. |

### Access & Secrets

| Checklist item | Tier | Mechanism / blocker |
|---|---|---|
| MFA on cloud provider / GitHub / registrar accounts | T2 (GitHub), T4 (others) | **T2:** GitHub API `GET /orgs/{org}/members?filter=2fa_disabled` returns MFA-disabled members. **T4:** Cloud provider and registrar MFA status is not externally queryable — console-only. |
| SSH keys attributed to individuals; no shared keys | T3, T4 | **T3:** SSH + read `~/.ssh/authorized_keys` on the server, cross-reference against known employee keys. **T4:** "No shared keys" requires organizational knowledge about how keys were provisioned. |
| Secrets in vault, not on disk/chat/email | T1 (code/disk), T4 (chat/email) | **T1:** Hardcoded secrets and `.env` files in repo → `SECRET_hardcoded` already. **T4:** Secrets in Slack history, email, or a dev's terminal buffer cannot be audited by any tool. |
| Former team members' access revoked | T2 (partial), T4 | **T2:** GitHub org members and collaborators are enumerable via API — but determining who *should* no longer have access requires knowing who left, which is organizational knowledge. |
| API keys scoped to least privilege | T1 (IaC), T2 (live) | **T1:** `*:*` IAM policies in Terraform → `CONFIG_excessive_permission` already in scope. **T2:** Cloud IAM API can enumerate live policy attachments and flag overly broad permissions. |

### Build Pipeline

| Checklist item | Tier | Mechanism / blocker |
|---|---|---|
| Main branch has push protection | T2 | GitHub API `GET /repos/{owner}/{repo}/branches/{branch}/protection` — directly checkable. Low-effort T2 win. |
| CI/CD secrets not hardcoded in workflow files | T1 | `.github/workflows/*.yml` files are source — already in `SECRET_hardcoded` scope. Secrets in workflow env blocks are findable today. |
| CI/CD actions pinned to specific versions | T1 | Workflow files are source. `uses: actions/checkout@main` vs `@v4.1.1` is a string match in-repo. New rubric entry (`CONFIG_insecure_default` or a new DEP category) — no architectural change needed. |
| Dependency update PRs reviewed before merge | T2, T4 | **T2:** GitHub API can check Dependabot auto-merge settings and whether recent Dependabot PRs were merged without human review (check for approved reviews). **T4:** Whether the review was substantive rather than rubber-stamped is a human judgment. |

### DNS & Domain

| Checklist item | Tier | Mechanism / blocker |
|---|---|---|
| Registrar has MFA + transfer lock | T4 | Registrar accounts have no external API exposing MFA or transfer-lock status. Registrar-specific console only. This one never moves out of T4 unless registrars build an audit API (none currently do). |
| No dangling DNS records | T2 | DNS query tool + enumeration of known cloud provider hostname patterns (Heroku `.herokuapp.com`, Netlify `.netlify.app`, GitHub Pages `.github.io`, etc.). Dangling CNAME detection is a solved problem in external tooling (dnsreaper, subjack) — straightforward T2 skill addition. |
| SSL certificate expiry monitored | T2 | `openssl s_client` or an HTTPS request to extract cert expiry. Detecting *whether alerting is configured* is harder (T4), but detecting *current expiry margin* is instant. |
| SPF / DKIM / DMARC configured | T2 | DNS TXT record lookups for `v=spf1`, `v=DKIM1`, `v=DMARC1` on the domain. Entirely external, no auth needed. Lowest-effort T2 item on the whole list. |

### Monitoring & Response

| Checklist item | Tier | Mechanism / blocker |
|---|---|---|
| Logs collected and retained | T1 (IaC config), T3 (flowing) | **T1:** CloudWatch / Stackdriver config in IaC is readable. **T3:** Whether logs are actually ingesting requires querying the logging backend — no proxy in source code. |
| Alerting on auth failures, anomalies, admin actions | T1 (partial), T3 | **T1:** Alert rule definitions in IaC (CloudWatch Alarms in Terraform) are readable — but only if they're in the repo. **T3:** Live cloud API to enumerate alarm state. |
| Kill switch procedure known and practiced | T4 | Procedure lives in people's heads or a runbook. "Known" cannot be verified externally. "Practiced" requires a human to have actually done it. |
| Incident playbook exists and is current | T1 (weak), T4 | **T1 (weak):** Can check for `SECURITY.md`, `runbooks/`, `incident-response.md` in repo — existence signal only. **T4:** Whether it reflects current reality and has been rehearsed is a human judgment. |
| Hosting provider security contact known | T4 | Organizational knowledge. No programmatic proxy. |

### Third-Party Services

| Checklist item | Tier | Mechanism / blocker |
|---|---|---|
| Third-party services receiving user data reviewed | T1 (identification), T4 (reviewed) | **T1:** Imports, API clients, outbound HTTP calls in source can identify *what* third parties are integrated. **T4:** Whether each has been assessed for security posture is a human judgment — the tool can surface the list, not the verdict. |
| OAuth scopes minimized | T1 | Scope strings in OAuth configuration code (`scope: "write:all"` vs `"read:profile"`) are readable. Flaggable today under `CONFIG_excessive_permission`. |
| Webhooks validate request signatures | T1 | Webhook handler code is readable — presence or absence of HMAC signature checks is a code pattern. Already in scope as `ARCH_trust_boundary`. |
| Process for learning about provider breaches | T4 | Organizational process. No code artefact, no external signal. |

### Human Factors

| Checklist item | Tier | Mechanism / blocker |
|---|---|---|
| No shared credentials | T1 (weak), T4 | **T1 (weak):** Hardcoded credentials shared across multiple contexts might be detectable — but "shared" as an organizational practice is not visible in source. **T4:** Fundamentally relies on human testimony or observation. |
| SSH keys passphrase-protected on dev machines | T4 | Would require read access to developer machines — invasive, impractical, and arguably should never be automated. |
| Formal offboarding checklist exists and is followed | T1 (weak), T4 | **T1 (weak):** Can check for the document's existence in repo. **T4:** Whether it's actually run at each departure is an HR/ops process, not a code artefact. |

### Summary by tier

**T1 — Actionable in current architecture (add to rubric or already covered):**
TLS config in server config files, database connection TLS, IaC encryption-at-rest, IaC firewall/security groups, IaC database public access, hardcoded secrets in CI/CD workflow files, CI/CD action version pinning, OAuth scope strings in code, webhook signature validation in code, IAM least-privilege in IaC, logging config in IaC (existence only), third-party integration identification.

The CI/CD action version pinning item is the most actionable gap — it's not currently in the rubric but is trivially checkable from workflow files. Candidate for a new rubric entry under `CONFIG_insecure_default` or a `DEP_supply_chain_risk` variant.

**T2 — Buildable as a skill enhancement with external tool access:**
Live TLS quality (ssllabs/testssl), SSL certificate expiry, SPF/DKIM/DMARC DNS records, dangling CNAME detection, GitHub branch protection rules, GitHub org MFA status, cloud IaC vs. live-state drift (IAM, security groups, RDS public access). The DNS and GitHub items are the lowest-friction T2 additions — both have clean APIs and no auth complexity for public repos.

**T3 — Requires a different product (continuous compliance agent, infra audit tool):**
Server OS patch status, live SSH config, live firewall state, database port reachability, SSH key attribution on servers, whether logging is actually flowing, backup existence in live cloud state. This tier is essentially a server/cloud audit agent — categorically different from a code reviewer, probably built on an authenticated cloud/SSH session rather than a code context.

**T4 — Meatspace only, never automatable:**
Domain registrar MFA and transfer lock, whether a restore has been tested, former team member access (requires knowing who left), kill switch procedure practiced, incident playbook rehearsed, provider security contact known, process for provider breach notifications, no-shared-credentials as an organizational practice, SSH keys passphrase-protected on dev machines, offboarding checklist actually followed. These are inherently human answers to human questions — the checklist can prompt them, but no tool can verify them.

---

## 15. Stochasticity, determinism, and the nature of security confidence

### Origin: what this tool turned out to be

This tool started as a practical idea: a fast, AI-native way to do what static analyzers do, fitting naturally into the way people actually write software today. Useful, but not a new idea — Semgrep with an LLM wrapper, essentially.

That framing turned out to be backwards. The shift from rule-based to reasoning-based security analysis isn't "same job, new engine." It's a change in the underlying epistemology of what the tool claims to know. Rule-based scanners trade completeness for certainty — they only assert what they can prove mechanically and stay silent on everything else. The silence looks like safety but is actually a blank space where the interesting vulnerabilities live. This tool does the opposite: it reasons across the whole surface, attaches explicit confidence to every claim, and treats uncertainty as information rather than something to hide. That's not a Semgrep clone. It's the inverse of the model Semgrep is built on.

The sections below work out the mechanics of why stochasticity is the honest representation of what security analysis actually is — and why the corroboration machinery is the right way to accumulate confidence from it over time.

### The apparent problem

Security has a determinism fetish. The foundational question is binary: *am I vulnerable or not?* The foundational event is binary: *was I breached or not?* Traditional static analysis tools have traded on this framing — Semgrep fires or it doesn't. A CVE either applies to your package version or it doesn't. The output is a list of facts, not a distribution.

An LLM-based scanner breaks this framing visibly. Run the same prompt on the same codebase twice and you will get different findings. The model might phrase a title differently, surface findings in a different order, add a finding on one run that it missed on another. For users raised on deterministic tools, this looks like a bug. It feels like the tool is guessing.

**The two layers of non-determinism:**

1. **Content variation.** The same vulnerability may be found on one run and missed on another. Confidence assignments may shift. Severity rationale may differ in detail even when the severity grade matches.

2. **ID instability.** If the finding ID is derived from content that varies — including the title — then a finding that appears on every single run gets a *different* ID on each run. The canonical deduplication machinery (D39, D42) sees it as a new finding each time. This is a mechanical problem with a mechanical fix (D44), but it only matters because of layer one.

### The deeper insight: traditional determinism was an illusion

The framing is wrong. Security judgment was never deterministic — the appearance of certainty was a product of the narrow scope tools chose to cover.

Semgrep fires on `cursor.execute("SELECT * FROM users WHERE id = " + user_id)`. It does not fire when the string interpolation happens across two function calls, when the ORM adds a thin layer of abstraction, when the SQL is built differently in different code paths, or when the real risk is that a nominally-parameterized query passes the whole user object in a way the ORM doesn't escape. These are the cases that actually get exploited. A tool that only flags the textbook pattern gives the developer *false confidence* that the non-textbook patterns were checked and cleared.

The apparent determinism of rule-based scanners is really **scope limitation dressed as certainty**. They commit to only the cases they can assess with perfect reliability — and quietly produce zero output on everything else. The result is not "no vulnerabilities found of this type." The result is "no vulnerabilities of this type found *that match our rules.*" These are completely different statements, and the latter is exactly what a sophisticated attacker exploits.

### LLMs make the probability explicit

An LLM-based scanner does what a senior security engineer does: it reasons about the code with contextual judgment. It considers: what is this variable's provenance? Does this ORM actually prevent injection in this usage pattern? Is this admin endpoint reachable without authentication given how the route registration works? A good engineer can answer these questions. A rule engine categorically cannot — it doesn't have the representation.

The cost is that this reasoning is probabilistic. The same engineer on a different day, with a different coffee, might miss a finding they'd catch the next day. They might phrase a concern differently. They might weigh a borderline case differently under time pressure. We do not say the engineer is broken. We say they are human. We handle this by having multiple engineers review high-stakes code, by having the reviewer justify their findings in writing (the `exploitation_path` requirement), by treating "no finding" as a signal that carries uncertainty.

The LLM is doing the same thing. The stochasticity is not a defect to be fixed — it is the honest representation of a probabilistic judgment process that was always probabilistic, just previously hidden.

### Corroboration as the frequentist answer

The right response to stochasticity is not to demand a deterministic output (you cannot get one without discarding the contextual reasoning that makes the tool valuable). The right response is to **take multiple samples and extract a frequentist signal from them.**

This is what the corroboration machinery (D42) does. When Claude Code finds `finding_id X` and Cursor independently finds `finding_id X`, the probability that X is a real vulnerability is substantially higher than when only one tool found it. When three tools agree, higher still. The `canonical_findings.corroboration_count` field is not administrative metadata — it is the primary confidence signal at scale.

The implication: **a single scan run is a point sample from a distribution, not a ground truth statement.** A finding with `confidence: medium` on a single run is more actionable than zero findings — but a finding with `confidence: high` corroborated by three independent tool runs is close to ground truth. The eval infrastructure is designed specifically to accumulate these samples over time.

### Finding ID stability as a prerequisite

For corroboration to work, the same vulnerability must produce the same finding ID across runs and tools. This requires the ID to be derived from information that is stable and tool-agnostic: the vulnerability's location in code (file and line) and its type (category). Title is excluded (D44) precisely because it varies. The result is a hash over `category + file + line_start` — the minimal stable identity.

This is a known tradeoff: a category mismatch (one tool calls it `CODE_injection`, another calls it `CODE_unsafe_api_use`) will produce non-matching IDs even if both tools found the same problem. Category is more stable than title but still not perfectly invariant. Over time, as the taxonomy matures and models converge on consistent categorization, the false-non-match rate will fall. For now, the occasional category disagreement means we *under-count* corroboration — we see two findings where there is conceptually one. This produces false negatives in the corroboration signal, which is the conservative failure mode: we underestimate confidence when tools agree but disagree on category. We do not overestimate confidence when they genuinely disagree. That asymmetry is acceptable.

### Product implications

**Communicating uncertainty.** The tool's output is explicitly probabilistic. The `confidence` field is not a binary flag — it is a calibrated estimate. The rendered report suppresses `low`-confidence findings from the default view (D22). Future versions should communicate the sampling context: "Based on 3 independent scans, corroboration count: 2" means something meaningfully different from "Based on 1 scan, corroboration count: 1." The UI for this doesn't exist yet; the data model already supports it.

**Re-scan semantics.** "The model didn't find it" does not mean "it's not there." A re-scan with a different model, different model tier (Haiku vs. Sonnet), or a different day may surface findings missed in prior runs. The scan-time `confidence` field captures within-run certainty; corroboration count captures cross-run confirmation. Both signals matter. Neither alone is a verdict.

**Model tier guidance.** Haiku-class models run in ~30 seconds and catch critical and high-severity findings reliably. Sonnet-class models run in ~10 minutes and surface the full finding set including subtle architectural issues. The model choice note in the standalone prompt exists because this is a meaningful tradeoff — a Haiku run is a fast, inexpensive point sample; a Sonnet run is a more thorough sample. Multiple Haiku runs are cheap and can approximate the coverage of a single Sonnet run with the added benefit of corroboration signal.

**Reframing the core thesis.** Traditional scanners traded on the illusion of determinism. This tool does not. The honest framing: *we produce probability estimates about the presence of vulnerabilities, grounded in contextual code reasoning, with explicit confidence tiers, designed to accumulate corroboration signal across runs and tools.* This is not a weaker claim than "Semgrep says there's no SQL injection." It is a more honest and ultimately more useful one — because it accounts for the cases Semgrep's rules don't cover, labels its uncertainty explicitly, and gets more confident over time as evidence accumulates.

---

| Date | Version | Change |
|---|---|---|
| 2026-05-23 | v0.1 | Initial draft from precheck conversation. |
| 2026-05-23 | v0.2 | Locked `schema.json` v0.1. Added decisions D10–D15 (evidence shape, severity model, repro metadata, exploitation_path required-when rules, category taxonomy structure, OWASP cross-reference field). Updated §7 to point to the schema as canonical; rewrote §8 with the locked 22-category enum. |
| 2026-05-23 | v0.3 | Wrote four worked examples in `examples/` covering all four domains; all findings validate against the schema. Added D16 (severity vs. CVSS semantics) and D17 (confidence calibration). Added four new open questions: scorecard algorithm, considered-and-dismissed reasoning, quality-bar doc, severity/confidence weighting in scorecard. |
| 2026-05-23 | v0.4 | Drafted `rubric.md` covering all four domains (cross-cutting principles, per-domain patterns, negative anchors, authoritative category-to-scorecard mapping, order of analysis). Coverage check passes — every schema category referenced in prose and mapped to exactly one bucket. Added D18 (category-to-scorecard mapping) and D19 (order of analysis). Added two new open questions about `INTEGRITY_failure` and `OTHER` bucket placement. |
| 2026-05-23 | v0.5 | Drafted `report-template.md` with rendering rules + the D20 scorecard derivation algorithm + a fully worked example. Envelope validates against schema; all derived grades match. Added D20 (scorecard derivation algorithm), D21 (model emits both JSON and markdown), D22 (low-confidence suppression in rendered report). Closed two open questions (scorecard algorithm, sev-vs-conf weighting). Added one new open question (envelope sanity checker as eval artifact). |
| 2026-05-23 | v0.6 | Drafted `prompt.md` (orchestration) and project `README.md`. Added D23 (size budget thresholds) and D24 (in-prompt self-consistency check, interim solution for the envelope sanity checker until the standalone script lands). Closed the size budget open question. v1 scaffold is feature-complete: all 11 files from the §9 repo layout are present (1,823 lines total). The remaining work is no longer authorship — it's running the tool on real code and iterating on findings quality. |
| 2026-05-24 | v0.7 | Locked the runtime UX. Added seven decisions: D25 (one-paste CTA into Claude Code with persistent dotdir clone path), D26 (persona positioning — optimize for the scan runner), D27 (three durable artifacts — json/md/html — written to disk plus a markdown summary in chat), D28 (flat `./security-review/` layout, no timestamp subdir), D29 (filename convention — `<project>-security-review-<YYYY-MM-DD>T<HHMM>.<ext>`, local time, minute precision), D30 (JSON envelope timestamp ISO 8601 with offset), D31 (Python `render.py` for HTML, static + stdlib only). Added a fourth architectural commitment to §6 (runtime UX optimized for the scan runner). Updated §9 to add `render.py` and the runtime output layout. Open follow-up work: write `render.py`, rewrite `prompt.md` Step 8, rewrite README quick-start, smoke-test against `demo-project/`. |
| 2026-05-24 | v0.9 | Added data sensitivity profiling. Schema bumped to v0.2 with new required `data_profile` object (sensitivity_tier enum, categories array with evidence, regulatory_flags array). New decisions: D32 (data profile is a first-class envelope field, not report narrative), D33 (soft escalation — data tier influences severity calibration via rubric guidance, not hard schema rules), D34 (data profile produced in new Step 1.5, before any findings passes, so it can inform severity throughout), D35 (regulatory flags assess all plausible regulations explicitly, including `unlikely` verdicts, to show the assessment was made not skipped). New rubric §8 covers detection signals, tier definitions, soft escalation rules, and regulatory applicability thresholds. Report template §3 specifies Data Profile section rendered before the Scorecard. |
| 2026-05-24 | v0.8 | Added ops checklist and automation horizon analysis. Created `ops-checklist.md` (reference doc for the 33 checklist items across 7 categories). Added `report-template.md` §12 specifying the static operator checklist appendix emitted in every report (was §10 before DFD and data profile sections were inserted ahead of it). Updated `prompt.md` Step 9 to instruct the model to always emit the checklist. Added §14 (ops checklist automation horizon) classifying all checklist items into T1–T4 tiers. Key finding: 12 items are T1 (current architecture, mostly already in rubric scope or trivially addable), 8 are T2 (skill + external tools, with DNS and GitHub API as lowest-friction wins), 7 are T3 (infra audit agent, a categorically different product), and 6 are permanently T4 (organizational knowledge, never automatable). CI/CD action version pinning flagged as the highest-value T1 gap not yet in the rubric. |
| 2026-05-24 | v1.2 | Release process documented. D43: two-repo distribution strategy (private dev + public release artifact, no git relationship). `RELEASE.md` created with public file manifest and pre-release checklist. `scripts/release.sh` automates the copy-commit-tag-push workflow. `README.public.md` placeholder created. `.gitignore.public` created (shipped to public repo as `.gitignore`). |
| 2026-05-25 | v1.6 | Stack-specific rule packs. D46: rule pack strategy — target the vibe coder SaaS power law by inverting the LLM build model (what AI assistants generate → where it's insecure). First pack: `rules/nextjs-supabase.md` — 13 rules covering Supabase (service role key exposure, RLS, storage), Next.js (NEXT_PUBLIC_ secrets, Server Action auth, IDOR, middleware bypass), Stripe (webhook signature, client-controlled pricing, fulfillment ordering), AI integrations (provider key exposure, rate limiting), and general multi-tenant IDOR. `prompt.md` extended with Step 1.1 (rule pack loading — stack detection → file read → rules active for all subsequent steps). `prompt-standalone.md` extended with inlined rule pack conditioned on stack detection (no filesystem access required). `rules/README.md` rewritten from placeholder to actual contract. `project.stack_packs_loaded` schema field was already present; now actively populated. D48: rule pack entry bar — a rule encodes stack-specific domain knowledge the baseline rubric cannot have (e.g. Supabase role key semantics, Stripe webhook trust model). It is NOT a new vulnerability class. If the baseline rubric would catch the finding anyway, the rule doesn't belong in the pack. Pack value is recall and calibration on stack-specific manifestations, not discovery. Generic packs (current) → free tier. Deep corpus-iterated packs → Pro tier. Pack value erodes as frontier models absorb stack knowledge; Pro packs stay ahead by going deeper and more specific. The corpus is the mechanism. |
| 2026-05-25 | v1.5 | Eval harness + web UI. `eval/batch_scan.py`: batch scanner with clone-on-demand (`depth=1`), file budget enforcement (150 files / 10k lines / 2k per file), binary sniffing, stack auto-detection, `--dry-run` token estimate, structured summary output. `eval/providers.py`: direct vendor SDK adapters for Anthropic, OpenAI, Google (D45 application — zero intermediary). `eval/ui/`: FastAPI + Jinja2 web UI with 7 views (dashboard, corpus, scan runner with SSE live log, project detail, scan detail, finding detail, compare). `docker-compose.yml` extended with `ui` (always-on) and `scanner` (profile-gated) services. `DOCKER.md` updated for the full five-service stack. `eval/README.md` rewritten from placeholder to full harness reference. Bug fix: Starlette 0.36+ changed `TemplateResponse` signature — `request` is now first positional arg; all 9 call sites updated. |
| 2026-05-25 | v1.4 | Dependency security policy. D45: high bar for codebase dependencies — official vendor SDKs and well-understood infrastructure only; no intermediary libraries in any path that touches user code, API keys, or scan output. Immediate application: replaced LiteLLM with direct vendor SDK adapters in `eval/providers.py` (~130 lines, zero intermediary). `eval/requirements.txt` trimmed to five first-party packages. Principle documented for all future dependency decisions. |
| 2026-05-25 | v1.3 | Epistemological reframe. Rewrote §2 (product definition): the tool is not "Semgrep with AI" but the inverse of the rule-based model — reasoning across the full surface with explicit confidence rather than achieving false certainty through scope limitation. Added D44 (finding ID stability: drop `title` from hash, derive ID from `sha1(category + "\|" + file + "\|" + line_start)[:8]`). Added §15 (Stochasticity, determinism, and the nature of security confidence): origin story, why traditional scanner determinism was an illusion, why stochastic reasoning is strictly more honest and more complete, corroboration machinery as the frequentist answer, product implications (re-scan semantics, model tier tradeoffs, confidence communication). Updated examples/README.md and all example finding IDs to the new hash. Updated ROADMAP.md finding ID stability item to resolved. |
| 2026-05-24 | v1.1 | Data strategy decisions added. D39: two-layer finding model (run_findings + canonical_findings). D40: projects as first-class entity. D41: SQLite for eval / Postgres for Pro — same schema. D42: cross-tool finding corroboration as primary confidence signal at scale. §7 updated to reference the eval DB schema. §9 eval directory expanded to show planned artifacts. Open question added for `scan.tool` field (planned for schema v0.4). |
| 2026-05-24 | v1.0 | Added Level 1 DFD to the findings envelope. Schema bumped to v0.3 with new required `threat_model` object containing `dfd.mermaid` (Mermaid flowchart source) and optional `dfd.notes`. New optional `dfd_element` field on findings for future diagram-to-finding cross-referencing. New decisions: D36 (DFD as first-class envelope field — the tool's highest-impact wow moment), D37 (Mermaid format + jsDelivr CDN rendering, narrow intentional deviation from D31's no-JS rule, noscript fallback preserves offline usability), D38 (Level 1 only, one diagram per scan, STRIDE deferred — target audience is first-time DFD viewers, simplicity wins). D31 updated to document the CDN exception. Changes across all five core files: `schema.json` v0.3 with `threat_model` required field; `rubric.md` §9 DFD construction guidance (node types, Mermaid conventions, simplification principles, trust boundary placement); `prompt.md` Step 5.5 build DFD after inventory, before findings passes; `report-template.md` §3 System Map now the first content section (before Data Profile and Scorecard); `render.py` full rewrite adding `render_dfd()` with mermaid.js CDN integration and noscript fallback, `render_data_profile()`, `dfd` badge on findings, updated rendering order. |
