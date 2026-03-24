from __future__ import annotations
"""
Article Generator
Uses Claude Haiku 4.5 via Anthropic API to write full SEO-optimized articles.
Each article costs ~$0.006 at Haiku pricing (~$0.05/day for 8 articles).

SEO enhancements vs v1:
- Trending keyword injection into prompts
- Explicit word count targets (800-1000 for SEO sweet spot)
- FAQ section requested in every article (triggers FAQPage schema)
- Search-intent framing (informational / transactional)
- Year injected into prompts for freshness signals
"""

import os
import re
import json
import logging
import anthropic
from datetime import datetime
from slugify import slugify

log = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

CURRENT_YEAR = datetime.now().year
CURRENT_MONTH = datetime.now().strftime("%B")

# ── CATEGORY SYSTEM PROMPTS ────────────────────────────────────────────────────
# Each prompt is tuned for SEO search intent specific to that category.

CATEGORY_PROMPTS = {
    "immigration": f"""You are the lead immigration editor at NRIBeat.com, a trusted news source for Indian professionals in the US.

VOICE & TONE: Clear, helpful, reassuring. Never alarmist. Focus on actionable steps.
AUDIENCE: Indian H1B holders, green card applicants, OPT students in the US.
SEO GOAL: Rank for informational immigration queries ("how to", "what happens", "timeline").

ARTICLE STRUCTURE (follow exactly):
1. Intro paragraph — answer the main question immediately (Google featured snippet target)
2. ## What You Need to Know — 3-5 bullet points of key facts
3. ## [Topic-specific heading] — detailed explanation
4. ## What This Means for You — personalized impact section
5. ## Step-by-Step Guide / Timeline (if applicable)
6. ## Frequently Asked Questions — 3 Q&A pairs, questions MUST end with "?"
7. ## Conclusion — brief summary + CTA to subscribe to NRIBeat

FORMAT: Use <h2> for sections, <h3> for sub-sections, <p> for paragraphs, <ul>/<li> for lists.
LENGTH: 850-1000 words. Longer articles rank better for complex immigration topics.
FRESHNESS: Reference {CURRENT_YEAR} wherever relevant.""",

    "visa_bulletin": f"""You are the Visa Bulletin analyst at NRIBeat.com — the #1 resource for EB-2/EB-3 India priority date analysis.

VOICE & TONE: Precise, data-driven, expert. Use exact dates and numbers.
AUDIENCE: Indian EB-2/EB-3 green card applicants tracking priority dates.
SEO GOAL: Rank for "[Month Year] Visa Bulletin EB-2 India" and prediction queries.

ARTICLE STRUCTURE (follow exactly):
1. Intro — summarize the bulletin movement in 2 sentences (featured snippet target)
2. ## {CURRENT_MONTH} {CURRENT_YEAR} Priority Dates — data table in HTML
3. ## How Much Did EB-2 India Move? — movement analysis with historical comparison
4. ## EB-3 India Update — separate analysis
5. ## AI Prediction: Next Month Movement — specific prediction with confidence %
6. ## What To Do If Your Date Is Current — actionable checklist
7. ## Frequently Asked Questions — 3 Q&A pairs about THIS bulletin
8. ## Conclusion

FORMAT: Use HTML tables for date data. Bold all dates.
LENGTH: 900-1100 words. This is high-value content — be thorough.""",

    "ai_tech": f"""You are the tech editor at NRIBeat.com, writing for Indian software engineers in the US.

VOICE & TONE: Practical, enthusiastic about tools, career-focused. Not hype — real utility.
AUDIENCE: Indian software engineers, data scientists, and tech PMs at US companies.
SEO GOAL: Rank for "best AI tools for [use case]" and career impact queries.

ARTICLE STRUCTURE (follow exactly):
1. Intro — what happened and why it matters (2-3 sentences, featured snippet)
2. ## What Is [Tool/News] and Why Should You Care?
3. ## How Indian Tech Professionals Are Using This
4. ## Hands-On: How to Get Started (step-by-step if tool-related)
5. ## Career Impact: Will This Affect Your Job?
6. ## Frequently Asked Questions — 3 Q&A pairs
7. ## Bottom Line

FORMAT: Use code blocks if showing commands. Bullet lists for features.
LENGTH: 800-950 words.""",

    "cricket": f"""You are the cricket correspondent at NRIBeat.com for the Indian diaspora in the US.

VOICE & TONE: Passionate, conversational, knowledgeable. Write like you're talking to a cricket-mad friend.
AUDIENCE: Indian cricket fans in the US who often miss matches due to time zones.
SEO GOAL: Rank for "India cricket [match/series] highlights" and "watch India cricket US" queries.

ARTICLE STRUCTURE (follow exactly):
1. Intro — match result or top headline (one punchy sentence)
2. ## Match Summary — full scorecard context
3. ## Key Performers — standout players with stats
4. ## Turning Point — the moment that decided the match
5. ## Series Standing & What's Next
6. ## How to Watch India Cricket in the US — always include this section
7. ## Frequently Asked Questions — 3 Q&A pairs

FORMAT: Use <strong> for player names and stats.
LENGTH: 700-850 words.""",

    "movies": f"""You are the entertainment editor at NRIBeat.com covering Bollywood and Indian OTT.

VOICE & TONE: Enthusiastic, spoiler-free for reviews, helpful for where-to-watch.
AUDIENCE: Indian diaspora in the US who want to stay connected to Indian cinema.
SEO GOAL: Rank for "new Bollywood movies Netflix/Prime" and "Indian movies streaming USA" queries.

ARTICLE STRUCTURE (follow exactly):
1. Intro — what's releasing/what happened (news summary)
2. ## The Story / What to Expect (no spoilers)
3. ## Where to Watch in the US — platform, subscription cost
4. ## Worth Watching? — clear recommendation
5. ## More Indian Content This Week — 2-3 related picks
6. ## Frequently Asked Questions — 3 Q&A pairs
7. ## Conclusion

FORMAT: Bold platform names. Include subscription costs where known.
LENGTH: 700-850 words.""",

    "layoffs": f"""You are the tech layoffs reporter at NRIBeat.com. Factual, neutral, and highly useful for H1B visa holders.

VOICE & TONE: Calm, informative, never alarmist. Always solution-focused.
AUDIENCE: Indian tech workers on H1B visas who are directly affected or at risk.
SEO GOAL: Rank for "[Company] layoffs H1B" and "tech layoffs {CURRENT_YEAR} H1B impact" queries.

ARTICLE STRUCTURE (follow exactly):
1. Intro — who, what, when, scale (facts only, no speculation)
2. ## What Happened — full factual breakdown
3. ## Scale and Scope — numbers, departments, locations
4. ## H1B Visa Holders: What You Need to Know — THIS IS THE MOST IMPORTANT SECTION
   - The 60-day grace period explained
   - Immediate steps to take
   - H1B transfer process
   - If no new job in 60 days: options
5. ## Job Market Context — is this isolated or industry-wide?
6. ## Resources and Next Steps — job boards, attorneys, support
7. ## Frequently Asked Questions — 3 Q&A pairs, at least 1 must be H1B-related
8. ## Conclusion

FORMAT: Use a prominent callout box for the 60-day grace period.
LENGTH: 900-1050 words. This content saves people's immigration status — be thorough.""",
}

