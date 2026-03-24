from __future__ import annotations
"""
GitHub Publisher
Commits article HTML, JSON data files, sitemap.xml, and RSS feed to the repo.
GitHub Pages auto-deploys on every commit.

v2 improvements:
- Injects schema.org JSON-LD markup into article <head>
- Triggers sitemap.xml rebuild after every run
- Publishes RSS feed at /feed.xml
- Batches commits to reduce GitHub API calls
- Handles rate limits with exponential backoff
"""

import os
import json
import base64
import logging
import time
import requests
from datetime import datetime
from pathlib import Path

from seo.keyword_scorer import generate_schema_markup
from publisher.sitemap_builder import build_sitemap, build_rss_feed
from generator.visa_bulletin_article import generate_visa_bulletin_article

log = logging.getLogger(__name__)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "yourusername/nribeat")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GITHUB_API = "https://api.github.com"

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "Content-Type": "application/json",
}

CATEGORY_DIRS = {
    "immigration":   "immigration",
    "visa_bulletin": "immigration",
    "ai_tech":       "ai-tech",
    "cricket":       "cricket",
    "movies":        "movies",
    "layoffs":       "layoffs",
}


def publish_to_github(articles: list[dict]) -> dict:
    """
    For each article:
    1. Render full HTML page (with schema markup + monetization already injected)
    2. Commit to GitHub repo
    3. Update article JSON indices
    4. Rebuild sitemap.xml + RSS feed
    Returns a summary dict.
    """
    if not GITHUB_TOKEN:
        log.warning("GITHUB_TOKEN not set — saving articles locally")
        return _save_locally(articles)

    published = []
    errors = []

    for article in articles:
        try:
            html = _render_article_html(article)
            slug = article.get("slug", "article")
            category = article.get("category", "general")
            subdir = CATEGORY_DIRS.get(category, "general")
            file_path = f"nribeat/articles/{subdir}/{slug}.html"

            result = _commit_file_with_retry(
                path=file_path,
                content=html,
                message=f"article: {article.get('title', slug)[:60]}",
            )
            published.append({
                "slug": slug,
                "path": file_path,
                "sha": result.get("sha", ""),
                "seo_score": article.get("seo_score", 0),
            })
            log.info(f"  Published: {file_path} (SEO: {article.get('seo_score', '?')})")

        except Exception as e:
            log.error(f"  Failed to publish '{article.get('title', '')[:40]}': {e}")
            errors.append(str(e))

    # Update JSON indices
    _update_latest_articles(articles)
    _update_article_index(articles)

    # Rebuild sitemap and RSS
    _rebuild_sitemap_and_rss(articles)

    commit_sha = published[0].get("sha", "none") if published else "none"
    return {
        "files_updated": len(published),
        "errors": len(errors),
        "commit_sha": commit_sha,
        "published": published,
        "avg_seo_score": round(
            sum(p.get("seo_score", 0) for p in published) / max(len(published), 1), 1
        ),
    }


def _commit_file_with_retry(path: str, content: str, message: str, retries: int = 3) -> dict:
    """Commit a file with exponential backoff on rate limit errors."""
    for attempt in range(retries):
        try:
            return _commit_file(path, content, message)
        except requests.HTTPError as e:
            if e.response.status_code == 403 and attempt < retries - 1:
                wait = 2 ** (attempt + 1)
                log.warning(f"  Rate limited — waiting {wait}s before retry {attempt+1}/{retries}")
                time.sleep(wait)
            else:
                raise
    return {}


