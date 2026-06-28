# Stack-Specific Rule Packs

Rule packs extend the baseline rubric with targeted checks for specific tech stacks. They exist because AI coding assistants produce recognizable code patterns, and those patterns have recognizable failure modes. A rule pack codifies the intersection of "what LLMs generate" and "where those patterns are vulnerable."

## Available packs

| File | Stack | Rules |
|------|-------|-------|
| `nextjs-supabase.md` | Next.js + Supabase (+ Stripe, OpenAI) | SUP-01–03, NJS-01–04, STR-01–03, AI-01–02, VC-01–02 |

## How packs are loaded

**Claude Code (agent mode):** `prompt.md` Step 1.1 instructs the model to identify the stack during inventory and read the applicable pack file before scanning. The pack is active for all subsequent steps.

**Standalone / paste mode:** `prompt-standalone.md` inlines the rule pack content directly into Step 1.1, conditioned on stack detection. No separate file read required.

**Batch scanner:** `batch_scan.py` uses `prompt-standalone.md` as its system prompt, so pack rules are included automatically.

In all modes, applicable pack IDs are recorded in `project.stack_packs_loaded` in the findings envelope.

## Rule pack contract

A rule pack is a markdown file with one section per rule. Each rule specifies:

- **Rule ID** — stable identifier in the form `PREFIX-NN` (e.g. `SUP-01`, `NJS-03`). Never reuse an ID.
- **Scan step** — which prompt step to apply this check within (Step 2 = dependencies, Step 3 = secrets/config, Step 4 = code, Step 5 = architecture).
- **Positive anchor** — specific code patterns, file locations, or conditions to look for. Be concrete: name the function, env var prefix, or API call pattern.
- **Negative anchor** — explicit false positive suppressors. These are required when the positive pattern has a known-safe variant (e.g., `NEXT_PUBLIC_SUPABASE_ANON_KEY` looks like a secret but is intentionally public).
- **Default severity** — the severity to apply when the pattern is found without additional escalating/mitigating context. The model may adjust per the baseline rubric's severity calibration rules.

Rules are **additive**. They do not replace Steps 2–5 of the baseline scan; they raise the priority and specificity of targeted checks within those steps.

## Bar for adding a new pack

1. The target stack must appear in the top tiers of the vibe coder stack distribution — broad enough that many real projects will trigger the pack.
2. At least three rules with documented real-world occurrence — not theoretical concerns, but patterns that LLM-generated codebases actually produce.
3. Each rule must have a concrete positive anchor (specific code pattern, API, or config) and, where applicable, a negative anchor preventing false positives on intentionally safe variants.
4. The pack must be validated against at least one real project before shipping.

## Planned packs

| File | Stack | Priority |
|------|-------|----------|
| `stripe.md` | Stripe integration (stack-agnostic) | High — STR rules apply beyond Next.js |
| `firebase.md` | Firebase + Firestore | High — distinct failure pattern (rules vs. code) |
| `fastapi-python.md` | FastAPI / Python API backends | Medium |
| `nextjs-auth.md` | NextAuth / Clerk patterns (Next.js) | Medium |
