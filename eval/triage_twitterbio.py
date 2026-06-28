"""
Triage all twitterbio scan runs (Opus Jan, Sonnet, Opus May, Haiku).

twitterbio (https://github.com/Nutlope/twitterbio) is a minimal Next.js + Together AI app.
No pre-defined ground truth — Track 1 real-world repo. Precision only; recall is unknown.

Triage basis: manual code review of app/api/together/route.ts and package.json.
Notable: GitHub issue #46 independently corroborates the open endpoint finding.
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
NOW = datetime.now(timezone.utc).isoformat()

SCAN_IDS = {
    "claude-opus-4-7-jan":        "bf4d221c1c667c58a6d784de7043a67ad730a72e",
    "claude-sonnet-4-6":          "2cfdb3580a3f2f075f9de33b3693bd4bf586b0e2",
    "claude-opus-4-7-may":        "97c634a1c849fdfd105fd862fc43f6bcca2c73bb",
    "claude-haiku-4-5-20251001":  "d600e7482210ebcfd28328a39d29afb060287844",
}

# ── Triage entries: (evidence_file, evidence_line, notes, category) ───────────
# No ground_truth_id — Track 1 has no pre-defined ground truth.
# Precision only; no FN entries.

TRIAGE = {
    "claude-opus-4-7-jan": {
        "tp": [
            ("app/api/together/route.ts", 6, "Unauthenticated endpoint + no rate limiting — open cost-burning proxy",     "INSECURE_DESIGN"),
            ("app/api/together/route.ts", 7, "No validation on model/prompt fields — client fully controls API params",    "CODE_input_validation"),
        ],
        "fp": [
            ("app/page.tsx",              159, "DOM-XSS speculation on bio text — no evidence of unsafe rendering path",  "OTHER"),
            ("app/api/together/route.ts",   6, "Logging gap — marginal on 22-line demo, not a meaningful security gap",   "ARCH_logging_gap"),
        ],
    },

    "claude-sonnet-4-6": {
        "tp": [
            ("app/api/together/route.ts", 4, "Open endpoint, no auth/rate limit — corroborated by GitHub issue #46",      "ARCH_missing_authz"),
            ("app/api/together/route.ts", 5, "Client-controlled model forwarded without allowlist; Qwen check ≠ allowlist","ARCH_trust_boundary_violation"),
            ("app/api/together/route.ts", 6, "Unbounded prompt sent to LLM — no length cap on input cost",                "INSECURE_DESIGN"),
        ],
        "fp": [
            ("app/api/together/route.ts", 4, "Logging gap — marginal on a demo app",                                      "ARCH_logging_gap"),
            ("package.json",              1, "Claimed no lockfile — incorrect, package-lock.json is present in repo",     "CONFIG_insecure_default"),
        ],
    },

    "claude-opus-4-7-may": {
        "tp": [
            ("app/api/together/route.ts", 6, "Unauthenticated endpoint + no rate limiting",                               "INSECURE_DESIGN"),
            ("app/api/together/route.ts", 7, "Client-controlled model and prompt forwarded without validation",            "ARCH_trust_boundary_violation"),
        ],
        "fp": [
            ("app/api/together/route.ts", 6, "Logging gap — marginal",                                                    "ARCH_logging_gap"),
            ("app/api/together/route.ts", 7, "Crash on malformed JSON — reliability concern, not a security issue",       "CODE_input_validation"),
        ],
    },

    "claude-haiku-4-5-20251001": {
        "tp": [
            ("app/api/together/route.ts",  7, "No auth on /api/together — confirmed open endpoint",                       "ARCH_missing_authz"),
            ("app/api/together/route.ts",  1, "No rate limiting — distinct control from auth, both absent",                "INSECURE_DESIGN"),
            ("app/api/together/route.ts", 15, "Streaming response exposes raw Together AI errors to client",               "ARCH_data_exposure"),
        ],
        "fp": [
            ("app/page.tsx",              32, "Frontend prompt validation — wrong layer, real control is at API route",    "CODE_unsafe_api_use"),
            ("app/page.tsx",              26, "Frontend model validation — same, wrong layer",                             "INSECURE_DESIGN"),
            ("app/api/together/route.ts", 15, "Missing CORS/CSP — framework defaults cover this for a demo app",          "CONFIG_insecure_default"),
            ("app/api/together/route.ts",  3, "API key exposure — speculative, no hardcoded key in code",                 "SECRET_hardcoded"),
        ],
    },
}


def make_triage_id(scan_id: str, verdict: str, finding_id: str | None) -> str:
    key = f"{scan_id}:{verdict}:{finding_id or ''}"
    return hashlib.sha1(key.encode()).hexdigest()


def _lookup_finding(db: DB, scan_id: str,
                    ev_file: str, ev_line: int, category: str) -> str | None:
    row = db.execute("""
        SELECT finding_id FROM run_findings
        WHERE scan_id = ? AND evidence_file = ? AND evidence_line_start = ? AND category = ?
    """, (scan_id, ev_file, ev_line, category)).fetchone()
    return row["finding_id"] if row else None


def triage_scan(db: DB, label: str, scan_id: str):
    db.execute("DELETE FROM scan_triage WHERE scan_id = ?", (scan_id,))

    spec = TRIAGE[label]
    inserted = 0

    for (ev_file, ev_line, notes, category) in spec["tp"]:
        finding_id = _lookup_finding(db, scan_id, ev_file, ev_line, category)
        if finding_id is None:
            print(f"  WARN: no finding for {label} @ {ev_file}:{ev_line} cat={category} (tp)")
            continue
        triage_id = make_triage_id(scan_id, "tp", finding_id)
        db.execute("""
            INSERT INTO scan_triage
                (triage_id, scan_id, verdict, finding_id, ground_truth_id, triaged_by, notes, created_at)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT DO NOTHING
        """, (triage_id, scan_id, "tp", finding_id, None, "manual", notes, NOW))
        inserted += 1

    for (ev_file, ev_line, notes, category) in spec["fp"]:
        finding_id = _lookup_finding(db, scan_id, ev_file, ev_line, category)
        if finding_id is None:
            print(f"  WARN: no finding for {label} @ {ev_file}:{ev_line} cat={category} (fp)")
            continue
        triage_id = make_triage_id(scan_id, "fp", finding_id)
        db.execute("""
            INSERT INTO scan_triage
                (triage_id, scan_id, verdict, finding_id, ground_truth_id, triaged_by, notes, created_at)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT DO NOTHING
        """, (triage_id, scan_id, "fp", finding_id, None, "manual", notes, NOW))
        inserted += 1

    db.commit()

    tp = len(spec["tp"])
    fp = len(spec["fp"])
    precision = tp / (tp + fp) if (tp + fp) else 0
    print(f"  {label:35s}  TP={tp}  FP={fp}  precision={precision:.2f}  ({inserted} rows)")


def main():
    db_url = os.environ.get("DATABASE_URL", str(DB_PATH))
    db = open_db(db_url)

    print("Triaging twitterbio scans (precision only — no ground truth)...")
    for label, scan_id in SCAN_IDS.items():
        triage_scan(db, label, scan_id)

    print("\nproject_benchmarks (twitterbio):")
    rows = db.execute("""
        SELECT pb.model, pb.scan_count, pb.avg_cost_usd,
               pb.tp_count, pb.fp_count, pb.fn_count, pb.precision
        FROM project_benchmarks pb
        WHERE pb.repo_name = 'twitterbio'
        ORDER BY pb.model
    """).fetchall()
    print(f"  {'model':<40} scans  cost      TP  FP  prec")
    for r in rows:
        print(f"  {r['model']:<40} {r['scan_count']:>5}  ${r['avg_cost_usd'] or 0:.4f}   "
              f"{r['tp_count']:>2}  {r['fp_count']:>2}  {r['precision'] or 0:.2f}")

    db.close()


if __name__ == "__main__":
    main()
