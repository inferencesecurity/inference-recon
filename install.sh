#!/usr/bin/env bash
# install.sh — install inference-recon to ~/.inference-recon/
#
# Usage:
#   ./install.sh          # install / update
#   ./install.sh --check  # print what would be installed, then exit
#
# After install, run a scan with:
#   cd /path/to/project && claude --add-dir ~/.inference-recon

set -euo pipefail

DEST="${INFERENCE_RECON_DIR:-$HOME/.inference-recon}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK_ONLY=false

if [[ "${1:-}" == "--check" ]]; then
    CHECK_ONLY=true
fi

# ── File manifest ─────────────────────────────────────────────────────────────

FILES=(
    prompt.md
    rubric.md
    schema.json
    report-template.md
    render.py
    COMPATIBILITY.md
)

DIRS=(
    examples
    rules
)

# ── Check mode ────────────────────────────────────────────────────────────────

if $CHECK_ONLY; then
    echo "Install destination: $DEST"
    echo ""
    echo "Files to install:"
    for f in "${FILES[@]}"; do
        echo "  $SCRIPT_DIR/$f → $DEST/$f"
    done
    for d in "${DIRS[@]}"; do
        echo "  $SCRIPT_DIR/$d/ → $DEST/$d/"
    done
    echo "  (generated) → $DEST/CLAUDE.md"
    exit 0
fi

# ── Install ───────────────────────────────────────────────────────────────────

mkdir -p "$DEST"

echo "→ Installing to $DEST ..."

for f in "${FILES[@]}"; do
    if [[ ! -f "$SCRIPT_DIR/$f" ]]; then
        echo "Error: source file not found: $f" >&2
        exit 1
    fi
    cp "$SCRIPT_DIR/$f" "$DEST/$f"
done

for d in "${DIRS[@]}"; do
    if [[ ! -d "$SCRIPT_DIR/$d" ]]; then
        echo "Error: source directory not found: $d" >&2
        exit 1
    fi
    rm -rf "$DEST/$d"
    cp -r "$SCRIPT_DIR/$d" "$DEST/$d"
done

# ── Write CLAUDE.md ───────────────────────────────────────────────────────────
# Claude Code auto-reads CLAUDE.md from every directory in the session.
# This file tells Claude to immediately start the security review procedure
# when invoked via: cd <project> && claude --add-dir ~/.inference-recon

cat > "$DEST/CLAUDE.md" << 'EOF'
# Inference Recon

You have been invoked for a security recon session.

Read `prompt.md` from this directory immediately and follow the procedure it describes. The project to scan is the **primary working directory** (the directory Claude Code was launched from — not this `--add-dir` directory).

Begin at Step 0 of `prompt.md` now. Do not explain what you are about to do. Do not ask for confirmation. Start the scan.
EOF

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "✓ Installed inference-recon to $DEST"
echo ""
echo "To scan a project:"
echo "  cd /path/to/project"
echo "  claude --add-dir $DEST"
