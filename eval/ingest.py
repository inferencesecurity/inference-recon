#!/usr/bin/env python3
"""
eval/ingest.py — Ingest a findings.json envelope into the eval database.

Usage:
    python3 eval/ingest.py <findings.json> [options]

    --tool TOOL          Tool that produced this scan.
                         Values: claude-code, cursor, codex, windsurf, aider,
                                 copilot-agent, gemini-cli, ai-studio, other
    --input-tokens N     Input token count (for cost tracking).
    --output-tokens N    Output token count.
    --project-url URL    Repository URL for stable project identity across scans.
    --db PATH            SQLite path (default: eval/db/eval.db). Ignored when
                         DATABASE_URL env var is set.

Backends:
    Postgres (preferred): set DATABASE_URL=postgresql://user:pass@host:port/db
    SQLite   (fallback):  use --db or leave DATABASE_URL unset.

Idempotent: re-running with the same findings.json is a no-op.
Requires schema v0.3+.
"""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

SCHEMA_PATH = Path(__file__).parent / "db" / "schema.sql"
DEFAULT_SQLITE_PATH = Path(__file__).parent / "db" / "eval.db"

MIN_SCHEMA_VERSION = (0, 3)


# ── Database adapter ──────────────────────────────────────────────────────────

class DB:
    """
    Thin adapter over sqlite3 and psycopg2.

    Normalises three differences between the two drivers:
      - Parameter placeholder:  sqlite3 uses ?, psycopg2 uses %s
      - Connection execute:     sqlite3 supports conn.execute(); psycopg2 requires a cursor
      - Row access:             both return dict-like rows (sqlite3.Row / RealDictCursor)
    """

    def __init__(self, url_or_path: str):
        self._pg = url_or_path.startswith(("postgresql://", "postgres://"))

        if self._pg:
            import psycopg2
            import psycopg2.extras
            self._conn = psycopg2.connect(
                url_or_path,
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
        else:
            self._conn = sqlite3.connect(url_or_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")

    # -- query helpers --------------------------------------------------------

    def _ph(self, sql: str) -> str:
        """Swap ? placeholders for %s when using Postgres."""
        return sql.replace("?", "%s") if self._pg else sql

    def execute(self, sql: str, params: tuple = ()):
        sql = self._ph(sql)
        if self._pg:
            cur = self._conn.cursor()
            cur.execute(sql, params)
            return cur
        return self._conn.execute(sql, params)

    def fetchone(self, sql: str, params: tuple = ()):
        return self.execute(sql, params).fetchone()

    # -- schema init ----------------------------------------------------------

    def is_initialised(self) -> bool:
        if self._pg:
            row = self.fetchone(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'projects'"
            )
        else:
            row = self.fetchone(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='projects'"
            )
        return row is not None

    def init_schema(self) -> None:
        schema = SCHEMA_PATH.read_text()
        if self._pg:
            cur = self._conn.cursor()
            # Split on ; — safe because our schema has no ; inside string literals
            for stmt in schema.split(";"):
                stmt = "\n".join(
                    line for line in stmt.splitlines()
                    if not line.strip().startswith("--")
                ).strip()
                if stmt:
                    cur.execute(stmt)
        else:
            self._conn.executescript(schema)

    # -- transaction ----------------------------------------------------------

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()


# Maps old/shortened model names from pre-alias JSON artifacts to canonical current names.
# Applied during ingest so benchmarks aggregate under stable tier labels.
_LEGACY_MODEL_MAP: dict[str, str] = {
    "claude-3-5-haiku":   "claude-haiku-4-5-20251001",
    "claude-opus-4-5":    "claude-opus-4-7",
    "claude-sonnet-4-5":  "claude-sonnet-4-6",
    "opus":               "claude-opus-4-7",
    "sonnet":             "claude-sonnet-4-6",
    "haiku":              "claude-haiku-4-5-20251001",
}


def _normalize_model(model: str) -> str:
    return _LEGACY_MODEL_MAP.get(model, model)


_KNOWN_PRICING = [
    # (model, effective_from, provider, input_per_1m, output_per_1m)
    # Claude 4 family — rates verified against docs 2026-05-26
    ("claude-opus-4-7",            "2025-07-01", "anthropic",  5.00, 25.00),
    ("claude-sonnet-4-6",          "2025-06-01", "anthropic",  3.00, 15.00),
    ("claude-haiku-4-5-20251001",  "2025-10-01", "anthropic",  1.00,  5.00),
    # Claude 3.5 legacy (for any pre-4.x runs)
    ("claude-3-5-sonnet-20241022", "2024-10-22", "anthropic",  3.00, 15.00),
    ("claude-3-5-haiku-20241022",  "2024-10-22", "anthropic",  0.80,  4.00),
]


def _seed_model_pricing(db: DB) -> None:
    for model, eff_from, provider, inp, out in _KNOWN_PRICING:
        if db._pg:
            db.execute(
                "INSERT INTO model_pricing (model, effective_from, provider, input_per_1m, output_per_1m) "
                "VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING",
                (model, eff_from, provider, inp, out),
            )
        else:
            db.execute(
                "INSERT OR IGNORE INTO model_pricing "
                "(model, effective_from, provider, input_per_1m, output_per_1m) "
                "VALUES (?,?,?,?,?)",
                (model, eff_from, provider, inp, out),
            )


def _apply_migrations(db: DB) -> None:
    """Add columns/tables introduced after the initial schema deploy."""
    # M1: cost_usd + cache columns on scans
    if db._pg:
        existing_cols = {
            r["column_name"] for r in db.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='scans'"
            ).fetchall()
        }
    else:
        existing_cols = {r["name"] for r in db.execute("PRAGMA table_info(scans)").fetchall()}

    for col, typedef in [
        ("cost_usd",               "REAL"),
        ("cache_creation_tokens",  "INTEGER"),
        ("cache_read_tokens",      "INTEGER"),
    ]:
        if col not in existing_cols:
            db.execute(f"ALTER TABLE scans ADD COLUMN {col} {typedef}")

    # M2: model_pricing table
    db.execute(
        "CREATE TABLE IF NOT EXISTS model_pricing ("
        "  model          TEXT NOT NULL,"
        "  effective_from TEXT NOT NULL,"
        "  provider       TEXT NOT NULL,"
        "  input_per_1m   REAL NOT NULL,"
        "  output_per_1m  REAL NOT NULL,"
        "  effective_to   TEXT,"
        "  notes          TEXT,"
        "  PRIMARY KEY (model, effective_from)"
        ")"
    )

    # M3: scan_triage table
    db.execute(
        "CREATE TABLE IF NOT EXISTS scan_triage ("
        "  triage_id       TEXT PRIMARY KEY,"
        "  scan_id         TEXT NOT NULL REFERENCES scans (scan_id),"
        "  verdict         TEXT NOT NULL CHECK (verdict IN ('tp', 'fp', 'fn')),"
        "  finding_id      TEXT,"
        "  ground_truth_id TEXT REFERENCES ground_truth (ground_truth_id),"
        "  triaged_by      TEXT NOT NULL DEFAULT 'manual',"
        "  notes           TEXT,"
        "  created_at      TEXT NOT NULL,"
        "  UNIQUE (scan_id, verdict, finding_id, ground_truth_id)"
        ")"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_triage_scan_id ON scan_triage (scan_id)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_triage_verdict ON scan_triage (verdict)"
    )

    # M5: correct mis-seeded pricing and backfill cost_usd (discovered 2026-05-26)
    # Opus 4.7 was seeded at $15/$75 (wrong); actual is $5/$25
    # Haiku 4.5 was seeded at $0.80/$4.00 (wrong); actual is $1.00/$5.00
    db.execute(
        "UPDATE model_pricing SET input_per_1m = 5.00, output_per_1m = 25.00 "
        "WHERE model = 'claude-opus-4-7' AND input_per_1m = 15.00"
    )
    db.execute(
        "UPDATE model_pricing SET input_per_1m = 1.00, output_per_1m = 5.00 "
        "WHERE model = 'claude-haiku-4-5-20251001' AND input_per_1m = 0.80"
    )
    # Recalculate cost_usd for all scans whose model pricing just changed
    db.execute(
        "UPDATE scans "
        "SET cost_usd = ("
        "  SELECT ROUND(CAST("
        "    (COALESCE(scans.input_tokens, 0)         * mp.input_per_1m +"
        "     COALESCE(scans.cache_creation_tokens, 0) * mp.input_per_1m * 1.25 +"
        "     COALESCE(scans.cache_read_tokens, 0)     * mp.input_per_1m * 0.10 +"
        "     COALESCE(scans.output_tokens, 0)         * mp.output_per_1m"
        "  ) / 1000000.0 AS NUMERIC), 6)"
        "  FROM model_pricing mp"
        "  WHERE mp.model = scans.model"
        "  ORDER BY mp.effective_from DESC LIMIT 1"
        ") "
        "WHERE scans.model IN ('claude-opus-4-7', 'claude-haiku-4-5-20251001')"
        "  AND (scans.input_tokens IS NOT NULL OR scans.output_tokens IS NOT NULL)"
    )

    # M6: project_benchmarks view — per-project/model; subquery avoids cost inflation
    #     from the one-to-many triage join
    db.execute("DROP VIEW IF EXISTS project_benchmarks")
    db.execute(
        "CREATE VIEW project_benchmarks AS "
        "SELECT "
        "  p.repo_name, s.model, "
        "  COUNT(s.scan_id)                                          AS scan_count, "
        "  ROUND(CAST(AVG(s.duration_seconds) AS NUMERIC), 1)        AS avg_duration_s, "
        "  ROUND(CAST(AVG(s.cost_usd) AS NUMERIC), 4)                AS avg_cost_usd, "
        "  ROUND(CAST(SUM(s.cost_usd) AS NUMERIC), 4)                AS total_cost_usd, "
        "  ROUND(AVG(s.input_tokens))                                 AS avg_input_tokens, "
        "  ROUND(AVG(s.output_tokens))                                AS avg_output_tokens, "
        "  COALESCE(SUM(tc.triage_count), 0)                         AS triage_count, "
        "  COALESCE(SUM(tc.tp_count), 0)                             AS tp_count, "
        "  COALESCE(SUM(tc.fp_count), 0)                             AS fp_count, "
        "  COALESCE(SUM(tc.fn_count), 0)                             AS fn_count, "
        "  ROUND(CAST(SUM(tc.tp_count) * 1.0 / "
        "    NULLIF(SUM(tc.tp_count) + SUM(tc.fp_count), 0) AS NUMERIC), 3) AS precision, "
        "  ROUND(CAST(SUM(tc.tp_count) * 1.0 / "
        "    NULLIF(SUM(tc.tp_count) + SUM(tc.fn_count), 0) AS NUMERIC), 3) AS recall "
        "FROM scans s "
        "JOIN projects p USING (project_id) "
        "LEFT JOIN ("
        "  SELECT scan_id, COUNT(*) AS triage_count, "
        "    COUNT(CASE WHEN verdict='tp' THEN 1 END) AS tp_count, "
        "    COUNT(CASE WHEN verdict='fp' THEN 1 END) AS fp_count, "
        "    COUNT(CASE WHEN verdict='fn' THEN 1 END) AS fn_count "
        "  FROM scan_triage GROUP BY scan_id"
        ") tc ON tc.scan_id = s.scan_id "
        "GROUP BY p.project_id, s.model "
        "ORDER BY p.repo_name, s.model"
    )

    # M4: model_benchmarks view (DROP + recreate; subquery fix applied in M6)
    db.execute("DROP VIEW IF EXISTS model_benchmarks")
    db.execute(
        "CREATE VIEW model_benchmarks AS "
        "SELECT "
        "  s.model, "
        "  COUNT(DISTINCT s.scan_id)                                AS scan_count, "
        "  COUNT(DISTINCT s.project_id)                            AS project_count, "
        "  ROUND(CAST(AVG(s.duration_seconds) AS NUMERIC), 1)      AS avg_duration_s, "
        "  ROUND(AVG(s.input_tokens))                               AS avg_input_tokens, "
        "  ROUND(AVG(s.output_tokens))                              AS avg_output_tokens, "
        "  ROUND(CAST(AVG(s.cost_usd) AS NUMERIC), 4)              AS avg_cost_usd, "
        "  ROUND(CAST(SUM(s.cost_usd) AS NUMERIC), 4)              AS total_cost_usd, "
        "  COALESCE(SUM(tc.triage_count), 0)                       AS triage_count, "
        "  COALESCE(SUM(tc.tp_count), 0)                           AS tp_count, "
        "  COALESCE(SUM(tc.fp_count), 0)                           AS fp_count, "
        "  COALESCE(SUM(tc.fn_count), 0)                           AS fn_count, "
        "  ROUND(CAST(SUM(tc.tp_count) * 1.0 / "
        "    NULLIF(SUM(tc.tp_count) + SUM(tc.fp_count), 0) AS NUMERIC), 3) AS precision, "
        "  ROUND(CAST(SUM(tc.tp_count) * 1.0 / "
        "    NULLIF(SUM(tc.tp_count) + SUM(tc.fn_count), 0) AS NUMERIC), 3) AS recall "
        "FROM scans s "
        "LEFT JOIN ("
        "  SELECT scan_id, COUNT(*) AS triage_count, "
        "    COUNT(CASE WHEN verdict='tp' THEN 1 END) AS tp_count, "
        "    COUNT(CASE WHEN verdict='fp' THEN 1 END) AS fp_count, "
        "    COUNT(CASE WHEN verdict='fn' THEN 1 END) AS fn_count "
        "  FROM scan_triage GROUP BY scan_id"
        ") tc ON tc.scan_id = s.scan_id "
        "GROUP BY s.model "
        "ORDER BY s.model"
    )


def compute_cost(db: DB, model: str,
                 input_tokens: int | None, output_tokens: int | None,
                 cache_creation_tokens: int = 0,
                 cache_read_tokens: int = 0) -> float | None:
    if not any([input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens]):
        return None
    row = db.fetchone(
        "SELECT input_per_1m, output_per_1m FROM model_pricing "
        "WHERE model = ? ORDER BY effective_from DESC LIMIT 1",
        (model,),
    )
    if not row:
        return None
    ip, op = row["input_per_1m"], row["output_per_1m"]
    # Anthropic cache pricing: write = 1.25× input, read = 0.10× input
    cost = (
        (input_tokens or 0)          * ip +
        (cache_creation_tokens or 0) * ip * 1.25 +
        (cache_read_tokens or 0)     * ip * 0.10 +
        (output_tokens or 0)         * op
    ) / 1_000_000
    return round(cost, 6)


def open_db(url_or_path: str) -> DB:
    db = DB(url_or_path)
    if not db.is_initialised():
        db.init_schema()
        db.commit()
        print(f"Initialised schema ({('Postgres' if url_or_path.startswith('postgres') else 'SQLite')})")
    _apply_migrations(db)
    _seed_model_pricing(db)
    db.commit()
    return db


# ── ID derivation ─────────────────────────────────────────────────────────────

def sha1_id(*parts: str) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()


def project_id_from(repo_url: str | None, project_name: str) -> str:
    return sha1_id(repo_url.strip().rstrip("/")) if repo_url else sha1_id("name", project_name)


def scan_id_from(project_id: str, timestamp: str, model: str) -> str:
    return sha1_id(project_id, timestamp, model)


def canonical_finding_id_from(project_id: str, finding_id: str) -> str:
    return sha1_id(project_id, finding_id)


def run_finding_id_from(scan_id: str, finding_id: str) -> str:
    return sha1_id(scan_id, finding_id)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Upsert helpers ────────────────────────────────────────────────────────────

def upsert_project(db: DB, envelope: dict,
                   project_url: str | None, scan_time: str) -> str:
    name = envelope["project"]["name"]
    pid = project_id_from(project_url, name)

    owner, repo_name = None, name
    if project_url:
        parts = project_url.rstrip("/").split("/")
        if len(parts) >= 2:
            owner, repo_name = parts[-2], parts[-1]

    if db.fetchone("SELECT 1 FROM projects WHERE project_id = ?", (pid,)):
        db.execute(
            "UPDATE projects SET last_scanned_at = ?, scan_count = scan_count + 1 "
            "WHERE project_id = ?",
            (scan_time, pid),
        )
    else:
        db.execute(
            "INSERT INTO projects "
            "(project_id, repo_url, repo_owner, repo_name, first_scanned_at, last_scanned_at, scan_count) "
            "VALUES (?, ?, ?, ?, ?, ?, 1)",
            (pid, project_url, owner, repo_name, scan_time, scan_time),
        )
    return pid


def insert_scan(db: DB, scan_id: str, project_id: str, envelope: dict,
                tool: str | None, input_tokens: int | None,
                output_tokens: int | None, json_path: str,
                cache_creation_tokens: int = 0,
                cache_read_tokens: int = 0,
                duration_seconds: float | None = None) -> None:
    scan = envelope["scan"]
    project = envelope["project"]
    cost = compute_cost(db, scan["model"], input_tokens, output_tokens,
                        cache_creation_tokens, cache_read_tokens)
    db.execute(
        "INSERT INTO scans "
        "(scan_id, project_id, timestamp, model, prompt_version, schema_version, "
        " tool, files_scanned, size_budget_status, commit_hash, branch, "
        " stack_packs_loaded, duration_seconds, input_tokens, output_tokens, cost_usd, "
        " cache_creation_tokens, cache_read_tokens, "
        " notes, findings_json_path, ingested_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            scan_id, project_id,
            scan["timestamp"], scan["model"], scan["prompt_version"],
            envelope["schema_version"], tool,
            project.get("files_scanned"), project.get("size_budget_status"),
            project.get("commit_hash"), project.get("branch"),
            json.dumps(project.get("stack_packs_loaded", [])),
            duration_seconds if duration_seconds is not None else scan.get("duration_seconds"),
            input_tokens, output_tokens, cost,
            cache_creation_tokens or None, cache_read_tokens or None,
            json.dumps(envelope.get("notes", [])),
            str(Path(json_path).resolve()),
            now_utc(),
        ),
    )


