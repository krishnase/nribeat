from __future__ import annotations
"""
Monetization Engine
Injects two revenue streams into every published article:

1. AFFILIATE LINKS — contextual links to relevant products/services.
   Each category has curated affiliate partners with real commission rates.
   Links are injected inline at first keyword occurrence + a "Resources" section.

2. GOOGLE ADSENSE SLOTS — three ad placements per article.
   Slots are strategic: after intro, mid-content, before footer.
   Requires ADSENSE_CLIENT_ID and ADSENSE_SLOT_IDs set as env vars.

FTC Compliance: All affiliate links carry rel="nofollow sponsored" and
the article gets an affiliate disclosure banner injected automatically.

Revenue model:
  - Immigration articles: $50-200/referral (Boundless, CitizenPath)
  - Tech articles: $10-45/referral (Udemy, Coursera, LinkedIn)
  - Cricket/Movies: $5-15/referral (Hotstar, Willow TV)
  - Money transfers: $15-30/referral (Remitly, Wise)
  - AdSense: $2-8 RPM at scale (paid per 1,000 impressions)
"""

import os
import re
import logging

log = logging.getLogger(__name__)

ADSENSE_CLIENT_ID = os.environ.get("ADSENSE_CLIENT_ID", "")
ADSENSE_SLOTS = {
    "intro":  os.environ.get("ADSENSE_SLOT_INTRO", ""),
    "middle": os.environ.get("ADSENSE_SLOT_MIDDLE", ""),
    "footer": os.environ.get("ADSENSE_SLOT_FOOTER", ""),
}

# ── AFFILIATE LINK DATABASE ───────────────────────────────────────────────────
# Format: {trigger_keyword_lower: {url, label, category, commission_note}}
# Links use tracking params — replace XXXXX with your actual affiliate IDs.

AFFILIATE_DB = {
    # ── IMMIGRATION ──────────────────────────────────────────────────────────
    "boundless": {
        "url": "https://www.boundless.com/?ref=nribeat",
        "label": "Boundless Immigration Services",
        "category": "immigration",
        "note": "$100-200/referral",
    },
    "citizenpath": {
        "url": "https://citizenpath.com/?ref=nribeat",
        "label": "CitizenPath DIY Immigration",
        "category": "immigration",
        "note": "$30-75/referral",
    },
    "immigration attorney": {
        "url": "https://www.boundless.com/attorneys/?ref=nribeat",
        "label": "Find an Immigration Attorney",
        "category": "immigration",
        "note": "$100/referral",
    },
    "i-485": {
        "url": "https://citizenpath.com/i-485-package/?ref=nribeat",
        "label": "I-485 Filing Guide",
        "category": "immigration",
        "note": "$30/referral",
    },
    "remitly": {
        "url": "https://www.remitly.com/us/en/india?referral=nribeat",
        "label": "Remitly — Send Money to India",
        "category": "immigration",
        "note": "$20/referral, first transfer fee-free for referrals",
    },
    "wise": {
        "url": "https://wise.com/invite/nribeat",
        "label": "Wise — Best Exchange Rates to India",
        "category": "immigration",
        "note": "$15/referral",
    },
    # ── AI & TECH ────────────────────────────────────────────────────────────
    "udemy": {
        "url": "https://www.udemy.com/?utm_source=nribeat&utm_medium=affiliate",
        "label": "Udemy — Top AI & Coding Courses",
        "category": "ai_tech",
        "note": "15% commission",
    },
    "coursera": {
        "url": "https://www.coursera.org/?utm_source=nribeat",
        "label": "Coursera — Google AI Certificate",
        "category": "ai_tech",
        "note": "$45/referral",
    },
    "linkedin premium": {
        "url": "https://www.linkedin.com/premium/products/?ref=nribeat",
        "label": "LinkedIn Premium — Accelerate Your Job Search",
        "category": "ai_tech",
        "note": "$20/referral",
    },
    "github copilot": {
        "url": "https://github.com/features/copilot?utm_source=nribeat",
        "label": "GitHub Copilot — AI Pair Programmer",
        "category": "ai_tech",
        "note": "10% commission",
    },
    "nordvpn": {
        "url": "https://nordvpn.com/referral/?ref=nribeat",
        "label": "NordVPN — Access Indian Content from the US",
        "category": "ai_tech",
        "note": "$50-100/referral",
    },
    # ── CRICKET & SPORTS ────────────────────────────────────────────────────
    "willow tv": {
        "url": "https://www.willow.tv/?ref=nribeat",
        "label": "Willow TV — Watch India Cricket Live in the US",
        "category": "cricket",
        "note": "$5/referral",
    },
    "hotstar": {
        "url": "https://www.hotstar.com/us?ref=nribeat",
        "label": "Hotstar US — IPL, Cricket & Bollywood",
        "category": "cricket",
        "note": "$8/referral",
    },
    "disney+ hotstar": {
        "url": "https://www.hotstar.com/us?ref=nribeat",
        "label": "Disney+ Hotstar US",
        "category": "cricket",
        "note": "$8/referral",
    },
    # ── MOVIES & OTT ────────────────────────────────────────────────────────
    "zee5": {
        "url": "https://www.zee5.com/?ref=nribeat",
        "label": "ZEE5 — Stream Bollywood Movies & Shows",
        "category": "movies",
        "note": "$5/referral",
    },
    "aha": {
        "url": "https://www.aha.video/?ref=nribeat",
        "label": "aha — Telugu & Tamil OTT",
        "category": "movies",
        "note": "$4/referral",
    },
    # ── LAYOFFS / CAREER ────────────────────────────────────────────────────
    "topresume": {
        "url": "https://www.topresume.com/?ref=nribeat",
        "label": "TopResume — Professional Resume Writing",
        "category": "layoffs",
        "note": "$30/referral",
    },
    "levels.fyi": {
        "url": "https://www.levels.fyi/?ref=nribeat",
        "label": "Levels.fyi — Tech Salary Data",
        "category": "layoffs",
        "note": "CPC model",
    },
    "h1b transfer": {
        "url": "https://www.boundless.com/h1b/?ref=nribeat",
        "label": "H1B Transfer Guide + Attorney Help",
        "category": "layoffs",
        "note": "$150/referral",
    },
}

