"""
Seed VAmPI ground truth and triage all three model runs (Opus, Sonnet, Haiku).

VAmPI (https://github.com/erev0s/VAmPI) is a deliberately vulnerable Flask REST API.
Ground truth sourced from the repo README and OWASP API Security Top 10 (2019) mapping.
"""

import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))
from ingest import DB, open_db

DB_PATH = Path(__file__).parent / "db" / "eval.db"

VAMPI_PROJECT_ID = "3895c51b809562d3e2c68ee74d39b753551e9aca"
NOW = datetime.now(timezone.utc).isoformat()

# ──────────────────────────────────────────────────────────
# Ground truth: the 10 intentional VAmPI vulnerabilities
# Each entry: (short_id, description, category, severity, file, line, notes)
# ──────────────────────────────────────────────────────────
GROUND_TRUTH = [
    ("GT-01", "SQL injection via unsanitised username path parameter in GET /users/v1/{username}",
     "CODE_injection", "critical", "models/user_model.py", 51,
     "Raw f-string SQL query; confirmed by repo docs"),

    ("GT-02", "Broken Object Level Authorization: any authenticated user can read any book secret via GET /books/v1/{book_title}",
     "AUTHZ_failure", "critical", "api_views/books.py", 47,
     "Authorization checks omitted; confirmed by repo docs"),

    ("GT-03", "Mass assignment: attacker can self-promote to admin by including admin=true in POST /users/v1/register body",
     "AUTHZ_failure", "critical", "api_views/users.py", 58,
     "Flask request.get_json() passed directly to model; confirmed by repo docs"),

    ("GT-04", "Broken Function Level Authorization: any authenticated user can change any other user's password via PUT /users/v1/{username}/password",
     "AUTHZ_failure", "critical", "api_views/users.py", 121,
     "No ownership check; confirmed by repo docs"),

    ("GT-05", "Hardcoded weak JWT signing secret 'random' in config.py enables token forgery",
     "SECRET_hardcoded", "critical", "config.py", 10,
     "Trivially guessable; confirmed by repo docs"),

    ("GT-06", "Unauthenticated debug endpoint GET /users/v1/_debug returns all users and plaintext passwords",
     "ARCH_data_exposure", "high", "api_views/users.py", 24,
     "No auth decorator; confirmed by repo docs"),

    ("GT-07", "Plaintext password storage — passwords stored and compared without hashing",
     "CODE_crypto_failure", "high", "models/user_model.py", 15,
     "No bcrypt/argon2; confirmed by repo docs"),

    ("GT-08", "No rate limiting on any endpoint — brute-force and credential stuffing trivially possible",
     "INSECURE_DESIGN", "high", "app.py", 14,
     "No Flask-Limiter or equivalent; confirmed by repo docs"),

    ("GT-09", "Flask debug mode enabled in production entrypoint (debug=True on 0.0.0.0)",
     "CONFIG_insecure_default", "high", "app.py", 14,
     "Exposes interactive Werkzeug debugger; confirmed by repo docs"),

    ("GT-10", "User enumeration via distinct error messages on login and user-lookup endpoints",
     "INSECURE_DESIGN", "medium", "api_views/users.py", 85,
     "Different HTTP status and message bodies for valid vs invalid users"),
]

# ──────────────────────────────────────────────────────────
# Scan IDs for the three VAmPI runs
# ──────────────────────────────────────────────────────────
SCAN_IDS = {
    "claude-opus-4-7":           "bf5b5edc699076642f4b96e12b8d2d567555a73a",
    "claude-sonnet-4-6":         "bcb73b5e98c1edd4216b8a2e08cc50f1ecc323df",
    "claude-haiku-4-5-20251001": "58149a91962f6e7a97034d1bd6b856e10f595b96",
}