def insert_scorecard(db: DB, scan_id: str, envelope: dict) -> None:
    sc = envelope["summary"]["scorecard"]
    sev = envelope["summary"]["counts_by_severity"]
    conf = envelope["summary"]["counts_by_confidence"]
    db.execute(
        "INSERT INTO scorecards "
        "(scan_id, code, dependencies, secrets_and_config, architecture, overall, "
        " count_critical, count_high, count_medium, count_low, count_info, "
        " count_confidence_high, count_confidence_medium, count_confidence_low) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            scan_id,
            sc["code"], sc["dependencies"], sc["secrets_and_config"],
            sc["architecture"], sc["overall"],
            sev["critical"], sev["high"], sev["medium"], sev["low"], sev["info"],
            conf["high"], conf["medium"], conf["low"],
        ),
    )


def insert_data_profile(db: DB, scan_id: str, envelope: dict) -> None:
    dp = envelope.get("data_profile")
    if not dp:
        return
    db.execute(
        "INSERT INTO data_profiles "
        "(scan_id, sensitivity_tier, context_note, categories, regulatory_flags) "
        "VALUES (?,?,?,?,?)",
        (
            scan_id,
            dp["sensitivity_tier"], dp.get("context_note"),
            json.dumps(dp.get("categories", [])),
            json.dumps(dp.get("regulatory_flags", [])),
        ),
    )


