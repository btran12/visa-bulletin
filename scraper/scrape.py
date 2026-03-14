#!/usr/bin/env python3
"""
visa_bulletin/scraper/scrape.py
────────────────────────────────
CLI script to fetch and parse the latest (or a specific) Visa Bulletin,
saving structured JSON to the data/ directory.

URL pattern (the only moving parts are YEAR and lowercase month name):
    https://travel.state.gov/.../visa-bulletin/YEAR/visa-bulletin-for-MONTH-YEAR.html

    March 2026  ->  .../visa-bulletin/2026/visa-bulletin-for-march-2026.html
    April 2025  ->  .../visa-bulletin/2025/visa-bulletin-for-april-2025.html

Output files are named  data/YYYY-MM.json  and are loaded directly by the
frontend — no manifest file is generated or required.

Usage
-----
    # Fetch the current month's bulletin
    python scrape.py

    # Fetch a specific month
    python scrape.py --year 2026 --month 3

    # Backfill last 12 months of history
    python scrape.py --backfill 12

    # Force re-fetch even if already cached
    python scrape.py --force

    # Preview JSON without saving
    python scrape.py --dry-run
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Allow running from any directory
sys.path.insert(0, str(Path(__file__).parent))
from parser import BulletinParser, MONTHS_EN

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"


def data_path(year: int, month: int) -> Path:
    return DATA_DIR / f"{year}-{month:02d}.json"


def save(data: dict, year: int, month: int) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = data_path(year, month)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Saved → %s  (%d bytes)", path, path.stat().st_size)
    return path


def fetch_month(year: int, month: int, force: bool = False, dry_run: bool = False) -> dict | None:
    path = data_path(year, month)
    if not force and path.exists() and not dry_run:
        log.info("Cache hit: %s — skipping (use --force to re-fetch)", path.name)
        return json.loads(path.read_text())

    log.info(
        "Fetching %s %d ...",
        MONTHS_EN[month - 1].title(),
        year,
    )
    try:
        data = BulletinParser.fetch_and_parse(year=year, month=month)
    except Exception as exc:
        log.error("Failed to fetch %d-%02d: %s", year, month, exc)
        return None

    if dry_run:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        save(data, year, month)

    return data


def current_bulletin_month() -> tuple[int, int]:
    """
    Derive the most likely current bulletin month from today's date.
    Bulletins are published around the 8th of the prior month, so once
    we're past the 8th we also try the next calendar month.
    """
    now = datetime.now(timezone.utc)
    return now.year, now.month


def main() -> None:
    ap = argparse.ArgumentParser(description="Fetch & parse U.S. Visa Bulletin data")
    ap.add_argument("--year",     type=int, help="Bulletin year  (default: current)")
    ap.add_argument("--month",    type=int, help="Bulletin month 1-12 (default: current)")
    ap.add_argument("--backfill", type=int, metavar="N", help="Fetch last N months")
    ap.add_argument("--force",    action="store_true", help="Re-fetch even if cached")
    ap.add_argument("--dry-run",  action="store_true", help="Print JSON, do not save")
    args = ap.parse_args()

    if args.backfill:
        now = datetime.now(timezone.utc)
        y, m = now.year, now.month
        months: list[tuple[int, int]] = []
        for _ in range(args.backfill):
            months.append((y, m))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        for year, month in reversed(months):
            fetch_month(year, month, force=args.force, dry_run=args.dry_run)
            time.sleep(1)  # be polite
    else:
        year, month = current_bulletin_month()
        if args.year:  year  = args.year
        if args.month: month = args.month
        result = fetch_month(year, month, force=args.force, dry_run=args.dry_run)
        if result is None:
            sys.exit(1)

    # No manifest needed — the frontend derives all URLs from the pattern:
    #   data/{YEAR}-{MM}.json  ←→  .../visa-bulletin/{YEAR}/visa-bulletin-for-{month}-{YEAR}.html


if __name__ == "__main__":
    main()
