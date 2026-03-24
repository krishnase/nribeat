"""
Movies & OTT News Fetcher
- fetch_ott_news():          Bollywood/OTT RSS news for article generation
- fetch_theatrical_releases(): Scrapes Wikipedia for Telugu/Hindi/Tamil
                               releases in the ±7-day window → movies-releases.json
"""

from __future__ import annotations
import re
import time
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, date

try:
    from bs4 import BeautifulSoup
    _BS4 = True
except ImportError:
    _BS4 = False

log = logging.getLogger(__name__)

# ── RSS feeds for OTT/Bollywood news ────────────────────────────────────────
OTT_RSS_FEEDS = [
    "https://www.bollywoodhungama.com/rss/news.xml",
    "https://timesofindia.indiatimes.com/rss/4719148.cms",
    "https://www.pinkvilla.com/feed",
]

BOLLYWOOD_KEYWORDS = [
    "bollywood", "netflix india", "amazon prime india", "hotstar",
    "disney+", "hindi film", "hindi series", "ott release",
    "box office", "trailer", "teaser", "first look", "release date",
    "shah rukh", "salman", "deepika", "ranveer", "alia", "ranbir",
    "hrithik", "akshay", "katrina", "kareena", "priyanka",
    "stree", "singham", "pushpa", "jawan", "pathaan", "animal",
    "kalki", "devara", "season 2", "season 3", "web series"
]

# ── Popular cast/director keywords for "notable film" filter ────────────────
_POPULAR = {
    # Telugu
    "prabhas", "allu arjun", "ram charan", "jr. ntr", "jr ntr",
    "mahesh babu", "pawan kalyan", "vijay deverakonda", "nani",
    "dulquer salmaan", "rana daggubati", "venkatesh", "balakrishna",
    "chiranjeevi", "ravi teja", "nagarjuna", "samantha", "rashmika",
    "pooja hegde", "sai pallavi",
    # Tamil
    "rajinikanth", "kamal haasan", "vijay", "ajith kumar", "suriya",
    "dhanush", "vikram", "sivakarthikeyan", "karthi", "vijay sethupathi",
    "nayanthara", "trisha", "shruti haasan", "fahadh faasil",
    # Hindi
    "shah rukh", "salman khan", "aamir khan", "hrithik roshan",
    "ranveer singh", "ranbir kapoor", "akshay kumar", "tiger shroff",
    "vicky kaushal", "ayushmann", "kartik aaryan", "shahid kapoor",
    "deepika padukone", "alia bhatt", "katrina kaif", "kareena kapoor",
    # Malayalam crossover
    "mohanlal", "mammootty",
    # Directors
    "rajamouli", "lokesh kanagaraj", "atlee", "shankar", "sukumar",
    "koratala siva", "trivikram", "buchi babu", "rohit shetty",
    "karthik subbaraj", "prashanth neel", "raj & dk",
}

_UA = {"User-Agent": "Mozilla/5.0 (compatible; NRIBeat/1.0)"}


# ── fetch_theatrical_releases ────────────────────────────────────────────────

