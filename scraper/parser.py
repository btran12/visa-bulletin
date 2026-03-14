"""
visa_bulletin/scraper/parser.py
────────────────────────────────
Scrapes and parses a U.S. Visa Bulletin page from travel.state.gov
into a clean, structured Python dict (serialisable to JSON).

Usage
-----
    from parser import BulletinParser
    data = BulletinParser.fetch_and_parse(year=2026, month=3)
    # or from a local file:
    data = BulletinParser.parse_file("march2026.html")
"""

from __future__ import annotations

import re
import json
import logging
from datetime import datetime, date, timezone
from typing import Optional
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

BASE_URL = "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin"

# URL pattern (year and lowercase month name are the only moving parts):
#   {BASE_URL}/{YEAR}/visa-bulletin-for-{month}-{YEAR}.html
#
# March 2026 → .../visa-bulletin/2026/visa-bulletin-for-march-2026.html
# April 2025 → .../visa-bulletin/2025/visa-bulletin-for-april-2025.html

MONTHS_EN = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]

MONTH_ABBR = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

# Column index → chargeability area key
COUNTRY_COLS = {
    1: "ALL_OTHER",
    2: "CHINA",
    3: "INDIA",
    4: "MEXICO",
    5: "PHILIPPINES",
}

# ──────────────────────────────────────────────────────────────────────────────
# Date helpers
# ──────────────────────────────────────────────────────────────────────────────

def parse_bulletin_date(raw: str) -> Optional[str]:
    """
    Convert raw bulletin date strings to ISO-8601 (YYYY-MM-DD).

    Handles:
        "01MAR23"  → "2023-03-01"
        "01MAR2023"→ "2023-03-01"
        "C"        → "C"   (Current)
        "U"        → "U"   (Unavailable)
        ""         → None
    """
    if not raw:
        return None
    raw = raw.strip().upper()
    if raw in ("C", "U"):
        return raw

    m = re.match(r"^(\d{1,2})([A-Z]{3})(\d{2,4})$", raw)
    if not m:
        log.debug("Unrecognised date format: %r", raw)
        return raw  # return as-is rather than drop

    day = int(m.group(1))
    mon = MONTH_ABBR.get(m.group(2))
    yr_raw = m.group(3)
    year = int(yr_raw) if len(yr_raw) == 4 else 2000 + int(yr_raw)

    if mon is None:
        return raw
    try:
        return date(year, mon, day).isoformat()
    except ValueError:
        return raw


# ──────────────────────────────────────────────────────────────────────────────
# Table parser
# ──────────────────────────────────────────────────────────────────────────────

