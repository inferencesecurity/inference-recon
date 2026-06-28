#!/usr/bin/env bash
# release.sh — publish a versioned release to the public GitHub repo
#
# Usage:
#   ./scripts/release.sh v1.0
#
# What it does:
#   1. Clones the public repo to a temp directory
#   2. Copies all files from the public manifest (README.public.md → README.md)
#   3. Commits and tags in the public repo
#   4. Pushes main + tag to the public repo
#   5. Tags this commit in the private repo as public-<version>
#
# Requirements:
#   - git, gh (GitHub CLI) or SSH access to the public repo
#   - Public repo must already exist on GitHub (see RELEASE.md for first-time setup)
#   - Set PUBLIC_REPO_URL below before first use

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────

PUBLIC_REPO_URL="https://github.com/markcmarshall/inference-recon-staging.git"
                     # Public staging repo — live at github.com/markcmarshall/inference-recon-staging.
                     # Update this URL if the repo is renamed or recreated. See RELEASE.md.

# Public file manifest — update RELEASE.md in sync if this list changes.
# Paths are relative to the private repo root.
PUBLIC_FILES=(
    "prompt.md"
    "prompt-analysis-only.md"
    "prompt-standalone.md"
    "rubric.md"
    "schema.json"
    "report-template.md"
    "render.py"
    "install.sh"
    "COMPATIBILITY.md"
    "LICENSE"
)

PUBLIC_DIRS=(
    "examples"
    "rules"
)

# Special renames: "source:destination" (relative to private root → public root)
RENAMED_FILES=(
    "README.public.md:README.md"
    ".gitignore.public:.gitignore"
)

# ── Validation ────────────────────────────────────────────────────────────────

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
    echo "Error: version argument required." >&2
    echo "Usage: ./scripts/release.sh v1.0" >&2
    exit 1
fi

if [[ -z "$PUBLIC_REPO_URL" ]]; then
    echo "Error: PUBLIC_REPO_URL is not set in scripts/release.sh." >&2
    echo "Create the public repo on GitHub, then set the URL. See RELEASE.md." >&2
    exit 1
fi

PRIVATE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Verify working tree is clean
if ! git -C "$PRIVATE_ROOT" diff --quiet HEAD; then
    echo "Error: private repo has uncommitted changes. Commit or stash before releasing." >&2
    exit 1
fi

# Verify all public files exist
for f in "${PUBLIC_FILES[@]}"; do
    if [[ ! -f "$PRIVATE_ROOT/$f" ]]; then
        echo "Error: public file not found: $f" >&2
        exit 1
    fi
done
for d in "${PUBLIC_DIRS[@]}"; do
    if [[ ! -d "$PRIVATE_ROOT/$d" ]]; then
        echo "Error: public directory not found: $d" >&2
        exit 1
    fi
done
for pair in "${RENAMED_FILES[@]}"; do
    src="${pair%%:*}"
    if [[ ! -f "$PRIVATE_ROOT/$src" ]]; then
        echo "Error: renamed source file not found: $src" >&2
        exit 1
    fi
done

# ── Release ───────────────────────────────────────────────────────────────────

WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

echo "→ Cloning public repo..."
git clone "$PUBLIC_REPO_URL" "$WORK_DIR/public"

echo "→ Clearing existing public files (preserving .git)..."
find "$WORK_DIR/public" -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +

echo "→ Copying public files..."
for f in "${PUBLIC_FILES[@]}"; do
    cp "$PRIVATE_ROOT/$f" "$WORK_DIR/public/$f"
done

for d in "${PUBLIC_DIRS[@]}"; do
    cp -r "$PRIVATE_ROOT/$d" "$WORK_DIR/public/$d"
done

for pair in "${RENAMED_FILES[@]}"; do
    src="${pair%%:*}"
    dst="${pair##*:}"
    cp "$PRIVATE_ROOT/$src" "$WORK_DIR/public/$dst"
done

echo "→ Staging changes..."
cd "$WORK_DIR/public"
git add -A

if git diff --cached --quiet; then
    echo "No changes to publish — public files are identical to last release."
    exit 0
fi

echo "→ Committing release $VERSION..."
git commit -m "Release $VERSION"
git tag "$VERSION"

echo "→ Pushing to public repo..."
git push -u origin main
git push origin "$VERSION"

echo "→ Tagging private repo at this release point..."
cd "$PRIVATE_ROOT"
git tag "public-$VERSION"

echo ""
echo "✓ Released $VERSION successfully."
echo "  Public repo: $PUBLIC_REPO_URL"
echo "  Private tag: public-$VERSION"
