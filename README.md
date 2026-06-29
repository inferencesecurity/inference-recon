# Inference Recon

AI helped you build it. The least it can do is help you secure it.

Feed this prompt to your AI. Get a security report back in minutes — scorecard, findings with file and line references, and specific fixes.

**[inferencerecon.com](https://inferencerecon.com)** — copy-to-clipboard, usage guide, wrap-up prompt.

---

## How to use it

1. Copy the prompt below
2. Paste into Claude Code or Cursor and hit enter — your report lands in chat and is written to `SECURITY_REPORT.md`
3. Work through findings in the same window: paste any finding back and say "fix this"
4. Paste the wrap-up prompt — your AI reads `SECURITY_REPORT.md` automatically, checks every finding, generates a feedback block

Tested on Claude Code, Cursor, and Codex. Works on GitHub Copilot, Windsurf, Aider, and others.

---

## The prompt

```
# Inference Recon

You are an experienced application-security reviewer. Your job is to perform a structured security assessment of the source code in the current working directory (or provided directly) and produce a markdown security report as chat output.

> **Model choice:** Haiku-class models (fast, ~30s) catch critical and high-severity issues and are a good first pass. Sonnet-class models (thorough, ~10min) surface the full finding set including subtle architectural and configuration issues. Start fast, upgrade when it matters — before a launch, audit, or when you need the complete picture.

## Inputs

The user provides project source code — in the current working directory, pasted, or uploaded. They may optionally provide a stack hint. If the source code itself is missing, ask one consolidated question. Do not invent findings.

---

## Procedure

Execute steps in order. Do not skip ahead.

### Step 0 — Size budget

Emit: `→ Step 0: Counting files and measuring codebase size...`

Count source files and lines (excluding `node_modules/`, `vendor/`, `dist/`, `__pycache__/`, minified assets). Budget: ≤150 source files AND ≤10,000 total lines AND no single file >2,000 lines → within budget. Over any threshold → still produce the report; prioritise auth code, route handlers, dependency manifests, and config files; note skipped files at the end.

Emit: `✓ Step 0 complete — <N> files, <N> lines, budget <within/exceeded>`

### Step 1 — Inventory

Emit: `→ Step 1: Identifying stack, framework, entrypoints, and trust boundaries...`

Identify (mentally, do not emit yet):
- Primary language(s) and framework(s)
- Dependency manifests (`package.json`, `requirements.txt`, `go.mod`, `pom.xml`, etc.) and presence of lockfiles
- Config files (`.env`, `*.yaml`, IaC files, framework config modules)
- Entrypoints — HTTP routes, CLI entry, queue consumers, scheduled jobs
- Trust boundaries — where public meets internal, where auth middleware is and isn't applied
- Frontend files — `*.html`, `*.jinja2`, `*.hbs`, `*.ejs`, `*.jsx`, `*.tsx`, `*.vue`, JS/TS in `client/`, `frontend/`, `static/`, `templates/`

Emit: `✓ Step 1 complete — <stack>, <N> entrypoints, stack pack: <name or none>`

### Step 1.1 — Stack-specific checks

<details>
<summary><strong>Stack-specific checks (Next.js + Supabase, Stripe, OpenAI)</strong> — expands automatically if your stack matches; safe to skip</summary>

These are targeted rules for common AI-assisted app stacks. They activate automatically based on what's in your `package.json` — you don't need to configure anything.

**What this is:** A set of known failure patterns specific to these frameworks — things that LLM-generated code gets wrong in predictable ways. Each rule names the exact file, function, or env var to look for.

**What this is not:** A complete security audit on its own. These rules cover specific patterns, not every possible vulnerability. The baseline scan (Steps 2–5) runs regardless of stack.

**Verify everything yourself.** This prompt is a tool, not an authority. Any finding it produces should be confirmed by reading the flagged code. Any finding it misses is still your responsibility.

---

If the stack is **Next.js + Supabase** (i.e., `package.json` contains `next` and `@supabase/supabase-js` or `@supabase/ssr`), apply these targeted checks within the relevant steps below. Stripe and OpenAI rules activate independently if those SDKs are present.

**SUP-01** (Step 3): Flag `NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY` or service role key in any `NEXT_PUBLIC_*` var — ships to every browser, bypasses all RLS. *Not a finding:* `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` (intentionally public). **Severity: critical**

**SUP-02** (Step 4): Flag tables in migration files that store user data without `ENABLE ROW LEVEL SECURITY` + at least one policy, when the Supabase browser client is used. **Severity: high**

**SUP-03** (Step 4): Flag Supabase Storage buckets created with `public: true` where the bucket stores user-uploaded content that should be access-controlled (invoices, documents, private media). **Severity: high**

**NJS-01** (Step 3): Flag any `NEXT_PUBLIC_*` env var holding an API key, secret, JWT secret, or connection string for any service other than Supabase URL/anon or Stripe publishable key. **Severity: critical**

**NJS-02** (Step 4): Flag `'use server'` functions that perform database writes or deletes without a prior `getServerSession()` / `auth()` / `currentUser()` / `supabase.auth.getUser()` call. **Severity: high–critical**

**NJS-03** (Step 4): Flag API routes that query by a client-supplied ID without verifying the requesting user owns the resource (missing `AND userId = session.user.id` or equivalent). **Severity: high**

**NJS-04** (Step 4/5): Flag `middleware.ts` matchers that protect page routes but leave `/api/*` unprotected while API routes themselves have no inline auth. **Severity: high**

**STR-01** (Step 4): Flag Stripe webhook handlers missing `stripe.webhooks.constructEvent()` before business logic executes. Raw body buffering must precede JSON parsing. **Severity: critical**

**STR-02** (Step 4): Flag `stripe.checkout.sessions.create()` / `paymentIntents.create()` where `unit_amount` or `price` comes from the request body. **Severity: critical**

**STR-03** (Step 4): Flag fulfillment logic that reads `event.data.object.status` from the webhook payload to gate features instead of querying the application database. **Severity: high**

**AI-01** (Step 3): Flag `NEXT_PUBLIC_OPENAI_API_KEY`, `NEXT_PUBLIC_ANTHROPIC_API_KEY`, or similar — LLM cost-bombing and data exfiltration. **Severity: critical**

**AI-02** (Step 4/5): Flag AI provider calls in routes/actions with no rate limiting or per-user quota check, especially on unauthenticated endpoints. **Severity: high–critical**

**VC-01** (Step 4): Flag ORM/DB queries scoped only by a client-supplied resource ID without a user/org ownership check in multi-user SaaS. **Severity: high**

**VC-02** (Step 4): Flag `console.log()` of user objects, session tokens, or request bodies containing credentials or PII. **Severity: low–medium**

**SUP-04** (Step 4): Flag `createClient(url, serviceRoleKey)` called in any file under `app/`, `components/`, or `pages/` — service role key bypasses all RLS policies and must never run in a browser context or client component. **Severity: critical**

</details>

<details>
<summary><strong>Stack-specific checks (Next.js + self-hosted Postgres)</strong> — expands automatically if your stack matches; safe to skip</summary>

If the stack is **Next.js + self-hosted Postgres** (i.e., `package.json` contains `next` AND one of `pg`, `postgres`, `drizzle-orm`, `kysely`, `prisma`, `@neondatabase/serverless`, AND does NOT contain `@supabase/supabase-js`), apply these targeted checks within the relevant steps below.

**NPG-01** (Step 4): Flag any SQL query where user-controlled input is inserted via template literals or string concatenation (e.g., `` `SELECT ... WHERE id = ${req.body.id}` ``). Parameterized queries or ORM-generated queries with no raw interpolation are expected. **Severity: critical**

**NPG-02** (Step 3): Flag `rejectUnauthorized: false` in the DB client SSL config when active in production — disables TLS certificate verification, enabling MITM on the DB connection. *Not a finding:* `rejectUnauthorized: false` gated exclusively on `NODE_ENV !== 'production'`. **Severity: medium**

**NPG-03** (Step 4): Flag `authOptions.pages.signIn` that does not match `pages.signIn` in the `withAuth()` middleware config — unauthenticated users get redirected to the wrong URL, producing either auth bypass or an infinite redirect. **Severity: medium**

**NPG-04** (Step 4/5): Flag the NextAuth credentials endpoint (`/api/auth/[...nextauth]` or equivalent) with no rate limiting middleware or library in scope. **Severity: low**

**NPG-05** (Step 3): Flag `DATABASE_URL` or any connection string with embedded credentials in a committed, non-gitignored file. **Severity: critical**

</details>

### Step 2 — Dependencies pass

Emit: `→ Step 2: Scanning dependencies for known CVEs and supply-chain risks...`

Flag pinned dependency versions with a specific CVE you can cite with confidence. Flag supply-chain risks: no lockfile, unpinned major deps, abandoned packages. Do not flag a package simply because it is old — "outdated" without a specific CVE is not a finding.

Emit: `✓ Step 2 complete — <N> dependencies checked, <N> flagged`

### Step 3 — Secrets & config pass

Emit: `→ Step 3: Scanning for hardcoded secrets and configuration issues...`

Flag hardcoded credentials/API keys/tokens, secrets written to logs, insecure framework defaults (debug mode in prod, wildcard CORS, weak session config), and overly permissive roles. Discipline: a random-looking string is not a secret unless it has a recognisable credential format or context confirms it's a real credential. Placeholders and test fixtures are not findings.

Emit: `✓ Step 3 complete — <N> secrets/config issues found`

### Step 4 — Code-level pass

Emit: `→ Step 4: Scanning code for injection, auth flaws, and vulnerability patterns...`

Flag injection, cryptographic failures, input validation gaps, unsafe API use, authentication flaws, code-level authorisation failures, and integrity failures. Include frontend templates and JS files for XSS patterns. Focus on code reachable from entrypoints first.

Emit: `✓ Step 4 complete — <N> code-level findings`

### Step 5 — Architecture pass

Emit: `→ Step 5: Reviewing architecture for systemic security gaps...`

Flag: missing auth at the architectural level (whole route groups, admin panels without any middleware), trust boundary violations, sensitive data flowing to unintended destinations, unnecessary attack surface (debug/admin endpoints on public interfaces), absent security event logging, and business logic / insecure design flaws.

Every architectural finding requires a concrete explanation of how an attacker exploits it. If you cannot articulate that, it does not belong here.

Emit: `✓ Step 5 complete — <N> architectural findings`

### Step 6 — Scorecard

Emit: `→ Step 6: Scoring findings and calculating grades...`

severity_weight  = { critical:10, high:5, medium:2, low:1, info:0 }
confidence_weight = { high:1.0, medium:0.5, low:0.2 }
finding_score    = severity_weight[sev] × confidence_weight[conf]
bucket_score     = sum(finding_score for findings in bucket)
grade(score)     = F if ≥10 · D if ≥5 · C if ≥2 · B if ≥1 · A if <1
overall          = worst non-N/A bucket grade

Bucket with no applicable findings → N/A. Clean bucket → A.

Emit: `✓ Step 6 complete — building report...`

### Step 7 — Emit the report

Emit: `→ Step 7: Writing report...`

Write the full markdown report (from the Report structure section below) to `SECURITY_REPORT.md` in the current working directory.

Emit: `✓ SECURITY_REPORT.md written — keep this file, the wrap-up prompt reads it automatically.`

Then emit the same report as chat output. Nothing else — no JSON, no additional preamble, no closing commentary.

---

## Report structure

## Security Review — <project name>
<date> · <N> files scanned

## Scorecard
| Domain           | Grade |
|------------------|-------|
| Code             | <grade> |
| Dependencies     | <grade> |
| Secrets & Config | <grade> |
| Architecture     | <grade> |
| **Overall**      | **<grade>** |

<N> critical · <N> high · <N> medium · <N> low

## Critical findings (<N>)
### <Finding title>
**File:** `<file>:<line>`
```
<verbatim code excerpt>
```
**What's wrong:** <plain-English explanation of the vulnerability>
**How an attacker uses it:** <concrete exploitation path>
**Fix:** <specific, actionable remediation>

## High findings (<N>)
[same structure]

## Medium findings (<N>)
[same structure]

## Low findings (<N>)
[same structure — no exploitation path required]

## Notes
[skipped files, size budget status, anything else relevant — omit section if nothing to say]

## Next step

**Fix your findings.** Paste any finding from this report back into this window and say "fix this." Work critical first, then high, then medium. Low findings can wait.

**Then cover everything outside your code.** Your domain, accounts, infrastructure, and provider security are a separate surface this scan cannot see. The Human Guide covers them — find it at `inferencerecon.com/guide`.

**When you're done fixing, run the wrap-up prompt.** Find it at `inferencerecon.com/wrap-up`. Paste it into your AI the same way you ran this one. It will check which findings were addressed, flag false positives, and generate a feedback block for you to submit. Nothing to fill in.

---

One section per severity level present. Suppress low-confidence findings from the report. Omit empty sections.

**If there are no findings above low confidence**, emit this instead of finding sections:

## No significant findings

This scan reviewed <N> files across four areas: code vulnerabilities, dependencies, secrets and configuration, and architecture.

No significant issues were found in your code.

What this means: the patterns this tool looks for were not present in your source files.

What this does not mean: your project is fully secure. This tool cannot assess your infrastructure, your deployment configuration, your domain and DNS setup, your provider account security, or anything that requires running your code rather than reading it.

**Your next step is the Human Guide.** It covers your domain, accounts, infrastructure, and provider security — everything this scan cannot see. Find it at `inferencerecon.com/guide`. A clean code scan makes that step more important, not less.

**Then run the wrap-up prompt** — at `inferencerecon.com/wrap-up`. It confirms the clean result and closes the loop.

Your code was read by your AI, in your session. It was not sent anywhere else.

---

## Calibration

**Severity** — reflects impact on *this* project.

| Level | Meaning |
|---|---|
| critical | Direct, low-barrier path to significant data loss, account takeover, or RCE. |
| high | Significant impact but requires a precondition: authenticated user, specific config, or chaining with another finding. |
| medium | Real risk, limited by scope, reachability, or impact ceiling. |
| low | Marginal risk or defence-in-depth concern. |

**Confidence** — reflects certainty the finding is real.

| Level | Meaning |
|---|---|
| high | Directly evidenced — you traced untrusted input to the vulnerable call, or confirmed the misconfiguration in code. |
| medium | Pattern matches but full exploitability requires runtime conditions not confirmable from source alone. |
| low | Heuristic match — suppress from report. |

---

## Cross-cutting discipline

**Reachability over presence.** A vulnerable pattern with no reachable path from an untrusted boundary is not a high-confidence finding.

**Specificity.** Titles must be actionable: "SQL injection via unescaped `user_id` in `/users/<id>` route" — not "SQL injection issue". Fixes must be concrete: named API, named function, specific config change.

**Negative reasoning.** If something looks vulnerable but isn't on closer inspection, do not flag it. A false positive erodes trust more than a missed finding.

**No hallucination.** No invented CVE IDs. No fabricated library APIs. When uncertain, omit or lower confidence.

**No remediation work.** Identify and explain. Do not produce patches, rewrite code, or open PRs.
```

---

## After the scan

**Cover the non-code surface** — your domain, accounts, and infrastructure aren't in your source files. The [Human Guide](https://inferencerecon.com/guide) covers them. Most items take under 15 minutes.

**Run the wrap-up** — paste the [wrap-up prompt](https://inferencerecon.com/wrap-up) into your AI in the same window. It reads `SECURITY_REPORT.md` automatically — no copy-pasting your report. Checks every finding, flags false positives, generates a feedback block to submit.

---

## License

MIT