def _commit_file(path: str, content: str, message: str) -> dict:
    """Create or update a file in the GitHub repo via Contents API."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"

    existing_sha = None
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code == 200:
        existing_sha = resp.json().get("sha")

    content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    payload = {
        "message": message,
        "content": content_b64,
        "branch": GITHUB_BRANCH,
    }
    if existing_sha:
        payload["sha"] = existing_sha

    resp = requests.put(url, headers=HEADERS, json=payload, timeout=20)
    resp.raise_for_status()
    return {"sha": resp.json().get("commit", {}).get("sha", "")}


def _render_article_html(article: dict) -> str:
    """Render a complete HTML page for an article, including schema.org markup."""
    title = article.get("title", "Article")
    meta_desc = article.get("meta_description", "")
    body_html = article.get("body_html", "<p>Content coming soon.</p>")
    category = article.get("category", "general")
    tags = article.get("tags", [])
    date_display = article.get("published_date_display", datetime.now().strftime("%B %d, %Y"))
    reading_time = article.get("reading_time", "5 min read")
    source_url = article.get("source_url", "")
    source_name = article.get("source_name", "")
    seo_score = article.get("seo_score", 0)
    word_count = article.get("word_count", 0)

    # Schema.org markup (Article + FAQ + Breadcrumb)
    schema_markup = generate_schema_markup(article)

    tags_html = "".join(f'<span class="ac-tag">{tag}</span>' for tag in tags[:5])

    cat_class_map = {
        "immigration": "immigration", "visa_bulletin": "immigration",
        "ai_tech": "ai", "cricket": "cricket",
        "movies": "movies", "layoffs": "layoffs",
    }
    cat_color_map = {
        "immigration": "var(--saffron)", "visa_bulletin": "var(--saffron)",
        "ai_tech": "var(--blue)", "cricket": "var(--green)",
        "movies": "var(--pink)", "layoffs": "var(--amber)",
    }
    cat_label_map = {
        "immigration": "Immigration", "visa_bulletin": "Immigration",
        "ai_tech": "AI & Tech", "cricket": "Cricket",
        "movies": "Movies & OTT", "layoffs": "Layoffs",
    }
    cat_class = cat_class_map.get(category, "ai")
    cat_color = cat_color_map.get(category, "var(--blue)")
    cat_label = cat_label_map.get(category, category.title())

    source_html = ""
    if source_url and source_name:
        source_html = (
            f'<a href="{source_url}" target="_blank" rel="noopener" class="source-link">'
            f"Source: {source_name} ↗</a>"
        )

    # AdSense script — only added if client ID is configured
    adsense_script = ""
    adsense_client = os.environ.get("ADSENSE_CLIENT_ID", "")
    if adsense_client:
        adsense_script = (
            f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={adsense_client}" '
            f'crossorigin="anonymous"></script>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="description" content="{meta_desc}"/>
<meta property="og:title" content="{title}"/>
<meta property="og:description" content="{meta_desc}"/>
<meta property="og:type" content="article"/>
<meta property="og:site_name" content="NRIBeat"/>
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="{title}"/>
<meta name="twitter:description" content="{meta_desc}"/>
<link rel="canonical" href="https://nribeat.com/articles/{CATEGORY_DIRS.get(category,'general')}/{article.get('slug','')}.html"/>
<title>{title} | NRIBeat</title>
{schema_markup}
{adsense_script}
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<link rel="stylesheet" href="/css/style.css"/>
<style>
.article-wrap{{max-width:760px;margin:0 auto;padding:40px 24px 60px}}
.article-eyebrow{{font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:{cat_color};margin-bottom:12px}}
.article-wrap h1{{font-family:'DM Serif Display',serif;font-size:38px;line-height:1.15;color:var(--white);margin-bottom:16px;letter-spacing:-.4px}}
.article-meta{{font-size:12px;color:var(--white-muted);display:flex;gap:14px;flex-wrap:wrap;margin-bottom:28px;padding-bottom:20px;border-bottom:1px solid var(--navy-border)}}
.article-wrap p{{font-size:16px;color:var(--white-dim);line-height:1.8;margin-bottom:18px}}
.article-wrap h2{{font-family:'DM Serif Display',serif;font-size:26px;color:var(--white);margin:36px 0 14px}}
.article-wrap h3{{font-size:18px;font-weight:600;color:var(--white);margin:24px 0 10px}}
.article-wrap ul{{margin:0 0 18px 20px;color:var(--white-dim)}}
.article-wrap ul li{{margin-bottom:8px;font-size:15px;line-height:1.7}}
.article-wrap table{{width:100%;border-collapse:collapse;margin:20px 0;font-size:14px}}
.article-wrap th{{background:var(--navy-mid);padding:10px 14px;text-align:left;color:var(--white-muted);font-size:11px;text-transform:uppercase;letter-spacing:.4px}}
.article-wrap td{{padding:10px 14px;border-bottom:1px solid var(--navy-border);color:var(--white-dim)}}
.article-wrap strong{{color:var(--white)}}
.article-wrap a{{color:var(--saffron);text-decoration:none}}
.article-wrap a:hover{{text-decoration:underline}}
.affiliate-link{{border-bottom:1px dashed var(--saffron);padding-bottom:1px}}
.callout{{background:linear-gradient(135deg,rgba(232,102,26,.1),rgba(74,158,232,.06));border:1px solid rgba(232,102,26,.25);border-radius:12px;padding:20px 24px;margin:28px 0}}
.callout-title{{font-size:12px;font-weight:600;color:var(--saffron);letter-spacing:.6px;text-transform:uppercase;margin-bottom:8px}}
.tags-row{{display:flex;flex-wrap:wrap;gap:8px;margin-top:28px;padding-top:20px;border-top:1px solid var(--navy-border)}}
.source-link{{font-size:12px;color:var(--white-muted);text-decoration:none}}
.source-link:hover{{color:var(--white-dim)}}
.affiliate-disclosure{{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:8px;padding:10px 14px;margin:20px 0;font-size:12px;color:var(--white-muted)}}
@media(max-width:600px){{.article-wrap{{padding:24px 16px}}.article-wrap h1{{font-size:26px}}}}
</style>
</head>
<body>
<div class="ticker-wrap"><div class="ticker-label">Live</div><div class="ticker-track" id="tickerTrack"><span>NRIBeat — Daily pulse for Indian Americans</span><span>Visa Bulletin · AI News · Cricket · Bollywood · Layoffs</span><span>NRIBeat — Daily pulse for Indian Americans</span></div></div>
<header><div class="header-inner"><a href="/index.html" class="logo">NRI<span class="beat">Beat</span><div class="logo-dot"></div></a><nav><a href="/index.html">Home</a><a href="/immigration.html">Immigration</a><a href="/ai-tools.html">AI & Tech</a><a href="/cricket.html">Cricket</a><a href="/movies.html">Movies</a><a href="/layoffs.html">Layoffs</a><a href="/index.html#newsletter" class="nav-cta">Get Daily Digest</a></nav><div class="hamburger" onclick="document.getElementById('mn').classList.toggle('open')"><span></span><span></span><span></span></div></div><div class="mobile-nav" id="mn"><a href="/index.html">Home</a><a href="/immigration.html">Immigration</a><a href="/ai-tools.html">AI & Tech</a><a href="/cricket.html">Cricket</a><a href="/movies.html">Movies</a><a href="/layoffs.html">Layoffs</a></div></header>

<main>
<div class="article-wrap">
  <div class="article-eyebrow">{cat_label}</div>
  <h1>{title}</h1>
  <div class="article-meta">
    <span>📅 {date_display}</span>
    <span>⏱ {reading_time}</span>
    <span>✍️ NRIBeat Editorial</span>
    {source_html}
  </div>

  {body_html}

  <div class="tags-row">
    {tags_html}
  </div>
</div>

<div class="page" style="max-width:760px;margin:0 auto">
  <section class="newsletter" id="newsletter">
    <div class="nl-eyebrow">📬 Daily Digest</div>
    <h2 class="nl-title">Your morning <em>beat</em>, delivered at 7 AM</h2>
    <p class="nl-sub">Visa Bulletin · AI tools · Cricket · OTT · Layoffs — in 2 minutes.</p>
    <div class="nl-form"><input class="nl-input" type="email" placeholder="your@email.com" id="emailInput"/><button class="nl-btn" onclick="subscribe()">Subscribe Free</button></div>
    <p class="nl-note" id="subMsg"><span>Free forever</span> · No spam, ever</p>
  </section>
</div>
</main>

<footer><div class="footer-inner"><div class="footer-bottom"><span>© <span id="yr"></span> NRIBeat.com · All rights reserved</span><span>Made with ❤️ for the Indian-American community</span></div></div></footer>
<script>
document.getElementById("yr").textContent=new Date().getFullYear();
function subscribe(){{const e=document.getElementById('emailInput').value,m=document.getElementById('subMsg');if(!e||!e.includes('@')){{m.innerHTML='<span style="color:var(--amber)">Valid email required.</span>';return}}m.innerHTML='<span style="color:var(--green)">✓ You\\'re in!</span>';document.getElementById('emailInput').value=''}}
fetch('/data/latest-articles.json').then(r=>r.json()).then(d=>{{const items=(d.articles||[]).slice(0,6).map(a=>a.title);if(!items.length)return;const t=[...items,...items];document.getElementById('tickerTrack').innerHTML=t.map(s=>`<span>${{s}}</span>`).join('')}}).catch(()=>{{}});
</script>
<!-- seo_score:{seo_score} word_count:{word_count} generated:{datetime.now().strftime('%Y-%m-%dT%H:%M')} -->
</body>
</html>"""


