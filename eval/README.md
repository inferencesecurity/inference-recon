# Eval Harness

Tools for running Inference Recon at scale against a corpus of repos and analyzing the results.

---

## Architecture

```
eval/
  batch_scan.py       # Batch scanner: clone repos → call API → ingest results
  providers.py        # Direct vendor SDK adapters (Anthropic / OpenAI / Google)
  ingest.py           # Idempotent ingestor: findings.json → Postgres
  requirements.txt    # Python dependencies for this package
  Dockerfile          # Shared image for ui + scanner Docker services
  corpus/
    repos.txt         # Target repo list (one URL per line, comments with #)
    repos/            # Clone cache (gitignored)
    findings/         # Raw findings.json output per scan (gitignored)
  db/
    schema.sql        # Postgres schema (auto-loaded on first docker compose up)
    init-metabase-db.sh
    test-fixture.json # Fixture for testing ingest pipeline
  ui/
    main.py           # FastAPI app
    db.py             # Read-only DB helpers (Postgres or SQLite)
    templates/        # Jinja2 templates
    static/           # CSS
```

Docker services (defined in `docker-compose.yml` at repo root):

| Service | Default port | Purpose |
|---------|-------------|---------|
| `db` | 5432 | Postgres 16 — scan results store |
| `ui` | 8000 | Web UI — dashboards, corpus, scan runner |
| `adminer` | 8080 | Lightweight DB admin |
| `metabase` | 3000 | Analytics dashboards |
| `scanner` | — | Batch scanner (profile-gated, not started by default) |

---

## Quick start

```bash
# Start the full eval stack
docker compose up -d

# Open the web UI
open http://localhost:8000
```

---

## Running a batch scan

### Via Docker (recommended)

```bash
# Haiku sweep of the whole corpus (fast, cheap)
docker compose run --rm scanner \
    python eval/batch_scan.py eval/corpus/repos.txt

# Sonnet pass for a deeper scan
docker compose run --rm scanner \
    python eval/batch_scan.py eval/corpus/repos.txt \
    --model anthropic/claude-3-5-sonnet-20241022

# Cross-vendor comparison
docker compose run --rm scanner \
    python eval/batch_scan.py eval/corpus/repos.txt \
    --model openai/gpt-4o-mini
```

### Locally (with DATABASE_URL set)

```bash
pip install -r eval/requirements.txt
export ANTHROPIC_API_KEY=...
export DATABASE_URL=postgresql://eval:eval@localhost:5432/ai_sec_review

python eval/batch_scan.py eval/corpus/repos.txt
```

### Dry run (no API calls — just file collection + token estimate)

```bash
python eval/batch_scan.py eval/corpus/repos.txt --dry-run
```

---

## Model string format

`provider/model-name` — the provider prefix is required unless the model name is unambiguous:

| String | Provider |
|--------|----------|
| `anthropic/claude-3-5-haiku-20241022` | Anthropic |
| `anthropic/claude-3-5-sonnet-20241022` | Anthropic |
| `openai/gpt-4o-mini` | OpenAI |
| `openai/gpt-4o` | OpenAI |
| `google/gemini-2.0-flash` | Google AI Studio |
| `google/gemini-2.5-pro` | Google AI Studio |

API keys: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` (or `GOOGLE_API_KEY`).

---

## repos.txt format

```
# Lines starting with # are comments
https://github.com/owner/repo.git

# Local paths are supported; --url overrides the canonical identity in the DB
/path/to/local/repo --url https://github.com/owner/repo
```

---

## Manual ingest

To ingest a `findings.json` produced outside the batch scanner (e.g. from a Claude Code desktop run):

```bash
python eval/ingest.py path/to/findings.json \
    --tool claude-code \
    --project-url https://github.com/owner/repo \
    --input-tokens 12500 \
    --output-tokens 3200
```

Supported `--tool` values: `claude-code`, `cursor`, `codex`, `windsurf`, `claude-ai`,
`api-anthropic`, `api-openai`, `api-google`, `api-other`.

Re-running with the same file is a no-op (idempotent — scan_id is derived from
project + timestamp + model).

---

## Dependency policy (D45)

The eval harness uses official vendor SDKs only — no intermediary abstraction
layers (e.g. LiteLLM) in any path that touches source code, API keys, or scan
output. See `design-doc.md` §5 decision D45 for rationale.

---

## Planned eval tooling

The following are scoped for a future iteration once corpus data is available:

- **`eval/sanity_check.py`** — ~30-line envelope validator: verifies ID derivation, count consistency, scorecard derivation, and conditional schema requirements. Runnable as a CI step against any scan output.
- **Golden set** — curated projects with known vulnerabilities; recall/precision tracking over time.
- **Scanner comparison** — run Semgrep/Snyk/gitleaks against the same corpus; honest characterization of where this tool adds or loses relative to rule-based scanners.
