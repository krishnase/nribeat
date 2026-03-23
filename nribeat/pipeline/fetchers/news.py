"""
Tech & AI News Fetcher
Uses NewsAPI.org free tier + GNews as backup.
Targets stories relevant to Indian tech professionals in the US.
"""

import os
import logging
import requests
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "")

# Keywords that make a story relevant to our audience
RELEVANCE_KEYWORDS = [
    "H1B", "OPT", "visa", "immigration", "layoff", "laid off",
    "OpenAI", "Anthropic", "Google AI", "Meta AI", "GPT", "Claude",
    "artificial intelligence", "machine learning", "software engineer",
    "tech job", "startup", "silicon valley", "USCIS", "green card",
    "AI tool", "Gemini", "Copilot", "ChatGPT"
]

AI_TECH_QUERIES = [
    "artificial intelligence tools 2025",
    "tech layoffs H1B visa",
    "OpenAI GPT announcement",
    "software engineering AI",
    "Indian engineers Silicon Valley",
]


def fetch_tech_ai_news() -> list[dict]:
    """
    Fetch tech and AI news from NewsAPI.
    Falls back to GNews if NewsAPI fails or key is missing.
    """
    stories = []

    if NEWS_API_KEY:
        stories = _fetch_from_newsapi()
    
    if not stories and GNEWS_API_KEY:
        stories = _fetch_from_gnews()

    if not stories:
        stories = _fetch_from_rss()

    return stories[:6]  # Max 6 tech stories per day


def _fetch_from_newsapi() -> list[dict]:
    """Fetch from NewsAPI.org (100 requests/day free)."""
    stories = []
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    for query in AI_TECH_QUERIES[:2]:  # Conserve API calls
        try:
            resp = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "from": yesterday,
                    "sortBy": "popularity",
                    "language": "en",
                    "pageSize": 5,
                    "apiKey": NEWS_API_KEY,
                },
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()

            for article in data.get("articles", []):
                if _is_relevant(article.get("title", "") + " " + article.get("description", "")):
                    stories.append(_normalize_news_article(article, "ai_tech"))

        except Exception as e:
            log.error(f"NewsAPI error for '{query}': {e}")

    return stories


def _fetch_from_gnews() -> list[dict]:
    """Fetch from GNews API (free tier: 100 requests/day)."""
    stories = []
    try:
        resp = requests.get(
            "https://gnews.io/api/v4/search",
            params={
                "q": "artificial intelligence OR tech layoffs OR H1B visa",
                "lang": "en",
                "country": "us",
                "max": 10,
                "apikey": GNEWS_API_KEY,
            },
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()

        for article in data.get("articles", []):
            if _is_relevant(article.get("title", "") + " " + article.get("description", "")):
                stories.append(_normalize_gnews_article(article))

    except Exception as e:
        log.error(f"GNews error: {e}")

    return stories


def _fetch_from_rss() -> list[dict]:
    """
    Fallback: fetch from free RSS feeds when no API key is available.
    Covers TechCrunch, Wired, VentureBeat AI sections.
    """
    import xml.etree.ElementTree as ET

    rss_feeds = [
        ("https://techcrunch.com/feed/", "ai_tech"),
        ("https://feeds.feedburner.com/venturebeat/SZYF", "ai_tech"),
        ("https://www.wired.com/feed/rss", "ai_tech"),
    ]

    stories = []
    for url, category in rss_feeds:
        try:
            resp = requests.get(url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (compatible; NRIBeat/1.0)"
            })
            resp.raise_for_status()

            root = ET.fromstring(resp.content)
            items = root.findall(".//item")[:5]

            for item in items:
                title = item.findtext("title", "")
                desc = item.findtext("description", "")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")

                if _is_relevant(title + " " + desc):
                    stories.append({
                        "category": category,
                        "title": title.strip(),
                        "raw_content": f"{title}. {_clean_html(desc)}",
                        "source": url.split("/")[2],
                        "url": link,
                        "published_at": pub_date,
                        "tags": _extract_tags(title),
                    })

            if len(stories) >= 6:
                break

        except Exception as e:
            log.error(f"RSS feed error for {url}: {e}")

    return stories


def _is_relevant(text: str) -> bool:
    """Check if a story is relevant to Indian tech professionals."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in RELEVANCE_KEYWORDS)


def _normalize_news_article(article: dict, category: str) -> dict:
    return {
        "category": category,
        "title": article.get("title", ""),
        "raw_content": f"{article.get('title', '')}. {article.get('description', '')}. {article.get('content', '')[:500]}",
        "source": article.get("source", {}).get("name", ""),
        "url": article.get("url", ""),
        "published_at": article.get("publishedAt", ""),
        "image_url": article.get("urlToImage", ""),
        "tags": _extract_tags(article.get("title", "")),
    }


def _normalize_gnews_article(article: dict) -> dict:
    return {
        "category": "ai_tech",
        "title": article.get("title", ""),
        "raw_content": f"{article.get('title', '')}. {article.get('description', '')}",
        "source": article.get("source", {}).get("name", ""),
        "url": article.get("url", ""),
        "published_at": article.get("publishedAt", ""),
        "image_url": article.get("image", ""),
        "tags": _extract_tags(article.get("title", "")),
    }


def _extract_tags(title: str) -> list[str]:
    tags = []
    tag_map = {
        "layoff": "Layoffs", "laid off": "Layoffs",
        "openai": "OpenAI", "chatgpt": "ChatGPT", "gpt": "GPT",
        "anthropic": "Anthropic", "claude": "Claude",
        "google": "Google AI", "gemini": "Gemini",
        "h1b": "H1B", "visa": "Visa",
        "startup": "Startups", "funding": "Funding",
        "ai": "AI", "machine learning": "ML",
    }
    title_lower = title.lower()
    for kw, tag in tag_map.items():
        if kw in title_lower and tag not in tags:
            tags.append(tag)
    return tags[:4]


def _clean_html(text: str) -> str:
    """Strip HTML tags from text."""
    import re
    return re.sub(r'<[^>]+>', '', text).strip()[:500]