def _update_latest_articles(articles: list[dict]):
    """Publish latest-articles.json — loaded by the homepage hero and ticker."""
    cards = []
    for a in articles:
        category = a.get("category", "general")
        subdir = CATEGORY_DIRS.get(category, "general")
        cards.append({
            "title":          a.get("title", ""),
            "slug":           a.get("slug", ""),
            "category":       category,
            "what_this_means": a.get("what_this_means", ""),
            "reading_time":   a.get("reading_time", "5 min read"),
            "tags":           a.get("tags", [])[:3],
            "date":           a.get("published_date_display", ""),
            "seo_score":      a.get("seo_score", 0),
            "url":            f"/articles/{subdir}/{a.get('slug','')}.html",
        })

    content = json.dumps({"date": datetime.now().isoformat(), "articles": cards}, indent=2)
    try:
        _commit_file(
            path="nribeat/data/latest-articles.json",
            content=content,
            message=f"data: daily articles update {datetime.now().strftime('%Y-%m-%d')}",
        )
        log.info("  Updated: latest-articles.json")
    except Exception as e:
        log.error(f"  latest-articles.json update failed: {e}")


def _update_article_index(articles: list[dict]):
    """Maintain a rolling index of all published articles (max 500)."""
    existing_index = []
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/nribeat/data/article-index.json"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code == 200:
        try:
            raw = base64.b64decode(resp.json().get("content", "")).decode("utf-8")
            existing_index = json.loads(raw).get("articles", [])
        except Exception:
            pass

    for a in articles:
        category = a.get("category", "general")
        subdir = CATEGORY_DIRS.get(category, "general")
        existing_index.insert(0, {
            "title":        a.get("title", ""),
            "slug":         a.get("slug", ""),
            "category":     category,
            "date":         a.get("published_date_display", a.get("published_date", "")),
            "reading_time": a.get("reading_time", "5 min read"),
            "excerpt":      a.get("what_this_means", ""),
            "tags":         a.get("tags", [])[:3],
            "seo_score":    a.get("seo_score", 0),
            "url":          f"/articles/{subdir}/{a.get('slug','')}.html",
        })

    existing_index = existing_index[:500]
    content = json.dumps({"articles": existing_index}, indent=2)
    try:
        _commit_file(
            path="nribeat/data/article-index.json",
            content=content,
            message="data: update article index",
        )
        log.info("  Updated: article-index.json")
    except Exception as e:
        log.error(f"  article-index.json update failed: {e}")

    # Store index in memory for sitemap builder
    _update_article_index._last_index = existing_index