def upsert_canonical_finding(db: DB, project_id: str, finding: dict,
                              scan_id: str, scan_time: str,
                              tool: str | None) -> str:
    cid = canonical_finding_id_from(project_id, finding["id"])
    ev = finding["evidence"]

    existing = db.fetchone(
        "SELECT corroboration_count, corroborating_tools FROM canonical_findings "
        "WHERE canonical_finding_id = ?",
        (cid,),
    )
    if existing:
        tools: list = json.loads(existing["corroborating_tools"] or "[]")
        if tool and tool not in tools:
            tools.append(tool)
            new_count = existing["corroboration_count"] + 1
        else:
            new_count = existing["corroboration_count"]
        db.execute(
            "UPDATE canonical_findings "
            "SET last_seen_scan_id=?, last_seen_at=?, "
            "    corroboration_count=?, corroborating_tools=? "
            "WHERE canonical_finding_id=?",
            (scan_id, scan_time, new_count, json.dumps(tools), cid),
        )
    else:
        db.execute(
            "INSERT INTO canonical_findings "
            "(canonical_finding_id, project_id, finding_id, category, title, "
            " evidence_file, evidence_line_start, "
            " first_seen_scan_id, last_seen_scan_id, first_seen_at, last_seen_at, "
            " corroboration_count, corroborating_tools, status, disclosure_status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?,'open','unreported')",
            (
                cid, project_id, finding["id"],
                finding["category"], finding["title"],
                ev["file"], ev["line_start"],
                scan_id, scan_id, scan_time, scan_time,
                json.dumps([tool] if tool else []),
            ),
        )
    return cid