def fetch_theatrical_releases() -> dict:
    """
    Scrape Wikipedia film lists for Telugu, Hindi, Tamil.
    Returns {"updated":..., "now_playing":[...], "coming_soon":[...]}
    suitable for writing directly to data/movies-releases.json.
    """
    if not _BS4:
        log.warning("  bs4 not installed — theatrical releases skipped")
        return {"updated": date.today().isoformat(), "now_playing": [], "coming_soon": []}

    today = date.today()
    window_start = today - timedelta(days=7)
    window_end   = today + timedelta(days=10)
    year = today.year

    sources = [
        ("Telugu", f"https://en.wikipedia.org/wiki/List_of_Telugu_films_of_{year}"),
        ("Hindi",  f"https://en.wikipedia.org/wiki/List_of_Hindi_films_of_{year}"),
        ("Tamil",  f"https://en.wikipedia.org/wiki/List_of_Tamil_films_of_{year}"),
    ]

    all_films: list[dict] = []
    for lang, url in sources:
        try:
            films = _scrape_wiki_films(url, lang, year)
            log.info(f"  Wikipedia {lang}: {len(films)} candidate films")
            all_films.extend(films)
        except Exception as e:
            log.error(f"  Wikipedia {lang} failed: {e}")
        time.sleep(0.8)

    # Deduplicate by title (same film in multiple tables)
    seen: set[str] = set()
    unique: list[dict] = []
    for f in all_films:
        key = f["title"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(f)

    now_playing = sorted(
        [f for f in unique if window_start <= f["_date"] <= today],
        key=lambda x: (not x["_popular"], x["_date"]),   # popular first, then by date
    )
    coming_soon = sorted(
        [f for f in unique if today < f["_date"] <= window_end],
        key=lambda x: (not x["_popular"], x["_date"]),   # popular first, then soonest
    )

    log.info(f"  Theatrical: {len(now_playing)} now playing, {len(coming_soon)} coming soon")

    def _export(films: list, limit: int = 6) -> list:
        out = []
        for f in films[:limit]:
            out.append({k: v for k, v in f.items() if not k.startswith("_")})
        return out

    return {
        "updated": today.isoformat(),
        "note": "Auto-fetched from Wikipedia. Popular Telugu/Hindi/Tamil theatrical releases.",
        "now_playing": _export(now_playing),
        "coming_soon": _export(coming_soon),
    }


def _scrape_wiki_films(url: str, language: str, year: int) -> list[dict]:
    resp = requests.get(url, timeout=15, headers=_UA)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "html.parser")

    content = soup.find(class_="mw-parser-output")
    if not content:
        return []

    films: list[dict] = []
    current_section_month: date | None = None

    for child in content.children:
        if not hasattr(child, "name") or not child.name:
            continue
        if child.name in ("h2", "h3"):
            current_section_month = _section_month(child.get_text(), year)
        elif child.name == "table" and "wikitable" in " ".join(child.get("class", [])):
            films.extend(_parse_table(child, language, current_section_month, year))

    return films