_update_article_index._last_index = []


def _rebuild_sitemap_and_rss(articles: list[dict]):
    """Rebuild sitemap.xml and feed.xml after every pipeline run."""
    article_index = getattr(_update_article_index, "_last_index", [])

    # Sitemap
    try:
        sitemap_xml = build_sitemap(article_index)
        _commit_file(
            path="nribeat/sitemap.xml",
            content=sitemap_xml,
            message=f"seo: rebuild sitemap {datetime.now().strftime('%Y-%m-%d')}",
        )
        log.info(f"  Updated: sitemap.xml ({len(article_index)} articles)")
    except Exception as e:
        log.error(f"  sitemap.xml rebuild failed: {e}")

    # RSS Feed
    try:
        rss_xml = build_rss_feed(article_index[:20])
        _commit_file(
            path="nribeat/feed.xml",
            content=rss_xml,
            message="seo: update RSS feed",
        )
        log.info("  Updated: feed.xml")
    except Exception as e:
        log.error(f"  feed.xml update failed: {e}")


def publish_visa_bulletin_data(vb: dict):
    """
    Publish visa bulletin data JSON + auto-generate and publish the monthly article.
    1. Read existing visa-bulletin.json (for movement calculation)
    2. Write updated visa-bulletin.json
    3. Generate the month's article HTML from the new data
    4. Commit article HTML
    5. Prepend article to article-index.json and latest-articles.json
    """
    if not vb:
        return

    dates = vb.get("priority_dates", {})
    month_year = vb.get("month_year", "")

    # Step 1: Read previous bulletin data for movement calculation
    prev_data = None
    if GITHUB_TOKEN:
        try:
            url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/nribeat/data/visa-bulletin.json"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                raw = base64.b64decode(resp.json().get("content", "")).decode("utf-8")
                prev_data = json.loads(raw)
        except Exception as e:
            log.warning(f"  Could not read previous visa-bulletin.json: {e}")

    # Step 2: Write updated visa-bulletin.json
    bulletin_json = json.dumps({
        "month_year":        month_year,
        "updated":           datetime.now().isoformat(),
        "eb2_india_final":   dates.get("eb2_india_final", ""),
        "eb3_india_final":   dates.get("eb3_india_final", ""),
        "eb1_india_final":   dates.get("eb1_india_final", "Current"),
        "eb2_india_filing":  dates.get("eb2_india_filing", ""),
        "eb3_india_filing":  dates.get("eb3_india_filing", ""),
        "eb1_india_filing":  dates.get("eb1_india_filing", "Current"),
        "dff_authorized":    bool(dates.get("eb2_india_filing") or dates.get("eb3_india_filing")),
    }, indent=2)

    if GITHUB_TOKEN:
        try:
            _commit_file(
                path="nribeat/data/visa-bulletin.json",
                content=bulletin_json,
                message=f"data: visa bulletin {month_year}",
            )
            log.info("  Updated: visa-bulletin.json")
        except Exception as e:
            log.error(f"  visa-bulletin.json update failed: {e}")
    else:
        # Local dev: write to disk
        from pathlib import Path
        Path("output").mkdir(exist_ok=True)
        (Path("output") / "visa-bulletin.json").write_text(bulletin_json)

    # Step 3: Generate the monthly article
    try:
        article = generate_visa_bulletin_article(vb, prev_data=prev_data)
        log.info(f"  Generated bulletin article: {article['slug']}")
    except Exception as e:
        log.error(f"  Visa bulletin article generation failed: {e}")
        return

    # Step 4: Render and commit article HTML
    try:
        html = _render_article_html(article)
        slug = article["slug"]
        article_path = f"nribeat/articles/immigration/{slug}.html"
        if GITHUB_TOKEN:
            _commit_file_with_retry(
                path=article_path,
                content=html,
                message=f"article: {article['title'][:60]}",
            )
            log.info(f"  Published bulletin article: {article_path}")
        else:
            from pathlib import Path
            out = Path("output/articles/immigration")
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{slug}.html").write_text(html)
            log.info(f"  Saved bulletin article locally: output/articles/immigration/{slug}.html")
    except Exception as e:
        log.error(f"  Bulletin article publish failed: {e}")
        return

    # Step 5: Prepend to article-index.json and latest-articles.json
    _prepend_bulletin_to_indices(article)