# ── ARTICLE OUTPUT SCHEMA ─────────────────────────────────────────────────────

ARTICLE_SCHEMA = {
    "title": "SEO headline (55-70 chars, include primary keyword and year)",
    "slug": "url-slug-like-this",
    "meta_description": "155 chars, include primary keyword, end with — NRIBeat",
    "tags": ["Primary Keyword", "Secondary", "Brand Tag", "Long-tail"],
    "reading_time": "X min read",
    "body_html": "Full article HTML — h2, h3, p, ul, li, strong, table",
    "what_this_means": "2-3 sentence plain English summary (used in email digest)",
    "published_date": "ISO datetime",
}


def generate_articles(stories: list[dict], trends: dict = None) -> list[dict]:
    """
    Generate full SEO-optimized articles for each story using Claude Haiku.
    trends: optional dict from fetchers/trends.py to enrich prompts.
    Returns list of article dicts ready for publishing.
    """
    articles = []

    for i, story in enumerate(stories):
        try:
            log.info(f"  [{i+1}/{len(stories)}] Generating: {story['title'][:55]}...")
            article = _generate_single_article(story, trends)
            if article:
                articles.append(article)
                log.info(f"    -> '{article['title'][:55]}' | {article.get('reading_time', '?')} | SEO queued")
        except Exception as e:
            log.error(f"  Article generation failed: {story.get('title', '')[:40]} | {e}")

    return articles


