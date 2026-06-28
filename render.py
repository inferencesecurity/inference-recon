#!/usr/bin/env python3
"""
render.py — Render a findings.json envelope to a self-contained HTML report.

Usage:
    python render.py path/to/findings.json
    python render.py path/to/findings.json --output path/to/report.html

If --output is omitted, the HTML lands at the same path as the JSON with the
extension swapped to .html.

The HTML is fully self-contained except for mermaid.js (loaded from jsDelivr
CDN to render the Level 1 DFD). All other assets are inlined. If the CDN is
unavailable the diagram degrades gracefully to a <pre> block with a link to
mermaid.live. Everything else (CSS, findings, scorecard) works offline.

stdlib only. No external Python dependencies. Python 3.8+.
"""
import argparse
import html
import json
import sys
from pathlib import Path


SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]
PRIMARY_SEVERITIES = ["critical", "high", "medium", "low"]

DATA_CATEGORY_LABELS = {
    "identity_basic": "Basic identity (name, email, username)",
    "contact_info": "Contact information (phone, address)",
    "auth_credentials": "Authentication credentials",
    "financial_payment": "Payment card data",
    "financial_account": "Financial account data",
    "government_id": "Government-issued ID",
    "health_phi": "Protected health information (PHI)",
    "biometric": "Biometric data",
    "location": "Precise location / movement data",
    "childrens_data": "Children's data (under 13)",
    "gdpr_special_category": "GDPR special-category data",
    "other_sensitive": "Other sensitive data",
}

APPLICABILITY_LABELS = {
    "likely": "Likely applicable",
    "possibly": "Possibly applicable",
    "unlikely": "Unlikely applicable",
}

TIER_LABELS = {
    "minimal": "MINIMAL",
    "standard": "STANDARD",
    "elevated": "ELEVATED",
    "high": "HIGH",
    "critical": "CRITICAL",
}


