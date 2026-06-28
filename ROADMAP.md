# Inference Recon — Roadmap

**Last updated:** 2026-05-26
**Status:** Pre-v1. Eval infrastructure complete. VAmPI calibration locked. Track 1 corpus scanned, twitterbio triaged. Immediate focus: thesis validation (chatbot-ui triage + Semgrep comparison) → prompt-only alpha release. Skill form factor deferred until after release.

This document captures the product tier model, feature ownership, near-term priorities, and Pro-tier foundations that need to be laid at the schema/architecture level before Pro ever ships. It is not in the scan-time model context (see `design-doc.md` for that distinction).

---

## Tier model

Three tiers. The boundary rule: **if it requires infrastructure, it's Pro.** Artificial feature gates (capped finding counts, watermarked reports, disabled categories) are explicitly off the table — they make the lower tiers feel broken and destroy trust.

### Free — public GitHub prompt

The always-free, always-open-source tier. Paste the prompt into Claude (or any capable model), share the code, get the report. No accounts, no hosted service, no cost to the user beyond their own LLM subscription.

- Hard limits set by model context windows (D23: ≤150 files, ≤10K lines, ≤2K per file)
- Single-pass analysis — one context, one scan
- Outputs: `findings.json`, `report.md`, `report.html` written to `./security-review/`
- All finding categories, all schema fields, all report sections — nothing gated
- Stack rule packs: generic packs (python-web, node-web, etc.) stay free and open-source
- `render.py` is bundled and open-source

### Skill — Claude Code integration

Better UX, not better capability. Wraps the free-tier analysis engine in a polished Claude skill form factor. Still free. The adoption funnel — makes the tool smooth enough that developers reach for it habitually, which builds the user base that Pro eventually sells into.

- One-paste CTA → skill clones repo, reads prompt, runs scan, writes files, auto-runs `render.py`
- Same analysis engine and same size limits as Free
- Same schema, same output format
- Open-source wrapper, free to use

Differentiator vs. Free: convenience. A developer who ran the free tier once will use the Skill tier on every project.

### Pro — hosted service

Where genuinely new capability lives — things that are architecturally impossible at the lower tiers, not things arbitrarily withheld. Requires a hosted backend. Paid tier.

| Feature | Why it can't be Free/Skill |
|---|---|
| CI/CD integration (GitHub Actions, GitLab CI, PR comments) | Requires a hosted service to receive webhooks and post back to the VCS. Not a prompt. |
| Large codebase support (>150 files, map-reduce) | Multiple model calls with orchestration state. Physically impossible in a single context pass. |
| Persistent findings tracking (open/closed, re-surfaced) | Requires a database and `finding.id` identity across scans. No persistence = no history. |
| Security posture trends over time | Same — requires history. |
| Diff-aware scanning (scan only changed files) | Requires stored previous-scan state + git integration. |
| External tool orchestration (Semgrep, Trivy, gitleaks, etc.) | Requires a server-side execution environment. |
| Team features (shared findings, assignment, audit trail) | Multi-user anything requires accounts and a backend. |
| Curated deep rule packs (rails-enterprise, java-spring-fintech) | Ongoing curation and maintenance work justifying ongoing payment, unlike generic packs. |
| API access (programmatic findings ingestion) | Requires a stable, versioned, hosted API endpoint. |
| Benchmarking / peer comparison | "You are in the bottom 10% of Flask apps for secrets hygiene." Requires a project corpus at sufficient scale to compute meaningful percentile distributions. Stack classification and sensitivity tier are already produced by every scan — the infrastructure is built at eval scale; the value compounds as corpus grows. |
| Vulnerability database + responsible disclosure workflow | Canonical findings deduplicated across runs, with lifecycle tracking (first seen, fixed, re-introduced) and per-finding disclosure status. At scale (hundreds of public repos), becomes a first-party vuln intelligence asset. Responsible disclosure workflow hangs off the canonical finding record. |

---

## Alpha standalone prompt ✅

**Status: Shipped.** `prompt-standalone.md` — self-contained single-file paste prompt (~310 lines). Includes inlined nextjs-supabase rule pack (Step 1.1, conditioned on stack detection). User pastes into Claude.ai or any capable chat UI, pastes code, gets findings in chat. No install, no CLI, no Docker.

Validated on vulnado and VAmPI via Claude Code. Not yet tested in pure paste mode via Claude.ai — that's the next validation step for this track.

---

## Near-term priorities

### Active — thesis validation → prompt-only alpha release

