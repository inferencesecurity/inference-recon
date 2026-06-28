# Docker Reference

The eval stack: **Postgres 16 + Web UI + Adminer + Metabase + batch scanner**.

| Service | Default port | Purpose |
|---------|-------------|---------|
| `db` | 5432 | Postgres — scan results store |
| `ui` | 8000 | Web UI — dashboards, corpus management, scan runner |
| `adminer` | 8080 | Lightweight DB admin / raw SQL |
| `metabase` | 3000 | Analytics dashboards |
| `scanner` | — | Batch scanner (profile-gated, not started by default) |

---

## Setup (first time)

```bash
# Copy env template and set credentials
cp .env.example .env          # edit if you want non-default creds

# Install Python dependencies (for running ingest.py locally, outside Docker)
pip3 install -r eval/requirements.txt
```

---

## Start / stop

```bash
# Start in background (db + ui + adminer + metabase)
docker compose up -d

# Start only the database + UI
docker compose up -d db ui

# Check status
docker compose ps

# Stop (preserves data volume)
docker compose down

# Stop AND wipe all data
docker compose down -v
```

---

## Ingest a scan

```bash
# With DATABASE_URL in .env, source it first:
export $(grep -v '^#' .env | xargs)

# Then ingest:
python3 eval/ingest.py path/to/findings.json \
  --tool claude-code \
  --project-url https://github.com/owner/repo \
  --input-tokens 12500 \
  --output-tokens 3200

# Or pass DATABASE_URL inline:
DATABASE_URL=postgresql://eval:eval@localhost:5432/ai_sec_review \
  python3 eval/ingest.py path/to/findings.json --tool cursor
```

Re-running with the same `findings.json` is a no-op (idempotent).

---

## Web UI

```
URL: http://localhost:8000
```

The UI starts automatically with `docker compose up`. No setup required.

Views available:
- **Dashboard** — recent scans with grades and finding counts
- **Corpus** — all scanned projects; repos.txt contents
- **Run a scan** — model picker, live log stream via SSE
- **Project detail** — scan history for a single project
- **Scan detail** — all findings for a scan, sorted by severity
- **Finding detail** — full evidence, exploitation path, remediation
- **Compare** — side-by-side comparison of two scans (common / unique findings)

The UI serves as a live view of whatever is in the database; it is read-only
except for triggering batch scans.

---

## Batch scanner

The scanner service uses a Docker profile so it doesn't start with
`docker compose up`. Invoke it with `docker compose run --rm`:

```bash
# Haiku sweep of the whole corpus (fast, cheap)
docker compose run --rm scanner \
    python eval/batch_scan.py eval/corpus/repos.txt

# Specific model
docker compose run --rm scanner \
    python eval/batch_scan.py eval/corpus/repos.txt \
    --model anthropic/claude-3-5-sonnet-20241022

# Cross-vendor comparison
docker compose run --rm scanner \
    python eval/batch_scan.py eval/corpus/repos.txt \
    --model openai/gpt-4o-mini

# Dry run (no API calls — just file collection + token estimate)
docker compose run --rm scanner \
    python eval/batch_scan.py eval/corpus/repos.txt --dry-run
```

API keys are passed via environment variables (set in your shell or `.env`):
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`.

---

## Metabase (dashboards)

```
URL: http://localhost:3000
```

**First-time setup (one-time, ~2 minutes):**

1. Open `http://localhost:3000` — Metabase runs its setup wizard on first launch.
2. Set language, create an admin account (email + password of your choice).
3. When asked to add data, choose **PostgreSQL** and enter:
   - Host: `db`  ← the container name, not localhost
   - Port: `5432`
   - Database: `ai_sec_review`
   - Username: `eval`
   - Password: `eval`
4. Finish the wizard. Your scan data is now queryable.

Metabase stores its own metadata (saved questions, dashboards, users) in the
`metabase` Postgres database — it survives container restarts.

