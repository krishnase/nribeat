"""
Cricket News Fetcher
Uses free RSS feeds from ESPN Cricinfo and CricBuzz.
No API key needed.
"""

import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

log = logging.getLogger(__name__)

CRICKET_RSS_FEEDS = [
    "https://www.espncricinfo.com/rss/content/story/feeds/0.xml",
    "https://cricbuzz-cricket.p.rapidapi.com/news/v1/index",  # RapidAPI backup
]

# Focus on India-related cricket
INDIA_KEYWORDS = [
    "india", "ipl", "bcci", "kohli", "rohit", "bumrah", "hardik",
    "shubman", "siraj", "jadeja", "dhoni", "icc", "test match",
    "odi", "t20", "wpl", "world cup", "cricket"
]


def fetch_cricket_news() -> list[dict]:
    """Fetch latest cricket news from RSS feeds."""
    stories = []

    # Primary: ESPN Cricinfo RSS
    try:
        resp = requests.get(
            "https://www.espncricinfo.com/rss/content/story/feeds/0.xml",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; NRIBeat/1.0)"}
        )
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        items = root.findall(".//item")

        for item in items[:10]:
            title = item.findtext("title", "").strip()
            desc = item.findtext("description", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "")

            if _is_india_related(title + " " + desc):
                stories.append({
                    "category": "cricket",
                    "title": title,
                    "raw_content": f"{title}. {_clean_html(desc)}",
                    "source": "ESPN Cricinfo",
                    "url": link,
                    "published_at": pub_date,
                    "tags": _extract_cricket_tags(title),
                })

        log.info(f"  Cricket: {len(stories)} India-related stories from ESPN Cricinfo")

    except Exception as e:
        log.error(f"ESPN Cricinfo RSS error: {e}")

    # Backup: Cricbuzz via another RSS
    if not stories:
        try:
            resp = requests.get(
                "https://feeds.feedburner.com/ndtvnews-sports-news",
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0 (compatible; NRIBeat/1.0)"}
            )
            resp.raise_for_status()

            root = ET.fromstring(resp.content)
            items = root.findall(".//item")

            for item in items[:10]:
                title = item.findtext("title", "").strip()
                desc = item.findtext("description", "").strip()
                link = item.findtext("link", "").strip()

                if _is_india_related(title + " " + desc) and "cricket" in (title + desc).lower():
                    stories.append({
                        "category": "cricket",
                        "title": title,
                        "raw_content": f"{title}. {_clean_html(desc)}",
                        "source": "NDTV Sports",
                        "url": link,
                        "published_at": datetime.now().isoformat(),
                        "tags": _extract_cricket_tags(title),
                    })

        except Exception as e:
            log.error(f"Backup cricket RSS error: {e}")

    return stories[:3]  # Max 3 cricket stories per day


def _is_india_related(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in INDIA_KEYWORDS)


def _extract_cricket_tags(title: str) -> list[str]:
    tags = ["Cricket"]
    title_lower = title.lower()
    tag_map = {
        "ipl": "IPL", "test": "Test Cricket", "odi": "ODI",
        "t20": "T20", "wpl": "WPL", "world cup": "World Cup",
        "kohli": "Kohli", "rohit": "Rohit Sharma", "bumrah": "Bumrah",
        "auction": "IPL Auction", "bcci": "BCCI", "icc": "ICC",
    }
    for kw, tag in tag_map.items():
        if kw in title_lower:
            tags.append(tag)
    return tags[:4]


def _clean_html(text: str) -> str:
    import re
    return re.sub(r'<[^>]+>', '', text).strip()[:400]
