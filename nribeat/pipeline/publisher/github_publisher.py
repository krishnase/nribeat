"""
GitHub Publisher
Generates article HTML files and commits them to the nribeat GitHub repo.
GitHub Pages then auto-deploys the updated site.
"""

import os
import json
import base64
import logging
import requests
from datetime import datetime
from pathlib import Path

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

# Category to subdirectory mapping
CATEGORY_DIRS = {
    "immigration": "immigration",
    "visa_bulletin": "immigration",
    "ai_tech": "ai-tech",
    "cricket": "cricket",
    "movies": "movies",
    "layoffs": "layoffs",
}


def publish_to_github(articles: list[dict]) -> dict:
    """
    For each article:
    1. Generate a full HTML page
    2. Commit it to the GitHub repo
    3. Update the homepage with new article cards
    Returns summary of what was published.
    """
    if not GITHUB_TOKEN:
        log.warning("GITHUB_TOKEN not set — saving articles locally instead")
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

            result = _commit_file(
                path=file_path,
                content=html,
                message=f"✨ New article: {article.get('title', slug)[:60]}"
            )
            published.append({"slug": slug, "path": file_path, "sha": result.get("sha", "")})
            log.info(f"    ✓ Published: {file_path}")

        except Exception as e:
            log.error(f"    ✗ Failed to publish '{article.get('title', '')[:40]}': {e}")
            errors.append(str(e))

    # Update the homepage with new article cards
    try:
        _update_homepage(articles)
        log.info("    ✓ Homepage updated")
    except Exception as e:
        log.error(f"    ✗ Homepage update failed: {e}")

    # Save article index JSON for the site to use
    try:
        _update_article_index(articles)
        log.info("    ✓ Article index updated")
    except Exception as e:
        log.error(f"    ✗ Article index update failed: {e}")

    return {
        "files_updated": len(published),
        "errors": len(errors),
        "commit_sha": published[0].get("sha", "unknown") if published else "none",
        "published": published,
    }


def _commit_file(path: str, content: str, message: str) -> dict:
    """Create or update a file in the GitHub repo."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"

    # Check if file exists (to get its SHA for update)
    existing_sha = None
    resp = requests.get(url, headers=HEADERS)
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

    resp = requests.put(url, headers=HEADERS, json=payload)
    resp.raise_for_status()

    return {"sha": resp.json().get("commit", {}).get("sha", "")}


def _render_article_html(article: dict) -> str:
    """Render a complete HTML page for an article."""
    title = article.get("title", "Article")
    meta_desc = article.get("meta_description", "")
    body_html = article.get("body_html", "<p>Content coming soon.</p>")
    category = article.get("category", "general")
    tags = article.get("tags", [])
    date_display = article.get("published_date_display", datetime.now().strftime("%B %d, %Y"))
    reading_time = article.get("reading_time", "5 min read")
    source_url = article.get("source_url", "")
    source_name = article.get("source_name", "")

    tags_html = "".join(f'<span class="ac-tag">{tag}</span>' for tag in tags[:4])

    cat_class_map = {
        "immigration": "immigration", "visa_bulletin": "immigration",
        "ai_tech": "ai", "cricket": "cricket",
        "movies": "movies", "layoffs": "layoffs",
    }
    cat_class = cat_class_map.get(category, "ai")
    cat_label_map = {
        "immigration": "Immigration", "visa_bulletin": "Immigration",
        "ai_tech": "AI & Tech", "cricket": "Cricket",
        "movies": "Movies & OTT", "layoffs": "Layoffs",
    }
    cat_label = cat_label_map.get(category, category.title())

    source_html = ""
    if source_url and source_name:
        source_html = f'<a href="{source_url}" target="_blank" rel="noopener" class="source-link">Source: {source_name} ↗</a>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<meta name="description" content="{meta_desc}"/>
<meta property="og:title" content="{title}"/>
<meta property="og:description" content="{meta_desc}"/>
<meta property="og:type" content="article"/>
<title>{title} | NRIBeat</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<link rel="stylesheet" href="/css/style.css"/>
<style>
.article-wrap{{max-width:760px;margin:0 auto;padding:40px 24px 60px}}
.article-eyebrow{{font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase;margin-bottom:12px}}
.article-eyebrow.{cat_class}{{color:var(--{'blue' if cat_class == 'ai' else 'green' if cat_class == 'cricket' else 'pink' if cat_class == 'movies' else 'amber' if cat_class == 'layoffs' else '74B3FF' if cat_class == 'immigration' else 'saffron'})}}
.article-wrap h1{{font-family:'DM Serif Display',serif;font-size:38px;line-height:1.15;color:var(--white);margin-bottom:16px;letter-spacing:-.4px}}
.article-meta{{font-size:12px;color:var(--white-muted);display:flex;gap:14px;flex-wrap:wrap;margin-bottom:28px;padding-bottom:20px;border-bottom:1px solid var(--navy-border)}}
.article-wrap p{{font-size:16px;color:var(--white-dim);line-height:1.8;margin-bottom:18px}}
.article-wrap h2{{font-family:'DM Serif Display',serif;font-size:26px;color:var(--white);margin:36px 0 14px}}
.article-wrap h3{{font-size:18px;font-weight:600;color:var(--white);margin:24px 0 10px}}
.article-wrap ul{{margin:0 0 18px 20px;color:var(--white-dim)}}
.article-wrap ul li{{margin-bottom:8px;font-size:15px;line-height:1.7}}
.article-wrap strong{{color:var(--white)}}
.article-wrap a{{color:var(--saffron);text-decoration:none}}
.article-wrap a:hover{{text-decoration:underline}}
.callout{{background:linear-gradient(135deg,rgba(232,102,26,.1),rgba(74,158,232,.06));border:1px solid rgba(232,102,26,.25);border-radius:12px;padding:20px 24px;margin:28px 0}}
.callout-title{{font-size:12px;font-weight:600;color:var(--saffron);letter-spacing:.6px;text-transform:uppercase;margin-bottom:8px}}
.tags-row{{display:flex;flex-wrap:wrap;gap:8px;margin-top:28px;padding-top:20px;border-top:1px solid var(--navy-border)}}
.source-link{{font-size:12px;color:var(--white-muted);text-decoration:none}}
.source-link:hover{{color:var(--white-dim)}}
@media(max-width:600px){{.article-wrap{{padding:24px 16px}}.article-wrap h1{{font-size:26px}}}}
</style>
</head>
<body>
<div class="ticker-wrap"><div class="ticker-label">Live</div><div class="ticker-track"><span>NRIBeat — Daily pulse for Indian Americans</span><span>Visa Bulletin · AI News · Cricket · Bollywood · Layoffs</span><span>NRIBeat — Daily pulse for Indian Americans</span><span>Visa Bulletin · AI News · Cricket · Bollywood · Layoffs</span></div></div>
<header><div class="header-inner"><a href="/index.html" class="logo">NRI<span class="beat">Beat</span><div class="logo-dot"></div></a><nav><a href="/index.html">Home</a><a href="/immigration.html">Immigration</a><a href="/ai-tools.html">AI & Tech</a><a href="/cricket.html">Cricket</a><a href="/movies.html">Movies</a><a href="/layoffs.html">Layoffs</a><a href="/index.html#newsletter" class="nav-cta">Get Daily Digest</a></nav><div class="hamburger" onclick="document.getElementById('mn').classList.toggle('open')"><span></span><span></span><span></span></div></div><div class="mobile-nav" id="mn"><a href="/index.html">Home</a><a href="/immigration.html">Immigration</a><a href="/ai-tools.html">AI & Tech</a><a href="/cricket.html">Cricket</a><a href="/movies.html">Movies</a><a href="/layoffs.html">Layoffs</a></div></header>

<main>
<div class="article-wrap">
  <div class="article-eyebrow {cat_class}">{cat_label}</div>
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

<footer><div class="footer-inner"><div class="footer-bottom"><span>© {datetime.now().year} NRIBeat.com · All rights reserved</span><span>Made with ❤️ for the Indian-American community</span></div></div></footer>
<script>function subscribe(){{const e=document.getElementById('emailInput').value,m=document.getElementById('subMsg');if(!e||!e.includes('@')){{m.innerHTML='<span style="color:var(--amber)">⚠ Valid email required.</span>';return}}m.innerHTML='<span style="color:var(--green)">✓ You\'re in!</span>';document.getElementById('emailInput').value=''}}</script>
</body>
</html>"""


