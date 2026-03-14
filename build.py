#!/usr/bin/env python3
"""
build.py
────────
Embeds all data/YYYY-MM.json files directly into frontend/index.html
as a JS constant, so the dashboard works with file://, localhost, or
any static host — no fetch() calls needed for already-downloaded data.

Run after scraping:
    python scraper/scrape.py
    python build.py

Or just use update.sh which calls both automatically.
"""
import glob
import json
import os
import re
import sys
from pathlib import Path

ROOT      = Path(__file__).parent
DATA_DIR  = ROOT / "data"
HTML_IN   = ROOT / "frontend" / "index.html"
HTML_OUT  = HTML_IN  # overwrite in place

def main():
    # ── Collect all scraped JSON files ────────────────────────────────────
    files = sorted(DATA_DIR.glob("????-??.json"), reverse=True)
    if not files:
        print("No data files found in data/. Run: python scraper/scrape.py")
        sys.exit(1)

    seeded = {}
    for f in files:
        key = f.stem  # e.g. "2026-03"
        try:
            seeded[key] = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  WARN: skipping {f.name} — {e}")

    print(f"Embedding {len(seeded)} bulletin(s): {sorted(seeded.keys(), reverse=True)}")

    # ── Read HTML ─────────────────────────────────────────────────────────
    html = HTML_IN.read_text(encoding="utf-8")

    # ── Replace SEEDED_DATA constant ─────────────────────────────────────
    # Pattern matches:  const SEEDED_DATA = {...};
    seeded_js = json.dumps(seeded, separators=(",", ":"), ensure_ascii=False)
    new_const = f"const SEEDED_DATA = {seeded_js};"

    pattern = r"const SEEDED_DATA = \{.*?\};"
    if re.search(pattern, html, re.DOTALL):
        html = re.sub(pattern, new_const, html, flags=re.DOTALL)
        print("✓ SEEDED_DATA updated in existing HTML")
    else:
        print("ERROR: SEEDED_DATA placeholder not found in index.html")
        sys.exit(1)

    # ── Write out ─────────────────────────────────────────────────────────
    HTML_OUT.write_text(html, encoding="utf-8")
    size_kb = HTML_OUT.stat().st_size / 1024
    print(f"✓ Written: {HTML_OUT}  ({size_kb:.1f} KB)")

if __name__ == "__main__":
    main()
