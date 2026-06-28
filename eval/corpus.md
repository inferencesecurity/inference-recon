# Eval Corpus

Two tracks. Run both. The combination is the credibility claim.

**Real World** (Track 1) — real open-source projects built on the Tier 1 vibe coder SaaS stack. Not synthetic, not intentionally broken — actual code that developers build from and ship. These repos test whether the tool catches the specific mistakes that appear in LLM-generated codebases. Ground truth is established through rule-pack predictions → scan → manual triage, not pre-seeded by design.

**Academic** (Track 2) — intentionally vulnerable apps with pre-given documented ground truth. The same benchmarks that security researchers use to evaluate other tools. These test whether the tool handles classical vulnerability patterns correctly and let us compare directly against existing scanners.

**Why both:** Academic-only means "scored well on the same benchmarks every other tool uses" — undifferentiated. Real World-only means "anecdotal results on cherry-picked repos" — unverifiable. Together: we match established scanners on recognized standards, *and* we find things in real production-adjacent codebases that those standards were never designed to test. The specific claim this enables: a rule-based scanner like Semgrep is silent on a missing Stripe webhook signature check in a 10k-star Next.js template; this tool flags it as critical with file/line evidence. That's a reproducible, falsifiable, publicly-checkable result — not marketing.

---

## Track 1 — Real World

Real open-source projects built on the Tier 1 vibe coder SaaS stack: Next.js + Supabase, Stripe, OpenAI. These are not synthetic — they are actual products and starters that real developers build from and ship. The scanning objective is different from Track 2: instead of pre-known ground truth, we start with rule-pack predictions (which rules should fire on this codebase?) and validate them after the scan.

**Ground truth method for Track 1:**
1. Before scanning: record which rule pack rules are expected to fire, and why (positive prediction)
2. Scan with the target model
3. Manually triage each finding: TP, FP, or FN against the prediction
4. Document surprises — findings the rule pack predicted but the scanner missed, and findings the scanner produced that the rule pack didn't predict
5. Use surprises to iterate the rule pack (missed pattern → add to rule) or the FP suppressors (incorrect fire → tighten negative anchor)

**Precision baseline note:** A repo maintained by a security-aware organization (Vercel, etc.) should produce few or no rule pack findings. Findings on these repos are candidate false positives — investigate carefully before concluding they're real.

---

### T1-1. nextjs-subscription-payments

- **Repo:** https://github.com/vercel/nextjs-subscription-payments
- **Stack:** Next.js + Supabase + Stripe
- **Maintainer:** Vercel (security-conscious organization)
- **Budget status:** ⬜ not yet measured
- **Purpose:** Rule pack recall + FP baseline. This is the canonical Tier 1 stack starter. Since Vercel maintains it, it should be relatively hardened — findings here are suspect and should be investigated. At the same time, even well-maintained starters can have patterns our rules target (webhook handling, RLS configuration).
- **Rule pack predictions:**
  - STR-01: Stripe webhook signature verification — *likely present (Vercel is careful), but verify*
  - STR-02: Client-controlled pricing — *likely absent, good FP baseline*
  - SUP-01: Service role key in NEXT_PUBLIC — *should not be present; would be critical if found*
  - SUP-02: RLS configuration — *expect to see RLS present; check policy completeness*

**Run log**

| Run | Date | Model | Prompt ver. | Pack loaded | Input tok. | Output tok. | Duration | TP | FP | Notable FNs | Sev. cal. | Overall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | — | — | — | — | — | — |

**Findings notes:** —

---

### T1-2. chatbot-ui

- **Repo:** https://github.com/mckaywrigley/chatbot-ui
- **Stack:** Next.js + Supabase + OpenAI
- **Maintainer:** McKay Wrigley (individual developer)
- **Budget status:** ⬜ not yet measured
- **Purpose:** Rule pack recall. Real AI app with real usage. Has had documented auth and RLS issues in earlier versions — good test of whether the rule pack catches patterns that were genuinely present in the wild. Represents the "solo dev built a popular AI thing" persona precisely.
- **Rule pack predictions:**
  - AI-01: OpenAI API key exposure — *possible; check for NEXT_PUBLIC_OPENAI_API_KEY*
  - AI-02: No rate limiting on AI endpoints — *likely; personal projects routinely omit this*
  - NJS-02: Server Actions without auth — *check if App Router; if so, high probability*
  - SUP-02: Missing RLS on chat/message tables — *known historical issue; check current state*
  - VC-01: Multi-tenant query isolation — *chat history scoping; check per-user isolation*

**Run log**

| Run | Date | Model | Prompt ver. | Pack loaded | Input tok. | Output tok. | Duration | TP | FP | Notable FNs | Sev. cal. | Overall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | — | — | — | — | — | — |

**Findings notes:** —

---

### T1-3. twitterbio

