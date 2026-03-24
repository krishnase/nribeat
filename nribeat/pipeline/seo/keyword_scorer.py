from __future__ import annotations
"""
SEO Keyword Scorer
Scores each article for SEO potential, enriches titles/meta with search-intent
keywords, and generates schema.org JSON-LD markup for rich search results.

Targets:
- Featured snippets (FAQ schema)
- Article rich results (Article schema)
- Breadcrumb rich results
- HowTo schema for guide articles
"""

import re
import json
import logging
from datetime import datetime

log = logging.getLogger(__name__)

# ── SEARCH INTENT KEYWORDS ────────────────────────────────────────────────────
# High commercial/informational value keywords by category.
# Sourced from SEMrush/Ahrefs data for Indian-American search patterns.

INTENT_KEYWORDS = {
    "immigration": {
        "informational": [
            "how to", "what is", "when will", "can i", "explained",
            "step by step", "guide", "checklist", "timeline", "process",
        ],
        "high_value": [
            "H1B visa", "green card", "OPT extension", "STEM OPT", "I-485",
            "priority date", "EB-2 India", "EB-3 India", "visa bulletin",
            "USCIS", "I-140", "PERM", "H1B transfer", "H1B layoff",
            "60 day grace period", "advance parole", "EAD card",
        ],
        "long_tail": [
            "H1B visa lottery odds 2025",
            "EB-2 India priority date prediction",
            "what to do after H1B layoff",
            "STEM OPT approval rate",
            "green card timeline India",
            "I-485 filing checklist",
        ],
    },
    "visa_bulletin": {
        "informational": ["analysis", "what changed", "prediction", "forecast"],
        "high_value": [
            "visa bulletin", "EB-2 India", "EB-3 India", "priority date",
            "final action date", "dates for filing", "retrogression",
        ],
        "long_tail": [
            "visa bulletin EB-2 India this month",
            "when will EB-2 India become current",
            "EB-2 India priority date movement",
        ],
    },
    "ai_tech": {
        "informational": ["review", "comparison", "how to use", "tutorial", "vs"],
        "high_value": [
            "AI tools", "ChatGPT", "Claude", "Gemini", "GitHub Copilot",
            "software engineer", "machine learning", "tech salary",
            "AI coding", "LLM", "prompt engineering",
        ],
        "long_tail": [
            "best AI tools for software engineers 2025",
            "ChatGPT vs Claude for coding",
            "will AI replace software engineers",
            "AI tools to boost developer productivity",
        ],
    },
    "cricket": {
        "informational": ["highlights", "scorecard", "preview", "analysis", "results"],
        "high_value": [
            "India cricket", "IPL", "Virat Kohli", "Rohit Sharma",
            "ICC", "Test match", "ODI", "T20", "BCCI",
        ],
        "long_tail": [
            "India cricket live score today",
            "IPL 2025 points table",
            "where to watch India cricket in USA",
        ],
    },
    "movies": {
        "informational": ["review", "where to watch", "streaming", "release date", "trailer"],
        "high_value": [
            "Bollywood", "Netflix India", "Amazon Prime India", "Hotstar",
            "Hindi movies", "OTT release", "Indian cinema",
        ],
        "long_tail": [
            "new Bollywood movies on Netflix this week",
            "Hindi movies releasing on OTT",
            "Indian shows on Amazon Prime USA",
        ],
    },
    "layoffs": {
        "informational": ["what happened", "impact", "guide", "what to do", "next steps"],
        "high_value": [
            "tech layoffs", "H1B layoff", "60 day grace period",
            "layoff H1B visa", "tech job market", "software engineer layoff",
        ],
        "long_tail": [
            "what happens H1B visa after layoff",
            "tech layoffs 2025 H1B impact",
            "60 day grace period H1B checklist",
        ],
    },
}

# ── SEO SCORING ───────────────────────────────────────────────────────────────

