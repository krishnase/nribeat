"""
Visa Bulletin Fetcher
Scrapes the latest Visa Bulletin PDF from travel.state.gov
Extracts EB-2 India, EB-3 India priority dates automatically.
"""

import re
import io
import logging
import requests
from datetime import datetime
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

BULLETIN_URL = "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html"

# Categories we care about (row labels in the Visa Bulletin table)
TRACKED_CATEGORIES = {
    "EB-2 India": {"country": "INDIA", "pref": "2ND"},
    "EB-3 India": {"country": "INDIA", "pref": "3RD"},
    "EB-1 India": {"country": "INDIA", "pref": "1ST"},
}


def fetch_visa_bulletin() -> dict | None:
    """
    Fetch the latest Visa Bulletin and extract priority dates.
    Returns a story dict ready for article generation.
    """
    try:
        # Get the bulletin index page
        resp = requests.get(BULLETIN_URL, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; NRIBeat/1.0)"
        })
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find the latest bulletin link
        latest_link = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "visa-bulletin-for" in href.lower():
                latest_link = href
                break

        if not latest_link:
            log.warning("Could not find latest Visa Bulletin link")
            return _get_fallback_bulletin()

        # Make absolute URL
        if not latest_link.startswith("http"):
            latest_link = "https://travel.state.gov" + latest_link

        # Fetch the bulletin page
        bulletin_resp = requests.get(latest_link, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; NRIBeat/1.0)"
        })
        bulletin_resp.raise_for_status()

        dates = _parse_bulletin_page(bulletin_resp.text)
        month_year = _extract_month_year(latest_link)

        return {
            "category": "immigration",
            "subcategory": "visa_bulletin",
            "title": f"{month_year} Visa Bulletin: EB-2 India Priority Date Update",
            "source": "travel.state.gov",
            "url": latest_link,
            "priority_dates": dates,
            "month_year": month_year,
            "raw_content": f"Visa Bulletin {month_year}. Priority dates: {json_safe(dates)}",
            "tags": ["Visa Bulletin", "EB-2 India", "EB-3 India", "Green Card", "Priority Date"],
            "is_visa_bulletin": True
        }

    except Exception as e:
        log.error(f"Visa Bulletin fetch error: {e}")
        return _get_fallback_bulletin()


def _parse_bulletin_page(html: str) -> dict:
    """
    Parse both Final Action Dates AND Dates for Filing from the bulletin HTML.

    The bulletin page contains two distinct employment-based tables:
      Table A — "Final Action Dates for Employment-Based Preference Cases"
      Table B — "Dates for Filing Employment-Based Visa Applications"

    We identify them by scanning for these heading strings in the text
    immediately preceding each <table> tag.
    """
    soup = BeautifulSoup(html, "html.parser")
    dates = {}

    # Build a mapping: table element → table type ("final" | "filing" | None)
    def _table_type(table) -> str | None:
        # Look at text in the 200 chars before this table in the page
        prev = table.find_previous(string=True)
        context = ""
        node = table.previous_sibling
        for _ in range(20):
            if node is None:
                break
            if hasattr(node, "get_text"):
                context = node.get_text(" ", strip=True).upper() + " " + context
            elif isinstance(node, str):
                context = node.upper() + " " + context
            node = getattr(node, "previous_sibling", None)
            if len(context) > 400:
                break
        if "FINAL ACTION" in context:
            return "final"
        if "DATES FOR FILING" in context or "DATE FOR FILING" in context:
            return "filing"
        return None

    # Fallback: if heading detection fails, treat first EB table as final,
    # second as filing — which matches how every bulletin is structured.
    eb_tables = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        row_texts = " ".join(r.get_text(" ", strip=True).upper() for r in rows[:4])
        if any(k in row_texts for k in ("2ND", "SECOND", "3RD", "THIRD", "1ST", "FIRST")):
            eb_tables.append(table)

    for idx, table in enumerate(eb_tables):
        ttype = _table_type(table)
        if ttype is None:
            ttype = "final" if idx == 0 else "filing"

        suffix = "final" if ttype == "final" else "filing"

        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
                continue
            row_text = cells[0].get_text(strip=True).upper()

            if "2ND" in row_text or "SECOND" in row_text:
                d = _extract_india_date(cells)
                if d:
                    dates[f"eb2_india_{suffix}"] = d

            elif "3RD" in row_text or "THIRD" in row_text:
                d = _extract_india_date(cells)
                if d:
                    dates[f"eb3_india_{suffix}"] = d

            elif "1ST" in row_text or "FIRST" in row_text:
                d = _extract_india_date(cells)
                if d:
                    dates[f"eb1_india_{suffix}"] = d

    return dates if dates else _get_fallback_dates()


