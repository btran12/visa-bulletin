# U.S. Visa Bulletin Dashboard

A full-stack, **no-cost** web application that scrapes, parses, and displays
the U.S. State Department Visa Bulletin — with zero dependency on any AI API.

```
visa-bulletin/
├── scraper/
│   ├── parser.py        ← Core HTML → JSON parser (BeautifulSoup + lxml)
│   └── scrape.py        ← CLI: fetch, cache, output JSON
├── frontend/
│   ├── index.html       ← Complete single-file SPA (no build step)
│   └── data/            ← JSON files served to the browser
│       └── 2026-03.json
├── data/                ← Scraper output directory
├── update.sh            ← Cron-friendly monthly updater
└── README.md
```

---

## How the URL works

The State Department bulletin URL follows a completely predictable pattern —
only the **year** and lowercase **month name** ever change:

```
https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin/
    {YEAR}/visa-bulletin-for-{month}-{YEAR}.html

Examples:
  March 2026  → .../visa-bulletin/2026/visa-bulletin-for-march-2026.html
  April 2025  → .../visa-bulletin/2025/visa-bulletin-for-april-2025.html
  January 2024→ .../visa-bulletin/2024/visa-bulletin-for-january-2024.html
```

The scraper constructs this URL automatically from any `--year` / `--month`
argument. The frontend generates the full 24-month dropdown from the same
formula — **no manifest file is needed or generated**.

Local data files mirror the same logic:

```
data/2026-03.json   ←→   .../visa-bulletin/2026/visa-bulletin-for-march-2026.html
data/2025-12.json   ←→   .../visa-bulletin/2025/visa-bulletin-for-december-2025.html
```

---

## Quick start

### 1. Install Python dependencies

```bash
pip install requests beautifulsoup4 lxml
```

### 2. Fetch the latest bulletin

```bash
python scraper/scrape.py
```

Fetches the current month, saves `data/YYYY-MM.json`.

### 3. Copy data to the frontend

```bash
cp data/*.json frontend/data/
```

Or just run `bash update.sh` — it does steps 2 + 3 automatically.

### 4. Open the frontend

```bash
cd frontend && python3 -m http.server 8080
# Open http://localhost:8080
```

---

## Scraper CLI reference

```bash
# Fetch current month (auto-detected from today's date)
python scraper/scrape.py

# Fetch a specific month
python scraper/scrape.py --year 2026 --month 3

# Backfill last 12 months of history
python scraper/scrape.py --backfill 12

# Force re-fetch even if already cached
python scraper/scrape.py --year 2026 --month 3 --force

# Preview JSON without saving
python scraper/scrape.py --dry-run
```

Fetched files are cached — re-running without `--force` skips months
already on disk.

---

## Automation (monthly cron)

Edit your crontab (`crontab -e`) and add:

```
# Run on the 1st of every month at 9 AM
0 9 1 * * /path/to/visa-bulletin/update.sh >> /var/log/vb.log 2>&1
```

`update.sh` fetches the current **and** next month (bulletins are released
~5 weeks ahead), then copies the JSON to `frontend/data/`. The frontend
automatically shows all available months in its dropdown — no config needed.

---

## Hosting

The frontend is a single static HTML file + JSON data files, so it deploys
anywhere:

| Platform           | Command                                              |
|--------------------|------------------------------------------------------|
| **GitHub Pages**   | Push repo, enable Pages → set root to `/frontend`   |
| **Netlify**        | `netlify deploy --dir frontend`                      |
| **Vercel**         | `vercel frontend`                                    |
| **Cloudflare Pages** | Connect repo, output dir = `frontend`              |
| **S3 + CloudFront**| `aws s3 sync frontend/ s3://your-bucket`             |
| **Any VPS**        | Serve `frontend/` with nginx or caddy               |

To automate data updates on a server: run `update.sh` via cron and it
syncs `data/` → `frontend/data/` automatically.

---

## Data format

Each bulletin is saved as `data/YYYY-MM.json`:

```json
{
  "meta": {
    "title": "Visa Bulletin For March 2026",
    "month": "March",
    "month_num": 3,
    "year": 2026,
    "volume": "XI",
    "number": "12",
    "published": "February 4, 2026",
    "url": "https://travel.state.gov/.../visa-bulletin-for-march-2026.html",
    "scraped_at": "2026-03-14T00:00:00+00:00"
  },
  "employment_final":  { "EB1": {"ALL_OTHER":"C","CHINA":"2023-03-01",...}, ... },
  "employment_filing": { ... },
  "family_final":      { "F1":  {"ALL_OTHER":"2016-11-08",...}, ... },
  "family_filing":     { ... },
  "dv_current":        { "AFRICA": {"cutoff":45000,"exceptions":{"Algeria":37000}}, ... },
  "dv_next":           { ... },
  "admin_notices":     [ "D. Availability notice...", "E. Religious workers..." ]
}
```

Dates are **ISO-8601** (`"2023-03-01"`). Special values: `"C"` = Current, `"U"` = Unavailable.

---

## Features

| Feature             | Details                                                          |
|---------------------|------------------------------------------------------------------|
| Personal lookup     | Category + country + priority date → instant eligibility result |
| EB tables           | EB-1 through EB-5 (all set-asides), Final Action + Filing dates |
| Family tables       | F1–F4, Final Action + Filing dates                              |
| Diversity lottery   | Current month + next-month advance preview                      |
| Trend history       | Cutoff movement across months once backfilled                   |
| How it works guide  | Plain-language explainers on all key concepts                   |
| Dark mode           | Automatic, follows OS preference                                |
| No build step       | Frontend is one HTML file                                        |
| Zero API cost       | Pure Python scraping — no AI, no paid services                  |
| No manifest file    | Month list derived directly from the URL pattern                 |

---

## Caveats

- Not legal advice. Always consult a licensed immigration attorney.
- The State Department may restructure the bulletin HTML; the parser may
  need updates if they do. The parser classifies tables by content rather
  than CSS selectors, making it resilient to minor markup changes.
- Be respectful of travel.state.gov — the cron fetches once a month,
  which is more than sufficient.