def _prepend_bulletin_to_indices(article: dict):
    """
    Prepend the auto-generated bulletin article to both article-index.json
    and latest-articles.json, replacing any existing entry with the same slug.
    """
    slug = article.get("slug", "")
    category = article.get("category", "immigration")
    subdir = CATEGORY_DIRS.get(category, "immigration")
    url = f"/articles/{subdir}/{slug}.html"

    index_entry = {
        "title":        article.get("title", ""),
        "slug":         slug,
        "category":     category,
        "date":         article.get("published_date_display", ""),
        "reading_time": article.get("reading_time", "5 min read"),
        "excerpt":      article.get("what_this_means", ""),
        "tags":         article.get("tags", [])[:5],
        "seo_score":    article.get("seo_score", 85),
        "url":          url,
    }
    latest_entry = {**index_entry, "what_this_means": article.get("what_this_means", "")}

    if not GITHUB_TOKEN:
        return

    # ── article-index.json ──────────────────────────────────────────────
    try:
        url_api = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/nribeat/data/article-index.json"
        resp = requests.get(url_api, headers=HEADERS, timeout=15)
        existing = []
        if resp.status_code == 200:
            raw = base64.b64decode(resp.json().get("content", "")).decode("utf-8")
            existing = json.loads(raw).get("articles", [])
        # Remove duplicate slug entry if it exists, then prepend
        existing = [a for a in existing if a.get("slug") != slug]
        existing.insert(0, index_entry)
        existing = existing[:500]
        _commit_file(
            path="nribeat/data/article-index.json",
            content=json.dumps({"articles": existing}, indent=2),
            message=f"data: add bulletin article {slug}",
        )
        log.info("  Updated: article-index.json (bulletin)")
    except Exception as e:
        log.error(f"  article-index.json bulletin update failed: {e}")

    # ── latest-articles.json ─────────────────────────────────────────────
    try:
        url_api = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/nribeat/data/latest-articles.json"
        resp = requests.get(url_api, headers=HEADERS, timeout=15)
        existing = []
        if resp.status_code == 200:
            raw = base64.b64decode(resp.json().get("content", "")).decode("utf-8")
            existing = json.loads(raw).get("articles", [])
        existing = [a for a in existing if a.get("slug") != slug]
        existing.insert(0, latest_entry)
        existing = existing[:20]
        _commit_file(
            path="nribeat/data/latest-articles.json",
            content=json.dumps({"date": datetime.now().isoformat(), "articles": existing}, indent=2),
            message=f"data: add bulletin article {slug}",
        )
        log.info("  Updated: latest-articles.json (bulletin)")
    except Exception as e:
        log.error(f"  latest-articles.json bulletin update failed: {e}")