CSS = """
* { box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.5;
    color: #222;
    background: #fafafa;
    margin: 0;
    padding: 2rem 1rem;
}
.container {
    max-width: 960px;
    margin: 0 auto;
    background: #fff;
    padding: 2.5rem;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
}

header h1 { margin: 0 0 .25rem; font-size: 1.75rem; }
header .subtitle { color: #666; font-size: .95rem; margin: 0 0 1.5rem; }
header .meta { color: #666; font-size: .85rem; margin: 0 0 2rem; padding-bottom: 1.5rem; border-bottom: 1px solid #eee; }
header .meta span { margin-right: 1.25rem; }

h2 { margin-top: 2.5rem; margin-bottom: 1rem; font-size: 1.25rem; border-bottom: 1px solid #eee; padding-bottom: .35rem; }
h3 { margin: 0 0 .5rem; font-size: 1.05rem; }

/* ── DFD / System Map ── */
.dfd-section { margin: 0 0 2rem; }
.dfd-diagram {
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    padding: 1.5rem;
    background: #fafafa;
    overflow-x: auto;
    text-align: center;
}
.dfd-diagram pre.mermaid-fallback {
    text-align: left;
    font-size: .78rem;
    background: none;
    border: none;
    padding: 0;
    margin: 0;
}
.dfd-note {
    margin: .75rem 0 0;
    padding: .6rem .9rem;
    background: #fff8e1;
    border-left: 3px solid #f9a825;
    border-radius: 0 4px 4px 0;
    font-size: .85rem;
    color: #555;
}

/* ── Data Profile ── */
.data-profile { margin: 0 0 2rem; }
.sensitivity-tier {
    display: inline-block;
    padding: .35rem 1rem;
    border-radius: 4px;
    font-weight: 700;
    font-size: 1rem;
    letter-spacing: .04em;
    margin: 0 0 1rem;
}
.tier-minimal  { background: #d4edda; color: #155724; }
.tier-standard { background: #d1ecf1; color: #0c5460; }
.tier-elevated { background: #fff3cd; color: #856404; }
.tier-high     { background: #ffe0b2; color: #8a4a00; }
.tier-critical { background: #f8d7da; color: #721c24; }
.profile-context { margin: 0 0 1rem; font-size: .95rem; color: #444; font-style: italic; }

/* ── Scorecard ── */
table.scorecard { width: 100%; border-collapse: collapse; margin: 1rem 0; }
table.scorecard th, table.scorecard td { padding: .55rem .75rem; text-align: left; border-bottom: 1px solid #eee; }
table.scorecard th { background: #f5f5f5; font-weight: 600; font-size: .85rem; text-transform: uppercase; letter-spacing: .03em; color: #555; }
table.scorecard tr.overall td { font-weight: 700; border-top: 2px solid #ddd; border-bottom: none; padding-top: .8rem; }

/* ── Shared table ── */
table.data-table { width: 100%; border-collapse: collapse; margin: .75rem 0 1.25rem; font-size: .9rem; }
table.data-table th, table.data-table td { padding: .5rem .75rem; text-align: left; border-bottom: 1px solid #eee; vertical-align: top; }
table.data-table th { background: #f5f5f5; font-weight: 600; font-size: .8rem; text-transform: uppercase; letter-spacing: .03em; color: #555; }
table.data-table td.unlikely { color: #999; }

.grade { display: inline-block; min-width: 2rem; padding: .2rem .65rem; border-radius: 4px; font-weight: 700; text-align: center; font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; }
.grade-A { background: #d4edda; color: #155724; }
.grade-B { background: #e2f0d9; color: #4a6e2a; }
.grade-C { background: #fff3cd; color: #856404; }
.grade-D { background: #ffe0b2; color: #8a4a00; }
.grade-F { background: #f8d7da; color: #721c24; }
.grade-NA { background: #e9ecef; color: #6c757d; }

.counts { margin: 1rem 0 2rem; padding: .85rem 1rem; background: #f5f5f5; border-radius: 4px; font-size: .95rem; }
.counts strong { color: #222; }

.finding { margin: 1.25rem 0; padding: 1.25rem 1.5rem; border-left: 4px solid #ddd; background: #fcfcfc; border-radius: 0 4px 4px 0; }
.finding.crit { border-left-color: #c0392b; }
.finding.high { border-left-color: #e67e22; }
.finding.medium { border-left-color: #f1c40f; }
.finding.low { border-left-color: #2980b9; }

.badges { margin: .35rem 0 .85rem; font-size: .8rem; }
.badge { display: inline-block; padding: .15rem .55rem; margin-right: .35rem; margin-bottom: .25rem; border-radius: 3px; font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; font-size: .78rem; }
.badge.sev-critical { background: #f8d7da; color: #721c24; }
.badge.sev-high { background: #ffe0b2; color: #8a4a00; }
.badge.sev-medium { background: #fff3cd; color: #856404; }
.badge.sev-low { background: #d1ecf1; color: #0c5460; }
.badge.sev-info { background: #e9ecef; color: #383d41; }
.badge.conf-high { background: #d4edda; color: #155724; }
.badge.conf-medium { background: #fff3cd; color: #856404; }
.badge.conf-low { background: #e9ecef; color: #6c757d; }
.badge.cat { background: #e2e3e5; color: #383d41; }
.badge.owasp { background: #cfe2ff; color: #084298; }
.badge.idtag { background: #f0f0f0; color: #6c757d; }
.badge.dfd { background: #e8d5f5; color: #5a1f8a; }

.finding .meta-row { color: #666; font-size: .85rem; margin: 0 0 .5rem; }
.finding .meta-row code { background: none; padding: 0; }

.finding h4 { margin: 1.1rem 0 .35rem; font-size: .8rem; text-transform: uppercase; letter-spacing: .05em; color: #555; font-weight: 600; }
.finding h5 { margin: 0 0 .35rem; font-size: .75rem; text-transform: uppercase; letter-spacing: .05em; color: #777; font-weight: 600; }
.finding p { margin: 0 0 .5rem; }

pre {
    background: #f5f5f5;
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    padding: .75rem 1rem;
    overflow-x: auto;
    font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
    font-size: .85rem;
    line-height: 1.45;
    margin: .35rem 0 .75rem;
}
code { font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; background: #f5f5f5; padding: .1rem .35rem; border-radius: 3px; font-size: .9em; }

.references ul { padding-left: 1.2rem; margin: .35rem 0; }
.references li { margin: .15rem 0; font-size: .9rem; }
.references a { color: #0066cc; word-break: break-all; }

.cvss { font-size: .85rem; color: #555; margin-top: .5rem; }
.cvss code { font-size: .82rem; }

.related { margin: .75rem 0; padding-left: 1rem; border-left: 2px solid #e0e0e0; }

.notes ul { padding-left: 1.2rem; }
.notes li { margin: .35rem 0; color: #444; font-size: .92rem; }

details.envelope { margin: 2.5rem 0 1rem; }
details.envelope summary { cursor: pointer; padding: .5rem 0; color: #666; font-size: .85rem; user-select: none; }
details.envelope summary:hover { color: #222; }
details.envelope pre { font-size: .72rem; max-height: 500px; overflow-y: auto; }

footer { margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid #eee; color: #888; font-size: .8rem; text-align: center; }
footer a { color: #666; }

@media print {
    body { background: #fff; padding: 0; }
    .container { box-shadow: none; padding: 1rem; max-width: 100%; border-radius: 0; }
    details.envelope { display: none; }
    .finding { page-break-inside: avoid; }
}
"""


