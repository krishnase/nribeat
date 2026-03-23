"""
Daily Email Digest
Sends a morning digest to ConvertKit subscribers.
Uses ConvertKit's free tier (up to 1,000 subscribers free).
"""

import os
import logging
import requests
from datetime import datetime

log = logging.getLogger(__name__)

CONVERTKIT_API_KEY = os.environ.get("CONVERTKIT_API_KEY", "")
CONVERTKIT_API = "https://api.convertkit.com/v3"

# Your ConvertKit broadcast settings
SENDER_NAME = "NRIBeat"
SENDER_EMAIL = "hello@nribeat.com"

CATEGORY_EMOJI = {
    "immigration": "🛂",
    "visa_bulletin": "📅",
    "ai_tech": "🤖",
    "cricket": "🏏",
    "movies": "🎬",
    "layoffs": "💼",
}


def send_daily_digest(articles: list[dict]) -> dict:
    """Send the daily digest email to all subscribers."""
    if not CONVERTKIT_API_KEY:
        log.warning("CONVERTKIT_API_KEY not set — skipping email send")
        return {"recipients": 0, "status": "skipped"}

    subject = _build_subject(articles)
    html_body = _build_email_html(articles)
    plain_body = _build_plain_text(articles)

    try:
        broadcast_id = _create_broadcast(subject, html_body, plain_body)
        result = _send_broadcast(broadcast_id)
        log.info(f"Email digest sent: broadcast_id={broadcast_id}")
        return {"recipients": result.get("total_recipients", 0), "broadcast_id": broadcast_id}
    except Exception as e:
        log.error(f"Email send failed: {e}")
        return {"recipients": 0, "error": str(e)}


def _build_subject(articles: list[dict]) -> str:
    """Build a compelling email subject line."""
    today = datetime.now().strftime("%b %d")
    
    # Lead with the most important story
    if articles:
        first = articles[0]
        category = first.get("category", "")
        if category == "visa_bulletin" or category == "immigration":
            return f"🛂 [{today}] Visa Bulletin update + today's top NRI news"
        elif category == "cricket":
            return f"🏏 [{today}] India cricket + immigration + AI news"
    
    return f"☀️ [{today}] Your NRIBeat Morning Digest"


def _build_email_html(articles: list[dict]) -> str:
    """Build the full HTML email body."""
    today = datetime.now().strftime("%A, %B %d, %Y")
    articles_html = _render_article_cards_html(articles)

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 0; background: #0B1320; color: #F8F5F0; }}
  .wrapper {{ max-width: 600px; margin: 0 auto; padding: 0; }}
  .header {{ background: #0B1320; padding: 24px; text-align: center; border-bottom: 2px solid #E8661A; }}
  .logo {{ font-size: 28px; font-weight: 700; color: #F8F5F0; text-decoration: none; }}
  .logo span {{ color: #E8661A; }}
  .date {{ font-size: 12px; color: #7A756E; margin-top: 6px; letter-spacing: 1px; text-transform: uppercase; }}
  .content {{ padding: 24px; }}
  .article {{ background: #162440; border-radius: 10px; padding: 18px 20px; margin-bottom: 14px; border-left: 3px solid #E8661A; }}
  .article-cat {{ font-size: 10px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: #E8661A; margin-bottom: 6px; }}
  .article-title {{ font-size: 17px; font-weight: 600; color: #F8F5F0; margin-bottom: 8px; line-height: 1.35; }}
  .article-summary {{ font-size: 13px; color: #C8C2B8; line-height: 1.6; margin-bottom: 10px; }}
  .read-link {{ display: inline-block; font-size: 12px; font-weight: 600; color: #E8661A; text-decoration: none; }}
  .footer {{ background: #0B1320; padding: 24px; text-align: center; border-top: 1px solid #1E3056; }}
  .footer p {{ font-size: 12px; color: #7A756E; margin: 4px 0; }}
  .footer a {{ color: #7A756E; text-decoration: none; }}
  .section-label {{ font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: #7A756E; margin: 20px 0 10px; }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <div class="logo">NRI<span>Beat</span></div>
    <div class="date">{today}</div>
  </div>
  <div class="content">
    <div class="section-label">Today's Top Stories</div>
    {articles_html}
  </div>
  <div class="footer">
    <p>You're receiving this because you subscribed to NRIBeat Daily Digest.</p>
    <p><a href="{{{{ unsubscribe_url }}}}">Unsubscribe</a> · <a href="https://nribeat.com">nribeat.com</a></p>
    <p>© {datetime.now().year} NRIBeat.com · Made for the Indian-American community</p>
  </div>
</div>
</body>
</html>"""


def _render_article_cards_html(articles: list[dict]) -> str:
    html = ""
    for article in articles[:6]:
        category = article.get("category", "")
        emoji = CATEGORY_EMOJI.get(category, "📰")
        cat_label_map = {
            "immigration": "Immigration", "visa_bulletin": "Visa Bulletin",
            "ai_tech": "AI & Tech", "cricket": "Cricket",
            "movies": "Movies & OTT", "layoffs": "Layoffs",
        }
        cat_label = cat_label_map.get(category, category.title())
        title = article.get("title", "")
        summary = article.get("what_this_means", "")
        slug = article.get("slug", "")
        subdir = {"immigration": "immigration", "visa_bulletin": "immigration",
                  "ai_tech": "ai-tech", "cricket": "cricket",
                  "movies": "movies", "layoffs": "layoffs"}.get(category, "general")
        article_url = f"https://nribeat.com/articles/{subdir}/{slug}.html"

        html += f"""
    <div class="article">
      <div class="article-cat">{emoji} {cat_label}</div>
      <div class="article-title">{title}</div>
      <div class="article-summary">{summary}</div>
      <a href="{article_url}" class="read-link">Read full article →</a>
    </div>"""

    return html


def _build_plain_text(articles: list[dict]) -> str:
    today = datetime.now().strftime("%B %d, %Y")
    lines = [f"NRIBeat Daily Digest — {today}", "=" * 50, ""]

    for article in articles[:6]:
        lines.append(f"• {article.get('title', '')}")
        lines.append(f"  {article.get('what_this_means', '')}")
        lines.append("")

    lines.append("Read more at nribeat.com")
    lines.append("To unsubscribe: {{ unsubscribe_url }}")
    return "\n".join(lines)


def _create_broadcast(subject: str, html_body: str, plain_body: str) -> str:
    """Create a draft broadcast on ConvertKit."""
    resp = requests.post(
        f"{CONVERTKIT_API}/broadcasts",
        json={
            "api_secret": CONVERTKIT_API_KEY,
            "subject": subject,
            "content": html_body,
            "description": f"NRIBeat Daily Digest — {datetime.now().strftime('%B %d, %Y')}",
            "email_layout_template": "none",
        },
        timeout=15
    )
    resp.raise_for_status()
    return resp.json()["broadcast"]["id"]


def _send_broadcast(broadcast_id: str) -> dict:
    """Send an existing broadcast immediately."""
    resp = requests.post(
        f"{CONVERTKIT_API}/broadcasts/{broadcast_id}/send",
        json={"api_secret": CONVERTKIT_API_KEY},
        timeout=15
    )
    resp.raise_for_status()
    return resp.json()