# Category → top 3 affiliate picks shown in "Resources" section
CATEGORY_TOP_AFFILIATES = {
    "immigration": [
        "boundless", "citizenpath", "remitly",
    ],
    "visa_bulletin": [
        "boundless", "citizenpath", "wise",
    ],
    "ai_tech": [
        "udemy", "coursera", "linkedin premium",
    ],
    "cricket": [
        "willow tv", "hotstar", "nordvpn",
    ],
    "movies": [
        "hotstar", "zee5", "nordvpn",
    ],
    "layoffs": [
        "h1b transfer", "linkedin premium", "topresume",
    ],
}

DISCLOSURE_HTML = """<div class="affiliate-disclosure" style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:8px;padding:10px 14px;margin:20px 0;font-size:12px;color:var(--white-muted);line-height:1.5">
<strong style="color:var(--white)">Disclosure:</strong> NRIBeat may earn a commission from links in this article at no extra cost to you. We only recommend services we believe in.
</div>"""


def inject_monetization(article: dict) -> dict:
    """
    Main entry point. Injects affiliate links and ad slots into an article.
    Returns the article with enriched body_html.
    """
    body_html = article.get("body_html", "")
    category = article.get("category", "general")

    if not body_html:
        return article

    # 1. Inject AdSense slots
    body_html = _inject_adsense_slots(body_html)

    # 2. Inject inline affiliate links (contextual, first occurrence only)
    body_html = _inject_inline_affiliates(body_html, category)

    # 3. Append "Useful Resources" section
    body_html = _append_resources_section(body_html, category)

    # 4. Prepend affiliate disclosure
    body_html = DISCLOSURE_HTML + body_html

    article["body_html"] = body_html
    article["has_monetization"] = True
    return article


def _inject_adsense_slots(body_html: str) -> str:
    """
    Insert three AdSense responsive ad units at strategic positions.
    Position 1: after 2nd </p> tag (after intro)
    Position 2: after the middle </p> tag
    Position 3: before the last </h2> or </p> block

    Falls back gracefully if ADSENSE_CLIENT_ID is not configured.
    """
    if not ADSENSE_CLIENT_ID:
        # Inject placeholder slots — will become real ads after AdSense approval
        return _inject_placeholder_ad_slots(body_html)

    ad_unit = lambda slot_key: (
        f'<div class="ad-unit" style="margin:28px 0;text-align:center">'
        f'<ins class="adsbygoogle" style="display:block" '
        f'data-ad-client="{ADSENSE_CLIENT_ID}" '
        f'data-ad-slot="{ADSENSE_SLOTS.get(slot_key, "")}" '
        f'data-ad-format="auto" data-full-width-responsive="true"></ins>'
        f'<script>(adsbygoogle=window.adsbygoogle||[]).push({{}});</script>'
        f'</div>'
    )

    paragraphs = [m.end() for m in re.finditer(r'</p>', body_html, re.IGNORECASE)]

    if len(paragraphs) < 4:
        return body_html

    # After 2nd paragraph
    intro_pos = paragraphs[1]
    body_html = body_html[:intro_pos] + "\n" + ad_unit("intro") + "\n" + body_html[intro_pos:]

    # Re-find positions after insertion
    paragraphs = [m.end() for m in re.finditer(r'</p>', body_html, re.IGNORECASE)]
    mid_idx = len(paragraphs) // 2
    if mid_idx < len(paragraphs):
        mid_pos = paragraphs[mid_idx]
        body_html = body_html[:mid_pos] + "\n" + ad_unit("middle") + "\n" + body_html[mid_pos:]

    # Before last heading/paragraph block
    last_h2 = list(re.finditer(r'<h2', body_html, re.IGNORECASE))
    if last_h2:
        insert_pos = last_h2[-1].start()
        body_html = body_html[:insert_pos] + ad_unit("footer") + "\n" + body_html[insert_pos:]

    return body_html