# ──────────────────────────────────────────────────────────
# Triage entries: 5-tuples of (evidence_file, evidence_line_start, gt_short_id_or_None, notes, category)
# The category field disambiguates cases where two findings share the same file:line.
# ──────────────────────────────────────────────────────────
TRIAGE_BY_MODEL = {
    "claude-opus-4-7": {
        "tp": [
            ("api_views/users.py",  65,  "GT-03", "Mass assignment to admin",          "AUTHZ_failure"),
            ("api_views/users.py", 158,  "GT-04", "Unauthorized password change",       "AUTHZ_failure"),
            ("config.py",           14,  "GT-05", "Hardcoded JWT secret",               "SECRET_hardcoded"),
            ("models/user_model.py",64,  "GT-01", "SQL injection",                      "CODE_injection"),
            ("api_views/books.py",  48,  "GT-02", "BOLA on books",                      "AUTHZ_failure"),
            ("api_views/users.py",  25,  "GT-06", "Debug endpoint exposes passwords",   "ARCH_data_exposure"),
            ("api_views/users.py",  89,  "GT-08", "No rate limiting",                   "INSECURE_DESIGN"),
            ("api_views/users.py",  95,  "GT-07", "Plaintext passwords",                "CODE_crypto_failure"),
            ("api_views/users.py", 104,  "GT-10", "User enumeration",                   "INSECURE_DESIGN"),
            ("app.py",              16,  "GT-09", "Debug mode in production",            "CONFIG_insecure_default"),
        ],
        "fp": [
            ("Dockerfile",           8,  None, "Container runs as root — valid but not in VAmPI documented vuln list",   "CONFIG_insecure_default"),
            ("models/user_model.py", 56, None, "Debug endpoint passwords — duplicate angle on GT-06",                    "SECRET_in_logs"),
            ("api_views/main.py",    6,  None, "/createdb unprotected — valid but not in VAmPI documented vuln list",    "ARCH_attack_surface"),
            ("api_views/users.py", 116, None, "No security event logging — valid but not in VAmPI documented vuln list", "ARCH_logging_gap"),
            ("api_views/users.py", 130, None, "ReDoS email regex — valid but not in VAmPI intentional vuln list",        "CODE_unsafe_api_use"),
            ("config.py",            7,  None, "No CSRF protection — valid but not in VAmPI documented vuln list",       "INTEGRITY_failure"),
        ],
    },

    "claude-sonnet-4-6": {
        "tp": [
            ("api_views/books.py",  47,  "GT-02", "BOLA on books",                      "AUTHZ_failure"),
            ("api_views/users.py",  62,  "GT-03", "Mass assignment to admin",            "AUTHZ_failure"),
            ("api_views/users.py", 131,  "GT-04", "Unauthorized password change",        "AUTHZ_failure"),
            ("config.py",           12,  "GT-05", "Hardcoded JWT secret",                "SECRET_hardcoded"),
            ("models/user_model.py",57,  "GT-01", "SQL injection",                       "CODE_injection"),
            ("api_views/users.py",  24,  "GT-06", "Debug endpoint",                      "ARCH_attack_surface"),
            ("app.py",              14,  "GT-08", "No rate limiting",                    "INSECURE_DESIGN"),
            ("app.py",              14,  "GT-09", "Debug mode",                          "CONFIG_insecure_default"),
            ("models/user_model.py",18,  "GT-07", "Plaintext passwords",                 "CODE_crypto_failure"),
            ("api_views/users.py",  88,  "GT-10", "User enumeration",                    "ARCH_data_exposure"),
        ],
        "fp": [
            ("api_views/main.py",    9,  None, "/vulnerable field self-identification — info-level, not a security finding",    "ARCH_data_exposure"),
            ("docker-compose.yaml",  9,  None, "JWT token lifetime — reasonable config observation, not a VAmPI vuln",          "CONFIG_insecure_default"),
            ("api_views/users.py", 106,  None, "Email update BOLA — valid but not in official VAmPI vuln list",                 "AUTHZ_failure"),
            ("openapi_specs/openapi3.yml", 19, None, "/createdb unprotected — valid but not in official VAmPI vuln list",       "ARCH_missing_authz"),
            ("api_views/users.py",  84,  None, "No security event logging — valid but not in official VAmPI vuln list",         "ARCH_logging_gap"),
            ("api_views/users.py", 113,  None, "ReDoS via email regex — valid but not in VAmPI intentional vuln list",          "INSECURE_DESIGN"),
        ],
    },

    "claude-haiku-4-5-20251001": {
        "tp": [
            ("api_views/books.py",  47,  "GT-02", "BOLA on books",                                                    "AUTHZ_failure"),
            ("api_views/users.py",  58,  "GT-03", "Mass assignment to admin",                                          "AUTHZ_failure"),
            ("api_views/users.py", 121,  "GT-04", "Unauthorized password change",                                      "AUTHZ_failure"),
            ("config.py",           10,  "GT-05", "Hardcoded JWT secret (labeled as CONFIG_excessive_permissions)",    "CONFIG_excessive_permissions"),
            ("models/user_model.py",51,  "GT-01", "SQL injection",                                                    "CODE_injection"),
            ("api_views/users.py",  37,  "GT-06", "Debug endpoint",                                                   "ARCH_data_exposure"),
            ("app.py",              14,  "GT-09", "Debug mode",                                                        "CONFIG_insecure_default"),
            ("models/user_model.py",15,  "GT-07", "Plaintext passwords",                                              "ARCH_data_exposure"),
            ("api_views/users.py",  85,  "GT-10", "User enumeration",                                                 "INSECURE_DESIGN"),
            # Two findings at users.py:73 — disambiguate by category
            ("api_views/users.py",  73,  "GT-08", "No rate limiting",                                                 "CODE_input_validation"),
        ],
        "fp": [
            ("api_views/users.py", 110, None, "ReDoS email regex — valid but not in VAmPI intentional vuln list",        "CODE_injection"),
            ("openapi_specs/openapi3.yml", 109, None, "GET /users/v1 publicly accessible — valid obs, not in official list", "ARCH_missing_authz"),
            ("app.py",              14, None, "Flask debug logs auth tokens — duplicate angle on GT-09",                  "SECRET_in_logs"),
            ("models/books_model.py",10, None, "IDOR title uniqueness — tenuous finding",                                 "CODE_input_validation"),
            # Two findings at users.py:73 — the logging one is FP
            ("api_views/users.py",  73, None, "No auth failure logging — valid but not in official VAmPI vuln list",     "ARCH_logging_gap"),
            ("requirements.txt",     1, None, "No lockfile — valid but not in official VAmPI vuln list",                  "DEP_supply_chain_risk"),
        ],
    },
}