- **Repo:** https://github.com/Nutlope/twitterbio
- **Stack:** Next.js 14 App Router + Together AI (no auth, no database) — *note: migrated from OpenAI to Together AI SDK since predictions were written*
- **Maintainer:** Antonio Erdeljac (Nutlope)
- **Budget status:** ✓ Within (17 source files, ~520 lines)
- **Purpose:** AI rule pack validation in isolation. Extremely minimal app — stripped of most complexity. The simplicity makes it clean for testing AI-01 and AI-02 without noise from auth/DB layers. Also representative of the "quick AI demo that escaped the weekend project stage" pattern.
- **Rule pack predictions:**
  - AI-01: OpenAI key in NEXT_PUBLIC — *high probability; simple apps commonly do this*
  - AI-02: No rate limiting — *high probability; no infra visible in simple apps*
  - NJS-01: Other NEXT_PUBLIC secrets — *check for any provider keys*

**Run log**

| Run | Date | Model | Prompt ver. | Pack loaded | Input tok. | Output tok. | Duration | TP | FP | Notable FNs | Sev. cal. | Overall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-05-25 | claude-sonnet-4-6 | 0.3 | none | — | — | — | 4 | 0 | AI-01 (true negative — key correctly server-side) | ✓ | C |

**Findings notes:**
- **4 findings, 0 FP against predictions.** AI-02 (no rate limiting) confirmed TP. AI-01 not fired — correctly: `TOGETHER_API_KEY` is server-side only, no `NEXT_PUBLIC_` exposure anywhere. True negative, not a miss. NJS-01 also clean.
- **Stack pivot:** Repo migrated from OpenAI to Together AI SDK. Underlying patterns (key exposure, rate limiting) are provider-agnostic — predictions remain valid.
- **Novel finding (36ee6fa7): Client-controlled model selection.** Client POSTs a model name string that the Route Handler passes directly to Together AI without validation. Not predicted; emerged from code analysis. High severity — attacker can force use of expensive models at operator cost. **Candidate for AI-03 in the rule pack.**
- **Secrets grade A:** Exemplary handling — useful positive baseline for the corpus. Key server-side only, no hardcoded values, no NEXT_PUBLIC_ exposure.
- **Findings files:** `eval/corpus/findings/twitterbio/findings.json`, `report.md`

---

### T1-4. roomGPT

- **Repo:** https://github.com/Nutlope/roomGPT
- **Stack:** Next.js 13 App Router + Replicate (image generation) + Bytescale (file upload) + Upstash Redis (optional rate limiting)
- **Maintainer:** Antonio Erdeljac (Nutlope)
- **Budget status:** ✓ Within (21 source files)
- **Purpose:** Second AI rule validation data point. Similar profile to twitterbio but uses Replicate (different provider pattern). Tests whether AI-02 fires on non-OpenAI AI endpoints and whether NJS-01 catches Replicate API token exposure.
- **Rule pack predictions:**
  - AI-02: No rate limiting — *high probability*
  - NJS-01: Replicate API token or other keys in NEXT_PUBLIC — *check*

**Run log**

| Run | Date | Model | Prompt ver. | Pack loaded | Input tok. | Output tok. | Duration | TP | FP | Notable FNs | Sev. cal. | Overall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-05-25 | claude-sonnet-4-6 | 0.3 | none | — | — | — | 5 | 0 | — | ✓ | C |

