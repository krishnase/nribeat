from __future__ import annotations
"""
Google Trends Fetcher
Discovers what the NRI audience is actively searching for — zero API cost.
Uses pytrends (unofficial Google Trends API wrapper).

Strategy: fetch trending keywords per category, return them as seed topics
so the article generator can target real search demand instead of guessing.
"""

import logging
import time
from datetime import datetime

log = logging.getLogger(__name__)

# Topics to probe — mapped to our content categories
TREND_PROBES = {
    "immigration": [
        "H1B visa 2025",
        "visa bulletin EB2 India",
        "green card priority date",
        "OPT STEM extension",
        "USCIS processing time",
        "H1B transfer new job",
        "I-485 filing",
        "H1B layoff grace period",
    ],
    "ai_tech": [
        "AI tools for developers",
        "ChatGPT alternatives",
        "software engineer AI job market",
        "tech layoffs 2025",
        "machine learning salary",
        "OpenAI Claude Gemini comparison",
    ],
    "cricket": [
        "India cricket score",
        "IPL 2025",
        "India vs Australia test",
        "Rohit Sharma Virat Kohli",
        "ICC World Cup 2025",
    ],
    "movies": [
        "new Bollywood movies 2025",
        "Netflix India originals",
        "Hotstar new releases",
        "Prime Video India shows",
        "Hindi movies OTT this week",
    ],
    "layoffs": [
        "tech layoffs 2025",
        "Google layoffs",
        "Meta layoffs H1B",
        "Amazon Microsoft layoffs",
        "software engineer jobs market",
    ],
}

# Geo targeting — US (our primary audience)
GEO = "US"

# Timeframe — last 7 days for freshness
TIMEFRAME = "now 7-d"


def fetch_trending_topics() -> dict:
    """
    Fetch trending search interest for each NRIBeat category.
    Returns dict: {category: [{"keyword": str, "interest": int, "rising": bool}]}

    Falls back to curated high-value keywords if pytrends is unavailable
    or rate-limited.
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        log.warning("pytrends not installed — using curated fallback keywords")
        return _get_fallback_trends()

    pytrends = TrendReq(hl="en-US", tz=300, timeout=(10, 25))
    results = {}

    for category, keywords in TREND_PROBES.items():
        try:
            trending = _fetch_category_trends(pytrends, category, keywords)
            results[category] = trending
            log.info(f"  Trends [{category}]: {len(trending)} keywords fetched")
            time.sleep(2)  # Respect rate limits — 2s between requests
        except Exception as e:
            log.warning(f"  Trends [{category}] failed: {e} — using fallback")
            results[category] = _get_fallback_for_category(category)

    return results


def _fetch_category_trends(pytrends, category: str, keywords: list) -> list:
    """Fetch interest-over-time for a batch of keywords."""
    # pytrends max 5 keywords per request
    batch = keywords[:5]

    pytrends.build_payload(
        kw_list=batch,
        cat=0,
        timeframe=TIMEFRAME,
        geo=GEO,
    )

    df = pytrends.interest_over_time()
    if df is None or df.empty:
        return _get_fallback_for_category(category)

    # Aggregate interest score per keyword (mean over the period)
    trend_data = []
    for kw in batch:
        if kw in df.columns:
            avg_interest = int(df[kw].mean())
            trend_data.append({
                "keyword": kw,
                "interest": avg_interest,
                "category": category,
                "rising": bool(df[kw].iloc[-1] > df[kw].mean()),
            })

    # Sort by interest descending
    trend_data.sort(key=lambda x: x["interest"], reverse=True)
    return trend_data


def get_top_keywords_for_category(trends: dict, category: str, n: int = 3) -> list[str]:
    """
    Get the top N trending keywords for a category.
    Used to enrich article generation prompts.
    """
    cat_trends = trends.get(category, [])
    return [t["keyword"] for t in cat_trends[:n]]


def get_rising_topics(trends: dict) -> list[dict]:
    """
    Return all rising (accelerating) topics across categories.
    These are the highest-opportunity content targets.
    """
    rising = []
    for category, items in trends.items():
        for item in items:
            if item.get("rising"):
                rising.append(item)
    rising.sort(key=lambda x: x["interest"], reverse=True)
    return rising


def _get_fallback_for_category(category: str) -> list:
    """High-value curated keywords when trends API is unavailable."""
    fallbacks = {
        "immigration": [
            {"keyword": "H1B visa 2025 lottery results", "interest": 85, "category": "immigration", "rising": True},
            {"keyword": "visa bulletin EB2 India priority date", "interest": 78, "category": "immigration", "rising": False},
            {"keyword": "green card processing time 2025", "interest": 72, "category": "immigration", "rising": True},
            {"keyword": "OPT STEM extension approval rate", "interest": 65, "category": "immigration", "rising": False},
        ],
        "ai_tech": [
            {"keyword": "best AI coding tools 2025", "interest": 90, "category": "ai_tech", "rising": True},
            {"keyword": "software engineer AI impact salary", "interest": 82, "category": "ai_tech", "rising": True},
            {"keyword": "ChatGPT vs Claude vs Gemini", "interest": 76, "category": "ai_tech", "rising": False},
            {"keyword": "tech layoffs H1B visa impact", "interest": 70, "category": "ai_tech", "rising": False},
        ],
        "cricket": [
            {"keyword": "India cricket live score", "interest": 88, "category": "cricket", "rising": True},
            {"keyword": "IPL 2025 schedule results", "interest": 85, "category": "cricket", "rising": True},
            {"keyword": "ICC Champions Trophy 2025", "interest": 72, "category": "cricket", "rising": False},
        ],
        "movies": [
            {"keyword": "new Bollywood OTT releases this week", "interest": 80, "category": "movies", "rising": True},
            {"keyword": "Netflix India new movies 2025", "interest": 75, "category": "movies", "rising": False},
            {"keyword": "Hotstar US Indian content", "interest": 68, "category": "movies", "rising": False},
        ],
        "layoffs": [
            {"keyword": "tech layoffs 2025 H1B impact", "interest": 82, "category": "layoffs", "rising": True},
            {"keyword": "Google Amazon Microsoft layoffs", "interest": 78, "category": "layoffs", "rising": False},
            {"keyword": "software engineer job market 2025", "interest": 70, "category": "layoffs", "rising": True},
        ],
    }
    return fallbacks.get(category, [])


def _get_fallback_trends() -> dict:
    """Return all fallback trends when pytrends is completely unavailable."""
    return {cat: _get_fallback_for_category(cat) for cat in TREND_PROBES}