def make_gt_id(short_id: str) -> str:
    return hashlib.sha1(f"vampi-{short_id}".encode()).hexdigest()


def make_triage_id(scan_id: str, verdict: str, finding_id: str | None, gt_id: str | None) -> str:
    key = f"{scan_id}:{verdict}:{finding_id or ''}:{gt_id or ''}"
    return hashlib.sha1(key.encode()).hexdigest()


def seed_ground_truth(db: DB):
    for (short_id, desc, cat, sev, file, line, notes) in GROUND_TRUTH:
        gt_id = make_gt_id(short_id)
        db.execute("""
            INSERT INTO ground_truth
                (ground_truth_id, project_id, vuln_description, expected_category,
                 expected_severity, evidence_file, evidence_line, verified_by, notes, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT DO NOTHING
        """, (gt_id, VAMPI_PROJECT_ID, desc, cat, sev, file, line, "manual", notes, NOW))
    db.commit()
    print(f"  Seeded {len(GROUND_TRUTH)} ground truth entries")


def _lookup_finding(db: DB, scan_id: str,
                    ev_file: str, ev_line: int, category: str) -> str | None:
    """Return finding_id for a specific (scan, file, line, category). None if not found."""
    row = db.execute("""
        SELECT finding_id FROM run_findings
        WHERE scan_id = ? AND evidence_file = ? AND evidence_line_start = ? AND category = ?
    """, (scan_id, ev_file, ev_line, category)).fetchone()
    return row["finding_id"] if row else None


