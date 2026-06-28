#!/usr/bin/env bash
# checkpoint.sh — session housekeeping
#
# Run periodically during long work sessions (suggested: every 90 min).
# Does NOT auto-commit — flags what needs attention and lets you decide.
#
# Usage:
#   ./checkpoint.sh          — full checkpoint
#   ./checkpoint.sh --quick  — git status only, skip health checks

set -euo pipefail
cd "$(dirname "$0")"

QUICK=0
[[ "${1:-}" == "--quick" ]] && QUICK=1

RECON_DIR="$(pwd)"
SITE_DIR="/Users/mark/Documents/Claude/Projects/Inference Security Site"
TS="$(date '+%Y-%m-%d %H:%M')"

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; RESET='\033[0m'

header()  { echo -e "\n${BOLD}━━━ $1 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"; }
ok()      { echo -e "  ${GREEN}✓${RESET}  $1"; }
warn()    { echo -e "  ${YELLOW}⚠${RESET}  $1"; }
flag()    { echo -e "  ${RED}✗${RESET}  $1"; }
note()    { echo -e "  ${DIM}→${RESET}  $1"; }

echo -e "\n${BOLD}${CYAN}Checkpoint — $TS${RESET}"

# ── Git: inference-recon ──────────────────────────────────────────────────────
header "inference-recon"

cd "$RECON_DIR"
STAGED=$(git diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
UNSTAGED=$(git diff --name-only 2>/dev/null | wc -l | tr -d ' ')
UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null | wc -l | tr -d ' ')
AHEAD=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)
LAST_COMMIT=$(git log -1 --format="%h  %s  ${DIM}(%ar)${RESET}" 2>/dev/null)

echo -e "  ${DIM}last commit:${RESET} $LAST_COMMIT"
echo ""

if [[ "$STAGED" -gt 0 ]]; then
  warn "${STAGED} staged file(s) — ready to commit but not committed"
  git diff --cached --name-only | sed 's/^/        /'
fi

if [[ "$UNSTAGED" -gt 0 ]]; then
  warn "${UNSTAGED} unstaged change(s)"
  git diff --name-only | sed 's/^/        /'
fi

if [[ "$UNTRACKED" -gt 0 ]]; then
  note "${UNTRACKED} untracked file(s) — check nothing sensitive"
  git ls-files --others --exclude-standard | sed 's/^/        /'
fi

if [[ "$AHEAD" -gt 0 ]]; then
  warn "${AHEAD} commit(s) ahead of origin — don't forget to push"
fi

if [[ "$STAGED" -eq 0 && "$UNSTAGED" -eq 0 && "$AHEAD" -eq 0 ]]; then
  ok "Clean — nothing to commit, up to date with origin"
fi

# ── Git: inference-security-site ─────────────────────────────────────────────
header "inference-security-site"

if [[ -d "$SITE_DIR" ]]; then
  cd "$SITE_DIR"
  STAGED_S=$(git diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
  UNSTAGED_S=$(git diff --name-only 2>/dev/null | wc -l | tr -d ' ')
  AHEAD_S=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)
  LAST_S=$(git log -1 --format="%h  %s  ${DIM}(%ar)${RESET}" 2>/dev/null)

  echo -e "  ${DIM}last commit:${RESET} $LAST_S"
  echo ""

  if [[ "$STAGED_S" -gt 0 ]]; then
    warn "${STAGED_S} staged file(s) — ready to commit"
    git diff --cached --name-only | sed 's/^/        /'
  fi
  if [[ "$UNSTAGED_S" -gt 0 ]]; then
    warn "${UNSTAGED_S} unstaged change(s)"
    git diff --name-only | sed 's/^/        /'
  fi
  if [[ "$AHEAD_S" -gt 0 ]]; then
    warn "${AHEAD_S} commit(s) ahead of origin"
  fi
  if [[ "$STAGED_S" -eq 0 && "$UNSTAGED_S" -eq 0 && "$AHEAD_S" -eq 0 ]]; then
    ok "Clean — up to date with origin"
  fi
else
  note "Site repo not found at expected path — skipping"
fi

cd "$RECON_DIR"

# ── Infrastructure (skip if --quick) ─────────────────────────────────────────
if [[ "$QUICK" -eq 0 ]]; then
  header "Infrastructure"
  DOCKER_OK=1
  docker compose ps --format 'table {{.Name}}\t{{.Status}}' 2>/dev/null | tail -n +2 | while read -r line; do
    if echo "$line" | grep -q "running\|Up"; then
      ok "$line"
    else
      flag "$line"
    fi
  done || { warn "Docker not running or compose failed"; DOCKER_OK=0; }
fi

# ── Reminders ─────────────────────────────────────────────────────────────────
header "Reminders"
echo -e "  ${YELLOW}Tasks${RESET}   — are pending tasks still accurate? anything completed or new?"
echo -e "  ${YELLOW}Memory${RESET}  — any aha moments, decisions, or design choices worth persisting?"
echo -e "  ${YELLOW}Commits${RESET} — write meaningful messages while context is fresh"
echo ""
echo -e "  ${DIM}Memory files: ~/.claude/projects/*/memory/${RESET}"
echo ""

echo -e "${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}Done.${RESET}  Run ${CYAN}./health.sh${RESET} for full DB + pipeline status.\n"