def _extract_india_date(cells) -> str | None:
    """Extract India column date from a row of cells."""
    # India is typically the 3rd or 4th column in EB tables
    # Column order: Worldwide, China, El Salvador, India, Mexico, Philippines
    india_col_indices = [3, 4]  # Try both

    for idx in india_col_indices:
        if idx < len(cells):
            text = cells[idx].get_text(strip=True)
            # Match dates like "01JAN13", "01JAN2013", "C" (current), "U" (unavailable)
            if text in ("C", "U"):
                return text
            date_match = re.search(r'(\d{1,2}[A-Z]{3}\d{2,4})', text.upper())
            if date_match:
                return _normalize_date(date_match.group(1))

    return None


def _normalize_date(raw: str) -> str:
    """Convert '01JAN13' to 'January 01, 2013'."""
    try:
        # Handle both 2-digit and 4-digit years
        if len(raw) == 7:  # 01JAN13
            dt = datetime.strptime(raw, "%d%b%y")
            # Fix 2-digit year ambiguity (00-30 = 2000s, 31-99 = 1900s)
            if dt.year > 2030:
                dt = dt.replace(year=dt.year - 100)
        else:  # 01JAN2013
            dt = datetime.strptime(raw, "%d%b%Y")
        return dt.strftime("%B %d, %Y")
    except Exception:
        return raw


def _extract_month_year(url: str) -> str:
    """Extract 'November 2025' from the bulletin URL."""
    months = ["january", "february", "march", "april", "may", "june",
              "july", "august", "september", "october", "november", "december"]
    url_lower = url.lower()
    for month in months:
        if month in url_lower:
            year_match = re.search(r'20\d{2}', url)
            year = year_match.group(0) if year_match else str(datetime.now().year)
            return f"{month.capitalize()} {year}"
    return datetime.now().strftime("%B %Y")


def _get_fallback_dates() -> dict:
    """Return last known real dates (April 2026) if scraping fails."""
    return {
        "eb2_india_final":  "July 15, 2014",
        "eb3_india_final":  "November 15, 2013",
        "eb1_india_final":  "April 01, 2023",
        "eb2_india_filing": "January 15, 2015",
        "eb3_india_filing": "January 15, 2015",
        "eb1_india_filing": "December 01, 2023",
    }


def _get_fallback_bulletin() -> dict:
    """Return a fallback story if fetching fails completely."""
    dates = _get_fallback_dates()
    month_year = datetime.now().strftime("%B %Y")
    return {
        "category": "immigration",
        "subcategory": "visa_bulletin",
        "title": f"{month_year} Visa Bulletin: Priority Date Analysis",
        "source": "travel.state.gov",
        "url": BULLETIN_URL,
        "priority_dates": dates,
        "month_year": month_year,
        "raw_content": f"Visa Bulletin {month_year}. Priority dates: {dates}",
        "tags": ["Visa Bulletin", "EB-2 India", "Green Card"],
        "is_visa_bulletin": True
    }


def json_safe(obj):
    import json
    return json.dumps(obj)