def triage_scan(db: DB, model: str, scan_id: str):
    # Clear any previous triage for this scan to avoid stale data
    db.execute("DELETE FROM scan_triage WHERE scan_id = ?", (scan_id,))

    spec = TRIAGE_BY_MODEL[model]
    inserted = 0

    # ── TPs ──
    for (ev_file, ev_line, gt_short, notes, category) in spec["tp"]:
        gt_id = make_gt_id(gt_short) if gt_short else None
        finding_id = _lookup_finding(db, scan_id, ev_file, ev_line, category)
        if finding_id is None:
            print(f"  WARN: no finding for {model} @ {ev_file}:{ev_line} cat={category} (tp)")
            continue
        triage_id = make_triage_id(scan_id, "tp", finding_id, gt_id)
        db.execute("""
            INSERT INTO scan_triage
                (triage_id, scan_id, verdict, finding_id, ground_truth_id, triaged_by, notes, created_at)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT DO NOTHING
        """, (triage_id, scan_id, "tp", finding_id, gt_id, "manual", notes, NOW))
        inserted += 1

    # ── FPs ──
    for (ev_file, ev_line, _, notes, category) in spec["fp"]:
        finding_id = _lookup_finding(db, scan_id, ev_file, ev_line, category)
        if finding_id is None:
            print(f"  WARN: no finding for {model} @ {ev_file}:{ev_line} cat={category} (fp)")
            continue
        triage_id = make_triage_id(scan_id, "fp", finding_id, None)
        db.execute("""
            INSERT INTO scan_triage
                (triage_id, scan_id, verdict, finding_id, ground_truth_id, triaged_by, notes, created_at)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT DO NOTHING
        """, (triage_id, scan_id, "fp", finding_id, None, "manual", notes, NOW))
        inserted += 1

    # ── FNs — ground truth entries not found by this model ──
    tp_gt_ids = {make_gt_id(gt) for (_, _, gt, _, _) in spec["tp"] if gt}
    for (short_id, desc, *_) in GROUND_TRUTH:
        gt_id = make_gt_id(short_id)
        if gt_id not in tp_gt_ids:
            triage_id = make_triage_id(scan_id, "fn", None, gt_id)
            db.execute("""
                INSERT INTO scan_triage
                    (triage_id, scan_id, verdict, finding_id, ground_truth_id, triaged_by, notes, created_at)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT DO NOTHING
            """, (triage_id, scan_id, "fn", None, gt_id, "manual",
                  f"Model missed: {desc[:80]}", NOW))
            inserted += 1

    db.commit()

    # ── summary ──
    tp = len(spec["tp"])
    fp = len(spec["fp"])
    fn = len(GROUND_TRUTH) - len(tp_gt_ids)
    precision = tp / (tp + fp) if (tp + fp) else 0
    recall    = tp / (tp + fn) if (tp + fn) else 0
    print(f"  {model:35s}  TP={tp}  FP={fp}  FN={fn}  "
          f"precision={precision:.2f}  recall={recall:.2f}  ({inserted} rows)")


def main():
    db_url = os.environ.get("DATABASE_URL", str(DB_PATH))
    db = open_db(db_url)

    print("Seeding ground truth...")
    seed_ground_truth(db)

    print("\nTriaging VAmPI scans...")
    for model, scan_id in SCAN_IDS.items():
        triage_scan(db, model, scan_id)

    print("\nmodel_benchmarks (VAmPI models):")
    rows = db.execute("""
        SELECT mb.model, mb.scan_count, mb.avg_cost_usd,
               mb.tp_count, mb.fp_count, mb.fn_count,
               mb.precision, mb.recall
        FROM model_benchmarks mb
        WHERE mb.model IN ('claude-opus-4-7','claude-sonnet-4-6','claude-haiku-4-5-20251001')
        ORDER BY mb.model
    """).fetchall()
    print(f"  {'model':<35} scans  cost    TP  FP  FN  prec  recall")
    for r in rows:
        print(f"  {r['model']:<35} {r['scan_count']:>5}  ${r['avg_cost_usd'] or 0:.4f}  "
              f"{r['tp_count']:>2}  {r['fp_count']:>2}  {r['fn_count']:>2}  "
              f"{r['precision'] or 0:.2f}  {r['recall'] or 0:.2f}")

    db.close()


if __name__ == "__main__":
    main()
