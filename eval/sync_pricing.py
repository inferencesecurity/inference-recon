#!/usr/bin/env python3
"""
eval/sync_pricing.py — Scrape Anthropic model pricing from docs and sync to DB.

Fetches the models overview page, parses the pricing comparison table, and
inserts new model_pricing rows for any changes detected. Existing rows are
never modified — a new row with today's date is inserted instead, preserving
price history. cost_usd is backfilled for all affected scans.

Guard: if a detected change exceeds MAX_CHANGE_FACTOR (2×) in either direction
it is skipped and logged — most likely a parse error, not a real price change.

Usage:
    python3 eval/sync_pricing.py [--dry-run] [--db PATH]

Intended to run daily. Natural fit alongside the model promotion benchmark:
before adopting a new model tier, run this first to ensure pricing is current.
"""

import argparse
import os
import re
import ssl
import sys
import time
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

try:
    import certifi
    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CONTEXT = ssl.create_default_context()

# ── Config ────────────────────────────────────────────────────────────────────

DOCS_URL = "https://platform.claude.com/docs/en/docs/about-claude/models/overview"
MAX_CHANGE_FACTOR = 2.0   # skip update if new price differs by more than this multiple

sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

from ingest import open_db, DEFAULT_SQLITE_PATH  # noqa: E402


# ── HTML table extractor ──────────────────────────────────────────────────────

class _TableExtractor(HTMLParser):
    """
    Walks HTML and collects all <table> contents as a list of row lists.
    Each cell is the concatenated text content (whitespace-normalised).
    <br> tags are replaced with a space so multi-line cells stay parseable.
    <sup> and other inline tags are stripped; only their text is kept.
    """

    def __init__(self):
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row:   list[str]       | None = None
        self._cell:  list[str]       | None = None
        self._depth = 0   # nested table depth

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._depth += 1
            if self._depth == 1:
                self._table = []
        elif tag == "tr" and self._depth == 1:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag == "table":
            if self._depth == 1 and self._table is not None:
                self.tables.append(self._table)
                self._table = None
            self._depth -= 1
        elif tag == "tr" and self._depth == 1:
            if self._row is not None and self._table is not None:
                self._table.append(self._row)
            self._row = None
        elif tag in ("td", "th") and self._row is not None:
            if self._cell is not None:
                text = re.sub(r"\s+", " ", " ".join(self._cell)).strip()
                self._row.append(text)
            self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            stripped = data.strip()
            if stripped:
                self._cell.append(stripped)


# ── Parsing ───────────────────────────────────────────────────────────────────

_PRICE_RE = re.compile(
    r"\$(\d+(?:\.\d+)?)\s*/\s*input\s*MTok"
    r".*?"
    r"\$(\d+(?:\.\d+)?)\s*/\s*output\s*MTok",
    re.IGNORECASE | re.DOTALL,
)

_MODEL_ID_RE = re.compile(r"^claude-[\w]+-[\w.-]+$", re.IGNORECASE)


def _parse_pricing_table(table: list[list[str]]) -> dict[str, tuple[float, float]]:
    """
    Given one table (list of rows), find the 'Claude API ID' and 'Pricing'
    rows and return {model_id: (input_per_1m, output_per_1m)}.
    """
    api_id_row: list[str] | None = None
    pricing_row: list[str] | None = None

    for row in table:
        if not row:
            continue
        label = row[0].lower()
        if "claude api id" in label or ("api" in label and "id" in label):
            api_id_row = row
        elif "pricing" in label and api_id_row is not None:
            pricing_row = row

    if api_id_row is None or pricing_row is None:
        return {}

    results: dict[str, tuple[float, float]] = {}
    cols = min(len(api_id_row), len(pricing_row))

    for col in range(1, cols):
        model_id = api_id_row[col].strip()
        if not _MODEL_ID_RE.match(model_id):
            continue

        price_match = _PRICE_RE.search(pricing_row[col])
        if not price_match:
            continue

        results[model_id] = (float(price_match.group(1)), float(price_match.group(2)))

    return results


def fetch_pricing() -> dict[str, tuple[float, float]]:
    """
    Fetch the Anthropic docs page and return all model pricing found.
    Raises on network error; returns empty dict if no pricing table parsed.
    """
    req = Request(
        DOCS_URL,
        headers={"User-Agent": "inference-recon-pricing-sync/1.0"},
    )
    try:
        with urlopen(req, timeout=15, context=_SSL_CONTEXT) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except URLError as exc:
        raise RuntimeError(f"Failed to fetch {DOCS_URL}: {exc}") from exc

    extractor = _TableExtractor()
    extractor.feed(html)

    results: dict[str, tuple[float, float]] = {}
    for table in extractor.tables:
        results.update(_parse_pricing_table(table))

    return results


