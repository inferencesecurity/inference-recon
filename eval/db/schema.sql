-- eval/db/schema.sql
-- Eval database schema for Inference Recon.
--
-- Compatible with SQLite (fallback) and PostgreSQL (primary backend).
-- No SQLite-specific idioms — migration = connection string swap (per D41).
--
-- Entity hierarchy:
--   projects  (1) ──► scans         (many)
--   projects  (1) ──► canonical_findings (many)
--   scans     (1) ──► run_findings   (many)
--   scans     (1) ──► scorecards     (1)
--   scans     (1) ──► data_profiles  (1)
--   projects  (1) ──► ground_truth   (many)
--   run_findings ──► canonical_findings  (many-to-one)
--
-- ID convention:
--   All IDs are TEXT: full SHA-1 hex (40 chars) for DB primary keys.
--   The 8-char finding.id in findings.json is stored as-is from the envelope;
--   canonical_finding_id = sha1(project_id + "|" + finding_id) for cross-project safety.


-- ── projects ─────────────────────────────────────────────────────────────────
-- One row per distinct repository / project being scanned.
-- project_id: sha1(repo_url) if known, else sha1("name|" + project_name).

CREATE TABLE IF NOT EXISTS projects (
    project_id          TEXT    PRIMARY KEY,
    repo_url            TEXT,                       -- null for local-only projects
    repo_owner          TEXT,
    repo_name           TEXT    NOT NULL,
    primary_language    TEXT,                       -- filled from first scan inventory
    primary_framework   TEXT,
    sensitivity_tier    TEXT,                       -- updated from each scan's data_profile
    first_scanned_at    TEXT    NOT NULL,
    last_scanned_at     TEXT    NOT NULL,
    scan_count          INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_projects_repo_url ON projects (repo_url);


-- ── scans ─────────────────────────────────────────────────────────────────────
-- One row per scan execution. Immutable after insert.
-- scan_id: sha1(project_id + "|" + timestamp + "|" + model).

CREATE TABLE IF NOT EXISTS scans (
    scan_id             TEXT    PRIMARY KEY,
    project_id          TEXT    NOT NULL REFERENCES projects (project_id),
    timestamp           TEXT    NOT NULL,           -- ISO 8601 from scan.timestamp
    model               TEXT    NOT NULL,           -- e.g. claude-opus-4-7
    prompt_version      TEXT    NOT NULL,           -- e.g. 0.1
    schema_version      TEXT    NOT NULL,           -- e.g. 0.3
    tool                TEXT,                       -- claude-code, cursor, codex, etc.
                                                    -- NULL until schema v0.4 adds scan.tool
    files_scanned       INTEGER,
    size_budget_status  TEXT    CHECK (size_budget_status IN ('within', 'exceeded', 'unknown')),
    commit_hash         TEXT,
    branch              TEXT,
    stack_packs_loaded  TEXT,                       -- JSON array
    duration_seconds    REAL,
    input_tokens        INTEGER,                    -- tracked externally, not in envelope
    output_tokens       INTEGER,
    cache_creation_tokens INTEGER,                  -- tokens written to prompt cache
    cache_read_tokens   INTEGER,                    -- tokens served from prompt cache
    cost_usd            REAL,                       -- computed from model_pricing at ingest time
    notes               TEXT,                       -- JSON array from envelope.notes
    findings_json_path  TEXT,                       -- absolute path to source file
    ingested_at         TEXT    NOT NULL            -- set by ingest.py, not the model
);

CREATE INDEX IF NOT EXISTS idx_scans_project_id  ON scans (project_id);
CREATE INDEX IF NOT EXISTS idx_scans_timestamp   ON scans (timestamp);
CREATE INDEX IF NOT EXISTS idx_scans_tool        ON scans (tool);
CREATE INDEX IF NOT EXISTS idx_scans_model       ON scans (model);
CREATE INDEX IF NOT EXISTS idx_scans_prompt_ver  ON scans (prompt_version);


-- ── canonical_findings ───────────────────────────────────────────────────────
-- One row per unique vulnerability per project, deduplicated across all runs
-- and tools. This is the vulnerability database.
-- canonical_finding_id: sha1(project_id + "|" + finding_id)

CREATE TABLE IF NOT EXISTS canonical_findings (
    canonical_finding_id    TEXT    PRIMARY KEY,
    project_id              TEXT    NOT NULL REFERENCES projects (project_id),
    finding_id              TEXT    NOT NULL,       -- original 8-char hash from envelope
    category                TEXT    NOT NULL,
    title                   TEXT    NOT NULL,
    evidence_file           TEXT    NOT NULL,
    evidence_line_start     INTEGER NOT NULL,
    first_seen_scan_id      TEXT    REFERENCES scans (scan_id),
    last_seen_scan_id       TEXT    REFERENCES scans (scan_id),
    first_seen_at           TEXT    NOT NULL,
    last_seen_at            TEXT    NOT NULL,
    corroboration_count     INTEGER NOT NULL DEFAULT 1,
    corroborating_tools     TEXT,                   -- JSON array of tool names
    -- lifecycle
    status                  TEXT    NOT NULL DEFAULT 'open'
                                    CHECK (status IN ('open', 'fixed', 'wontfix')),
    -- disclosure workflow (Pro)
    disclosure_status       TEXT    NOT NULL DEFAULT 'unreported'
                                    CHECK (disclosure_status IN (
                                        'unreported', 'disclosed', 'acknowledged',
                                        'fixed', 'wontfix')),
    disclosed_at            TEXT,
    fixed_at                TEXT,
    notes                   TEXT,
    UNIQUE (project_id, finding_id)
);

CREATE INDEX IF NOT EXISTS idx_canonical_project   ON canonical_findings (project_id);
CREATE INDEX IF NOT EXISTS idx_canonical_category  ON canonical_findings (category);
CREATE INDEX IF NOT EXISTS idx_canonical_status    ON canonical_findings (status);


-- ── run_findings ─────────────────────────────────────────────────────────────
-- One row per finding per scan run. Immutable after insert.
-- run_finding_id: sha1(scan_id + "|" + finding_id)

CREATE TABLE IF NOT EXISTS run_findings (
    run_finding_id          TEXT    PRIMARY KEY,
    scan_id                 TEXT    NOT NULL REFERENCES scans (scan_id),
    finding_id              TEXT    NOT NULL,       -- 8-char hash from envelope
    canonical_finding_id    TEXT    REFERENCES canonical_findings (canonical_finding_id),
    category                TEXT    NOT NULL,
    severity                TEXT    NOT NULL CHECK (severity IN ('critical','high','medium','low','info')),
    confidence              TEXT    NOT NULL CHECK (confidence IN ('high','medium','low')),
    title                   TEXT    NOT NULL,
    evidence_file           TEXT    NOT NULL,
    evidence_line_start     INTEGER NOT NULL,
    evidence_line_end       INTEGER NOT NULL,
    evidence_quote          TEXT    NOT NULL,
    exploitation_path       TEXT,
    remediation             TEXT    NOT NULL,
    owasp_mapping           TEXT,                   -- JSON array
    dfd_element             TEXT,
    references_list         TEXT,                   -- JSON array ("references" reserved in some SQL)
    cvss_version            TEXT,
    cvss_vector             TEXT,
    cvss_score              REAL
);

CREATE INDEX IF NOT EXISTS idx_run_findings_scan_id   ON run_findings (scan_id);
CREATE INDEX IF NOT EXISTS idx_run_findings_canonical ON run_findings (canonical_finding_id);
CREATE INDEX IF NOT EXISTS idx_run_findings_severity  ON run_findings (severity);
CREATE INDEX IF NOT EXISTS idx_run_findings_category  ON run_findings (category);


-- ── scorecards ───────────────────────────────────────────────────────────────
-- One row per scan. Derived from findings — stored for query performance.

CREATE TABLE IF NOT EXISTS scorecards (
    scan_id                 TEXT    PRIMARY KEY REFERENCES scans (scan_id),
    code                    TEXT    CHECK (code IN ('A','B','C','D','F','N/A')),
    dependencies            TEXT    CHECK (dependencies IN ('A','B','C','D','F','N/A')),
    secrets_and_config      TEXT    CHECK (secrets_and_config IN ('A','B','C','D','F','N/A')),
    architecture            TEXT    CHECK (architecture IN ('A','B','C','D','F','N/A')),
    overall                 TEXT    CHECK (overall IN ('A','B','C','D','F','N/A')),
    count_critical          INTEGER NOT NULL DEFAULT 0,
    count_high              INTEGER NOT NULL DEFAULT 0,
    count_medium            INTEGER NOT NULL DEFAULT 0,
    count_low               INTEGER NOT NULL DEFAULT 0,
    count_info              INTEGER NOT NULL DEFAULT 0,
    count_confidence_high   INTEGER NOT NULL DEFAULT 0,
    count_confidence_medium INTEGER NOT NULL DEFAULT 0,
    count_confidence_low    INTEGER NOT NULL DEFAULT 0
);


-- ── data_profiles ────────────────────────────────────────────────────────────
-- One row per scan. Stored as JSON for the arrays; queried via sensitivity_tier.

CREATE TABLE IF NOT EXISTS data_profiles (
    scan_id             TEXT    PRIMARY KEY REFERENCES scans (scan_id),
    sensitivity_tier    TEXT    NOT NULL
                                CHECK (sensitivity_tier IN (
                                    'minimal','standard','elevated','high','critical')),
    context_note        TEXT,
    categories          TEXT    NOT NULL,           -- JSON array of data_category_entry objects
    regulatory_flags    TEXT    NOT NULL            -- JSON array of regulatory_flag objects
);

CREATE INDEX IF NOT EXISTS idx_data_profiles_tier ON data_profiles (sensitivity_tier);


-- ── ground_truth ─────────────────────────────────────────────────────────────
-- Eval-only. Human-annotated known vulnerabilities for precision/recall tracking.
-- ground_truth_id: sha1(project_id + "|" + evidence_file + "|" + str(evidence_line) + "|" + expected_category)

CREATE TABLE IF NOT EXISTS ground_truth (
    ground_truth_id     TEXT    PRIMARY KEY,
    project_id          TEXT    NOT NULL REFERENCES projects (project_id),
    vuln_description    TEXT    NOT NULL,
    expected_category   TEXT,
    expected_severity   TEXT    CHECK (expected_severity IN ('critical','high','medium','low','info')),
    cve_id              TEXT,
    evidence_file       TEXT,
    evidence_line       INTEGER,
    verified_by         TEXT,                       -- "manual", "cve", "semgrep", etc.
    notes               TEXT,
    created_at          TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ground_truth_project ON ground_truth (project_id);


-- ── model_pricing ─────────────────────────────────────────────────────────────
-- Per-model, per-date pricing so cost_usd on scans can be computed accurately
-- even after pricing changes. Seeded by ingest.py; update when Anthropic prices change.

CREATE TABLE IF NOT EXISTS model_pricing (
    model           TEXT    NOT NULL,
    effective_from  TEXT    NOT NULL,   -- YYYY-MM-DD
    provider        TEXT    NOT NULL,
    input_per_1m    REAL    NOT NULL,   -- USD per million input tokens
    output_per_1m   REAL    NOT NULL,   -- USD per million output tokens
    effective_to    TEXT,               -- NULL = active / current
    notes           TEXT,
    PRIMARY KEY (model, effective_from)
);


-- ── scan_triage ───────────────────────────────────────────────────────────────
-- Human-annotated triage of individual findings per scan. Source of precision/recall.
--   tp  — finding produced, correct (true positive)
--   fp  — finding produced, incorrect (false positive)
--   fn  — finding NOT produced but should have been (false negative; link ground_truth_id)

CREATE TABLE IF NOT EXISTS scan_triage (
    triage_id       TEXT    PRIMARY KEY,            -- sha1(scan_id|verdict|finding_id|gt_id)
    scan_id         TEXT    NOT NULL REFERENCES scans (scan_id),
    verdict         TEXT    NOT NULL CHECK (verdict IN ('tp', 'fp', 'fn')),
    finding_id      TEXT,                           -- set for tp/fp; NULL for fn
    ground_truth_id TEXT    REFERENCES ground_truth (ground_truth_id),
    triaged_by      TEXT    NOT NULL DEFAULT 'manual',
    notes           TEXT,
    created_at      TEXT    NOT NULL,
    UNIQUE (scan_id, verdict, finding_id, ground_truth_id)
);

CREATE INDEX IF NOT EXISTS idx_triage_scan_id  ON scan_triage (scan_id);
CREATE INDEX IF NOT EXISTS idx_triage_verdict  ON scan_triage (verdict);


-- ── project_benchmarks (view) ────────────────────────────────────────────────
-- Per-project, per-model aggregate: keeps calibration (VAmPI) and real-world
-- (Track 1) accuracy separate so they don't blend in model_benchmarks.

CREATE OR REPLACE VIEW project_benchmarks AS
SELECT
    p.repo_name,
    s.model,
    COUNT(s.scan_id)                                            AS scan_count,
    ROUND(CAST(AVG(s.duration_seconds) AS NUMERIC), 1)           AS avg_duration_s,
    ROUND(CAST(AVG(s.cost_usd) AS NUMERIC), 4)                   AS avg_cost_usd,
    ROUND(CAST(SUM(s.cost_usd) AS NUMERIC), 4)                   AS total_cost_usd,
    ROUND(AVG(s.input_tokens))                                   AS avg_input_tokens,
    ROUND(AVG(s.output_tokens))                                  AS avg_output_tokens,
    COALESCE(SUM(tc.triage_count), 0)                            AS triage_count,
    COALESCE(SUM(tc.tp_count), 0)                                AS tp_count,
    COALESCE(SUM(tc.fp_count), 0)                                AS fp_count,
    COALESCE(SUM(tc.fn_count), 0)                                AS fn_count,
    ROUND(CAST(
        SUM(tc.tp_count) * 1.0 /
        NULLIF(SUM(tc.tp_count) + SUM(tc.fp_count), 0) AS NUMERIC), 3
    )                                                            AS precision,
    ROUND(CAST(
        SUM(tc.tp_count) * 1.0 /
        NULLIF(SUM(tc.tp_count) + SUM(tc.fn_count), 0) AS NUMERIC), 3
    )                                                            AS recall
FROM scans s
JOIN projects p USING (project_id)
LEFT JOIN (
    SELECT scan_id,
           COUNT(*)                                              AS triage_count,
           COUNT(CASE WHEN verdict = 'tp' THEN 1 END)           AS tp_count,
           COUNT(CASE WHEN verdict = 'fp' THEN 1 END)           AS fp_count,
           COUNT(CASE WHEN verdict = 'fn' THEN 1 END)           AS fn_count
    FROM scan_triage GROUP BY scan_id
) tc ON tc.scan_id = s.scan_id
GROUP BY p.project_id, s.model
ORDER BY p.repo_name, s.model;


-- ── model_benchmarks (view) ───────────────────────────────────────────────────
-- Per-model aggregate: cost, throughput, and precision/recall where triage exists.
-- Precision and recall are NULL until scan_triage rows exist for that model.

CREATE OR REPLACE VIEW model_benchmarks AS
SELECT
    s.model,
    COUNT(DISTINCT s.scan_id)                                   AS scan_count,
    COUNT(DISTINCT s.project_id)                                AS project_count,
    ROUND(CAST(AVG(s.duration_seconds) AS NUMERIC), 1)           AS avg_duration_s,
    ROUND(AVG(s.input_tokens))                                   AS avg_input_tokens,
    ROUND(AVG(s.output_tokens))                                  AS avg_output_tokens,
    ROUND(CAST(AVG(s.cost_usd) AS NUMERIC), 4)                   AS avg_cost_usd,
    ROUND(CAST(SUM(s.cost_usd) AS NUMERIC), 4)                   AS total_cost_usd,
    COALESCE(SUM(tc.triage_count), 0)                            AS triage_count,
    COALESCE(SUM(tc.tp_count), 0)                                AS tp_count,
    COALESCE(SUM(tc.fp_count), 0)                                AS fp_count,
    COALESCE(SUM(tc.fn_count), 0)                                AS fn_count,
    ROUND(CAST(
        SUM(tc.tp_count) * 1.0 /
        NULLIF(SUM(tc.tp_count) + SUM(tc.fp_count), 0) AS NUMERIC), 3
    )                                                            AS precision,
    ROUND(CAST(
        SUM(tc.tp_count) * 1.0 /
        NULLIF(SUM(tc.tp_count) + SUM(tc.fn_count), 0) AS NUMERIC), 3
    )                                                            AS recall
FROM scans s
LEFT JOIN (
    SELECT scan_id,
           COUNT(*)                                             AS triage_count,
           COUNT(CASE WHEN verdict = 'tp' THEN 1 END)          AS tp_count,
           COUNT(CASE WHEN verdict = 'fp' THEN 1 END)          AS fp_count,
           COUNT(CASE WHEN verdict = 'fn' THEN 1 END)          AS fn_count
    FROM scan_triage GROUP BY scan_id
) tc ON tc.scan_id = s.scan_id
GROUP BY s.model
ORDER BY s.model;
