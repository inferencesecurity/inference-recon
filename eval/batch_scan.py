#!/usr/bin/env python3
"""
eval/batch_scan.py — Batch Inference Recon scanner.

Clones (or reuses cached) repos from a list, runs the Inference Recon scanner against
each, saves findings.json, and ingests into the eval DB.

Usage:
    python3 eval/batch_scan.py eval/corpus/repos.txt [options]

    --model MODEL     Provider model string (provider/model-name)
                      Default: anthropic/claude-haiku-4-5-20251001
                      Examples: anthropic/claude-sonnet-4-6  anthropic/claude-opus-4-7
                                openai/gpt-4o-mini  google/gemini-2.0-flash
    --pull            Git-pull cached repos before scanning
    --dry-run         Collect files and build prompt; skip API call and ingest
    --db PATH         SQLite path when DATABASE_URL is not set

Examples:
    # Haiku sweep of the whole corpus (fast, cheap)
    python3 eval/batch_scan.py eval/corpus/repos.txt

    # Sonnet pass on one repo
    python3 eval/batch_scan.py eval/corpus/repos.txt \\
        --model anthropic/claude-sonnet-4-6

    # Opus pass (best quality, higher cost)
    python3 eval/batch_scan.py eval/corpus/repos.txt \\
        --model anthropic/claude-opus-4-7

    # Cross-vendor comparison
    python3 eval/batch_scan.py eval/corpus/repos.txt --model openai/gpt-4o-mini
    python3 eval/batch_scan.py eval/corpus/repos.txt --model google/gemini-2.0-flash

    # Docker (from repo root)
    docker compose run --rm scanner python eval/batch_scan.py eval/corpus/repos.txt
"""

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Load .env from repo root before any SDK initialisation
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass  # python-dotenv not installed — rely on environment variables

# ── Paths ─────────────────────────────────────────────────────────────────────

REPO_ROOT    = Path(__file__).parent.parent
PROMPT_PATH  = REPO_ROOT / "prompt-standalone.md"
EVAL_DIR     = Path(__file__).parent
CACHE_DIR    = EVAL_DIR / "corpus" / "repos"
FINDINGS_DIR = EVAL_DIR / "corpus" / "findings"
DEFAULT_DB   = EVAL_DIR / "db" / "eval.db"

DEFAULT_MODEL = "haiku"

# ── File-collection constants ─────────────────────────────────────────────────

SKIP_DIRS = {
    "node_modules", "vendor", "dist", "__pycache__", ".git",
    "build", "target", ".venv", "venv", "env", "coverage",
    ".nyc_output", "out", "bin", "obj", ".gradle", ".mvn",
    "htmlcov", "site-packages", ".next", ".nuxt", "public/build",
}

SKIP_FILENAMES = {
    "package-lock.json", "yarn.lock", "poetry.lock", "Pipfile.lock",
    "composer.lock", "Gemfile.lock", "go.sum",
}

BINARY_EXTENSIONS = {
    ".jar", ".class", ".war", ".ear", ".pyc", ".pyo",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".zip", ".tar", ".gz", ".tgz", ".rar", ".7z",
    ".exe", ".dll", ".so", ".dylib", ".a", ".lib",
    ".woff", ".woff2", ".ttf", ".eot",
    ".mp3", ".mp4", ".avi", ".mov",
    ".db", ".sqlite", ".sqlite3",
}

# Files without an extension or not in this set get a binary sniff check
KNOWN_TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb", ".php",
    ".cs", ".cpp", ".c", ".h", ".hpp", ".rs", ".swift", ".kt", ".scala",
    ".html", ".htm", ".jinja2", ".jinja", ".j2", ".hbs", ".ejs",
    ".vue", ".svelte", ".xml", ".json", ".yaml", ".yml", ".toml",
    ".ini", ".cfg", ".env", ".sh", ".bash", ".zsh", ".ps1", ".bat",
    ".sql", ".graphql", ".gql", ".proto", ".md", ".txt", ".rst",
    ".tf", ".tfvars", ".hcl", ".gradle", ".properties",
}

MAX_FILES      = 150
MAX_LINES      = 10_000
MAX_FILE_LINES = 2_000


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class RepoSpec:
    source:        str   # URL or absolute local path
    canonical_url: str   # stable identity for the DB (= source if URL)
    name:          str   # slug used for cache dir and output filenames