# ── DB sync ───────────────────────────────────────────────────────────────────

def sync_pricing(db_url: str, dry_run: bool = False) -> int:
    """
    Sync scraped pricing to DB. Returns number of models updated/added.
    """
    print(f"Fetching {DOCS_URL} ...")
    try:
        scraped = fetch_pricing()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 0

    if not scraped:
        print("ERROR: no pricing data parsed from page — structure may have changed",
              file=sys.stderr)
        return 0

    print(f"  Parsed {len(scraped)} model(s) from docs")

    db = open_db(db_url)
    today = date.today().isoformat()
    updated = 0
    skipped = 0

    for model_id, (new_in, new_out) in sorted(scraped.items()):
        row = db.fetchone(
            "SELECT input_per_1m, output_per_1m FROM model_pricing "
            "WHERE model = ? ORDER BY effective_from DESC LIMIT 1",
            (model_id,),
        )

        if row is None:
            # New model not yet in our table
            print(f"  NEW    {model_id:<40}  ${new_in} / ${new_out}")
            if not dry_run:
                db.execute(
                    "INSERT OR IGNORE INTO model_pricing "
                    "(model, effective_from, provider, input_per_1m, output_per_1m) "
                    "VALUES (?,?,?,?,?)",
                    (model_id, today, "anthropic", new_in, new_out),
                )
            updated += 1
            continue

        cur_in, cur_out = float(row["input_per_1m"]), float(row["output_per_1m"])

        if cur_in == new_in and cur_out == new_out:
            print(f"  OK     {model_id:<40}  ${cur_in} / ${cur_out}")
            continue

        # Sanity guard: skip implausible changes
        in_factor  = max(new_in, cur_in)  / min(new_in, cur_in)  if cur_in  else 999
        out_factor = max(new_out, cur_out) / min(new_out, cur_out) if cur_out else 999
        factor = max(in_factor, out_factor)

        if factor > MAX_CHANGE_FACTOR:
            print(f"  SKIP   {model_id:<40}  "
                  f"${cur_in}/${cur_out} → ${new_in}/${new_out}  "
                  f"({factor:.1f}× — exceeds {MAX_CHANGE_FACTOR}× guard, skipping)")
            skipped += 1
            continue

        print(f"  UPDATE {model_id:<40}  "
              f"${cur_in}/${cur_out} → ${new_in}/${new_out}")

        if not dry_run:
            db.execute(
                "INSERT OR IGNORE INTO model_pricing "
                "(model, effective_from, provider, input_per_1m, output_per_1m) "
                "VALUES (?,?,?,?,?)",
                (model_id, today, "anthropic", new_in, new_out),
            )
            # Backfill cost_usd for scans using this model
            db.execute(
                "UPDATE scans "
                "SET cost_usd = ("
                "  SELECT ROUND(("
                "    (COALESCE(scans.input_tokens, 0)          * mp.input_per_1m +"
                "     COALESCE(scans.cache_creation_tokens, 0) * mp.input_per_1m * 1.25 +"
                "     COALESCE(scans.cache_read_tokens, 0)     * mp.input_per_1m * 0.10 +"
                "     COALESCE(scans.output_tokens, 0)         * mp.output_per_1m"
                "  ) / 1000000.0), 6)"
                "  FROM model_pricing mp"
                "  WHERE mp.model = scans.model"
                "  ORDER BY mp.effective_from DESC LIMIT 1"
                ") "
                "WHERE scans.model = ?"
                "  AND (scans.input_tokens IS NOT NULL OR scans.output_tokens IS NOT NULL)",
                (model_id,),
            )
        updated += 1

    if not dry_run and updated:
        db.commit()

    db.close()

    prefix = "[dry-run] " if dry_run else ""
    print(f"\n{prefix}{updated} updated/added, {skipped} skipped (guard)")
    return updated


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing to DB")
    parser.add_argument("--loop", action="store_true",
                        help="Run continuously, syncing once every 24 hours")
    parser.add_argument("--db", default=str(DEFAULT_SQLITE_PATH),
                        help=f"SQLite path (default: {DEFAULT_SQLITE_PATH})")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL") or args.db

    if args.loop:
        while True:
            sync_pricing(db_url, dry_run=args.dry_run)
            print("Sleeping 24 h ...", flush=True)
            time.sleep(86400)
    else:
        sync_pricing(db_url, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
