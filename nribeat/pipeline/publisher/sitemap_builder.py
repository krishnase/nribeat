from __future__ import annotations
"""
Sitemap Builder
Auto-generates sitemap.xml from the article index and static pages.
Committed to the repo on every pipeline run so Google always has fresh URLs.

Priority logic:
  - Homepage: 1.0
  - Visa Bulletin dashboard: 0.9 (freshest, most searched)
  - Immigration / Layoff articles: 0.8
  - AI & Tech articles: 0.7
  - Cricket / Movies articles: 0.6
  - Static guide pages: 0.5
"""

import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

SITE_URL = "https://nribeat.com"

# Static pages that are always in the sitemap
STATIC_PAGES = [
    {"loc": "/",                  "changefreq": "daily",   "priority": "1.0"},
    {"loc": "/immigration.html",  "changefreq": "daily",   "priority": "0.9"},
    {"loc": "/visa-bulletin.html","changefreq": "monthly", "priority": "0.9"},
    {"loc": "/cricket.html",      "changefreq": "daily",   "priority": "0.7"},
    {"loc": "/movies.html",       "changefreq": "weekly",  "priority": "0.6"},
    {"loc": "/layoffs.html",      "changefreq": "daily",   "priority": "0.8"},
    {"loc": "/ai-tools.html",     "changefreq": "weekly",  "priority": "0.7"},
]

CATEGORY_PRIORITY = {
    "immigration":  "0.8",
    "visa_bulletin": "0.85",
    "ai_tech":      "0.7",
    "cricket":      "0.6",
    "movies":       "0.6",
    "layoffs":      "0.8",
}

CATEGORY_CHANGEFREQ = {
    "immigration":  "weekly",
    "visa_bulletin": "monthly",
    "ai_tech":      "weekly",
    "cricket":      "weekly",
    "movies":       "weekly",
    "layoffs":      "weekly",
}

SUBDIR_MAP = {
    "immigration":  "immigration",
    "visa_bulletin": "immigration",
    "ai_tech":      "ai-tech",
    "cricket":      "cricket",
    "movies":       "movies",
    "layoffs":      "layoffs",
}


def build_sitemap(article_index: list[dict]) -> str:
    """
    Generate a complete sitemap.xml string from static pages + article index.
    article_index: list of article dicts from article-index.json
    Returns the full XML content as a string.
    """
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = []

    # Static pages
    for page in STATIC_PAGES:
        urls.append(_make_url_entry(
            loc=SITE_URL + page["loc"],
            lastmod=now_iso,
            changefreq=page["changefreq"],
            priority=page["priority"],
        ))

    # Article pages — use published date for lastmod
    for article in article_index:
        category = article.get("category", "general")
        slug = article.get("slug", "")
        if not slug:
            continue

        subdir = SUBDIR_MAP.get(category, "general")
        loc = f"{SITE_URL}/articles/{subdir}/{slug}.html"

        # Parse article date for lastmod
        raw_date = article.get("date", "")
        lastmod = _parse_date_to_iso(raw_date) or now_iso

        priority = CATEGORY_PRIORITY.get(category, "0.6")
        changefreq = CATEGORY_CHANGEFREQ.get(category, "weekly")

        urls.append(_make_url_entry(loc, lastmod, changefreq, priority))

    sitemap = _wrap_xml(urls)
    log.info(f"  Sitemap: {len(urls)} URLs generated")
    return sitemap


def _make_url_entry(loc: str, lastmod: str, changefreq: str, priority: str) -> str:
    return (
        f"  <url>\n"
        f"    <loc>{loc}</loc>\n"
        f"    <lastmod>{lastmod}</lastmod>\n"
        f"    <changefreq>{changefreq}</changefreq>\n"
        f"    <priority>{priority}</priority>\n"
        f"  </url>"
    )


def _wrap_xml(url_entries: list[str]) -> str:
    header = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n'
        '        xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9\n'
        '        http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd">\n'
    )
    footer = "</urlset>"
    return header + "\n".join(url_entries) + "\n" + footer


def _parse_date_to_iso(raw_date: str) -> str | None:
    """Convert 'March 23, 2026' → '2026-03-23'. Returns None on failure."""
    formats = ["%B %d, %Y", "%b %d, %Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]
    for fmt in formats:
        try:
            dt = datetime.strptime(raw_date.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def build_rss_feed(articles: list[dict]) -> str:
    """
    Generate an RSS 2.0 feed from the latest articles.
    Published at /feed.xml — enables Google News indexing and feed readers.
    """
    now_rfc = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    items = []
    for article in articles[:20]:  # Latest 20 articles in feed
        category = article.get("category", "general")
        slug = article.get("slug", "")
        subdir = SUBDIR_MAP.get(category, "general")
        url = f"{SITE_URL}/articles/{subdir}/{slug}.html"
        title = _xml_escape(article.get("title", ""))
        desc = _xml_escape(article.get("excerpt", article.get("what_this_means", "")))
        pub_date = _to_rfc_date(article.get("date", "")) or now_rfc

        cat_label_map = {
            "immigration": "Immigration", "visa_bulletin": "Immigration",
            "ai_tech": "AI & Tech", "cricket": "Cricket",
            "movies": "Movies & OTT", "layoffs": "Layoffs",
        }
        cat_label = cat_label_map.get(category, "General")

        items.append(
            f"  <item>\n"
            f"    <title>{title}</title>\n"
            f"    <link>{url}</link>\n"
            f"    <guid isPermaLink=\"true\">{url}</guid>\n"
            f"    <description>{desc}</description>\n"
            f"    <pubDate>{pub_date}</pubDate>\n"
            f"    <category>{cat_label}</category>\n"
            f"  </item>"
        )

    feed = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        f"    <title>NRIBeat — Daily Pulse for Indian Americans</title>\n"
        f"    <link>{SITE_URL}</link>\n"
        f"    <description>Immigration, AI, Cricket, Bollywood, and Layoffs — curated daily for the Indian-American community.</description>\n"
        f'    <atom:link href="{SITE_URL}/feed.xml" rel="self" type="application/rss+xml"/>\n'
        f"    <language>en-us</language>\n"
        f"    <lastBuildDate>{now_rfc}</lastBuildDate>\n"
        f"    <ttl>1440</ttl>\n"
        + "\n".join(items) + "\n"
        "  </channel>\n"
        "</rss>"
    )
    return feed


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
    )


def _to_rfc_date(raw: str) -> str | None:
    """Convert 'March 23, 2026' → RFC 2822 date string."""
    iso = _parse_date_to_iso(raw)
    if not iso:
        return None
    try:
        dt = datetime.strptime(iso, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt.strftime("%a, %d %b %Y 07:00:00 +0000")
    except ValueError:
        return None