def _parse_table(table, language: str, section_month: date | None, year: int) -> list[dict]:
    rows = table.find_all("tr")
    if len(rows) < 2:
        return []

    # Identify columns from header row
    hcells  = rows[0].find_all(["th", "td"])
    headers = [c.get_text(strip=True).lower() for c in hcells]

    title_idx = _col(headers, ["title", "film", "name"])
    dir_idx   = _col(headers, ["director"])
    cast_idx  = _col(headers, ["cast", "starring", "star cast"])
    date_idx  = _col(headers, ["release", "date", "released"])

    if title_idx is None:
        title_idx = 0   # fallback: first column

    films: list[dict] = []
    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        texts = [_cell_text(c) for c in cells]
        if len(texts) < 2:
            continue

        # Title
        ti = min(title_idx, len(texts) - 1)
        title = texts[ti].strip("*# ").strip()
        if not title or title.isdigit() or len(title) < 2:
            continue

        director = texts[dir_idx].strip()  if dir_idx  is not None and dir_idx  < len(texts) else ""
        cast     = texts[cast_idx].strip() if cast_idx is not None and cast_idx < len(texts) else ""

        # Popularity / notability check
        combined   = (title + " " + cast + " " + director).lower()
        is_popular = any(k in combined for k in _POPULAR)
        # Title has its own Wikipedia article = notable
        title_cell  = cells[ti]
        has_article = bool(title_cell.find(
            "a", href=lambda h: h and h.startswith("/wiki/") and ":" not in h
        ))

        if not is_popular and not has_article:
            continue

        # Release date — try dedicated column first, then any cell, then section month
        release: date | None = None
        if date_idx is not None and date_idx < len(texts):
            release = _parse_date(texts[date_idx], year)
        if release is None:
            for t in texts:
                release = _parse_date(t, year)
                if release:
                    break
        if release is None and section_month:
            release = section_month
        if release is None:
            continue

        genre = _genre_from(texts)
        today = date.today()
        days_since = (today - release).days

        films.append({
            "title":            title,
            "language":         language,
            "also_in":          [],
            "genre":            genre or "—",
            "cast":             (cast or "—")[:120],
            "director":         director or "—",
            "release_date":     _fmt_date(release),
            "release_date_iso": release.isoformat(),
            "buzz":             "High" if is_popular else "Medium",
            "desc":             _auto_desc(title, language, genre, director, cast, release),
            # for now_playing only
            "verdict":          "Now Playing",
            "verdict_class":    "hit",
            "weeks_running":    max(1, days_since // 7) if days_since >= 0 else 0,
            "collection_india": "",   # not available from Wikipedia
            # internal sort keys — stripped before export
            "_date":    release,
            "_popular": is_popular,
        })

    return films


# ── helpers ──────────────────────────────────────────────────────────────────

def _col(headers: list[str], keywords: list[str]) -> int | None:
    for kw in keywords:
        for i, h in enumerate(headers):
            if kw in h:
                return i
    return None


def _cell_text(cell) -> str:
    for sup in cell.find_all("sup"):
        sup.decompose()
    text = cell.get_text(separator=", ", strip=True)
    text = re.sub(r'\[.*?\]', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def _section_month(heading: str, year: int) -> date | None:
    MONTHS = ["january","february","march","april","may","june",
              "july","august","september","october","november","december"]
    h = heading.lower()
    for i, m in enumerate(MONTHS):
        if m in h:
            return date(year, i + 1, 1)
    return None


def _parse_date(text: str, fallback_year: int) -> date | None:
    text = re.sub(r'\[.*?\]', '', text).strip()
    text = re.sub(r'\s+', ' ', text)
    if not text or text.upper() in ("TBA", "TBD", "—", "-", "N/A"):
        return None
    for fmt in ("%d %B %Y", "%B %d, %Y", "%d %b %Y", "%b %d, %Y",
                "%Y-%m-%d", "%d/%m/%Y",
                "%d %B", "%B %d", "%d %b", "%b %d"):
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.year == 1900:
                parsed = parsed.replace(year=fallback_year)
            return parsed.date()
        except ValueError:
            pass
    return None


def _fmt_date(d: date) -> str:
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def _genre_from(texts: list[str]) -> str:
    GENRES = ["action", "drama", "comedy", "thriller", "romance", "horror",
              "fantasy", "biography", "historical", "period", "crime", "sports"]
    for text in texts:
        t = text.lower()
        for g in GENRES:
            if g in t:
                return g.title()
    return ""


def _auto_desc(title: str, lang: str, genre: str, director: str, cast: str, rel: date) -> str:
    lead = cast.split(",")[0].strip() if cast and cast != "—" else ""
    parts = [f"{title} is a {lang}{' ' + genre if genre and genre != '—' else ''} film."]
    if lead:
        parts.append(f"Starring {lead}.")
    if director and director != "—":
        parts.append(f"Directed by {director}.")
    return " ".join(parts)


# ── fetch_ott_news (unchanged) ───────────────────────────────────────────────

def fetch_ott_news() -> list[dict]:
    """Fetch Bollywood and OTT news from RSS feeds."""
    stories = []

    for feed_url in OTT_RSS_FEEDS:
        if len(stories) >= 4:
            break
        try:
            resp = requests.get(feed_url, timeout=10, headers=_UA)
            resp.raise_for_status()
            root  = ET.fromstring(resp.content)
            items = root.findall(".//item")

            for item in items[:8]:
                title    = item.findtext("title", "").strip()
                desc     = item.findtext("description", "").strip()
                link     = item.findtext("link", "").strip()
                pub_date = item.findtext("pubDate", "")

                if _is_bollywood_relevant(title + " " + desc):
                    stories.append({
                        "category":    "movies",
                        "title":       title,
                        "raw_content": f"{title}. {_clean_html(desc)}",
                        "source":      _source_from_url(feed_url),
                        "url":         link,
                        "published_at": pub_date,
                        "tags":        _extract_movie_tags(title),
                    })

        except Exception as e:
            log.error(f"OTT RSS error for {feed_url}: {e}")

    return stories[:2]


def _is_bollywood_relevant(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in BOLLYWOOD_KEYWORDS)


def _extract_movie_tags(title: str) -> list[str]:
    tags = []
    title_lower = title.lower()
    tag_map = {
        "netflix": "Netflix", "prime": "Amazon Prime", "hotstar": "Hotstar",
        "ott": "OTT", "box office": "Box Office", "review": "Review",
        "trailer": "Trailer", "release": "Release", "bollywood": "Bollywood",
        "hindi": "Bollywood", "season": "Web Series",
    }
    for kw, tag in tag_map.items():
        if kw in title_lower and tag not in tags:
            tags.append(tag)
    return tags[:4] or ["Movies & OTT"]


def _source_from_url(url: str) -> str:
    domain_map = {
        "bollywoodhungama": "Bollywood Hungama",
        "timesofindia":     "Times of India",
        "pinkvilla":        "PinkVilla",
    }
    for key, name in domain_map.items():
        if key in url:
            return name
    return url.split("/")[2]


def _clean_html(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text).strip()[:400]
