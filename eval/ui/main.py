#!/usr/bin/env python3
"""
eval/ui/main.py — FastAPI web UI for the Inference Recon eval pipeline.

Run locally:
    cd <repo-root>
    uvicorn eval.ui.main:app --host 0.0.0.0 --port 8000 --reload

Via Docker:
    docker compose up ui
"""

import asyncio
import os
import sys
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ── Path setup ────────────────────────────────────────────────────────────────

UI_DIR       = Path(__file__).parent
EVAL_DIR     = UI_DIR.parent
REPO_ROOT    = EVAL_DIR.parent
REPOS_FILE   = EVAL_DIR / "corpus" / "repos.txt"
BATCH_SCRIPT = EVAL_DIR / "batch_scan.py"

# Make eval/ui/ importable (for db.py)
for _p in (str(UI_DIR), str(EVAL_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from db import q, q1  # noqa: E402  (eval/ui/db.py)
from batch_scan import DEFAULT_MODEL  # noqa: E402  (single source of truth)

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="AI Sec Review", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=UI_DIR / "static"), name="static")
templates = Jinja2Templates(directory=UI_DIR / "templates")

# Inject badge helpers into every template
GRADE_CSS = {
    "A": "grade-a", "B": "grade-b", "C": "grade-c",
    "D": "grade-d", "F": "grade-f", "N/A": "grade-na",
}
SEV_CSS = {
    "critical": "sev-critical", "high": "sev-high",
    "medium": "sev-medium",     "low": "sev-low", "info": "sev-info",
}
templates.env.globals.update(grade_css=GRADE_CSS, sev_css=SEV_CSS)

import json as _json
templates.env.filters["from_json"] = lambda s: _json.loads(s) if s else []

# ── Scan process state (single-user — no locking needed) ─────────────────────

_scan_running: bool      = False
_scan_log:     list[str] = []
_scan_code:    int | None = None


# ── Corpus helpers ────────────────────────────────────────────────────────────

def load_corpus_repos() -> list[dict]:
    """Return uncommented repos from repos.txt as [{name, source}]."""
    if not REPOS_FILE.exists():
        return []
    out = []
    for raw in REPOS_FILE.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts  = line.split()
        source = parts[0]
        name   = source.rstrip("/").split("/")[-1].removesuffix(".git")
        out.append({"name": name, "source": source})
    return out


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    scans = q("""
        SELECT s.scan_id, s.timestamp, s.model, s.tool,
               p.repo_name, p.project_id,
               sc.overall,
               sc.count_critical, sc.count_high, sc.count_medium, sc.count_low
        FROM   scans s
        JOIN   projects   p  ON s.project_id = p.project_id
        JOIN   scorecards sc ON s.scan_id    = sc.scan_id
        ORDER  BY s.timestamp DESC
        LIMIT  40
    """)
    return templates.TemplateResponse(
        request, "dashboard.html", {"scans": scans}
    )


@app.get("/corpus", response_class=HTMLResponse)
async def corpus(request: Request):
    projects = q("""
        SELECT p.project_id, p.repo_name, p.repo_url,
               p.scan_count, p.last_scanned_at,
               sc.overall
        FROM   projects p
        LEFT JOIN scans      s  ON  s.project_id = p.project_id
                                AND s.timestamp  = p.last_scanned_at
        LEFT JOIN scorecards sc ON  sc.scan_id   = s.scan_id
        ORDER  BY p.last_scanned_at DESC NULLS LAST
    """)
    repos = load_corpus_repos()
    return templates.TemplateResponse(
        request, "corpus.html", {"projects": projects, "repos": repos}
    )


@app.get("/scan", response_class=HTMLResponse)
async def scan_form(request: Request):
    repos = load_corpus_repos()
    return templates.TemplateResponse(request, "scan_run.html", {
        "repos": repos, "running": _scan_running,
    })


@app.post("/scan/run")
async def scan_run(
    request: Request,
    model: str = Form(default=DEFAULT_MODEL),
):
    global _scan_running, _scan_log, _scan_code

    if _scan_running:
        return RedirectResponse("/scan/live", status_code=303)

    _scan_running = True
    _scan_log     = []
    _scan_code    = None

    asyncio.create_task(_run_scan(str(REPOS_FILE), model))
    return RedirectResponse("/scan/live", status_code=303)


@app.get("/scan/live", response_class=HTMLResponse)
async def scan_live(request: Request):
    return templates.TemplateResponse(
        request, "scan_live.html", {"running": _scan_running}
    )


@app.get("/scan/stream")
async def scan_stream():
    """SSE endpoint — streams buffered scan log lines to the browser."""
    async def generate():
        sent = 0
        while True:
            while sent < len(_scan_log):
                line = _scan_log[sent].replace("\n", " ").replace("\r", "")
                yield f"data: {line}\n\n"
                sent += 1
            if not _scan_running and sent >= len(_scan_log):
                code = _scan_code if _scan_code is not None else 0
                yield f"event: done\ndata: exit_code={code}\n\n"
                return
            await asyncio.sleep(0.15)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/projects/{project_id}", response_class=HTMLResponse)