def esc(value):
    """HTML-escape a value; tolerate None."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def severity_class(sev):
    return {"critical": "crit", "high": "high", "medium": "medium",
            "low": "low", "info": "low"}.get(sev, "low")


def grade_class(grade):
    if grade in (None, "N/A"):
        return "grade-NA"
    return f"grade-{grade}"


def fmt_location(loc):
    if not loc:
        return ""
    file_path = esc(loc.get("file", ""))
    line_start = loc.get("line_start", "")
    line_end = loc.get("line_end", line_start)
    if line_start == line_end:
        return f"{file_path}:{line_start}"
    return f"{file_path}:{line_start}-{line_end}"


def render_evidence(evidence):
    if not evidence:
        return ""
    location = fmt_location(evidence)
    quote = esc(evidence.get("quote", ""))
    return f'<p class="meta-row">Evidence — <code>{location}</code></p>\n<pre>{quote}</pre>'


def render_related(locations):
    if not locations:
        return ""
    items = []
    for loc in locations:
        location = fmt_location(loc)
        quote = esc(loc.get("quote", ""))
        items.append(f'<p class="meta-row"><code>{location}</code></p>\n<pre>{quote}</pre>')
    body = "\n".join(items)
    return f'<div class="related">\n<h5>Related locations</h5>\n{body}\n</div>'


def render_references(refs):
    if not refs:
        return ""
    items = []
    for ref in refs:
        ref_esc = esc(ref)
        if str(ref).startswith(("http://", "https://")):
            items.append(f'<li><a href="{ref_esc}">{ref_esc}</a></li>')
        else:
            items.append(f"<li>{ref_esc}</li>")
    body = "".join(items)
    return f'<div class="references">\n<h4>References</h4>\n<ul>{body}</ul>\n</div>'


def render_cvss(cvss):
    if not cvss:
        return ""
    version = esc(cvss.get("version", ""))
    vector = esc(cvss.get("vector", ""))
    score = cvss.get("score", "")
    return f'<p class="cvss">CVSS v{version} <code>{vector}</code> (score {score})</p>'


def render_finding(finding):
    sev = finding.get("severity", "low")
    conf = finding.get("confidence", "low")
    category = finding.get("category", "OTHER")
    finding_id = finding.get("id", "")
    title = esc(finding.get("title", ""))
    owasp = finding.get("owasp_mapping") or []
    dfd_el = finding.get("dfd_element")

    sev_class = severity_class(sev)
    owasp_badges = "".join(f'<span class="badge owasp">{esc(o)}</span>' for o in owasp)
    dfd_badge = f'<span class="badge dfd">dfd: {esc(dfd_el)}</span>' if dfd_el else ""

    badges = (
        f'<span class="badge sev-{esc(sev)}">{esc(sev)}</span>'
        f'<span class="badge conf-{esc(conf)}">conf: {esc(conf)}</span>'
        f'<span class="badge cat">{esc(category)}</span>'
        f'{owasp_badges}'
        f'{dfd_badge}'
        f'<span class="badge idtag">id: {esc(finding_id)}</span>'
    )

    evidence_html = render_evidence(finding.get("evidence"))
    related_html = render_related(finding.get("related_locations"))

    exploit = finding.get("exploitation_path")
    exploit_html = f"<h4>Exploitation path</h4>\n<p>{esc(exploit)}</p>" if exploit else ""

    remediation = esc(finding.get("remediation", ""))
    remediation_html = f"<h4>Remediation</h4>\n<p>{remediation}</p>" if remediation else ""

    references_html = render_references(finding.get("references") or [])
    cvss_html = render_cvss(finding.get("cvss"))

    parts = [
        f'<article class="finding {sev_class}">',
        f"<h3>{title}</h3>",
        f'<div class="badges">{badges}</div>',
        evidence_html,
        related_html,
        exploit_html,
        remediation_html,
        references_html,
        cvss_html,
        "</article>",
    ]
    return "\n".join(p for p in parts if p)


def render_dfd(threat_model):
    """Render the Level 1 DFD section using mermaid.js."""
    if not threat_model:
        return ""
    dfd = threat_model.get("dfd") or {}
    mermaid_src = dfd.get("mermaid", "").strip()
    notes = dfd.get("notes", "")

    if not mermaid_src:
        return '<section class="dfd-section"><h2>System Map</h2><p><em>System map not available for this scan.</em></p></section>'

    mermaid_escaped = esc(mermaid_src)
    notes_html = f'<div class="dfd-note">⚠️ {esc(notes)}</div>' if notes else ""

    # The mermaid div is processed by mermaid.js; the noscript fallback
    # shows the raw source with a link to mermaid.live for offline viewing.
    mermaid_live_url = "https://mermaid.live/edit#base64:" + _b64_mermaid(mermaid_src)

    return f"""<section class="dfd-section">
