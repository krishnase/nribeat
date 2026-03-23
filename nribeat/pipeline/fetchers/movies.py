"""
Movies & OTT News Fetcher
Fetches Bollywood and Indian OTT release news via RSS feeds.
No API key needed.
"""

import re
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

log = logging.getLogger(__name__)

OTT_RSS_FEEDS = [
    "https://www.bollywoodhungama.com/rss/news.xml",
    "https://timesofindia.indiatimes.com/rss/4719148.cms",  # TOI Entertainment
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


def fetch_ott_news() -> list[dict]:
    """Fetch Bollywood and OTT news from RSS feeds."""
    stories = []

    for feed_url in OTT_RSS_FEEDS:
        if len(stories) >= 4:
            break
        try:
            resp = requests.get(
                feed_url,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0 (compatible; NRIBeat/1.0)"}
            )
            resp.raise_for_status()

            root = ET.fromstring(resp.content)
            items = root.findall(".//item")

            for item in items[:8]:
                title = item.findtext("title", "").strip()
                desc = item.findtext("description", "").strip()
                link = item.findtext("link", "").strip()
                pub_date = item.findtext("pubDate", "")

                if _is_bollywood_relevant(title + " " + desc):
                    stories.append({
                        "category": "movies",
                        "title": title,
                        "raw_content": f"{title}. {_clean_html(desc)}",
                        "source": _source_from_url(feed_url),
                        "url": link,
                        "published_at": pub_date,
                        "tags": _extract_movie_tags(title),
                    })

        except Exception as e:
            log.error(f"OTT RSS error for {feed_url}: {e}")

    return stories[:2]  # Max 2 movie/OTT stories per day


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
        "timesofindia": "Times of India",
        "pinkvilla": "PinkVilla",
    }
    for key, name in domain_map.items():
        if key in url:
            return name
    return url.split("/")[2]


def _clean_html(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text).strip()[:400]