**Findings notes:**
- **5 findings, 0 FP.** 1 high, 3 medium, 1 low.
- **AI-02 prediction: partially correct — interesting.** Rate limiting IS implemented via `@upstash/ratelimit`, but conditional on Upstash Redis being configured. The `.example.env` marks Redis credentials as "Optional". In most deployments (forks, local, quick deploys without Upstash setup), `ratelimit === undefined` and the `if (ratelimit)` block is a no-op. This is a subtler and arguably more dangerous pattern than twitterbio's total absence — operators see rate limiting in the code and assume they're protected. **Candidate pattern for a rule: AI-02 variant — "rate limiting gated on optional infrastructure."**
- **NJS-01 prediction: partial.** `REPLICATE_API_KEY` correctly server-side only (true negative). `NEXT_PUBLIC_UPLOAD_API_KEY` flagged at medium/medium — Bytescale upload key is client-visible by the NEXT_PUBLIC_ prefix. Ambiguous whether this is public-by-design (like Stripe publishable key). Requires checking Bytescale docs before confirming.
- **Novel findings:** Unbounded polling loop (no timeout → DoS risk if Replicate hangs), unvalidated `imageUrl` forwarded to Replicate (operator's API key used to process attacker-supplied URLs).
- **Comparison with T1-3 twitterbio (same developer):** roomGPT shows more security awareness — rate limiting was attempted, secrets better handled. Pattern suggests developers improve with iteration but leave subtle gaps.
- **Findings file:** `eval/corpus/findings/roomGPT/findings.json`

**Findings notes:** —

---

### T1-5. taxonomy

- **Repo:** https://github.com/shadcn-ui/taxonomy
- **Stack:** Next.js 13 App Router + Prisma + Auth.js + Stripe
- **Maintainer:** shadcn
- **Budget status:** ⬜ not yet measured (estimated ~60-80 files)
- **Purpose:** App Router era auth and Stripe pattern validation. This is one of the first widely-forked App Router starters — thousands of repos were built from it. The App Router introduced Server Actions, and early ecosystem code frequently got auth on those wrong. Stripe integration is the other primary target.
- **Rule pack predictions:**
  - NJS-02: Server Actions without auth — *high probability in early App Router code*
  - NJS-03: IDOR in API routes — *check `/api/users/[id]` and similar resource endpoints*
  - NJS-04: Middleware matcher gaps — *early App Router starters commonly have this*
  - STR-01: Webhook signature verification — *strong prior that tutorials skip this*
  - STR-02: Client-controlled pricing — *check checkout session creation*

**Run log**

| Run | Date | Model | Prompt ver. | Pack loaded | Input tok. | Output tok. | Duration | TP | FP | Notable FNs | Sev. cal. | Overall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | — | — | — | — | — | — |

**Findings notes:** —

---

### T1-6. next-saas-stripe-starter

- **Repo:** https://github.com/mickasmt/next-saas-stripe-starter
- **Stack:** Next.js 14 + Prisma + Auth.js + Stripe (10k+ stars)
- **Maintainer:** mickasmt
- **Budget status:** ⬜ not yet measured
- **Purpose:** High-signal Stripe integration test. Very popular template — findings here have broad impact since many production apps were built from it. Primary focus is the Stripe integration (STR-01/02/03) and Next.js 14 auth patterns (NJS-02/03).
- **Rule pack predictions:**
  - STR-01: Webhook signature verification — *primary test case for this rule*
  - STR-02: Client-controlled pricing — *check checkout creation code*
  - STR-03: Fulfillment from webhook payload — *check subscription gating logic*
  - NJS-02: Server Actions without auth — *Next.js 14 template, high probability*
  - NJS-03: IDOR in API routes — *user/subscription resource endpoints*

**Run log**

| Run | Date | Model | Prompt ver. | Pack loaded | Input tok. | Output tok. | Duration | TP | FP | Notable FNs | Sev. cal. | Overall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | — | — | — | — | — | — |

**Findings notes:** —

---

## Track 2 — Academic

Intentionally vulnerable apps with documented ground truth. The same benchmarks the security research community uses to evaluate scanners. Purpose: confirm the baseline rubric handles classical vulnerability patterns correctly, catch regressions on prompt/rubric changes, and provide a basis for direct comparison against existing tools (Semgrep, Snyk, Bandit, etc.). These do not exercise the rule packs — they're stack-agnostic validation against a known bar.

**Metrics key**

| Field | What to record |
|---|---|
| **TP** | True positives — known vulns correctly identified with right category |
| **FP** | False positives — findings that are not real issues |
| **Notable FNs** | Known vulns missed entirely (focus on things findable from source) |
| **Sev. cal.** | Severity calibration: ✓ accurate · ⚠ mixed · ✗ off |
| **DFD** | DFD accuracy: ✓ reflects app · ⚠ partial · ✗ wrong |
| **Data profile** | Data profile accuracy: ✓ correct tier + categories · ⚠ partial · ✗ wrong |
| **Exploit paths** | Exploitation path quality: ✓ concrete · ⚠ mixed · ✗ generic/hallucinated |
| **Overall** | Letter grade: A / B / C / D / F |

---

### C1. vulnado

- **Repo:** https://github.com/sbvgk/vulnado *(fork; ScaleSec original is private)*
- **Stack:** Java / Spring Boot
- **Source:** 13 files · 589 lines
- **Budget status:** ✓ Within
- **Priority:** Calibration. Smallest Java app; RCE, SSRF, SQLi, and hardcoded credentials clearly present. Any miss is a rubric problem.
- **Ground truth:** SQL injection (string concatenation), SSRF (user-supplied URL fetched server-side), XSS (unsanitised output), command injection / RCE (shell exec), hardcoded credentials.

**Run log**

| Run | Date | Model | Prompt ver. | Input tok. | Output tok. | Duration | TP | FP | Notable FNs | Sev. cal. | DFD | Data profile | Exploit paths | Overall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-05-24 | claude-sonnet-4-6 | 0.1 | — | — | — | 14 | 0 | XSS (client JS not scanned; self-reported in notes) | ✓ | ✓ | ✓ | ✓ | B |

**Findings notes:**
- **All 14 findings confirmed TP.** SQLi (×2), OS command injection, JWT hardcoded secret, MD5 password hashing, SSRF, missing authz on /cowsay+/links, incomplete IP blocklist in linksV2, comment username spoofing, CORS wildcard, DB credentials in docker-compose, jsoup CVE-2021-37714, Spring Boot EOL, logging gap.
- **1 FN: Stored XSS** (client/index.html). Model correctly noted client HTML files were not read and flagged this explicitly in `notes[]`. Scope limitation, not a rubric gap — resolved with prompt v0.2 frontend scope addition.
- **CVSS caveat:** jsoup CVE CVSS vector reported as derived from memory, not copied from NVD. Protocol violation per the prompt (Step 2 requires verbatim copy). Treat CVSS value as unverified.
- **DFD quality:** Excellent. Explicitly labeled `/cowsay` and `/links` as "no auth enforced", showed unsanitized SQL data flow, internal Docker network SSRF target, OS shell as a process node.
- Token counts not captured — run via Claude Code desktop.

---

### C2. VAmPI

- **Repo:** https://github.com/erev0s/VAmPI
- **Stack:** Python / Flask / REST API
- **Source:** 11 files · 520 lines
- **Budget status:** ✓ Within
- **Priority:** Calibration. Explicitly implements OWASP API Top 10. Clean sweep expected.
- **Ground truth:** Broken object-level authorization (BOLA/IDOR), broken user authentication, excessive data exposure, lack of resource limiting / rate limiting, broken function-level authorization, mass assignment, SQL injection, unauthorized password change via parameter tampering, user enumeration via timing attack.

**Run log**

| Run | Date | Model | Prompt ver. | Input tok. | Output tok. | Duration | TP | FP | Notable FNs | Sev. cal. | DFD | Data profile | Exploit paths | Overall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-05-24 | claude-sonnet-4-6 | 0.2 | — | — | — | 14 | 0 | None — all 9 OWASP API Top 10 categories found | ✓ | ✓ | ✓ | ✓ | A |

**Findings notes:**
- **Clean sweep: 14 TP / 0 FP / 0 FN.** All 9 documented OWASP API Top 10 (2019) categories found. 4 critical, 3 high, 6 medium, 1 low.
- **Standout findings:** JWT key hardcoded as the string `'random'` (critical); `/users/v1/_debug` unauthenticated endpoint dumping all plaintext passwords (critical); `/createdb` publicly accessible database reset (critical); mass assignment enabling admin self-promotion at registration (high).
- **DFD quality:** Excellent. Debug and createdb endpoints shown as separate nodes with "no auth enforced" labels; SQL injection path and "SELECT * — dumps all passwords" flow visible at a glance.
- **Data profile:** Correct standard tier; strong context note linking plaintext password storage to amplified impact of every other finding.
- Token counts not captured — run via Claude Code desktop.

---

### C3. NodeGoat *(primary regression target)*

- **Repo:** https://github.com/OWASP/NodeGoat
- **Stack:** Node.js / Express / MongoDB
- **Source:** 44 files · 3,084 lines
- **Budget status:** ✓ Within
- **Priority:** Core baseline. Best-documented ground truth in the corpus — OWASP Top 10 (2013) explicitly mapped to code in the repo wiki. Primary regression target for prompt/rubric changes.
- **Ground truth:** NoSQL injection (MongoDB), broken authentication (weak session management, no account lockout), XSS (reflected and stored), IDOR (account data accessible across users), security misconfiguration (no HTTPS, default session secret), sensitive data exposure (passwords in responses), missing function-level access control (admin routes), CSRF (no token validation), known vulnerable components (outdated dependencies), unvalidated redirects.

**Run log**

| Run | Date | Model | Prompt ver. | Input tok. | Output tok. | Duration | TP | FP | Notable FNs | Sev. cal. | DFD | Data profile | Exploit paths | Overall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |

**Findings notes:** —

---

## Secondary fixtures (queued)

The following are in the original corpus plan and remain useful for breadth testing, but are not a priority until Track 1 and the primary calibration fixtures are complete.

| # | App | Stack | Tier |
|---|---|---|---|
| S1 | vulpy (bad/ + good/) | Python / Flask | FP/FN split test |
| S2 | govwa | Go / net/http | Language breadth |
| S3 | DVGA | Python / Flask / GraphQL | Vuln-type breadth |
| S4 | DVRestaurant | Python / FastAPI | Vuln-type breadth |
| S5 | dvws-node | Node.js / SOAP+REST+GraphQL | Vuln-type breadth |
| S6 | Tiredful-API | Python / Django REST | Full-size |
| S7 | xvwa | PHP | Full-size |
| S8 | Generic-University | PHP / Laravel | Full-size |
| S9 | RailsGoat | Ruby / Rails | Over-budget stress |

Full entry details for these apps are preserved in git history (pre-pivot commit). Restore them to this file when they become active.