def insert_run_finding(db: DB, scan_id: str, finding: dict,
                       canonical_id: str) -> None:
    ev = finding["evidence"]
    cvss = finding.get("cvss") or {}
    db.execute(
        "INSERT INTO run_findings "
        "(run_finding_id, scan_id, finding_id, canonical_finding_id, "
        " category, severity, confidence, title, "
        " evidence_file, evidence_line_start, evidence_line_end, evidence_quote, "
        " exploitation_path, remediation, owasp_mapping, dfd_element, "
        " references_list, cvss_version, cvss_vector, cvss_score) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            run_finding_id_from(scan_id, finding["id"]),
            scan_id, finding["id"], canonical_id,
            finding["category"], finding["severity"], finding["confidence"],
            finding["title"],
            ev["file"], ev["line_start"], ev["line_end"], ev["quote"],
            finding.get("exploitation_path"), finding["remediation"],
            json.dumps(finding.get("owasp_mapping", [])),
            finding.get("dfd_element"),
            json.dumps(finding.get("references", [])),
            cvss.get("version"), cvss.get("vector"), cvss.get("score"),
        ),
    )


# ── Main ingest ───────────────────────────────────────────────────────────────

def ingest(db_url: str, json_path: str, tool: str | None = None,
           input_tokens: int | None = None, output_tokens: int | None = None,
           cache_creation_tokens: int = 0, cache_read_tokens: int = 0,
           project_url: str | None = None,
           duration_seconds: float | None = None) -> str:

    envelope = json.loads(Path(json_path).read_text())

    ver = tuple(int(x) for x in envelope["schema_version"].split("."))
    if ver < MIN_SCHEMA_VERSION:
        print(f"Error: schema_version {envelope['schema_version']} unsupported. "
              f"Requires {'.'.join(str(x) for x in MIN_SCHEMA_VERSION)}+", file=sys.stderr)
        sys.exit(1)

    db = open_db(db_url)
    try:
        scan_time = envelope["scan"]["timestamp"]
        raw_model = envelope["scan"]["model"]
        envelope["scan"]["model"] = _normalize_model(raw_model)
        project_id = upsert_project(db, envelope, project_url, scan_time)
        sid = scan_id_from(project_id, scan_time, raw_model)  # use raw for stable ID

        if db.fetchone("SELECT 1 FROM scans WHERE scan_id = ?", (sid,)):
            print(f"Already ingested — scan {sid[:8]} skipped.")
            return sid

        insert_scan(db, sid, project_id, envelope, tool,
                    input_tokens, output_tokens, json_path,
                    cache_creation_tokens, cache_read_tokens,
                    duration_seconds)
        insert_scorecard(db, sid, envelope)
        insert_data_profile(db, sid, envelope)

        finding_count = 0
        for finding in envelope.get("findings", []):
            cid = upsert_canonical_finding(db, project_id, finding, sid, scan_time, tool)
            insert_run_finding(db, sid, finding, cid)
            finding_count += 1

        dp = envelope.get("data_profile")
        if dp:
            db.execute(
                "UPDATE projects SET sensitivity_tier = ? WHERE project_id = ?",
                (dp["sensitivity_tier"], project_id),
            )

        db.commit()

        sc = envelope["summary"]["scorecard"]
        sev = envelope["summary"]["counts_by_severity"]
        cost = compute_cost(db, envelope["scan"]["model"], input_tokens, output_tokens,
                            cache_creation_tokens, cache_read_tokens)
        cost_str = f"${cost:.4f}" if cost is not None else "unknown"
        print(f"✓ Ingested  {envelope['project']['name']}")
        print(f"  Scan ID   {sid[:8]}")
        print(f"  Tool      {tool or 'unspecified'}")
        print(f"  Model     {envelope['scan']['model']}")
        if input_tokens:
            cache_str = ""
            if cache_read_tokens:
                cache_str = f"  cache_read={cache_read_tokens:,}"
            elif cache_creation_tokens:
                cache_str = f"  cache_write={cache_creation_tokens:,}"
            print(f"  Tokens    {input_tokens:,}in / {output_tokens or 0:,}out{cache_str}  cost {cost_str}")
        print(f"  Findings  {finding_count}  "
              f"({sev['critical']}C {sev['high']}H {sev['medium']}M)")
        print(f"  Overall   {sc['overall']}  "
              f"(code:{sc['code']} deps:{sc['dependencies']} "
              f"secrets:{sc['secrets_and_config']} arch:{sc['architecture']})")
        return sid

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest a findings.json envelope into the eval database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("findings_json", help="Path to findings.json")
    parser.add_argument(
        "--tool",
        choices=["claude-code", "claude-ai", "cursor", "codex", "windsurf",
                 "aider", "copilot-agent", "gemini-cli", "ai-studio",
                 "api-anthropic", "api-openai", "api-google", "api-other",
                 "other"],
        help="Tool that produced this scan",
    )
    parser.add_argument("--input-tokens",  type=int)
    parser.add_argument("--output-tokens", type=int)
    parser.add_argument("--project-url",   help="Repository URL")
    parser.add_argument(
        "--db",
        default=str(DEFAULT_SQLITE_PATH),
        help=f"SQLite path when DATABASE_URL is not set (default: {DEFAULT_SQLITE_PATH})",
    )
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL") or args.db

    ingest(
        db_url=db_url,
        json_path=args.findings_json,
        tool=args.tool,
        input_tokens=args.input_tokens,
        output_tokens=args.output_tokens,
        project_url=args.project_url,
    )


if __name__ == "__main__":
    main()