<h2>System Map</h2>
<div class="dfd-diagram">
<pre class="mermaid">{mermaid_escaped}</pre>
<noscript>
<pre class="mermaid-fallback">{mermaid_escaped}</pre>
<p style="font-size:.82rem;color:#666;margin:.5rem 0 0">
JavaScript is disabled — diagram not rendered.
<a href="{esc(mermaid_live_url)}" target="_blank">Open in mermaid.live ↗</a>
</p>
</noscript>
</div>
{notes_html}
</section>"""


def _b64_mermaid(src):
    """Base64-encode mermaid source for a mermaid.live URL (best-effort)."""
    import base64
    try:
        return base64.urlsafe_b64encode(src.encode()).decode()
    except Exception:
        return ""


def render_data_profile(data_profile):
    """Render the Data Profile section."""
    if not data_profile:
        return ""

    tier = data_profile.get("sensitivity_tier", "minimal")
    tier_label = TIER_LABELS.get(tier, tier.upper())
    tier_css = f"tier-{tier}"
    context_note = data_profile.get("context_note", "")
    categories = data_profile.get("categories") or []
    reg_flags = data_profile.get("regulatory_flags") or []

    context_html = f'<p class="profile-context">{esc(context_note)}</p>' if context_note else ""

    # Categories table
    if categories:
        cat_rows = ""
        for entry in categories:
            cat_key = entry.get("category", "")
            cat_label = esc(DATA_CATEGORY_LABELS.get(cat_key, cat_key))
            evidence = esc(entry.get("evidence_summary", ""))
            conf = entry.get("confidence", "")
            cat_rows += f"<tr><td>{cat_label}</td><td>{evidence}</td><td>{esc(conf)}</td></tr>\n"
        cats_html = (
            '<table class="data-table">'
            "<tr><th>Data category</th><th>Evidence</th><th>Confidence</th></tr>\n"
            f"{cat_rows}</table>"
        )
    else:
        cats_html = "<p><em>No specific data categories identified.</em></p>"

    # Regulatory flags table — suppress "unlikely" rows unless ALL are unlikely
    all_unlikely = all(f.get("applicability") == "unlikely" for f in reg_flags)
    visible_flags = reg_flags if all_unlikely else [f for f in reg_flags if f.get("applicability") != "unlikely"]

    if visible_flags:
        reg_rows = ""
        for flag in visible_flags:
            reg = esc(flag.get("regulation", ""))
            app = flag.get("applicability", "")
            app_label = esc(APPLICABILITY_LABELS.get(app, app))
            rationale = esc(flag.get("rationale", ""))
            unlikely_class = ' class="unlikely"' if app == "unlikely" else ""
            reg_rows += f"<tr{unlikely_class}><td>{reg}</td><td>{app_label}</td><td>{rationale}</td></tr>\n"
        regs_html = (
            "<h3>Regulatory scope</h3>"
            '<table class="data-table">'
            "<tr><th>Regulation</th><th>Applicability</th><th>Basis</th></tr>\n"
            f"{reg_rows}</table>"
        )
    else:
        regs_html = ""

    return f"""<section class="data-profile">
