# Rule Pack: Next.js + Supabase

**Pack ID:** `nextjs-supabase`
**Applies when:** Next.js (any version, App Router or Pages Router) detected in `package.json`, with Supabase client (`@supabase/supabase-js` or `@supabase/ssr`) present. Stripe and OpenAI rules in this pack activate independently if those SDKs are present.

This pack targets the vulnerability patterns that appear predictably in LLM-generated Next.js + Supabase SaaS codebases. These are not theoretical concerns — they are the actual mistakes that AI coding assistants produce routinely, and they recur at scale. When this pack is active, apply these checks within the relevant scan steps in addition to the baseline rubric.

Rules are additive: they narrow the focus and raise priority within existing steps; they do not replace the baseline code, dependency, secrets, or architecture passes.

---

## Supabase rules

### SUP-01 — Service role key exposed to client
**Step:** 3 (Secrets & Config) and 4 (Code)

Look for the Supabase service role key assigned to a `NEXT_PUBLIC_` prefixed environment variable, e.g. `NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY`. Next.js statically bundles any `NEXT_PUBLIC_*` value into the client-side JavaScript — the key ships to every visitor's browser. The service role key bypasses all Row Level Security policies; possessing it grants unrestricted read/write access to the entire database.

Also look for the service role key used in a file under `components/`, `app/` (excluding `app/api/` and Server Components), or any file that imports from `'react'` or uses `'use client'` — these paths indicate client-side execution.

**Not a finding:** `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` are intentionally public by design — the anon key is scoped by RLS, and the URL is not sensitive. Do not flag these.

**Severity if found:** critical

---

### SUP-02 — Row Level Security absent on user-data tables
**Step:** 4 (Code) — check migration files and schema definitions

Look in database migration files (`supabase/migrations/`, `*.sql`) for `CREATE TABLE` statements on tables that store user or business data (orders, profiles, posts, subscriptions, documents, messages, etc.) without a corresponding `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` and at least one `CREATE POLICY`. If RLS is disabled and the Supabase client is used from browser-side code (check for `createBrowserClient`, `createClient` in client components, or direct SDK calls in `'use client'` files), any authenticated user can read or write any row via the Supabase API endpoint.

Also check the Supabase dashboard config file if present (`supabase/config.toml`) for `enabled = false` under `[db.rls]`.

**Not a finding:** Tables used only by server-side code (API routes, Server Actions, Edge Functions) where the service role key is used only in non-client paths are lower risk — note the exposure level in the finding. Internal tables that contain no user-identifiable data are borderline — use judgment.

**Severity if found:** high (critical if SUP-01 is also present — the combination means the entire database is directly accessible from the browser)

---

### SUP-03 — Supabase storage bucket publicly accessible
**Step:** 4 (Code)

Look for Supabase Storage bucket creation with `public: true` where the bucket stores user-uploaded content that should be access-controlled (profile photos are typically fine; uploaded documents, ID scans, invoices, private media are not). Also look for signed URL generation being skipped in favor of constructing public URLs directly.

**Severity if found:** high (medium if the public content is genuinely non-sensitive, e.g. marketing images)

---

## Next.js rules

### NJS-01 — Sensitive value in NEXT_PUBLIC_ env var
**Step:** 3 (Secrets & Config)

Scan `.env`, `.env.local`, `.env.production`, and all files referencing `process.env.NEXT_PUBLIC_*`. Any of the following are critical findings if assigned a `NEXT_PUBLIC_` name: API keys for OpenAI, Anthropic, Stripe, Resend, SendGrid, Twilio, AWS, or any other provider with a cost-bearing or data-bearing API; database connection strings; JWT secrets; admin tokens; private keys of any kind.

**Not a finding:** `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` (intentionally public), `NEXT_PUBLIC_POSTHOG_KEY` (analytics public key), `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` (intentionally public — distinct from the secret key).

**Severity if found:** critical

---

### NJS-02 — Server Action without authentication check
**Step:** 4 (Code)

Look for functions in files containing `'use server'` (the directive), or in files conventionally named `actions.ts` / `actions.js` / `*-actions.ts`, that perform database writes, deletions, or sensitive reads without first verifying the caller's identity. Verification patterns to look for: calls to `getServerSession()`, `auth()` (NextAuth v5), `currentUser()` (Clerk), `createServerClient()` + `supabase.auth.getUser()`, or equivalent before any privileged operation.

