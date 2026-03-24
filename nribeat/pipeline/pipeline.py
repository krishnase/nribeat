#!/usr/bin/env python3
from __future__ import annotations
"""
NRIBeat Daily Pipeline — Production v2
Runs every morning at 5 AM EST via GitHub Actions.

Step 1 — TRENDS:   Fetch what the NRI audience is searching for today
Step 2 — FETCH:    Pull raw stories from all sources
Step 3 — FILTER:   Remove political, negative, duplicate content
Step 4 — GENERATE: Write SEO-optimized articles with Claude Haiku
Step 5 — SEO:      Score articles, enrich metadata, generate schema markup
Step 6 — MONETIZE: Inject affiliate links + AdSense slots
Step 7 — PUBLISH:  Commit to GitHub (articles + JSON + sitemap + RSS)
Step 8 — EMAIL:    Send morning digest to subscribers via ConvertKit

Cost per run:  ~$0.05 Claude API (8 articles × $0.006 each)
Time per run:  ~6-8 minutes (dominated by Claude + GitHub API calls)
"""

import os
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# ── Logging setup ─────────────────────────────────────────────────────────────
log_file = Path(__file__).parent / "pipeline.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, mode="a", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ── Imports ───────────────────────────────────────────────────────────────────
from fetchers.visa_bulletin import fetch_visa_bulletin
from fetchers.news import fetch_tech_ai_news
from fetchers.cricket import fetch_cricket_news
from fetchers.reddit import fetch_reddit_trending
from fetchers.movies import fetch_ott_news, fetch_theatrical_releases
from fetchers.trends import fetch_trending_topics, get_rising_topics

from filters.content_filter import filter_stories
from generator.article_gen import generate_articles
from generator.visa_predict import generate_visa_prediction

from seo.keyword_scorer import score_article_seo, enrich_with_seo_keywords, rank_articles_by_seo
from monetization.affiliate_injector import inject_monetization, get_email_affiliate_block

from publisher.github_publisher import publish_to_github, publish_visa_bulletin_data, publish_movies_data, publish_movies_releases
from publisher.email_digest import send_daily_digest

DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
MAX_ARTICLES_PER_RUN = int(os.environ.get("MAX_ARTICLES", "8"))