async def project(request: Request, project_id: str):
    proj = q1("SELECT * FROM projects WHERE project_id = ?", (project_id,))
    if not proj:
        return HTMLResponse("Project not found", status_code=404)

    scans = q("""
        SELECT s.scan_id, s.timestamp, s.model, s.tool,
               sc.overall, sc.code, sc.dependencies,
               sc.secrets_and_config, sc.architecture,
               sc.count_critical, sc.count_high, sc.count_medium, sc.count_low
        FROM   scans s
        JOIN   scorecards sc ON s.scan_id = sc.scan_id
        WHERE  s.project_id = ?
        ORDER  BY s.timestamp DESC
    """, (project_id,))

    return templates.TemplateResponse(
        request, "project.html", {"proj": proj, "scans": scans}
    )


@app.get("/scans/{scan_id}", response_class=HTMLResponse)
async def scan_detail(request: Request, scan_id: str):
    scan = q1("""
        SELECT s.*, p.repo_name, p.project_id,
               sc.overall, sc.code, sc.dependencies,
               sc.secrets_and_config, sc.architecture,
               sc.count_critical, sc.count_high, sc.count_medium, sc.count_low
        FROM   scans s
        JOIN   projects   p  ON s.project_id = p.project_id
        JOIN   scorecards sc ON s.scan_id    = sc.scan_id
        WHERE  s.scan_id = ?
    """, (scan_id,))
    if not scan:
        return HTMLResponse("Scan not found", status_code=404)

    findings = q("""
        SELECT *
        FROM   run_findings
        WHERE  scan_id = ?
        ORDER BY
          CASE severity
            WHEN 'critical' THEN 1  WHEN 'high'   THEN 2
            WHEN 'medium'   THEN 3  WHEN 'low'    THEN 4  ELSE 5
          END,
          CASE confidence
            WHEN 'high' THEN 1  WHEN 'medium' THEN 2  ELSE 3
          END
    """, (scan_id,))

    return templates.TemplateResponse(
        request, "scan.html", {"scan": scan, "findings": findings}
    )


@app.get("/findings/{run_finding_id}", response_class=HTMLResponse)
async def finding_detail(request: Request, run_finding_id: str):
    finding = q1("""
        SELECT rf.*,
               cf.corroboration_count, cf.corroborating_tools, cf.status,
               p.repo_name, p.project_id,
               s.model, s.timestamp, s.scan_id
        FROM   run_findings      rf
        JOIN   canonical_findings cf ON rf.canonical_finding_id = cf.canonical_finding_id
        JOIN   scans              s  ON rf.scan_id    = s.scan_id
        JOIN   projects           p  ON s.project_id = p.project_id
        WHERE  rf.run_finding_id = ?
    """, (run_finding_id,))
    if not finding:
        return HTMLResponse("Finding not found", status_code=404)

    return templates.TemplateResponse(
        request, "finding.html", {"f": finding}
    )


@app.get("/compare", response_class=HTMLResponse)
async def compare(request: Request, a: str = "", b: str = ""):
    # Scan picker — no params yet
    if not a or not b:
        scans = q("""
            SELECT s.scan_id, s.timestamp, s.model, p.repo_name
            FROM   scans s
            JOIN   projects p ON s.project_id = p.project_id
            ORDER  BY p.repo_name, s.timestamp DESC
            LIMIT  60
        """)
        return templates.TemplateResponse(
            request, "compare.html", {"scans": scans, "scan_a": None, "scan_b": None}
        )

    def load_scan_meta(sid: str) -> dict | None:
        return q1("""
            SELECT s.scan_id, s.timestamp, s.model, s.tool, p.repo_name,
                   sc.overall, sc.count_critical, sc.count_high,
                   sc.count_medium, sc.count_low
            FROM   scans s
            JOIN   projects   p  ON s.project_id = p.project_id
            JOIN   scorecards sc ON s.scan_id    = sc.scan_id
            WHERE  s.scan_id = ?
        """, (sid,))

    scan_a = load_scan_meta(a)
    scan_b = load_scan_meta(b)
    if not scan_a or not scan_b:
        return HTMLResponse("One or both scans not found", status_code=404)

    def load_findings(sid: str) -> dict:
        rows = q("SELECT * FROM run_findings WHERE scan_id = ?", (sid,))
        return {r["finding_id"]: r for r in rows}

    fa = load_findings(a)
    fb = load_findings(b)

    common = [fa[fid] for fid in fa if fid in fb]
    only_a = [fa[fid] for fid in fa if fid not in fb]
    only_b = [fb[fid] for fid in fb if fid not in fa]

    # Sort each group by severity
    _sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    for lst in (common, only_a, only_b):
        lst.sort(key=lambda r: _sev_order.get(r.get("severity", ""), 5))

    return templates.TemplateResponse(request, "compare.html", {
        "scans": [],           # not needed in comparison mode
        "scan_a": scan_a, "scan_b": scan_b,
        "common": common, "only_a": only_a, "only_b": only_b,
    })


# ── Background scan task ──────────────────────────────────────────────────────

async def _run_scan(repos_file: str, model: str) -> None:
    global _scan_running, _scan_log, _scan_code

    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(BATCH_SCRIPT), repos_file, "--model", model,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(REPO_ROOT),
        env={**os.environ},
    )

    async for raw in proc.stdout:
        _scan_log.append(raw.decode("utf-8", errors="replace").rstrip())

    await proc.wait()
    _scan_code    = proc.returncode
    _scan_running = False