The core question that has been deferred too long: does the thesis hold? LLM-based scanning needs to demonstrably find real things that static tools miss on real SaaS stacks, or the pitch isn't earned. This is the gate before any public release. Once the thesis is confirmed, the prompt-only alpha ships immediately — the release infrastructure is ready.

**Step 1 — Prove the thesis:**

- [ ] **Triage chatbot-ui.** The meaningful benchmark. Complex auth/RLS surface, Supabase + Next.js, real multi-user app. Run haiku/opus scans (only sonnet exists), triage all three, write `eval/triage_chatbot_ui.py`. Expected to differentiate tiers on recall in a way twitterbio couldn't.
- [ ] **Semgrep comparison.** Run Semgrep against chatbot-ui and twitterbio. Compare side-by-side: what does each find that the other doesn't? This is the differentiation claim made concrete — the core of the public pitch. Required before release.

**Step 2 — Validate the release artifact:**

- [ ] **Validate `prompt-standalone.md` in pure paste mode.** Test via Claude.ai paste with a real project (chatbot-ui is a natural candidate). The standalone prompt has never been tested end-to-end in the paste flow it's designed for.

**Step 3 — Ship:**

- [ ] **Create public repo.** `gh repo create` + set `PUBLIC_REPO_URL` in `scripts/release.sh`. Update `inference-recon-staging` placeholder in `README.public.md`.
- [ ] **Run `scripts/release.sh`.** Pre-release checklist in `RELEASE.md`. The mechanics are ready; this is a one-hour task once steps 1–2 are done.

---

### Queued — after alpha release

- [ ] **Triage remaining Track 1 repos.** nextjs-subscription-payments, taxonomy, next-saas-stripe-starter. roomGPT and vulnado scans show $0 cost — investigate before triaging (possible empty/aborted runs).
- [ ] **Run Track 2 (Academic) — NodeGoat.** Best-documented ground truth. Establishes recall baseline for Semgrep comparison on an academic benchmark.
- [ ] **`eval/sanity_check.py`.** ~30-line envelope validator. Deferred since D24.
- [ ] **Additional rule packs.** `firebase.md`, `fastapi-python.md`, `stripe.md`. Bar: validated against at least one real project before shipping.
- [ ] **STRIDE annotations (schema v0.4).** Optional STRIDE table per DFD node. Alongside `scan.tool` field.
- [ ] **Skill form factor (Claude).** Deferred until after prompt-only alpha is live and validated by real users. Wrapping an unvalidated thesis in a polished form factor is premature investment.

- [x] **Multi-model / multi-IDE compatibility.** Research complete. `COMPATIBILITY.md` (13 tools), `prompt-analysis-only.md`, multi-tool ingest. Validation testing against corpus remains.
- [x] **Product name → Inference Recon.** Name decided. Rename sweep complete. DB name (`inference_recon`) and `prompt_version` values set.

---

## Completed milestones

### Eval infrastructure (2026-05-25)

Full eval pipeline from source → findings → database → UI.

- `eval/batch_scan.py` — batch scanner: clone-on-demand (depth=1), file budget enforcement, stack auto-detection, `--dry-run` token estimate, multi-vendor output
- `eval/providers.py` — direct vendor SDK adapters: Anthropic, OpenAI, Google (D45 — no intermediary libraries)
- `eval/ingest.py` — idempotent findings.json → Postgres ingestor
- `eval/ui/` — FastAPI + Jinja2 web UI, 7 views (dashboard, corpus, live scan runner with SSE, project detail, scan detail, finding detail, compare)
- Docker stack: db (Postgres 16) + ui (always-on) + adminer + metabase + scanner (profile-gated)
- `eval/db/schema.sql` — Postgres schema: projects, scans, run_findings, canonical_findings, scorecards, data_profiles

### Rule packs (2026-05-25)

First stack-specific rule pack targeting the Tier 1 vibe coder SaaS stack.

- `rules/nextjs-supabase.md` — 14 rules: SUP-01–03 (Supabase), NJS-01–04 (Next.js), STR-01–03 (Stripe), AI-01–02 (LLM integrations), VC-01–02 (multi-tenant patterns)
- `prompt.md` Step 1.1 — stack detection → file read → rules active for all subsequent steps
- `prompt-standalone.md` — inlined condensed rule pack (no filesystem access required)
- `stack_packs_loaded` envelope field now populated

### Corpus strategy pivot (2026-05-25)

Two-track corpus: Academic (intentional vuln fixtures, comparable to existing tools) + Real World (actual vibe coder SaaS repos, validates rule pack recall). See `eval/corpus.md`.

### Alpha standalone prompt (2026-05-25)