def _update_homepage(articles: list[dict]):
    """Add new article cards to the homepage index."""
    # Generate article cards JSON for the homepage to load dynamically
    cards = []
    for a in articles:
        cards.append({
            "title": a.get("title", ""),
            "slug": a.get("slug", ""),
            "category": a.get("category", ""),
            "what_this_means": a.get("what_this_means", ""),
            "reading_time": a.get("reading_time", "5 min read"),
            "tags": a.get("tags", [])[:3],
            "date": a.get("published_date_display", ""),
            "url": f"/articles/{CATEGORY_DIRS.get(a.get('category','general'), 'general')}/{a.get('slug','')}.html"
        })

    content = json.dumps({"date": datetime.now().isoformat(), "articles": cards}, indent=2)
    _commit_file(
        path="nribeat/data/latest-articles.json",
        content=content,
        message=f"📰 Daily article update — {datetime.now().strftime('%B %d, %Y')}"
    )


def _update_article_index(articles: list[dict]):
    """Maintain a rolling index of all published articles."""
    # Try to get existing index
    index = []
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/nribeat/data/article-index.json"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        try:
            existing_content = base64.b64decode(resp.json().get("content", "")).decode("utf-8")
            existing = json.loads(existing_content)
            index = existing.get("articles", [])
        except Exception:
            pass

    # Add new articles to front
    for a in articles:
        index.insert(0, {
            "title": a.get("title", ""),
            "slug": a.get("slug", ""),
            "category": a.get("category", ""),
            "date": a.get("published_date_display", a.get("published_date", "")),
            "reading_time": a.get("reading_time", "5 min read"),
            "excerpt": a.get("what_this_means", ""),
            "tags": a.get("tags", [])[:3],
            "url": f"/articles/{CATEGORY_DIRS.get(a.get('category','general'), 'general')}/{a.get('slug','')}.html"
        })

    # Keep last 500 articles
    index = index[:500]

    content = json.dumps({"articles": index}, indent=2)
    _commit_file(
        path="nribeat/data/article-index.json",
        content=content,
        message="📚 Update article index"
    )


def _save_locally(articles: list[dict]) -> dict:
    """Save articles locally when GitHub token is not set (for testing)."""
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
        log.info(f"    Saved locally: {file_path}")

    return {
        "files_updated": len(saved),
        "errors": 0,
        "commit_sha": "local",
        "published": saved,
    }