<h2>Data Profile</h2>
<span class="sensitivity-tier {tier_css}">Sensitivity tier: {tier_label}</span>
{context_html}
{cats_html}
{regs_html}
</section>"""


def render_scorecard(summary):
    scorecard = summary.get("scorecard", {})
    rows = [
        ("Code", scorecard.get("code", "N/A")),
        ("Dependencies", scorecard.get("dependencies", "N/A")),
        ("Secrets & Config", scorecard.get("secrets_and_config", "N/A")),
        ("Architecture", scorecard.get("architecture", "N/A")),
    ]
    overall = scorecard.get("overall", "N/A")
    row_html = "".join(
        f'<tr><td>{esc(name)}</td><td><span class="grade {grade_class(g)}">{esc(g)}</span></td></tr>'
        for name, g in rows
    )
    return (
        '<h2>Scorecard</h2>\n'
        '<table class="scorecard">\n'
        "<tr><th>Domain</th><th>Grade</th></tr>\n"
        f"{row_html}\n"
        f'<tr class="overall"><td>Overall</td><td><span class="grade {grade_class(overall)}">{esc(overall)}</span></td></tr>\n'
        "</table>"
    )


def render_counts(summary):
    sev_counts = summary.get("counts_by_severity", {})
    conf_counts = summary.get("counts_by_confidence", {})
    sev_parts = [f"{sev_counts.get(s, 0)} {s}" for s in PRIMARY_SEVERITIES]
    sev_str = ", ".join(sev_parts)
    return (
        '<div class="counts">'
        f"<strong>{sev_str}</strong> — high-confidence: {conf_counts.get('high', 0)}, "
        f"medium: {conf_counts.get('medium', 0)}, low: {conf_counts.get('low', 0)}"
        "</div>"
    )


def render_notes(notes):
    if not notes:
        return ""
    items = "".join(f"<li>{esc(n)}</li>" for n in notes)
    return f'<section class="notes">\n<h2>Notes</h2>\n<ul>{items}</ul>\n</section>'


def render_findings_sections(findings):
    """Group findings by severity descending. Suppress low-confidence per D22."""
    visible = [f for f in findings if f.get("confidence") != "low"]
    by_sev = {sev: [] for sev in SEVERITY_ORDER}
    for f in visible:
        sev = f.get("severity", "info")
        if sev in by_sev:
            by_sev[sev].append(f)

    sections = []
    for sev in SEVERITY_ORDER:
        bucket = by_sev[sev]
        if not bucket:
            continue
        sections.append(f'<section class="findings-section"><h2>{sev.capitalize()} findings ({len(bucket)})</h2>')
        sections.extend(render_finding(f) for f in bucket)
        sections.append("</section>")
    return "\n".join(sections)


def render_html(envelope):
    project = envelope.get("project", {}) or {}
    scan = envelope.get("scan", {}) or {}
    summary = envelope.get("summary", {}) or {}
    findings = envelope.get("findings", []) or []
    notes = envelope.get("notes", []) or []
    data_profile = envelope.get("data_profile") or {}
    threat_model = envelope.get("threat_model") or {}

    project_name = esc(project.get("name", "project"))
    timestamp = esc(scan.get("timestamp", ""))
    model = esc(scan.get("model", ""))
    prompt_version = esc(scan.get("prompt_version", ""))
    files_scanned = esc(project.get("files_scanned", ""))

    envelope_json = json.dumps(envelope, indent=2)

    # Report order: System Map → Data Profile → Scorecard → Findings → Notes
    dfd_html = render_dfd(threat_model)
    profile_html = render_data_profile(data_profile)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Security Review — {project_name}</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">
<header>
<h1>Security Review</h1>
<p class="subtitle">{project_name}</p>
<p class="meta">
<span>Scanned: {timestamp}</span>
<span>Files: {files_scanned}</span>
<span>Model: {model}</span>
<span>Prompt v{prompt_version}</span>
</p>
</header>

{dfd_html}
{profile_html}
{render_scorecard(summary)}
{render_counts(summary)}
{render_findings_sections(findings)}
{render_notes(notes)}

<details class="envelope">
<summary>JSON envelope (full data)</summary>
<pre>{esc(envelope_json)}</pre>
</details>

<footer>
Generated by <a href="https://inferencerecon.com">Inference Recon</a>
</footer>
</div>

<!-- mermaid.js: renders .mermaid blocks as SVG diagrams.
     Requires internet connectivity. Degrades to <pre> fallback if unavailable. -->
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
  mermaid.initialize({{ startOnLoad: true, theme: 'default', securityLevel: 'loose' }});
</script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(
        description="Render a findings.json envelope to a self-contained HTML report.",
    )
    parser.add_argument("findings_path", type=Path, help="Path to a findings JSON file.")
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="HTML output path (default: alongside findings.json with .html extension).",
    )
    args = parser.parse_args()

    if not args.findings_path.exists():
        print(f"render.py: findings file not found: {args.findings_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with args.findings_path.open(encoding="utf-8") as f:
            envelope = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"render.py: invalid JSON in {args.findings_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    html_content = render_html(envelope)
    out_path = args.output or args.findings_path.with_suffix(".html")
    out_path.write_text(html_content, encoding="utf-8")
    print(f"render.py: wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
