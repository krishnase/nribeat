"""
Article Generator
Uses Claude Haiku 4.5 via Anthropic API to write full articles.
Each article costs ~$0.006 at Haiku pricing.
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

# Category-specific writing prompts
CATEGORY_PROMPTS = {
    "immigration": """You write for NRIBeat.com, a news site for Indian professionals in the US.
Write a clear, helpful, optimistic article. Always include a "What this means for you" section.
Focus on actionable information. Avoid fear-mongering. Neutral on politics.
Format: Intro paragraph → Key facts → What this means for you → FAQ (2-3 questions) → Conclusion.""",

    "visa_bulletin": """You write Visa Bulletin analysis for NRIBeat.com for Indian green card applicants.
Be precise with dates. Explain movement in plain English. Include historical context.
Always include: current date, movement from last month, 3-month prediction, what filers should do now.
Format: Summary → Current dates table → Movement analysis → AI prediction → What to do now → FAQ.""",

    "ai_tech": """You write tech news for NRIBeat.com for Indian software engineers in the US.
Make it relevant to their careers and work. Explain what tools mean practically.
Format: What happened → Why it matters for Indian tech professionals → How to use it → Conclusion.""",

    "cricket": """You write cricket news for NRIBeat.com for Indian fans living in the US.
Include match context, key performers, series standings. Conversational and excited tone.
Format: Result/headline → Match highlights → Key performers → Series context → What's next.""",

    "movies": """You write Bollywood and OTT news for NRIBeat.com for the Indian diaspora in the US.
Include streaming platform, availability, watch worthiness. Spoiler-free for reviews.
Format: News summary → Context → Where to watch → Recommendation.""",

    "layoffs": """You write tech layoff news for NRIBeat.com. Be factual and neutral — never alarmist.
ALWAYS include a dedicated "H1B Visa Holders: What You Need to Know" section with the 60-day grace period explained.
Format: What happened → Scale and scope → H1B section → Job market context → Resources.""",
}

ARTICLE_SCHEMA = {
    "title": "SEO-optimized headline (60-70 chars)",
    "slug": "url-friendly-slug",
    "meta_description": "155 char meta description",
    "category": "category name",
    "tags": ["tag1", "tag2"],
    "reading_time": "X min read",
    "body_html": "Full article HTML with h2, h3, p, ul tags",
    "what_this_means": "2-3 sentence plain English summary",
    "published_date": "ISO date string"
}


def generate_articles(stories: list[dict]) -> list[dict]:
    """
    Generate full articles for each story using Claude Haiku.
    Returns list of article dicts ready for publishing.
    """
    articles = []

    for i, story in enumerate(stories):
        try:
            log.info(f"  Generating article {i+1}/{len(stories)}: {story['title'][:50]}...")
            article = _generate_single_article(story)
            if article:
                articles.append(article)
        except Exception as e:
            log.error(f"  Article generation failed for '{story['title'][:40]}': {e}")

    return articles


def _generate_single_article(story: dict) -> dict | None:
    """Generate a single article using Claude Haiku 4.5."""
    category = story.get("category", "ai_tech")
    system_prompt = CATEGORY_PROMPTS.get(category, CATEGORY_PROMPTS["ai_tech"])

    user_prompt = f"""Write a complete article for NRIBeat.com based on this story.

SOURCE INFORMATION:
Title: {story.get('title', '')}
Category: {category}
Source: {story.get('source', '')}
Content: {story.get('raw_content', '')[:800]}
Tags: {', '.join(story.get('tags', []))}

REQUIREMENTS:
- Length: 600-900 words
- Tone: Helpful, informative, optimistic
- No politics, no negativity beyond facts
- Include "What this means for you" section
- End with a call to action to subscribe to NRIBeat daily digest

Return ONLY valid JSON matching this exact structure:
{{
  "title": "compelling SEO headline (60-70 chars)",
  "slug": "url-slug-like-this",
  "meta_description": "155 char meta description ending with - NRIBeat",
  "tags": ["tag1", "tag2", "tag3"],
  "reading_time": "5 min read",
  "body_html": "<p>Full article HTML here...</p>",
  "what_this_means": "2-3 sentence plain English summary for the email digest"
}}"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        raw = response.content[0].text.strip()

        # Strip markdown code fences if present
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

        data = json.loads(raw)

        # Enrich with metadata
        data["category"] = category
        data["source_url"] = story.get("url", "")
        data["published_date"] = datetime.now().isoformat()
        data["published_date_display"] = datetime.now().strftime("%B %d, %Y")
        data["source_name"] = story.get("source", "")
        data["is_visa_bulletin"] = story.get("is_visa_bulletin", False)

        # Generate slug from title if not provided
        if not data.get("slug"):
            data["slug"] = slugify(data.get("title", "article"))

        return data

    except json.JSONDecodeError as e:
        log.error(f"JSON parse error: {e}. Raw: {raw[:200]}")
        return None
    except Exception as e:
        log.error(f"Claude API error: {e}")
        return None