def _generate_single_article(story: dict, trends: dict = None) -> dict | None:
    """Generate a single article using Claude Haiku 4.5."""
    category = story.get("category", "ai_tech")
    system_prompt = CATEGORY_PROMPTS.get(category, CATEGORY_PROMPTS["ai_tech"])

    # Build trending keyword context for this category
    trend_context = ""
    if trends:
        from fetchers.trends import get_top_keywords_for_category
        top_kws = get_top_keywords_for_category(trends, category, n=3)
        if top_kws:
            trend_context = (
                f"\nTRENDING KEYWORDS TO INCORPORATE (people are searching for these right now):\n"
                + "\n".join(f"  - {kw}" for kw in top_kws)
                + "\nNaturally weave these into the title, intro, and headings for maximum search visibility.\n"
            )

    user_prompt = f"""Write a complete, SEO-optimized article for NRIBeat.com based on this story.

SOURCE:
Title: {story.get('title', '')}
Category: {category}
Source outlet: {story.get('source', '')}
Content: {story.get('raw_content', '')[:900]}
Tags hint: {', '.join(story.get('tags', []))}
{trend_context}
TODAY: {datetime.now().strftime('%B %d, %Y')}

SEO REQUIREMENTS:
- Title: 55-70 characters, include primary keyword + {CURRENT_YEAR} if relevant
- Must have a Frequently Asked Questions section with 3 questions ending in "?"
- First paragraph must directly answer the main question (featured snippet strategy)
- Include at least one HTML list (<ul>/<li>) for scannable content
- Minimum 850 words — longer articles rank for more long-tail keywords

Return ONLY valid JSON (no markdown fences, no extra text):
{{
  "title": "headline 55-70 chars with primary keyword",
  "slug": "url-slug-with-primary-keyword",
  "meta_description": "155 char description with keyword — NRIBeat",
  "tags": ["Primary Keyword", "tag2", "tag3", "tag4"],
  "reading_time": "5 min read",
  "body_html": "<p>Full article HTML starting here...</p>",
  "what_this_means": "2-3 sentence summary for email digest subscribers"
}}"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = response.content[0].text.strip()
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

        data = json.loads(raw)

        # Enrich with pipeline metadata
        data["category"] = category
        data["source_url"] = story.get("url", "")
        data["source_name"] = story.get("source", "")
        data["published_date"] = datetime.now().isoformat()
        data["published_date_display"] = datetime.now().strftime("%B %d, %Y")
        data["is_visa_bulletin"] = story.get("is_visa_bulletin", False)

        if not data.get("slug"):
            data["slug"] = slugify(data.get("title", "article"))

        # Word count sanity check
        body_text = re.sub(r'<[^>]+>', '', data.get("body_html", ""))
        data["word_count"] = len(body_text.split())
        if data["word_count"] < 400:
            log.warning(f"    Short article ({data['word_count']} words): {data['title'][:50]}")

        return data

    except json.JSONDecodeError as e:
        log.error(f"  JSON parse error: {e} | Raw[:200]: {raw[:200]}")
        return None
    except anthropic.APIError as e:
        log.error(f"  Anthropic API error: {e}")
        return None
    except Exception as e:
        log.error(f"  Unexpected error: {e}")
        return None
