#!/usr/bin/env python3
"""
build.py — Embeds all data/YYYY-MM.json files into frontend/index.html.
Run after scraping: python scraper/scrape.py && python build.py
"""
import json, sys
from pathlib import Path

ROOT     = Path(__file__).parent
DATA_DIR = ROOT / "data"
HTML     = ROOT / "frontend" / "index.html"

def main():
    files = sorted(DATA_DIR.glob("????-??.json"), reverse=True)
    if not files:
        print("No data files found. Run: python scraper/scrape.py"); sys.exit(1)

    seeded = {}
    for f in files:
        try: seeded[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e: print(f"  WARN: skipping {f.name} — {e}")

    print(f"Embedding {len(seeded)} bulletin(s): {sorted(seeded.keys(), reverse=True)}")

    new_val = json.dumps(seeded, separators=(",",":"), ensure_ascii=False)
    lines   = HTML.read_text(encoding="utf-8").split("\n")

    for i, line in enumerate(lines):
        if line.startswith("const SEEDED_DATA = "):
            lines[i] = f"const SEEDED_DATA = {new_val};"
            HTML.write_text("\n".join(lines), encoding="utf-8")
            print(f"Written: {HTML}  ({HTML.stat().st_size/1024:.1f} KB)")
            return

    print("ERROR: 'const SEEDED_DATA = ' line not found in index.html"); sys.exit(1)

if __name__ == "__main__":
    main()