def parse_preference_table(table: Tag) -> dict[str, dict[str, Optional[str]]]:
    """
    Extract a preference-category table (family or employment) into:
        { "F1": {"ALL_OTHER": "2016-11-08", "CHINA": "2016-11-08", ...}, ... }
    """
    result: dict[str, dict[str, Optional[str]]] = {}
    rows = table.find_all("tr")

    for row in rows:
        cells = [c.get_text(separator=" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 2:
            continue

        cat_raw = cells[0].strip()
        # Skip header rows
        if not cat_raw or re.search(r"(?i)(family|employ|chargeability|based)", cat_raw):
            continue
        # Normalise the category key
        cat = _normalise_category(cat_raw)
        if cat is None:
            continue

        row_data: dict[str, Optional[str]] = {}
        for col_idx, key in COUNTRY_COLS.items():
            if col_idx < len(cells):
                row_data[key] = parse_bulletin_date(cells[col_idx])
            else:
                row_data[key] = None

        result[cat] = row_data

    return result


def _normalise_category(raw: str) -> Optional[str]:
    """Map raw row label to a canonical category key."""
    raw_up = raw.upper().strip()

    # Family
    if re.match(r"^F1\b", raw_up):   return "F1"
    if re.match(r"^F2A\b", raw_up):  return "F2A"
    if re.match(r"^F2B\b", raw_up):  return "F2B"
    if re.match(r"^F3\b", raw_up):   return "F3"
    if re.match(r"^F4\b", raw_up):   return "F4"

    # Employment numbered rows
    if re.match(r"^1ST\b|^1\b", raw_up):  return "EB1"
    if re.match(r"^2ND\b|^2\b", raw_up):  return "EB2"
    if re.match(r"^3RD\b|^3\b", raw_up):  return "EB3"
    if "OTHER WORKER" in raw_up:           return "EB3_OTHER"
    if re.match(r"^4TH\b|^4\b", raw_up):  return "EB4"
    if "RELIGIOUS" in raw_up:             return "EB4_RELIGIOUS"

    # EB-5 variants
    if "RURAL" in raw_up:        return "EB5_RURAL"
    if "HIGH UNEMPLOY" in raw_up: return "EB5_HIGH_UNEMP"
    if "INFRA" in raw_up:        return "EB5_INFRA"
    if re.match(r"^5TH\b|^5\b", raw_up):  return "EB5_UNRESERVED"

    return None


# ──────────────────────────────────────────────────────────────────────────────
# DV table parser
# ──────────────────────────────────────────────────────────────────────────────

def parse_dv_table(table: Tag) -> dict:
    """
    Parse a Diversity Visa table into:
        {
          "AFRICA": {"cutoff": 45000, "exceptions": {"Algeria": 37000, "Egypt": 22250}},
          ...
        }
    """
    result: dict[str, dict] = {}
    REGION_MAP = {
        "AFRICA": "AFRICA",
        "ASIA": "ASIA",
        "EUROPE": "EUROPE",
        "NORTH AMERICA": "NORTH_AMERICA",
        "OCEANIA": "OCEANIA",
        "SOUTH AMERICA": "SOUTH_AMERICA",
    }

    rows = table.find_all("tr")
    for row in rows:
        cells = [c.get_text(separator=" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 2:
            continue

        region_raw = cells[0].strip().upper()
        region_key = None
        for pattern, key in REGION_MAP.items():
            if pattern in region_raw:
                region_key = key
                break
        if region_key is None:
            continue

        # Cutoff in column 1
        cutoff_raw = re.sub(r"[^\d]", "", cells[1])
        cutoff = int(cutoff_raw) if cutoff_raw else 0

        # Exceptions in column 2 (if present)
        exceptions: dict[str, int] = {}
        exc_text = cells[2] if len(cells) > 2 else ""
        # e.g. "Except: Algeria 37,000 Egypt 22,250"
        exc_clean = re.sub(r"(?i)except\s*:?", "", exc_text)
        pairs = re.findall(r"([A-Za-z][A-Za-z\s]{2,20?})\s+([\d,]+)", exc_clean)
        for country, num in pairs:
            country_clean = country.strip().title()
            if country_clean:
                exceptions[country_clean] = int(num.replace(",", ""))

        result[region_key] = {"cutoff": cutoff, "exceptions": exceptions}

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Main parser class
# ──────────────────────────────────────────────────────────────────────────────

class BulletinParser:

    @staticmethod
    def bulletin_url(year: int, month: int) -> str:
        month_name = MONTHS_EN[month - 1]
        return f"{BASE_URL}/{year}/visa-bulletin-for-{month_name}-{year}.html"

    @staticmethod
    def fetch_html(year: int, month: int, timeout: int = 20) -> str:
        url = BulletinParser.bulletin_url(year, month)
        log.info("Fetching %s", url)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; VisaBulletinBot/1.0; "
                "+https://github.com/yourusername/visa-bulletin)"
            )
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.text

    @staticmethod
    def parse_html(html: str, year: int, month: int) -> dict:
        soup = BeautifulSoup(html, "lxml")

        # ── Metadata ────────────────────────────────────────────────────────
        title_tag = soup.find("h1", string=re.compile(r"Visa Bulletin", re.I))
        title = title_tag.get_text(strip=True) if title_tag else f"Visa Bulletin {MONTHS_EN[month-1].title()} {year}"

        # Volume / Number from italic tag
        volume = number = published = ""
        for em in soup.find_all("em"):
            text = em.get_text(" ", strip=True)
            v = re.search(r"Number\s+(\d+)", text)
            n = re.search(r"Volume\s+(\w+)", text, re.I)
            if v: number = v.group(1)
            if n: volume = n.group(1)

        # Published date from "CA/VO: Month DD, YYYY" pattern
        body_text = soup.get_text(" ")
        pub_m = re.search(r"CA/VO\s*:\s*([A-Za-z]+ \d+,\s*\d{4})", body_text)
        if pub_m:
            published = pub_m.group(1).strip()

        # ── All tables in document order ─────────────────────────────────────
        tables = soup.find_all("table")

        # We identify tables by their header row content
        fam_final = fam_filing = emp_final = emp_filing = None
        dv_current = dv_next = None

        # Strategy: scan tables sequentially, identify by preceding heading text
        # and/or header row contents.
        section_context = ""
        for tag in soup.find_all(["h2", "h3", "h4", "p", "b", "strong", "table"]):
            if tag.name != "table":
                txt = tag.get_text(" ", strip=True).upper()
                if "FINAL ACTION" in txt and "FAMILY" in txt:
                    section_context = "FAM_FINAL"
                elif "DATES FOR FILING" in txt and "FAMILY" in txt:
                    section_context = "FAM_FILING"
                elif "FINAL ACTION" in txt and "EMPLOY" in txt:
                    section_context = "EMP_FINAL"
                elif "DATES FOR FILING" in txt and "EMPLOY" in txt:
                    section_context = "EMP_FILING"
                elif "DIVERSITY" in txt and ("MARCH" in txt or "CURRENT" in txt or "FOR THE MONTH" in txt):
                    section_context = "DV_CURRENT"
                elif "DIVERSITY" in txt and ("APRIL" in txt or "NEXT" in txt or "RANK CUT" in txt):
                    section_context = "DV_NEXT"
                continue

            # It's a table — check its own header for context too
            header_txt = ""
            first_row = tag.find("tr")
            if first_row:
                header_txt = first_row.get_text(" ", strip=True).upper()

            # Classify by header cell content
            is_family = bool(re.search(r"F1|F2|F3|F4|FAMILY", header_txt))
            is_employ = bool(re.search(r"1ST|2ND|3RD|EB|EMPLOY|OTHER WORK", header_txt))
            is_dv = bool(re.search(r"AFRICA|ASIA|EUROPE|OCEANIA|REGION", header_txt))

            if is_dv:
                if section_context == "DV_NEXT" or dv_current is not None:
                    if dv_next is None:
                        dv_next = parse_dv_table(tag)
                else:
                    dv_current = parse_dv_table(tag)
                continue

            if is_family or "FAMILY" in section_context:
                parsed = parse_preference_table(tag)
                if parsed:
                    if section_context == "FAM_FILING" and fam_filing is None:
                        fam_filing = parsed
                    elif fam_final is None:
                        fam_final = parsed
                continue

            if is_employ or "EMP" in section_context:
                parsed = parse_preference_table(tag)
                if parsed:
                    if section_context == "EMP_FILING" and emp_filing is None:
                        emp_filing = parsed
                    elif emp_final is None:
                        emp_final = parsed
                continue

        # ── Admin notices (section D onwards) ────────────────────────────────
        admin_notices: list[str] = []
        # Look for bold section headers like "D.", "E.", "F." and capture their paragraph
        for tag in soup.find_all(["b", "strong"]):
            txt = tag.get_text(strip=True)
            if re.match(r"^[D-G]\.", txt):
                # Grab the parent paragraph
                parent = tag.find_parent(["p", "div"])
                if parent:
                    notice = parent.get_text(" ", strip=True)
                    if len(notice) > 30:
                        admin_notices.append(notice)

        return {
            "meta": {
                "title": title,
                "month": MONTHS_EN[month - 1].title(),
                "month_num": month,
                "year": year,
                "volume": volume,
                "number": number,
                "published": published,
                "url": BulletinParser.bulletin_url(year, month),
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            },
            "employment_final": emp_final or {},
            "employment_filing": emp_filing or {},
            "family_final": fam_final or {},
            "family_filing": fam_filing or {},
            "dv_current": dv_current or {},
            "dv_next": dv_next or {},
            "admin_notices": admin_notices,
        }

    @staticmethod
    def fetch_and_parse(year: int, month: int) -> dict:
        html = BulletinParser.fetch_html(year, month)
        return BulletinParser.parse_html(html, year, month)

    @staticmethod
    def parse_file(path: str | Path, year: int, month: int) -> dict:
        html = Path(path).read_text(encoding="utf-8")
        return BulletinParser.parse_html(html, year, month)
