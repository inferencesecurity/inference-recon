#!/usr/bin/env bash
# Session health check — run at the start of each work session.
# Verifies: Docker hosts, pipeline, DB sanity, code state.

set -euo pipefail
cd "$(dirname "$0")"

echo "━━━ Docker hosts ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose ps --format 'table {{.Name}}\t{{.Status}}\t{{.Ports}}'

echo ""
echo "━━━ Pipeline (pricing-sync last run) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose logs pricing-sync --tail=6 2>&1 | grep -v "^$"

echo ""
echo "━━━ Database ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 -c "
import sys
sys.path.insert(0, 'eval')
from ingest import open_db

db = open_db('postgresql://eval:eval@localhost:5432/inference_recon')

scans    = db.execute('SELECT COUNT(*) as c FROM scans').fetchone()['c']
projects = db.execute('SELECT COUNT(*) as c FROM projects').fetchone()['c']
triage   = db.execute('SELECT COUNT(*) as c FROM scan_triage').fetchone()['c']
print(f'projects={projects}  scans={scans}  triage={triage}')

print()
print('Pricing (latest per model):')
rows = db.execute('''
    SELECT model, input_per_1m, output_per_1m, effective_from
    FROM model_pricing
    WHERE (model, effective_from) IN (
        SELECT model, MAX(effective_from) FROM model_pricing GROUP BY model
    )
    ORDER BY model
''').fetchall()
for r in rows:
    print(f'  {r[\"model\"]:<40}  \${r[\"input_per_1m\"]}/\${r[\"output_per_1m\"]}  (since {r[\"effective_from\"]})')

print()
print('VAmPI benchmark (calibration):')
rows = db.execute('''
    SELECT model, scan_count, avg_cost_usd, precision, recall
    FROM project_benchmarks
    WHERE repo_name = %s
    ORDER BY model
''', ('VAmPI',)).fetchall()
for r in rows:
    print(f'  {r[\"model\"]:<40}  scans={r[\"scan_count\"]}  cost=\${r[\"avg_cost_usd\"]}  prec={r[\"precision\"]}  rec={r[\"recall\"]}')

db.close()
"

echo ""
echo "━━━ Code state ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
git status --short
echo ""
git log --oneline -5