`prompt-standalone.md` shipped. Self-contained single-file paste prompt with inlined rule pack. Tested on vulnado and VAmPI via Claude Code.

### Multi-model / multi-IDE compatibility (2026-05-24)

Research complete. The prompt runs natively in Claude Code and adapts to 10 other AI coding assistants with little or no modification. See `COMPATIBILITY.md` for the full matrix and testing checklist.

**Findings summary:**

| Area | Outcome |
|---|---|
| JSON output reliability | All Tier 1 tools reliable. Explicit JSON instruction added to `prompt.md`; `prompt-analysis-only.md` foregrounds it for non-native environments. |
| Context window | D23 budget fits all Tier 1 tools. Cursor is the tightest at ~40–60K effective; `@codebase` mitigates. AI Studio handles up to 1M for analysis-only. |
| File read access | Autonomous tool calls: Cursor, Windsurf, Cline, Copilot. Explicit add: Aider. Semantic index: Cursor `@codebase`. No file writes: AI Studio. |
| Multi-file output | Native in all Tier 1 tools. AI Studio emits JSON+markdown to chat; user runs render.py locally. |
| Instruction following | No known issues with Claude Sonnet 4.6. Other models untested. |
| `render.py` execution | Native in most tools. AI Studio / pure-chat: user runs locally from JSON output. |

**Shipped artifacts:**
- `COMPATIBILITY.md` — 13-tool compatibility matrix, per-tool invocation guides, testing checklist
- `prompt-analysis-only.md` — AI Studio / chat variant (analysis + chat output; no file writes)
- `prompt.md` — "How to invoke" section + pointer to `COMPATIBILITY.md`

**Remaining work:** Validate each tool against `vulnado` (see testing checklist in `COMPATIBILITY.md`). Update checklist as runs are completed.

---

---

## Data strategy

Scan data has value on three independent axes that compound at scale. The eval data layer is the foundation for all three — and it gets built now, at eval scale, so the Pro migration is architectural continuity rather than a rewrite.

### Three primary value vectors

**Tool improvement** — primary key: the run. Every scan is a data point on how good the tool is: recall against known vulnerabilities, false positive rate by category, grade calibration, instruction-following quality by tool and model combination. The compatibility testing and corpus battle-testing work feeds this directly. At scale: prompt version comparison, model regression detection.

**Vulnerability database** — primary key: the canonical finding. A unique vulnerability in a specific project, deduplicated across all tools and runs that have ever scanned it. At scale (hundreds of public repos), this becomes a first-party vuln intelligence asset — useful for responsible disclosure to maintainers, for benchmarking ground truth, and as research signal on which vulnerability types cluster in which stacks.

**Benchmarking and peer comparison** — primary key: the project. At scale, "you are in the bottom 10% of Flask apps for secrets hygiene" is a meaningful statement because you have the comparison corpus. Stack classification and sensitivity tier are already produced by every scan. This is a Pro feature, but the data infrastructure to support it is built now — there is no meaningful incremental cost to capturing it early.

### The flywheel

More scans → richer benchmarking baselines → more useful individual reports → more people use the tool → more scans. The data layer is what makes the flywheel turn. The eval SQLite work costs almost nothing extra and avoids a painful migration when Pro ships and has real user data to move.

### Two-layer finding model

The critical structural decision: two tables for findings, not one.

**`run_findings`** — immutable record of what each individual scan produced. One row per finding per run. Source of truth for "what did Tool X find on Date Y?"

**`canonical_findings`** — one row per unique vulnerability per project, deduplicated across all runs and tools. This is the vuln database. When a new run is ingested, each finding is matched against existing canonicals for that project via the finding ID hash (sha1 of category + file + line_start — title excluded for stability). Match → link to existing canonical. No match → new canonical record.

This structure gives you:
- **Cross-tool corroboration as confidence signal**: if Claude Code, Cursor, and Codex all independently produce the same `finding_id` for the same repo, confidence is very high that it's a real finding — not a hallucination from any one model. This is the primary ground-truth strategy at scale.
- **Finding lifecycle**: first seen, last seen, confirmed fixed (appeared then disappeared across commits).
- **Responsible disclosure tracking**: status per canonical finding (unreported, disclosed, acknowledged, fixed, wontfix).

### Schema design principle

SQLite now; Postgres for Pro. No SQLite-specific idioms in the table definitions. The migration is a connection string change, not a schema redesign. Design it right once.

### One gap in the current JSON schema: `scan.tool`

`schema.json` captures `scan.model` and `scan.prompt_version` but has no `scan.tool` field — there is currently no way to distinguish a Claude Code run from a Cursor run of the same project at the same prompt version. This is the one missing column before multi-tool comparison queries are possible. Planned for schema v0.4 alongside STRIDE annotations. See Pro-tier foundations.