The failure mode: Server Actions are POST endpoints. Without auth, any unauthenticated request to the action endpoint can trigger the database mutation.

**Severity if found:** high (critical if the action deletes data, modifies other users' records, or creates records with elevated privilege)

---

### NJS-03 — IDOR in API route or Route Handler
**Step:** 4 (Code)

Look for route handlers in `app/api/` or `pages/api/` that fetch, update, or delete a resource by ID taken from the request (URL param, query string, or body) without verifying that the requesting user owns or has permission to access that resource. The pattern: `const user = await db.users.findUnique({ where: { id: params.id } })` without a subsequent check that `session.user.id === params.id` (or an equivalent ownership/role check).

Focus on routes that accept a user-controlled identifier and return or mutate records from tables containing user data.

**Severity if found:** high

---

### NJS-04 — Middleware matcher leaves API routes unprotected
**Step:** 4 (Code) and 5 (Architecture)

Look at `middleware.ts` (or `middleware.js`) in the project root. Check the `matcher` config in the exported `config` object. If authentication is enforced in middleware but the matcher only covers page routes (e.g., `/dashboard/:path*`) and excludes `/api/:path*`, then API routes are unprotected — the middleware auth check is bypassed for all API calls.

Also check for a broad `matcher` that inadvertently excludes a sensitive route, or a `matcher` set to `'/((?!api|_next/static|favicon.ico).*)'` that explicitly excludes the API path.

**Not a finding:** API routes that are individually protected by inline session checks (belt and suspenders is fine). API routes that are intentionally public (webhook endpoints, public data endpoints).

**Severity if found:** high

---

## Stripe rules

### STR-01 — Webhook handler missing signature verification
**Step:** 4 (Code)

Look for POST route handlers at paths containing `webhook` or `webhooks` (e.g., `app/api/webhooks/stripe/route.ts`, `pages/api/stripe-webhook.js`) that process Stripe events without calling `stripe.webhooks.constructEvent(body, signature, webhookSecret)` before acting on the event. If signature verification is absent or placed after the business logic executes, an attacker can forge any Stripe event — granting free subscriptions, triggering fulfillment without payment, or spoofing refund events.

Check that: (1) the raw request body is read as a buffer/string before JSON parsing (required for signature verification), (2) the Stripe-Signature header is checked, (3) `constructEvent` is called and any exception causes the handler to return a 400 before executing business logic.

**Not a finding:** Webhook handlers that are stub/placeholder (no business logic, just logging). Test files.

**Severity if found:** critical

---

### STR-02 — Price or amount sourced from client request
**Step:** 4 (Code)

Look for calls to `stripe.checkout.sessions.create()`, `stripe.paymentIntents.create()`, or `stripe.invoiceItems.create()` where `unit_amount`, `amount`, `price`, or a related pricing field is derived from `req.body`, `params`, `formData`, or any other client-controlled input. Prices must be defined server-side (hardcoded constants, a price lookup by product slug against the Stripe Products API, or a value fetched from the application database by server code) — never taken from the client. A client-controlled amount means the user can set their own price.

**Severity if found:** critical

---

### STR-03 — Subscription status gated on webhook payload rather than database
**Step:** 4 (Code)

Look for business logic (feature flags, plan checks, access grants) that reads subscription status directly from the incoming webhook body (`event.data.object.status`) rather than querying the application database. The correct pattern: webhook handler updates the database record; business logic reads from the database. Reading from the webhook payload means a replayed or forged event can alter feature access.

**Severity if found:** high

---

## AI integration rules

### AI-01 — LLM provider API key exposed to client
**Step:** 3 (Secrets & Config)

This is a specific instance of NJS-01 worth calling out explicitly: `NEXT_PUBLIC_OPENAI_API_KEY`, `NEXT_PUBLIC_ANTHROPIC_API_KEY`, `NEXT_PUBLIC_GOOGLE_API_KEY` (when used for Gemini), or similar. LLM API keys exposed client-side allow cost-bombing (attacker makes unlimited API calls at owner's expense), model extraction, and data exfiltration via prompt injection if the attacker can control inputs.

**Severity if found:** critical

---

### AI-02 — No rate limiting on AI-powered endpoints
**Step:** 4 (Code) and 5 (Architecture)

Look for route handlers or Server Actions that call an LLM provider SDK (`openai.chat.completions.create()`, `anthropic.messages.create()`, etc.) without any rate-limiting middleware, request throttling, or per-user quota check. An unprotected AI endpoint allows an attacker (or a misconfigured client) to make thousands of requests, generating significant API costs. Look for: absence of rate-limiting packages (`@upstash/ratelimit`, `express-rate-limit`, custom Redis counters), no check on a per-user call count, no token budget enforcement.

The finding is most severe when the endpoint is unauthenticated (anyone can call it) and when the model used is expensive per-call.

**Not a finding:** Endpoints protected by authentication where the authenticated user is paying for their own usage. Internal-only endpoints. Endpoints that already enforce a hard input token budget.

**Severity if found:** high (critical if the endpoint is unauthenticated)


---

## General vibe coder patterns

### VC-01 — Multi-tenant data isolation missing
**Step:** 4 (Code)

In SaaS applications with multiple users or organizations, look for database queries that filter by a resource ID from the request without also scoping to the requesting user's identity. The canonical pattern: `prisma.order.findUnique({ where: { id: orderId } })` where `orderId` comes from the URL, without `AND userId = session.user.id` in the where clause. Any authenticated user who guesses or enumerates another user's resource ID can read or modify it.

Focus on: order/invoice lookups, file/document access, profile updates, admin resource endpoints, and any route that exposes an ID in the URL.

**Severity if found:** high

---

### VC-03 — Real credentials in committed template or example files
**Step:** 3 (Secrets & Config)

Look for key-shaped values in files intended as configuration templates: `.env.example`, `.env.sample`, `.env.template`, `.env.defaults`, `.env.ci`, `.env.test`, and any file whose name contains `example`, `sample`, or `template`. Also scan inline code blocks in `README.md` and files under `docs/` that demonstrate environment variable configuration — these are a secondary common landing spot.

The failure mode: template files are tracked by git by design (new developers need them), so a developer who populates one with a real key "temporarily" commits it as soon as they run `git add .`. The key is then in the repository's history permanently, even after the file is cleaned up, because `git log -p` retrieves it indefinitely.

Key shapes to recognise:
- Anthropic: `sk-ant-` followed by 90+ mixed chars
- OpenAI: `sk-` or `sk-proj-` followed by 40+ chars
- Stripe live: `sk_live_` followed by 24+ chars; test keys (`sk_test_`) are lower severity
- Supabase service role: a long JWT (three base64 segments separated by `.`, 150+ chars)
- GitHub: `ghp_`, `ghs_`, or `github_pat_` prefixes
- Generic: any value of 32+ non-repeating alphanumeric+special characters assigned to a variable whose name contains `key`, `secret`, `token`, `password`, or `credential`

Also check `.gitignore`: if `.env` is not listed and the file collection includes an actual `.env` file (not `.env.example`), that is a separate critical finding — the real secrets file was committed directly.

**Not a finding:** Placeholder values that a developer would recognise as non-functional: `sk-ant-...`, `your-key-here`, `<YOUR_KEY>`, `REPLACE_ME`, `changeme`, `example`, `dummy`, `fake`, `test123`, `xxx`, or values that are structurally too short or too regular to be real keys (e.g. `sk-proj-abcdefghijklmnop` with an obvious repeating pattern).

**Severity if found:** critical — keys in git history are retrievable by anyone with repo access, and for public repos by anyone on the internet; cost-bearing APIs (Anthropic, OpenAI, Stripe) allow immediate financial exploitation once the key is known

---

### VC-02 — Sensitive data in console.log
**Step:** 4 (Code)

Look for `console.log()`, `console.error()`, or `console.debug()` calls that log objects likely to contain PII or credentials: user objects, session tokens, request bodies (which may contain passwords or payment data), API responses from auth providers, database query results containing user records. LLM-generated code frequently adds verbose logging during development that is never removed.

This is a lower-severity finding in isolation but escalates if the application runs in an environment where logs are aggregated and accessible (Vercel logs, Datadog, etc.) and the data is sensitive per the `data_profile`.

**Severity if found:** low (medium if data_profile sensitivity is high or critical, or if session tokens / auth credentials are logged)
