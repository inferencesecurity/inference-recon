# Inference Recon — Wrap-up

Run this after you've worked through your findings.

Paste this prompt into your AI, then paste your original Inference Recon report after it. Your AI checks the current code against every finding, flags false positives, and generates a structured feedback block to submit at [inferencerecon.com/feedback.html](https://inferencerecon.com/feedback.html).

---

```
# Inference Recon — Wrap-up

You are reviewing the results of a previous Inference Recon security scan on this codebase.

Paste your Inference Recon report below this prompt before hitting enter. If it is missing, ask for it before proceeding.

---

## Procedure

### Step 1 — Parse the original report

Extract every finding: its severity, title, file, and line reference. Note the overall grade.

### Step 2 — Check current state

For each finding, read the referenced file and line in the current codebase. Determine the verdict:

- **fixed** — the vulnerability is no longer present
- **false_positive** — on closer review, the finding does not apply to this codebase; explain why in the note field
- **open** — still present, not yet addressed

### Step 3 — Recalculate score

Using the same scoring as the original scan, calculate the post-fix overall grade based on remaining open findings only.

### Step 4 — Emit the feedback block

Emit exactly the block below — nothing before it, nothing after it. The user will copy and submit it. Do not add commentary, do not summarize, do not explain.

---

```yaml
inference_recon_feedback:
  version: 1
  scan_date: <date from original report>
  stack: <stack identified in original report>
  overall_before: <Overall grade from original report>
  overall_after: <recalculated grade>
  findings:
<one entry per finding from original report>
    - severity: <critical|high|medium|low>
      title: "<finding title from report>"
      verdict: <fixed|false_positive|open>
      note: "<required for false_positive — one sentence. optional for fixed/open>"
```

---

Copy the block above and submit it at: https://inferencerecon.com/feedback.html
```