def score_article_seo(article: dict, trends: dict = None) -> dict:
    """
    Score an article 0-100 for SEO potential.
    Also enriches the article with SEO metadata.
    Returns the article dict with added seo_score and seo_signals fields.
    """
    category = article.get("category", "ai_tech")
    title = article.get("title", "")
    meta_desc = article.get("meta_description", "")
    body_html = article.get("body_html", "")
    tags = article.get("tags", [])

    score = 0
    signals = []

    # ── Title quality (25 pts) ────────────────────────────────────────────────
    title_len = len(title)
    if 50 <= title_len <= 70:
        score += 25
        signals.append("title_length_optimal")
    elif 40 <= title_len <= 80:
        score += 15
        signals.append("title_length_acceptable")
    else:
        signals.append("title_length_poor")

    # ── High-value keyword in title (20 pts) ─────────────────────────────────
    kw_data = INTENT_KEYWORDS.get(category, INTENT_KEYWORDS["ai_tech"])
    title_lower = title.lower()
    for kw in kw_data["high_value"]:
        if kw.lower() in title_lower:
            score += 20
            signals.append(f"hv_keyword_in_title:{kw}")
            break

    # ── Intent signal in title (10 pts) ──────────────────────────────────────
    for intent_kw in kw_data["informational"]:
        if intent_kw in title_lower:
            score += 10
            signals.append(f"intent_signal:{intent_kw}")
            break

    # ── Meta description quality (10 pts) ────────────────────────────────────
    meta_len = len(meta_desc)
    if 120 <= meta_len <= 160:
        score += 10
        signals.append("meta_desc_optimal")
    elif meta_len > 0:
        score += 5
        signals.append("meta_desc_present")

    # ── Current year in title (5 pts — freshness signal) ─────────────────────
    if str(datetime.now().year) in title:
        score += 5
        signals.append("year_in_title")

    # ── Body length (10 pts) ──────────────────────────────────────────────────
    body_text = re.sub(r'<[^>]+>', '', body_html)
    word_count = len(body_text.split())
    if word_count >= 800:
        score += 10
        signals.append(f"word_count_good:{word_count}")
    elif word_count >= 500:
        score += 5
        signals.append(f"word_count_ok:{word_count}")

    # ── Has H2/H3 structure (5 pts) ───────────────────────────────────────────
    if re.search(r'<h[23]', body_html, re.IGNORECASE):
        score += 5
        signals.append("has_headings")

    # ── Has internal/external links (5 pts) ───────────────────────────────────
    if '<a href=' in body_html:
        score += 5
        signals.append("has_links")

    # ── Trending boost (10 pts) ───────────────────────────────────────────────
    if trends:
        cat_trends = trends.get(category, [])
        for trend in cat_trends:
            if trend.get("interest", 0) > 70 and trend.get("rising"):
                score += 10
                signals.append(f"trending_topic_boost:{trend['keyword'][:30]}")
                break

    article["seo_score"] = min(score, 100)
    article["seo_signals"] = signals
    return article


def enrich_with_seo_keywords(article: dict, trends: dict = None) -> dict:
    """
    Enrich article title and meta description with SEO keywords
    if they're missing key signals.
    """
    category = article.get("category", "ai_tech")
    title = article.get("title", "")
    meta_desc = article.get("meta_description", "")
    year = str(datetime.now().year)

    # Add year to title if not present and it's a timely category
    timely_cats = {"immigration", "visa_bulletin", "ai_tech", "layoffs"}
    if year not in title and category in timely_cats:
        article["title"] = title.rstrip(".").rstrip("?") + f" [{year}]"
        if len(article["title"]) > 75:
            article["title"] = title  # Revert if too long

    # Ensure meta ends with brand
    if meta_desc and "NRIBeat" not in meta_desc:
        if len(meta_desc) < 140:
            article["meta_description"] = meta_desc.rstrip(".") + " — NRIBeat"

    # Add canonical long-tail keyword as a tag
    kw_data = INTENT_KEYWORDS.get(category, {})
    long_tails = kw_data.get("long_tail", [])
    tags = article.get("tags", [])
    title_lower = title.lower()
    for lt in long_tails:
        if any(word in title_lower for word in lt.split()[:3]):
            if lt not in tags:
                tags.append(lt)
                break
    article["tags"] = tags[:6]

    return article