def run_pipeline() -> dict:
    start_time = datetime.now()
    log.info("=" * 65)
    log.info("NRIBeat Daily Pipeline v2 — Starting")
    log.info(f"Date: {start_time.strftime('%A, %B %d, %Y — %I:%M %p EST')}")
    log.info(f"Mode: {'DRY RUN (no publish)' if DRY_RUN else 'LIVE'}")
    log.info("=" * 65)

    results = {
        "date": start_time.isoformat(),
        "dry_run": DRY_RUN,
        "steps": {},
    }

    vb = None  # Visa Bulletin story (referenced across steps)

    # ────────────────────────────────────────────────────────────────────────
    # STEP 1 — TRENDS: Discover what people are searching for today
    # ────────────────────────────────────────────────────────────────────────
    log.info("\nStep 1: Fetching trending topics...")
    trends = {}
    try:
        trends = fetch_trending_topics()
        rising = get_rising_topics(trends)
        log.info(f"  Trends fetched: {sum(len(v) for v in trends.values())} keywords across {len(trends)} categories")
        if rising:
            log.info(f"  Rising now: {', '.join(t['keyword'] for t in rising[:3])}")
        results["steps"]["trends"] = {"status": "ok", "keyword_count": sum(len(v) for v in trends.values())}
    except Exception as e:
        log.warning(f"  Trends fetch failed (non-critical): {e}")
        results["steps"]["trends"] = {"status": "fallback", "error": str(e)}

    # ────────────────────────────────────────────────────────────────────────
    # STEP 2 — FETCH: Pull raw stories from all sources
    # ────────────────────────────────────────────────────────────────────────
    log.info("\nStep 2: Fetching stories from all sources...")
    stories = []
    fetch_results = {}

    try:
        vb = fetch_visa_bulletin()
        if vb:
            stories.append(vb)
            log.info(f"  Visa Bulletin: {vb['title'][:60]}")
            fetch_results["visa_bulletin"] = 1
    except Exception as e:
        log.error(f"  Visa Bulletin failed: {e}")
        fetch_results["visa_bulletin"] = 0

    for name, fetcher, key in [
        ("Tech/AI",  fetch_tech_ai_news,    "ai_tech"),
        ("Cricket",  fetch_cricket_news,    "cricket"),
        ("Reddit",   fetch_reddit_trending, "reddit"),
        ("OTT/Movies", fetch_ott_news,      "movies"),
    ]:
        try:
            batch = fetcher()
            stories.extend(batch)
            log.info(f"  {name}: {len(batch)} stories")
            fetch_results[key] = len(batch)
        except Exception as e:
            log.error(f"  {name} fetch failed: {e}")
            fetch_results[key] = 0

    # Theatrical releases (structured data for movies-releases.json, not article stories)
    releases_data = {}
    try:
        releases_data = fetch_theatrical_releases()
        np = len(releases_data.get("now_playing", []))
        cs = len(releases_data.get("coming_soon", []))
        log.info(f"  Theatrical releases: {np} now playing, {cs} coming soon")
        fetch_results["theatrical"] = np + cs
    except Exception as e:
        log.error(f"  Theatrical releases fetch failed: {e}")
        fetch_results["theatrical"] = 0

    log.info(f"  Total raw stories: {len(stories)}")
    results["steps"]["fetch"] = {"status": "ok", "raw_count": len(stories), "by_source": fetch_results}

    # ────────────────────────────────────────────────────────────────────────
    # STEP 3 — FILTER: Remove political, negative, duplicate content
    # ────────────────────────────────────────────────────────────────────────
    log.info("\nStep 3: Filtering stories...")
    filtered = filter_stories(stories)
    log.info(f"  After filter: {len(filtered)} stories (removed {len(stories) - len(filtered)})")

    if len(filtered) < 3:
        log.warning("  Too few stories after filtering — check data sources")

    results["steps"]["filter"] = {
        "status": "ok",
        "before": len(stories),
        "after": len(filtered),
        "removed": len(stories) - len(filtered),
    }

    # ────────────────────────────────────────────────────────────────────────
    # STEP 4 — GENERATE: Write SEO-optimized articles with Claude Haiku
    # ────────────────────────────────────────────────────────────────────────
    log.info(f"\nStep 4: Generating articles with Claude Haiku (max {MAX_ARTICLES_PER_RUN})...")
    articles = generate_articles(filtered[:MAX_ARTICLES_PER_RUN], trends=trends)
    log.info(f"  Generated: {len(articles)} articles")

    # Visa Bulletin prediction article (only in first half of month)
    if vb and datetime.now().day <= 15:
        log.info("  Generating Visa Bulletin prediction article...")
        try:
            vb_prediction = generate_visa_prediction(vb)
            articles.insert(0, vb_prediction)
            log.info(f"  VB Prediction: {vb_prediction.get('predicted_eb2_movement', '?')} | Risk: {vb_prediction.get('retrogression_risk', '?')}")
        except Exception as e:
            log.error(f"  VB prediction failed: {e}")

    results["steps"]["generate"] = {"status": "ok", "article_count": len(articles)}

    # ────────────────────────────────────────────────────────────────────────
    # STEP 5 — SEO: Score + enrich every article
    # ────────────────────────────────────────────────────────────────────────
    log.info("\nStep 5: Scoring and enriching articles for SEO...")
    seo_articles = []
    for article in articles:
        article = score_article_seo(article, trends=trends)
        article = enrich_with_seo_keywords(article, trends=trends)
        seo_articles.append(article)
        log.info(f"  SEO [{article.get('seo_score', 0):3d}/100] {article.get('title', '')[:55]}")

    # Publish highest SEO-value articles first
    seo_articles = rank_articles_by_seo(seo_articles)
    avg_seo = round(sum(a.get("seo_score", 0) for a in seo_articles) / max(len(seo_articles), 1), 1)
    log.info(f"  Average SEO score: {avg_seo}/100")
    results["steps"]["seo"] = {"status": "ok", "avg_score": avg_seo}

    # ────────────────────────────────────────────────────────────────────────
    # STEP 6 — MONETIZE: Inject affiliate links + AdSense slots
    # ────────────────────────────────────────────────────────────────────────
    log.info("\nStep 6: Injecting monetization...")
    monetized_articles = []
    for article in seo_articles:
        monetized = inject_monetization(article)
        monetized_articles.append(monetized)

    log.info(f"  Monetized: {len(monetized_articles)} articles (affiliate links + ad slots)")
    results["steps"]["monetize"] = {"status": "ok", "article_count": len(monetized_articles)}

    # ────────────────────────────────────────────────────────────────────────
    # STEP 7 — PUBLISH: Commit to GitHub
    # ────────────────────────────────────────────────────────────────────────
    log.info("\nStep 7: Publishing to GitHub...")

    if DRY_RUN:
        log.info("  DRY RUN — skipping GitHub publish")
        _save_dry_run_output(monetized_articles)
        results["steps"]["publish"] = {"status": "dry_run"}
    else:
        if vb:
            publish_visa_bulletin_data(vb)

        publish_movies_data()
        publish_movies_releases(releases_data)

        try:
            pub_result = publish_to_github(monetized_articles)
            log.info(f"  Published: {pub_result['files_updated']} files | Avg SEO: {pub_result.get('avg_seo_score', '?')}/100")
            log.info(f"  Commit: {pub_result['commit_sha'][:8] if pub_result['commit_sha'] != 'none' else 'none'}")
            results["steps"]["publish"] = {"status": "ok", **pub_result}
        except Exception as e:
            log.error(f"  GitHub publish failed: {e}")
            results["steps"]["publish"] = {"status": "error", "error": str(e)}

    # ────────────────────────────────────────────────────────────────────────
    # STEP 8 — EMAIL: Send morning digest
    # ────────────────────────────────────────────────────────────────────────
    log.info("\nStep 8: Sending daily digest email...")
    if DRY_RUN:
        log.info("  DRY RUN — skipping email send")
        results["steps"]["email"] = {"status": "dry_run"}
    else:
        try:
            email_result = send_daily_digest(monetized_articles)
            log.info(f"  Email sent to {email_result.get('recipients', 0)} subscribers")
            results["steps"]["email"] = {"status": "ok", **email_result}
        except Exception as e:
            log.error(f"  Email send failed: {e}")
            results["steps"]["email"] = {"status": "error", "error": str(e)}

    # ────────────────────────────────────────────────────────────────────────
    # SUMMARY
    # ────────────────────────────────────────────────────────────────────────
    elapsed = (datetime.now() - start_time).total_seconds()
    results["elapsed_seconds"] = round(elapsed, 1)
    results["article_count"] = len(monetized_articles)
    results["avg_seo_score"] = avg_seo

    log.info("\n" + "=" * 65)
    log.info("Pipeline Complete!")
    log.info(f"  Articles:   {len(monetized_articles)}")
    log.info(f"  Avg SEO:    {avg_seo}/100")
    log.info(f"  Elapsed:    {elapsed:.1f}s ({elapsed/60:.1f} min)")
    log.info("=" * 65 + "\n")

    return results


def _save_dry_run_output(articles: list[dict]):
    """Write dry-run summary to disk for inspection."""
    output = Path("output")
    output.mkdir(exist_ok=True)
    summary = {
        "dry_run": True,
        "date": datetime.now().isoformat(),
        "articles": [
            {
                "title": a.get("title"),
                "slug": a.get("slug"),
                "category": a.get("category"),
                "seo_score": a.get("seo_score"),
                "word_count": a.get("word_count"),
                "tags": a.get("tags"),
                "what_this_means": a.get("what_this_means"),
                "has_monetization": a.get("has_monetization", False),
            }
            for a in articles
        ],
    }
    (output / "dry_run_output.json").write_text(json.dumps(summary, indent=2))
    log.info(f"  Dry run output → output/dry_run_output.json")


if __name__ == "__main__":
    result = run_pipeline()
    # Exit with error code if any critical step failed
    steps = result.get("steps", {})
    critical_failures = [
        k for k, v in steps.items()
        if isinstance(v, dict) and v.get("status") == "error"
        and k in ("generate", "publish")
    ]
    sys.exit(1 if critical_failures else 0)