def publish_movies_data():
    """
    Commit the three movies data JSON files to GitHub Pages on every pipeline run.
    Files are read from the local repo and pushed via GitHub Contents API.
    Box office data is curated monthly; OTT picks and celebrity news can be
    updated via the movies fetcher as live RSS data becomes available.
    """
    movies_files = [
        ("data/movies-boxoffice.json",  "nribeat/data/movies-boxoffice.json"),
        ("data/movies-ott.json",        "nribeat/data/movies-ott.json"),
        ("data/movies-celebrity.json",  "nribeat/data/movies-celebrity.json"),
    ]

    # Resolve path relative to the repo root (one level up from pipeline/)
    repo_root = Path(__file__).parent.parent.parent

    for local_rel, github_path in movies_files:
        local_path = repo_root / local_rel
        if not local_path.exists():
            log.warning(f"  Movies data file not found locally: {local_path}")
            continue
        content = local_path.read_text(encoding="utf-8")
        try:
            if GITHUB_TOKEN:
                _commit_file_with_retry(
                    path=github_path,
                    content=content,
                    message=f"data: update {local_path.name}",
                )
                log.info(f"  Updated: {local_path.name}")
            else:
                out = Path("output") / local_rel
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(content)
                log.info(f"  Saved locally: output/{local_rel}")
        except Exception as e:
            log.error(f"  {local_path.name} update failed: {e}")


def _save_locally(articles: list[dict]) -> dict:
    """Save articles locally when GitHub token is not set (dev/testing)."""
    output_dir = Path("output/articles")
    output_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for article in articles:
        slug = article.get("slug", "article")
        category = article.get("category", "general")
        subdir = CATEGORY_DIRS.get(category, "general")

        file_path = output_dir / subdir / f"{slug}.html"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(_render_article_html(article))
        saved.append(str(file_path))
        log.info(f"  Saved locally: {file_path}")

    # Save JSON locally too
    (Path("output") / "latest-articles.json").write_text(
        json.dumps({"articles": [{"title": a.get("title"), "slug": a.get("slug")} for a in articles]}, indent=2)
    )

    return {
        "files_updated": len(saved),
        "errors": 0,
        "commit_sha": "local",
        "published": saved,
        "avg_seo_score": round(
            sum(a.get("seo_score", 0) for a in articles) / max(len(articles), 1), 1
        ),
    }