@dataclass
class ScanResult:
    repo:          str
    status:        str   # ok | error | dry-run
    scan_id:       str   = ""
    findings:      int   = 0
    critical:      int   = 0
    high:          int   = 0
    medium:        int   = 0
    overall:       str   = ""
    input_tokens:           int   = 0
    output_tokens:          int   = 0
    cache_creation_tokens:  int   = 0
    cache_read_tokens:      int   = 0
    elapsed:                float = 0.0
    error:         str   = ""


# ── repos.txt parser ──────────────────────────────────────────────────────────

def parse_repos_file(path: str) -> list[RepoSpec]:
    """
    Parse repos.txt. Format per line:
        <url-or-path> [--url <canonical-url>]

    Lines starting with # and blank lines are ignored.
    """
    specs = []
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        source = parts[0]

        # Optional --url override for local paths
        canonical_url = source
        if "--url" in parts:
            idx = parts.index("--url")
            if idx + 1 < len(parts):
                canonical_url = parts[idx + 1]

        # Derive name from last path component
        name = source.rstrip("/").split("/")[-1].removesuffix(".git")

        # Resolve local paths to absolute
        if not source.startswith(("http://", "https://", "git@")):
            source = str(Path(source).expanduser().resolve())

        specs.append(RepoSpec(source=source, canonical_url=canonical_url, name=name))

    return specs


# ── Repo management ───────────────────────────────────────────────────────────

def ensure_repo(spec: RepoSpec, pull: bool) -> Path:
    """Return local path to repo, cloning or pulling as needed."""
    import git  # noqa: PLC0415

    # Local path — verify it exists, optionally pull
    if not spec.source.startswith(("http://", "https://", "git@")):
        p = Path(spec.source)
        if not p.exists():
            raise FileNotFoundError(f"local path not found: {spec.source}")
        if pull:
            print(f"    pulling {spec.name}...")
            try:
                git.Repo(p).remotes.origin.pull()
            except Exception as exc:
                print(f"    WARNING: pull failed ({exc}), using existing cache")
        return p

    # Remote URL — use cache
    dest = CACHE_DIR / spec.name
    if dest.exists():
        if pull:
            print(f"    pulling {spec.name}...")
            try:
                git.Repo(dest).remotes.origin.pull()
            except Exception as exc:
                print(f"    WARNING: pull failed ({exc}), using existing cache")
        else:
            print(f"    using cached {spec.name}")
    else:
        print(f"    cloning {spec.name}...")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        git.Repo.clone_from(spec.source, dest, depth=1)

    return dest


# ── Source file collector ─────────────────────────────────────────────────────

def collect_source(repo_path: Path) -> tuple[str, int, int]:
    """
    Walk repo_path and build a concatenated text blob of all scannable files.
    Returns (blob, file_count, line_count).
    Respects the size budget (MAX_FILES, MAX_LINES, MAX_FILE_LINES).
    """
    sections: list[str] = []
    file_count = 0
    line_count = 0

    for root, dirs, files in os.walk(repo_path):
        # Prune unwanted directories before recursing
        dirs[:] = sorted(
            d for d in dirs
            if d not in SKIP_DIRS and not d.startswith(".")
        )

        for fname in sorted(files):
            if file_count >= MAX_FILES or line_count >= MAX_LINES:
                break
            if fname in SKIP_FILENAMES:
                continue

            fpath    = Path(root) / fname
            suffix   = fpath.suffix.lower()

            if suffix in BINARY_EXTENSIONS:
                continue

            # For unknown extensions, sniff for null bytes
            if suffix not in KNOWN_TEXT_EXTENSIONS:
                try:
                    if b"\x00" in fpath.read_bytes()[:512]:
                        continue
                except OSError:
                    continue

            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            lines = content.splitlines()
            if not lines:
                continue

            if len(lines) > MAX_FILE_LINES:
                lines   = lines[:MAX_FILE_LINES]
                content = "\n".join(lines) + f"\n... (truncated at {MAX_FILE_LINES} lines)"

            rel = fpath.relative_to(repo_path)
            sections.append(f"=== {rel} ===\n{content}")
            file_count += 1
            line_count += len(lines)

    return "\n\n".join(sections), file_count, line_count


def detect_stack(repo_path: Path) -> str:
    """Best-effort stack detection from manifest files."""
    hints = []
    if (repo_path / "pom.xml").exists():
        hints.append("Java (Maven)")
    elif any(repo_path.glob("build.gradle*")):
        hints.append("Java (Gradle)")
    if (repo_path / "package.json").exists():
        hints.append("Node.js")
    if any([
        (repo_path / "requirements.txt").exists(),
        (repo_path / "pyproject.toml").exists(),
        (repo_path / "Pipfile").exists(),
    ]):
        hints.append("Python")
    if (repo_path / "go.mod").exists():
        hints.append("Go")
    if (repo_path / "Gemfile").exists():
        hints.append("Ruby")
    if (repo_path / "composer.json").exists():
        hints.append("PHP")
    if any(repo_path.rglob("*.csproj")):
        hints.append(".NET")
    return ", ".join(hints) if hints else "unknown"


