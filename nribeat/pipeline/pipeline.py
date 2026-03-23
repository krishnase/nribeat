#!/usr/bin/env python3
"""
NRIBeat Daily Pipeline
Runs every morning at 5 AM EST via GitHub Actions.
Fetches data → filters → generates articles with Claude → publishes to site.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path

from fetchers.visa_bulletin import fetch_visa_bulletin
from fetchers.news import fetch_tech_ai_news
from fetchers.cricket import fetch_cricket_news
from fetchers.reddit import fetch_reddit_trending
from fetchers.movies import fetch_ott_news
from filters.content_filter import filter_stories
from generator.article_gen import generate_articles
from generator.visa_predict import generate_visa_prediction
from publisher.github_publisher import publish_to_github
from publisher.email_digest import send_daily_digest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)


def run_pipeline():
    log.info("=" * 60)
    log.info("NRIBeat Daily Pipeline Starting")
    log.info(f"Date: {datetime.now().strftime('%B %d, %Y')}")
    log.info("=" * 60)

    stories = []

    # ── 1. FETCH ──────────────────────────────────────────────
    log.info("Step 1: Fetching data from all sources...")

    try:
        vb = fetch_visa_bulletin()
        if vb:
            stories.append(vb)
            log.info(f"  ✓ Visa Bulletin: {vb['title'][:60]}")
    except Exception as e:
        log.error(f"  ✗ Visa Bulletin fetch failed: {e}")

    try:
        tech_stories = fetch_tech_ai_news()
        stories.extend(tech_stories)
        log.info(f"  ✓ Tech/AI news: {len(tech_stories)} stories")
    except Exception as e:
        log.error(f"  ✗ Tech/AI fetch failed: {e}")

    try:
        cricket_stories = fetch_cricket_news()
        stories.extend(cricket_stories)
        log.info(f"  ✓ Cricket: {len(cricket_stories)} stories")
    except Exception as e:
        log.error(f"  ✗ Cricket fetch failed: {e}")

    try:
        reddit_stories = fetch_reddit_trending()
        stories.extend(reddit_stories)
        log.info(f"  ✓ Reddit trending: {len(reddit_stories)} posts")
    except Exception as e:
        log.error(f"  ✗ Reddit fetch failed: {e}")

    try:
        ott_stories = fetch_ott_news()
        stories.extend(ott_stories)
        log.info(f"  ✓ OTT/Movies: {len(ott_stories)} stories")
    except Exception as e:
        log.error(f"  ✗ OTT fetch failed: {e}")

    log.info(f"  Total raw stories: {len(stories)}")

    # ── 2. FILTER ─────────────────────────────────────────────
    log.info("Step 2: Filtering stories...")
    filtered = filter_stories(stories)
    log.info(f"  Stories after filtering: {len(filtered)} (removed {len(stories) - len(filtered)})")

    if len(filtered) < 3:
        log.warning("Too few stories after filtering. Check data sources.")

    # ── 3. GENERATE ───────────────────────────────────────────
    log.info("Step 3: Generating articles with Claude Haiku...")
    articles = generate_articles(filtered[:8])  # max 8 articles/day
    log.info(f"  Generated: {len(articles)} articles")

    # Also generate Visa Bulletin AI prediction if it's the right day
    if vb and datetime.now().day <= 15:
        log.info("  Generating Visa Bulletin prediction...")
        try:
            vb_prediction = generate_visa_prediction(vb)
            articles.insert(0, vb_prediction)
            log.info("  ✓ Visa Bulletin prediction generated")
        except Exception as e:
            log.error(f"  ✗ Visa prediction failed: {e}")

    # ── 4. PUBLISH ────────────────────────────────────────────
    log.info("Step 4: Publishing to GitHub...")
    try:
        result = publish_to_github(articles)
        log.info(f"  ✓ Published: {result['files_updated']} files updated")
        log.info(f"  ✓ Commit: {result['commit_sha'][:8]}")
    except Exception as e:
        log.error(f"  ✗ GitHub publish failed: {e}")

    # ── 5. EMAIL ──────────────────────────────────────────────
    log.info("Step 5: Sending daily digest email...")
    try:
        email_result = send_daily_digest(articles)
        log.info(f"  ✓ Email sent to {email_result['recipients']} subscribers")
    except Exception as e:
        log.error(f"  ✗ Email send failed: {e}")

    log.info("=" * 60)
    log.info("Pipeline Complete!")
    log.info("=" * 60)

    return articles


if __name__ == "__main__":
    run_pipeline()