def _inject_placeholder_ad_slots(body_html: str) -> str:
    """
    Inject <!-- AD SLOT --> HTML comments when AdSense is not yet active.
    These are instantly swappable for real <ins> tags after approval.
    """
    placeholder = (
        '<div class="ad-slot-placeholder" '
        'style="background:rgba(255,255,255,.03);border:1px dashed rgba(255,255,255,.08);'
        'border-radius:8px;height:90px;display:flex;align-items:center;justify-content:center;'
        'margin:24px 0;font-size:11px;color:rgba(255,255,255,.2);letter-spacing:.6px;'
        'text-transform:uppercase">Ad Slot — Pending AdSense Approval</div>'
    )

    paragraphs = [m.end() for m in re.finditer(r'</p>', body_html, re.IGNORECASE)]
    if len(paragraphs) < 3:
        return body_html

    # Insert after 2nd paragraph
    pos = paragraphs[1]
    body_html = body_html[:pos] + "\n" + placeholder + body_html[pos:]

    # Insert mid-article
    paragraphs = [m.end() for m in re.finditer(r'</p>', body_html, re.IGNORECASE)]
    mid_pos = paragraphs[len(paragraphs) // 2]
    body_html = body_html[:mid_pos] + "\n" + placeholder + body_html[mid_pos:]

    return body_html


def _inject_inline_affiliates(body_html: str, category: str) -> str:
    """
    Replace first occurrence of affiliate trigger keywords with hyperlinked versions.
    Only replaces if not already inside an <a> tag.
    Max 2 inline injections per article to avoid over-linking.
    """
    injected_count = 0
    max_injections = 2

    for trigger, data in AFFILIATE_DB.items():
        if injected_count >= max_injections:
            break

        # Only inject category-matching affiliates
        if data["category"] not in (category, "immigration") and data["category"] != category:
            if category not in ("immigration", "visa_bulletin") or data["category"] != "immigration":
                continue

        # Find first occurrence of trigger (case-insensitive, not already in <a>)
        pattern = re.compile(
            r'(?<!href=["\'])(?<!</a>)\b(' + re.escape(trigger) + r')\b',
            re.IGNORECASE,
        )

        # Skip if keyword is already a link
        if re.search(rf'href="[^"]*{re.escape(trigger[:10])}', body_html, re.IGNORECASE):
            continue

        new_link = (
            f'<a href="{data["url"]}" '
            f'rel="nofollow sponsored noopener" '
            f'target="_blank" '
            f'title="{data["label"]}" '
            f'class="affiliate-link">'
            r'\1</a>'
        )

        new_body, count = pattern.subn(new_link, body_html, count=1)
        if count > 0:
            body_html = new_body
            injected_count += 1
            log.debug(f"  Injected affiliate: {trigger} → {data['url'][:40]}")

    return body_html


def _append_resources_section(body_html: str, category: str) -> str:
    """
    Append a styled "Useful Resources" section with 2-3 curated affiliate links.
    This section is clearly labeled — transparent, not deceptive.
    """
    top_keys = CATEGORY_TOP_AFFILIATES.get(category, [])
    if not top_keys:
        return body_html

    items_html = ""
    for key in top_keys:
        aff = AFFILIATE_DB.get(key)
        if not aff:
            continue
        items_html += (
            f'<li style="margin-bottom:8px">'
            f'<a href="{aff["url"]}" '
            f'rel="nofollow sponsored noopener" target="_blank" '
            f'class="affiliate-link" style="color:var(--saffron);font-weight:500">'
            f'{aff["label"]}</a>'
            f'</li>\n'
        )

    if not items_html:
        return body_html

    resources_html = f"""
<div class="resources-section" style="background:var(--navy-card);border:1px solid var(--navy-border);border-radius:12px;padding:20px 24px;margin:32px 0">
  <div style="font-size:12px;font-weight:600;letter-spacing:.6px;text-transform:uppercase;color:var(--white-muted);margin-bottom:12px">Useful Resources</div>
  <ul style="margin:0;padding-left:18px;color:var(--white-dim);font-size:14px;line-height:1.8">
{items_html}  </ul>
  <p style="font-size:11px;color:var(--white-muted);margin:10px 0 0">Affiliate links — NRIBeat may earn a small commission at no cost to you.</p>
</div>"""

    return body_html + resources_html


def get_email_affiliate_block(category: str) -> str:
    """
    Generate an affiliate block for the email digest.
    One sponsored link per email, clearly labeled.
    """
    top_keys = CATEGORY_TOP_AFFILIATES.get(category, [])
    if not top_keys:
        return ""

    key = top_keys[0]
    aff = AFFILIATE_DB.get(key)
    if not aff:
        return ""

    return (
        f'<div style="background:#1a2d4e;border-radius:8px;padding:14px 16px;'
        f'margin:16px 0;border-left:3px solid #E8661A">'
        f'<div style="font-size:10px;font-weight:700;letter-spacing:1px;'
        f'text-transform:uppercase;color:#7A756E;margin-bottom:6px">Sponsored</div>'
        f'<a href="{aff["url"]}" style="font-size:14px;font-weight:600;'
        f'color:#F8F5F0;text-decoration:none" target="_blank">'
        f'{aff["label"]} →</a>'
        f'</div>'
    )
