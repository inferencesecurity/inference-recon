# Multi-Model / Multi-IDE Compatibility

**Last updated:** 2026-05-24  
**Status:** Research complete; OpenAI Codex, Cursor, and Windsurf untested (near-drop-in expected for all three); AI Studio variant built; Copilot Workspace ruled out.

This document records which AI coding assistants can run the security review prompt, what adaptations are needed for each, and the testing status. See `ROADMAP.md` for the milestone plan.

---

## Compatibility matrix

| Tool | Workflow fit | File reading | Multi-file write | Shell exec | JSON reliability | Invocation |
|---|---|---|---|---|---|---|
| **Claude Code** | ✅ Native | Autonomous, full repo | ✅ Native | ✅ Native | ✅ Excellent | One-paste CTA |
| **OpenAI Codex** | ✅ Near drop-in | Autonomous, full repo (sandboxed) | ✅ Native | ✅ Native | ✅ Good (GPT-4.1 / o3) | `codex` CLI or codex.openai.com |
| **Cursor Agent** | ✅ Near drop-in | Semantic index + tool calls | ✅ Native | ✅ (YOLO mode = zero clicks) | ✅ Good (model-dependent) | Paste into Agent panel |
| **Windsurf Cascade** | ✅ Near drop-in | Full project index + tool calls | ✅ Native | ✅ Native | ✅ Good (model-dependent) | Paste into Cascade panel |
| **Cline / Roo Code** | ✅ Near drop-in | Autonomous reads | ✅ Native | ✅ Native | ✅ Good (model-dependent) | Paste into Cline panel |
| **Aider** | ✅ Works, minor prep | Repo-map + explicit `/add` | ✅ Native | ✅ Native | ✅ Good | Terminal, pre-add files |
| **GitHub Copilot Agent** | ✅ Works, minor notes | Autonomous tool calls | ✅ Native | ✅ (approval click default) | ✅ Good | Chat panel → Agent mode |
| **Gemini Code Assist** | ✅ Works, billing caveat | Tool calls (agent mode) | ✅ Native | ⚠️ Buggy in VS Code ext | ✅ Good | VS Code sidebar → Agent |
| **Gemini CLI** | ✅ Works | Tool calls | ✅ Native | ✅ Native | ✅ Good | Terminal, paste prompt |
| **Continue.dev** | ✅ Works (BYOK) | `@codebase` + tool calls | ✅ Native | ✅ Native | Depends on model | Chat panel → Agent mode |
| **Zed AI** | ✅ Near drop-in | Autonomous reads | ✅ Native | ✅ Native | ✅ Good | Agent panel, paste prompt |
| **JetBrains AI** | ✅ Works | Tool calls | ✅ Native | ✅ Native | ✅ Good | AI chat → Agent mode |
| **AI Studio** | ⚠️ Analysis-only | Manual upload / paste | ❌ No file writes | ❌ No shell | ✅ Excellent (JSON mode) | Browser, upload files |
| **Copilot Workspace** | ❌ Not compatible | Repo via GitHub API | ❌ PR-only output | ❌ None | — | Browser, issue-based |

---

## Tool-by-tool notes

### Claude Code *(primary target)*
No adaptation needed. The full prompt runs as designed.

---

### OpenAI Codex *(Tier 1 — near drop-in)*

**Status:** Not yet tested.

**Note on naming:** There are two products called "Codex." The original OpenAI Codex model (2021–2023) is deprecated and powered the first generation of GitHub Copilot. The tool documented here is the **new OpenAI Codex agent** (launched May 2025) — a cloud-based software-engineering agent analogous to Claude Code. It is an entirely separate product from GitHub Copilot and from Copilot Workspace.

**How to invoke:**
1. Install the Codex CLI: `npm install -g @openai/codex` (or use the web UI at codex.openai.com).
2. Navigate to the project directory.
3. Run `codex` to open the interactive session, or:
   ```bash
   codex -p "$(cat ~/.inference-recon/prompt.md)"
   ```
4. Codex clones/reads the repo in a sandboxed environment and runs the full procedure.

**Sandboxed environment:** Codex runs in a Docker-based cloud sandbox. It has full filesystem access to the cloned repo and can execute shell commands natively — `python3 render.py` runs without manual approval. File outputs are written to the sandbox and can be downloaded or committed back to the repo.

**Underlying model:** GPT-4.1 (default) or o3. GPT-4.1 is recommended for this use case — strong instruction following on multi-step procedural prompts and reliable JSON output. o3 is slower and more expensive but may improve reasoning on complex architectural findings.

**JSON output:** Reliable with GPT-4.1. If the model wraps the JSON in prose, add the explicit JSON instruction (see below) to the top of the prompt.

**Context window:** GPT-4.1 has a 1M token context window. In practice the effective agent context is lower due to sandbox overhead, but the D23 size budget fits comfortably.

**No prompt changes required** beyond optionally adding `@codebase` or the explicit JSON instruction if JSON wrapping occurs.