**Existing volume gotcha:** The `metabase` database is created by an init script
that only runs on a fresh volume. If you already had the stack running before
Metabase was added, create it manually once:
```bash
docker exec $(docker compose ps -q db) psql -U eval -d ai_sec_review -c "CREATE DATABASE metabase;"
```
Then restart Metabase:
```bash
docker compose restart metabase
```

---

## Adminer (lightweight DB admin)

```
URL:      http://localhost:8080
System:   PostgreSQL
Server:   db
Username: eval
Password: eval
Database: ai_sec_review
```

Useful for quick table browsing and ad-hoc queries. Metabase is better for
dashboards; Adminer is better for raw SQL exploration.

---

## psql (direct shell)

```bash
# Open psql inside the container
docker exec -it $(docker compose ps -q db) psql -U eval -d ai_sec_review

# One-off query without entering the shell
docker exec $(docker compose ps -q db) psql -U eval -d ai_sec_review -c "SELECT * FROM projects;"
```

### Useful queries

```sql
-- Overview: all projects with scan counts and grades
SELECT p.repo_name, p.scan_count, p.sensitivity_tier,
       s.overall, s.count_critical, s.count_high
FROM projects p
JOIN scans sc ON sc.project_id = p.project_id
JOIN scorecards s ON s.scan_id = sc.scan_id
ORDER BY p.repo_name, sc.timestamp DESC;

-- Findings by tool (cross-tool comparison)
SELECT sc.tool, rf.category, rf.severity, rf.confidence, rf.title
FROM run_findings rf
JOIN scans sc ON sc.scan_id = rf.scan_id
ORDER BY sc.tool, rf.severity;

-- High-confidence findings corroborated by multiple tools
SELECT cf.title, cf.category, cf.corroboration_count, cf.corroborating_tools
FROM canonical_findings cf
WHERE cf.corroboration_count > 1
ORDER BY cf.corroboration_count DESC;

-- Grade distribution across all scanned projects
SELECT overall, COUNT(*) FROM scorecards GROUP BY overall ORDER BY overall;

-- Token cost by tool and model
SELECT tool, model, SUM(input_tokens) AS total_in, SUM(output_tokens) AS total_out
FROM scans
GROUP BY tool, model;
```

---

## Data management

```bash
# Backup the database
docker exec $(docker compose ps -q db) \
  pg_dump -U eval ai_sec_review > eval/db/backup-$(date +%Y%m%d).sql

# Restore from backup
docker exec -i $(docker compose ps -q db) \
  psql -U eval ai_sec_review < eval/db/backup-20260524.sql

# Wipe all data and re-initialise schema (nuclear option)
docker compose down -v
docker compose up -d
```

---

## Logs

```bash
# Postgres logs
docker compose logs db

# Follow logs (useful for debugging connection issues)
docker compose logs -f db
```

---

## Troubleshooting

**Container won't start / port conflict**
```bash
# Check what's using port 5432
lsof -i :5432
# Change the port in .env: DB_PORT=5433
```

**`psycopg2` connection refused**
```bash
# Confirm the container is healthy
docker compose ps
# Should show "healthy" — if not, check logs:
docker compose logs db
```

**Schema not initialised (tables missing)**

The schema is loaded automatically on first `docker compose up` via the
`initdb` mount. If you started the container before `eval/db/schema.sql`
existed, the volume has an empty database. Fix:
```bash
docker compose down -v   # wipe volume
docker compose up -d     # re-initialise with current schema
```

**Adminer shows "No database selected" or connection error**

Make sure you're entering `db` (not `localhost`) as the Server field —
Adminer resolves the container name, not the host port.

**`Already ingested — scan skipped`**

This is correct behaviour (idempotent). If you need to re-ingest a
modified findings.json, the scan_id is derived from project + timestamp +
model, so change the timestamp in the file or delete the row:
```sql
DELETE FROM scans WHERE scan_id = 'the8charprefix%';
-- then re-run ingest
```