---

## Pro-tier foundations to lay now

These are schema or architectural decisions that cost almost nothing to make today but are painful to retrofit later when Pro ships and has real user data to migrate.

**Finding ID stability (resolved — D44).** The two-layer finding model depends entirely on `finding.id` being deterministic and stable across scans and tools. Locked: `sha1(category + "|" + evidence.file + "|" + evidence.line_start)[:8]`. Title is excluded because it varies across runs and model versions — the same vulnerability phrased differently would produce a different ID, breaking canonical deduplication. All five prompt files and schema.json updated. Needs a corresponding test in `eval/sanity_check.py` when that is built.

**`scan.tool` field (add in schema v0.4).** Currently missing from `schema.json` — no way to distinguish a Claude Code run from a Cursor run at the same prompt version. Required before multi-tool comparison queries in the eval DB are possible. Plan: add as an optional string field to `scan` alongside the STRIDE annotations bump. Values: `claude-code`, `cursor`, `codex`, `windsurf`, `aider`, `copilot-agent`, `gemini-cli`, etc.

**Projects as a first-class entity.** The benchmarking use case requires `project` to be a persistent entity across scans, not just a string inside a scan record. The eval DB `projects` table captures: repo URL, owner, name, primary language, primary framework, first/last scanned, scan count. Stack classification (produced by the Step 1 inventory) and sensitivity tier (produced by Step 1.5) are stored on the project record and become the dimensions for percentile segmentation.

**Two-layer finding model in the eval DB.** `run_findings` + `canonical_findings` as described in the Data strategy section. Build the deduplication logic in `eval/ingest.py` — when a new scan is ingested, match findings against canonicals via finding ID hash; create new canonical records for unmatched findings. The canonical finding record carries the disclosure status fields for the eventual responsible disclosure workflow.

**Schema versioning discipline.** Free-tier users' `findings.json` files are downstream consumers of whatever schema version was current when they scanned. Pro's ingestion pipeline has to handle all schema versions it will ever encounter. The current v0.1/v0.2/v0.3 progression is clean; keep it that way. Never remove a required field without a major version bump; never add a required field in a patch.

**`run_id` field (reserve now, use later).** Pro's historical tracking needs a way to group findings by scan run. Add an optional `scan.run_id` string to schema v0.4 — free tier sets it to a timestamp hash, Pro sets it to a UUID tied to the CI run. Reserving the field name prevents a later collision.

**Diff-aware scanning schema hook.** When Pro builds diff-aware scanning, findings need to declare their scope. An optional `scan.scope` field (`full` | `diff` | `partial`) prevents ambiguity in the history database.

---

## What never gets gated

Regardless of tier, these stay in Free forever:

- All 22 finding categories
- All severity and confidence levels
- The full JSON schema (no field restrictions)
- The HTML renderer (`render.py`)
- The DFD and data profiling features
- The ops checklist appendix
- Finding counts (no "only show top 5 findings on Free")
- Report quality (no watermarks, no "upgrade to see remediation")

The product earns its Pro revenue from genuinely superior capability, not from degrading the free experience.

---

## Changelog