---

### Cursor Agent *(Tier 1 — near drop-in)*

**Status:** Not yet tested.

**How to invoke:**
1. Open Cursor. Press `Cmd+I` (Mac) or `Ctrl+I` (Windows/Linux) to open the Agent panel.
2. Paste the contents of `prompt.md` at the top of the chat.
3. Add `@codebase` on the first line to trigger semantic retrieval across the whole project.
4. Send.

**Context window caveat:** Cursor's effective usable window is ~40–60K tokens after overhead (even with a 200K model like Claude Sonnet 4.6). For projects near the D23 size budget ceiling, the agent may not read every file. Mitigate by leading with `@codebase` and making sure the target project is open as the active workspace.

**Shell execution:** Requires one approval click per terminal command unless YOLO mode is enabled (`Settings → Features → Enable YOLO Mode`). For the render.py step, one click is acceptable.

**JSON output:** Reliable with Claude Sonnet 4.6 or GPT-4.1. If the model wraps the JSON in prose, add the explicit JSON instruction (see below).

**No prompt changes required** beyond adding `@codebase` at the top.

---

### Windsurf Cascade *(Tier 1 — near drop-in)*

**Status:** Not yet tested.

**How to invoke:**
1. Open the project in Windsurf.
2. Open the Cascade panel (right sidebar).
3. Paste the contents of `prompt.md`.
4. Send.

**Windsurf Workflows:** For repeated use, encode the prompt as a `.workflow` file in the project root. This makes the scan a one-click operation — the strongest UX outside of Claude Code.

**Context window:** Model-dependent; select Claude Sonnet 4.6 or Gemini 2.5 Pro for the largest window.

**No prompt changes required.**

---

### Cline / Roo Code *(Tier 1 — near drop-in)*

**Status:** Not yet tested.

Free, open-source VS Code extensions. BYOK (Bring Your Own Key — use your own Anthropic/OpenAI/Gemini API key). Cline has ~8M installs; Roo Code is its fork with a multi-mode system.

**How to invoke (Cline):**
1. Install the Cline extension in VS Code.
2. Configure your API key in the extension settings.
3. Open the Cline panel.
4. Paste the contents of `prompt.md`.
5. Approve the initial file reads (or enable auto-approve).

**Roo Code note:** Roo Code's Architect mode is ideal for analysis-heavy prompts — it separates the "think" phase from the "write files" phase, which matches the prompt's Step 1–5 (analysis) / Step 6–10 (output) structure.

**Context truncation:** Cline truncates without summarization when context is full. For large projects, use Roo Code or scope the files explicitly.

**No prompt changes required.**

---

### Aider *(Tier 1 — works, minor pre-flight)*

**Status:** Not yet tested.

Terminal-based, git-first. All changes become atomic git commits. Works with any API-accessible model.

**How to invoke:**
```bash
# Install
pip install aider-chat

# Start with Claude (recommended)
aider --model claude-sonnet-4-6

# Pre-add the output files so aider knows to create them
/add security-review/findings.json security-review/report.md security-review/report.html

# Paste the prompt contents and send
```

**Architect mode (recommended for this use case):**
```bash
aider --architect --model claude-sonnet-4-6 --editor-model claude-sonnet-4-6
```
Uses one model for planning (the 10-step analysis) and another for writing output files. Reduces skipped steps on complex procedural prompts.

**Repo-map:** Aider builds a compact map of all git-tracked files automatically. This gives the model codebase awareness without reading every file in full. For security review, add the most relevant source files explicitly with `/add` to ensure they're fully read.

**No prompt changes required,** but pre-adding the output files before running is essential.

---

### GitHub Copilot Agent Mode *(Tier 2 — works, minor notes)*

**Status:** Not yet tested.

The VS Code chat panel in Agent mode, **not** Copilot Workspace (see below).

**How to invoke:**
1. Open VS Code with the GitHub Copilot extension.
2. Open the Chat panel (`Cmd+Shift+I` / `Ctrl+Shift+I`).
3. Select **Agent** from the model dropdown (not "Ask" or "Edit").
4. Paste the contents of `prompt.md`.
5. Send.

**File context:** Copilot reads files via tool calls as it works — it discovers and reads files autonomously. For security review, add `Use @workspace to read all project files` at the top of the prompt to encourage broad file access.

**Shell execution:** Requires a user approval click per terminal command. One click for `python3 render.py` is fine. Pre-authorize it in `.github/copilot-instructions.md` if running frequently.

**Persistent instructions:** For repeated use, add the prompt (or a shorter "invoke security review" instruction) to `.github/copilot-instructions.md` or a `.prompt.md` file callable from the Copilot Prompts panel.

**Underlying model:** User-selectable from GPT-4.1, Claude 3.5/3.7 Sonnet, Gemini 2.0 Flash. Recommend Claude Sonnet for this use case.