# ── JSON extractor ────────────────────────────────────────────────────────────

def extract_json(text: str) -> dict:
    """Extract and parse the first ```json fenced block from model output.

    Attempts a lenient parse first: if strict json.loads fails due to trailing
    content (a common model formatting error), strips the offending suffix and
    retries once before raising.
    """
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if not match:
        raise ValueError("no ```json block found in model response")
    raw = match.group(1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        # Attempt to recover by truncating at the position of the error
        # (handles stray closing braces / extra tokens after valid JSON).
        truncated = raw[:exc.pos].rstrip().rstrip(",")
        # Walk back to the last complete closing brace
        last_brace = truncated.rfind("}")
        if last_brace != -1:
            candidate = truncated[:last_brace + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
        raise


# ── Main scan pipeline ────────────────────────────────────────────────────────

def scan_one(
    spec:    RepoSpec,
    model:   str,
    prompt:  str,
    db_url:  str,
    pull:    bool,
    dry_run: bool,
) -> ScanResult:
    t0 = time.time()

    try:
        repo_path = ensure_repo(spec, pull)
    except Exception as exc:
        return ScanResult(repo=spec.name, status="error", error=f"repo: {exc}")

    source_text, file_count, line_count = collect_source(repo_path)
    stack = detect_stack(repo_path)

    user_msg = (
        f"Project: {spec.name}\n"
        f"Stack hint: {stack}\n"
        f"Files collected: {file_count} ({line_count} lines)\n\n"
        f"{source_text}"
    )

    print(f"    {file_count} files · {line_count} lines · {stack}")

    if dry_run:
        chars = len(prompt) + len(user_msg)
        print(f"    [dry-run] ~{chars // 4:,} estimated tokens (prompt + source)")
        return ScanResult(repo=spec.name, status="dry-run", elapsed=time.time() - t0)

    # ── API call ──────────────────────────────────────────────────────────────
    from providers import call, provider_from_model, resolve_model  # noqa: PLC0415

    try:
        resp = call(model=model, system=prompt, user=user_msg)
    except Exception as exc:
        return ScanResult(repo=spec.name, status="error",
                          error=f"api: {exc}", elapsed=time.time() - t0)

    # ── Extract JSON envelope ─────────────────────────────────────────────────
    try:
        envelope = extract_json(resp.text)
    except Exception as exc:
        FINDINGS_DIR.mkdir(parents=True, exist_ok=True)
        raw_path = FINDINGS_DIR / f"{spec.name}-raw-{_ts()}.txt"
        # Prepend token metadata so costs are recoverable even if JSON is malformed
        token_header = (
            f"# PARSE ERROR — token counts preserved for cost recovery\n"
            f"# model:                  {resolve_model(model).split('/', 1)[-1]}\n"
            f"# input_tokens:           {resp.input_tokens}\n"
            f"# output_tokens:          {resp.output_tokens}\n"
            f"# cache_creation_tokens:  {resp.cache_creation_tokens}\n"
            f"# cache_read_tokens:      {resp.cache_read_tokens}\n"
            f"# error:                  {exc}\n"
            f"#\n"
        )
        raw_path.write_text(token_header + resp.text)
        return ScanResult(
            repo=spec.name, status="error",
            error=f"json_parse: {exc} — raw saved to {raw_path.name}",
            input_tokens=resp.input_tokens, output_tokens=resp.output_tokens,
            cache_creation_tokens=resp.cache_creation_tokens,
            cache_read_tokens=resp.cache_read_tokens,
            elapsed=time.time() - t0,
        )

    # Resolve tier alias (e.g. "opus" → "claude-opus-4-7") and strip provider prefix
    # before storing. Model's self-reported name is unreliable; always use ours.
    envelope.setdefault("scan", {})
    envelope["scan"]["model"] = resolve_model(model).split("/", 1)[-1]

    # ── Save findings.json ────────────────────────────────────────────────────
    FINDINGS_DIR.mkdir(parents=True, exist_ok=True)
    findings_path = FINDINGS_DIR / f"{spec.name}-{_ts()}.json"
    findings_path.write_text(json.dumps(envelope, indent=2))
    print(f"    saved {findings_path.name}")

    # ── Ingest into DB ────────────────────────────────────────────────────────
    tool = provider_from_model(model)
    try:
        from ingest import ingest  # noqa: PLC0415
        scan_id = ingest(
            db_url=db_url,
            json_path=str(findings_path),
            tool=tool,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            cache_creation_tokens=resp.cache_creation_tokens,
            cache_read_tokens=resp.cache_read_tokens,
            project_url=spec.canonical_url if spec.canonical_url != spec.source else None,
            duration_seconds=round(time.time() - t0, 1),
        )
    except Exception as exc:
        return ScanResult(
            repo=spec.name, status="error", error=f"ingest: {exc}",
            input_tokens=resp.input_tokens, output_tokens=resp.output_tokens,
            elapsed=time.time() - t0,
        )

    sev     = envelope.get("summary", {}).get("counts_by_severity", {})
    overall = envelope.get("summary", {}).get("scorecard", {}).get("overall", "?")

    return ScanResult(
        repo=spec.name, status="ok",
        scan_id=scan_id[:8],
        findings=sum(sev.values()),
        critical=sev.get("critical", 0),
        high=sev.get("high", 0),
        medium=sev.get("medium", 0),
        overall=overall,
        input_tokens=resp.input_tokens,
        output_tokens=resp.output_tokens,
        cache_creation_tokens=resp.cache_creation_tokens,
        cache_read_tokens=resp.cache_read_tokens,
        elapsed=time.time() - t0,
    )


def _ts() -> str:
    return datetime.now().strftime("%Y%m%dT%H%M%S")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch Inference Recon scanner.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("repos_file", help="Path to repos.txt")
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"Provider model string — provider/model-name (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--pull", action="store_true",
        help="Git-pull cached repos before scanning",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Collect files and estimate tokens; skip API call and ingest",
    )
    parser.add_argument(
        "--db", default=str(DEFAULT_DB),
        help=f"SQLite path when DATABASE_URL is unset (default: {DEFAULT_DB})",
    )
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL") or args.db
    prompt = PROMPT_PATH.read_text()
    repos  = parse_repos_file(args.repos_file)

    if not repos:
        print("No repos found in repos file — nothing to do.")
        sys.exit(0)

    print(f"model   : {args.model}")
    print(f"repos   : {len(repos)}")
    print(f"db      : {db_url}")
    if args.dry_run:
        print("mode    : dry-run (no API calls)")
    print()

    results: list[ScanResult] = []
    for spec in repos:
        print(f"→ {spec.name}")
        result = scan_one(spec, args.model, prompt, db_url, args.pull, args.dry_run)
        results.append(result)

        if result.status == "ok":
            cache_note = ""
            if result.cache_read_tokens:
                cache_note = f"  cache_hit={result.cache_read_tokens:,}"
            elif result.cache_creation_tokens:
                cache_note = f"  cache_write={result.cache_creation_tokens:,}"
            print(
                f"  ✓  {result.findings} findings "
                f"({result.critical}C {result.high}H {result.medium}M)  "
                f"overall:{result.overall}  "
                f"scan:{result.scan_id}  "
                f"{result.input_tokens:,}in/{result.output_tokens:,}out"
                f"{cache_note}  {result.elapsed:.0f}s"
            )
        elif result.status == "dry-run":
            print(f"  –  {result.elapsed:.1f}s")
        else:
            print(f"  ✗  {result.error}")
        print()

    # ── Summary ───────────────────────────────────────────────────────────────
    ok     = [r for r in results if r.status == "ok"]
    errors = [r for r in results if r.status == "error"]
    print("─" * 60)
    print(f"done: {len(ok)} ok  {len(errors)} errors  {len(results)} total")

    if ok:
        total_in       = sum(r.input_tokens          for r in ok)
        total_out      = sum(r.output_tokens         for r in ok)
        total_cache_w  = sum(r.cache_creation_tokens for r in ok)
        total_cache_r  = sum(r.cache_read_tokens     for r in ok)
        total_sec      = sum(r.elapsed               for r in ok)
        cache_summary  = ""
        if total_cache_w or total_cache_r:
            cache_summary = f"  cache_write={total_cache_w:,}  cache_read={total_cache_r:,}"
        print(f"tokens: {total_in:,} in / {total_out:,} out{cache_summary}")
        print(f"time  : {total_sec:.0f}s total")

    if errors:
        print("\nerrors:")
        for r in errors:
            print(f"  {r.repo}: {r.error}")


if __name__ == "__main__":
    main()
