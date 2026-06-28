# Inference Recon

A structured security recon tool for AI coding assistants. Paste it into Claude Code (or any capable AI assistant), point it at your project, and get a findings report across four domains: code vulnerabilities, dependencies, secrets and configuration, and architecture. Outputs a scored JSON findings envelope, a markdown report, and a self-contained HTML report with a data flow diagram.

---

## Quick start (Claude Code)

Paste this into Claude Code from your project directory:

```
Clone https://github.com/markcmarshall/inference-recon-staging to ~/.inference-recon/ if not already present, then read ~/.inference-recon/prompt.md and follow the procedure to perform a security review of the current working directory.
```

Claude will read the project files, run the analysis, and write three files to `./security-review/`:

- `<project>-security-review-<timestamp>.json` — structured findings (machine-readable)
- `<project>-security-review-<timestamp>.md` — markdown report
- `<project>-security-review-<timestamp>.html` — self-contained HTML report with scorecard and data flow diagram

Add `security-review/` to your project's `.gitignore`.

---

## What it covers

| Domain | What it looks for |
|---|---|
| **Code** | Injection, cryptographic failures, input validation, unsafe API use, auth flaws |
| **Dependencies** | Known CVEs (with CVSS scores), supply chain risks |
| **Secrets & config** | Hardcoded credentials, insecure defaults, IaC misconfigurations |
| **Architecture** | Trust boundary violations, missing authorization layers, data flow risks, attack surface, logging gaps |

Every finding comes with: a file and line citation, a verbatim code quote, a confidence tier (high / medium / low), and a concrete remediation. High and critical findings include an exploitation path.

Each scan also produces a **data sensitivity profile** (what types of data the app handles and which regulatory frameworks may apply) and a **Level 1 data flow diagram** derived from the source code.

---

## Size limits

This tool performs a single-pass analysis within one model context window.

- ≤ 150 source files
- ≤ 10,000 source lines total
- No single file > 2,000 lines

Projects that exceed these limits still get a report — the tool will flag which files were skipped and set `size_budget_status: exceeded` in the output.

---

## Other AI tools

The prompt works with Cursor, Windsurf, OpenAI Codex, Aider, GitHub Copilot Agent, Gemini CLI, and others with minor or no adaptation. See [`COMPATIBILITY.md`](COMPATIBILITY.md) for per-tool invocation steps and notes.

For environments without file write access (AI Studio, plain chat), use [`prompt-analysis-only.md`](prompt-analysis-only.md).

---

## Output schema

The JSON findings envelope conforms to [`schema.json`](schema.json) (v0.3). The schema is stable and versioned — downstream tooling can rely on it.

---

## License

MIT