| Date | Change |
|---|---|
| 2026-05-24 | Initial draft. Three-tier model, near-term priorities, Pro foundations. |
| 2026-05-24 | Multi-IDE milestone complete. `COMPATIBILITY.md` written (13 tools). `prompt-analysis-only.md` created. Multi-IDE priority marked done. |
| 2026-05-24 | Release process added. `RELEASE.md` documents two-repo strategy and public file manifest. `scripts/release.sh` automates release. `README.public.md` placeholder created. Release schedule TBD post-v1 validation. |
| 2026-05-24 | Data strategy added. Two-layer finding model, three value vectors (tool improvement / vuln database / benchmarking), flywheel framing. Pro features expanded with benchmarking and vuln database rows. Pro-tier foundations expanded with `scan.tool` field, projects-as-entity, and canonical_findings deduplication. Eval data layer added to near-term priorities. |
| 2026-05-25 | Eval infrastructure complete. Batch scanner, direct vendor SDK adapters (D45), Postgres ingest pipeline, FastAPI web UI (7 views, SSE live log), Docker multi-service stack. |
| 2026-05-25 | Rule packs launched. `rules/nextjs-supabase.md` — 14 rules targeting the Tier 1 vibe coder SaaS stack (Supabase, Next.js, Stripe, AI integrations, multi-tenant). Step 1.1 added to both prompts. Stack_packs_loaded field now populated. |
| 2026-05-25 | AI-03 reverted. Finding (client-controlled model selection) was caught by baseline rubric as standard input validation failure — no stack-specific domain knowledge required. Rule pack bar: encode what the baseline can't know. 14 rules. |
| 2026-05-25 | Corpus strategy pivot. Two-track corpus: Real World (6 vibe coder SaaS repos, rule-pack-prediction-based ground truth) + Academic (intentional vuln fixtures, comparable against existing tools). Framing: neither track alone is sufficient; the combination produces a reproducible, falsifiable credibility claim. |
| 2026-05-25 | Product name decided: Inference Recon. Rename sweep scoped as a single future commit (repo URLs, schema prefix, hardcoded strings in eval tooling). |
| 2026-05-26 | VAmPI calibration complete across all three tiers. haiku/sonnet/opus all land at recall 1.00, precision 0.625. The 6 FPs are consistent structural prompt noise — not model-specific. Baseline locked. |
| 2026-05-26 | Model tier aliases introduced. `TIERS` dict in `eval/providers.py` maps haiku/sonnet/opus → canonical model IDs. `resolve_model()` called before storing to DB so tier shortcuts never appear in scan records. Pricing corrected: opus $5/$25, haiku $1/$5 (previously seeded wrong). Cost backfill applied to all scans. |
| 2026-05-26 | Daily pricing sync automated. `eval/sync_pricing.py` scrapes Anthropic docs page, detects changes against DB, updates `model_pricing` table, backfills `cost_usd` on affected scans. Guard: changes >2× in either direction are skipped as likely parse errors. Docker `pricing-sync` service runs it in `--loop` mode with `time.sleep(86400)` between runs. |
| 2026-05-26 | Metabase dashboard live. 7 cards on "Inference Recon — Model Performance": VAmPI recall/precision by model, findings breakdown (TP/FP/FN), cost vs quality, cost per scan over time, cumulative spend, scan duration, project benchmark summary table. Connects to Postgres via API key. |
| 2026-05-26 | Track 1 triage methodology established. Precision-only approach for repos without pre-defined ground truth: manual code review, community corroboration (GitHub issues) as signal. `project_benchmarks` view keeps calibration (VAmPI) and real-world (Track 1) data separate. `eval/triage_twitterbio.py` written. |
| 2026-05-26 | twitterbio triage complete (all four model runs). Sonnet: 3 TP / 2 FP (prec 0.60). Opus: 2 TP / 2 FP per run (prec 0.50). Haiku: 3 TP / 4 FP (prec 0.43). All tiers find same 3 core issues — app too simple to differentiate on recall. chatbot-ui identified as the meaningful next differentiation test (complex auth/RLS surface). |
| 2026-05-26 | Three Postgres compatibility bugs fixed: (1) `load_dotenv(override=True)` in Docker overwrote container env vars with .env localhost values — drop override=True; (2) `RealDictCursor` rows accessed by integer index instead of column name — use `r["column_name"]`; (3) `ROUND(double precision, n)` not valid in Postgres — use `ROUND(CAST(x AS NUMERIC), n)` universally. `eval/db/schema.sql` updated to match. |
| 2026-05-26 | `health.sh` added. Session-opening sanity check: Docker host status, pricing-sync last run, DB row counts + pricing + VAmPI benchmark, git state. Runs in ~5s. Standard ritual: `bash health.sh` before every session. |
| 2026-05-26 | Brand finalized. Inference Security (company, inferencesecurity.ai) / Inference Recon (product, inferencerecon.com). Primary tagline: "Inferring real risk from static files." |
| 2026-05-26 | Rename sweep complete. `inference-recon` for tool/code references; `Inference Recon` for human-facing text. DB name and prompt_version values left as internal identifiers. Project directory renamed to `Inference Recon` on disk. |
| 2026-05-27 | DB renamed `ai_sec_review` → `inference_recon`. Postgres compat fixes: `CREATE OR REPLACE VIEW`, `init-metabase-db.sh` `--dbname postgres`, triage scripts ported to DB adapter (`INSERT ... ON CONFLICT DO NOTHING`, column-name row access), `load_dotenv()` added to ingest.py and triage scripts. Legacy model name normalization added to ingest.py (`claude-3-5-haiku` → `claude-haiku-4-5-20251001`, etc.) so benchmarks aggregate under canonical tier labels. |
| 2026-05-27 | Priority reframe: thesis validation (chatbot-ui triage + Semgrep comparison) → prompt-only alpha release is the immediate critical path. Skill form factor deferred until after release and real-user validation. |