**Prompt addition needed:** Add `Use @workspace to read all project source files before beginning Step 0.` at the top.

---

### Gemini Code Assist / Gemini CLI *(Tier 2 — works, billing caveat)*

**Status:** Not yet tested.

**Billing note (important as of June 2026):** The free "individuals" tier of Gemini Code Assist is being shut down on June 18, 2026. Team/enterprise use requires Standard or Enterprise tiers (GCP-billed). The **Gemini CLI** remains free for individuals.

**Gemini CLI (preferred for this use case):**
```bash
# Install (requires Node.js)
npm install -g @google/gemini-cli

# Run
gemini
# Paste the prompt, or use:
gemini -p "$(cat prompt.md)"
```
The CLI has reliable shell execution, full file access, and the 1M-token context window. More reliable than the VS Code extension for shell commands.

**Gemini Code Assist VS Code (agent mode):**
Open the Gemini Code Assist chat sidebar → ensure agent mode is selected → paste the prompt. Shell execution has reported bugs; use the CLI if `python3 render.py` fails to execute.

**JSON output:** Add the explicit JSON instruction (see below). The API supports `responseSchema` but it's not exposed in the VS Code chat panel.

**Prompt addition needed:** Add the explicit JSON instruction below.

---

### AI Studio *(analysis-only variant)*

**Status:** Variant prompt written (`prompt-analysis-only.md`).

AI Studio has no file writing and no shell execution. It IS the best tool for getting clean, valid JSON output due to native JSON mode — useful for testing the prompt's analysis quality in isolation.

**How to invoke:**
1. Go to [aistudio.google.com](https://aistudio.google.com).
2. Use Gemini 2.5 Pro.
3. Enable JSON output mode in System Instructions.
4. Paste the contents of `prompt-analysis-only.md`.
5. Upload the project as a zip file or paste individual source files.
6. Run. Copy the JSON from the response and save manually as `findings.json`.
7. Run `python3 render.py findings.json` locally to produce the HTML report.

See `prompt-analysis-only.md` for the stripped version.

---

### Copilot Workspace *(not compatible)*

Copilot Workspace (githubnext.com/projects/copilot-workspace) is a browser-based issue-to-PR tool. It does not accept free-form procedural prompts, cannot run shell commands, and produces pull requests rather than local files. **This is a fundamentally different product from Copilot Agent Mode in VS Code.** It is not suitable for this workflow without a complete redesign into a GitHub Actions / issue-template flow (a future Pro-tier CI integration, not a free-tier prompt adaptation).

---

## Explicit JSON output instruction

Add this to the prompt when using tools without native JSON mode that have shown a tendency to wrap JSON in prose:

```
IMPORTANT: The JSON envelope in Step 7 must be emitted as a single ```json fenced code block with no prose before the opening ``` or after the closing ```. The markdown report follows immediately after. Do not interleave explanation with the JSON output.
```

This instruction is safe to add to the main `prompt.md` — it has no negative effect on Claude Code and helps every other tool.

---

## Context window guide

| Scenario | Recommended approach |
|---|---|
| Project within D23 budget, any Tier 1 tool | No changes needed |
| Project near D23 ceiling (>100 files or >8K lines) with Cursor | Add `@codebase` to prompt; YOLO mode on |
| Project at or over D23 budget | Expect `size_budget_status: exceeded`; tool will do partial scan |
| Large project, need full coverage | Use AI Studio (1M window) for analysis-only; run render.py locally |
| Privacy-sensitive project, no cloud | Use Aider or Continue.dev with a local model via Ollama |

---

## Testing checklist

For each tool, run against `vulnado` (13 files, 589 lines — smallest corpus app) and verify:

- [ ] Model reads all 13 source files without explicit prompting
- [ ] JSON envelope is valid (run `eval/sanity_check.py` when built)
- [ ] `findings.json`, `report.md`, `report.html` all written to `security-review/`
- [ ] `render.py` executes without manual intervention (or one click on approval-gated tools)
- [ ] DFD mermaid source renders correctly in the HTML report
- [ ] Finding count and scorecard match manual review of ground truth

| Tool | Tested | Notes |
|---|---|---|
| Claude Code | — | Primary target, assumed working |
| OpenAI Codex | ⬜ | — |
| Cursor Agent | ⬜ | — |
| Windsurf Cascade | ⬜ | — |
| Cline / Roo Code | ⬜ | — |
| Aider | ⬜ | — |
| GitHub Copilot Agent | ⬜ | — |
| Gemini CLI | ⬜ | — |
| AI Studio (analysis-only) | ⬜ | — |

---

## Changelog

| Date | Change |
|---|---|
| 2026-05-24 | Initial research complete. Compatibility matrix documented. AI Studio analysis-only variant written. Copilot Workspace ruled out. Testing checklist added. |
| 2026-05-24 | Added OpenAI Codex (new 2025 agent) — Tier 1 near drop-in. Clarified naming distinction from deprecated Codex model and Copilot Workspace. |