def generate_schema_markup(article: dict, site_url: str = "https://nribeat.com") -> str:
    """
    Generate schema.org JSON-LD markup for rich search results.
    Produces Article schema + FAQPage schema (if FAQs detected in body).
    """
    title = article.get("title", "")
    meta_desc = article.get("meta_description", "")
    category = article.get("category", "general")
    slug = article.get("slug", "article")
    date_iso = article.get("published_date", datetime.now().isoformat())
    tags = article.get("tags", [])
    body_html = article.get("body_html", "")

    subdir_map = {
        "immigration": "immigration", "visa_bulletin": "immigration",
        "ai_tech": "ai-tech", "cricket": "cricket",
        "movies": "movies", "layoffs": "layoffs",
    }
    subdir = subdir_map.get(category, "general")
    article_url = f"{site_url}/articles/{subdir}/{slug}.html"

    cat_label_map = {
        "immigration": "Immigration", "visa_bulletin": "Immigration",
        "ai_tech": "AI & Tech", "cricket": "Cricket",
        "movies": "Movies & OTT", "layoffs": "Layoffs",
    }

    # Article schema
    article_schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": meta_desc,
        "url": article_url,
        "datePublished": date_iso,
        "dateModified": date_iso,
        "author": {
            "@type": "Organization",
            "name": "NRIBeat Editorial",
            "url": site_url,
        },
        "publisher": {
            "@type": "Organization",
            "name": "NRIBeat",
            "url": site_url,
            "logo": {
                "@type": "ImageObject",
                "url": f"{site_url}/images/logo.png",
            },
        },
        "articleSection": cat_label_map.get(category, "General"),
        "keywords": ", ".join(tags),
        "mainEntityOfPage": {
            "@type": "WebPage",
            "@id": article_url,
        },
    }

    schemas = [article_schema]

    # FAQPage schema — detect FAQ questions in the body
    faqs = _extract_faqs_from_html(body_html)
    if faqs:
        faq_schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": q,
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": a,
                    },
                }
                for q, a in faqs
            ],
        }
        schemas.append(faq_schema)

    # BreadcrumbList schema
    breadcrumb_schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": site_url},
            {
                "@type": "ListItem",
                "position": 2,
                "name": cat_label_map.get(category, "General"),
                "item": f"{site_url}/{subdir}.html",
            },
            {"@type": "ListItem", "position": 3, "name": title, "item": article_url},
        ],
    }
    schemas.append(breadcrumb_schema)

    lines = [
        f'<script type="application/ld+json">{json.dumps(s, separators=(",", ":"))}</script>'
        for s in schemas
    ]
    return "\n".join(lines)


def _extract_faqs_from_html(body_html: str) -> list[tuple[str, str]]:
    """
    Extract Q&A pairs from article body HTML.
    Looks for FAQ sections with h2/h3 questions followed by p answers.
    """
    faqs = []
    # Match patterns like <h3>Question text</h3><p>Answer text</p>
    pattern = re.compile(
        r'<h[23][^>]*>(.*?)</h[23]>\s*<p[^>]*>(.*?)</p>',
        re.IGNORECASE | re.DOTALL,
    )
    matches = pattern.findall(body_html)
    for q_html, a_html in matches:
        q_text = re.sub(r'<[^>]+>', '', q_html).strip()
        a_text = re.sub(r'<[^>]+>', '', a_html).strip()
        # Only include if it looks like a genuine question
        if q_text.endswith("?") and len(a_text) > 30:
            faqs.append((q_text, a_text[:500]))
    return faqs[:5]  # Max 5 FAQs in schema


def rank_articles_by_seo(articles: list[dict]) -> list[dict]:
    """Sort articles by SEO score descending — publish highest-value first."""
    return sorted(articles, key=lambda a: a.get("seo_score", 0), reverse=True)
