"""
Content Filter
Removes political content, overly negative stories, duplicates.
NRIBeat rule: positive, neutral, helpful tone only.
"""

import re
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

log = logging.getLogger(__name__)

# ── POLITICAL BLOCKLIST ───────────────────────────────────────
# Stories containing these are automatically skipped
POLITICAL_BLOCKLIST = [
    # US Politics
    "trump", "biden", "democrat", "republican", "congress", "senate",
    "white house", "president biden", "president trump", "maga",
    "election", "ballot", "partisan", "gop", "dnc", "rnc",
    # India Politics
    "modi", "bjp", "congress party", "aap", "rahul gandhi",
    "arvind kejriwal", "lok sabha", "rajya sabha", "election commission",
    # Inflammatory
    "racism", "discrimination lawsuit", "hate crime", "protest riot",
    "deport", "mass deportation", "immigration ban",
    # Religion (avoid religious controversy)
    "hindu vs", "muslim vs", "christian vs", "religion controversy",
]

# ── NEGATIVITY PATTERNS ───────────────────────────────────────
# These signal overly negative content we want to skip
NEGATIVITY_PATTERNS = [
    r'\b(disaster|catastrophe|crisis|meltdown|collapse|crash)\b',
    r'\b(scam|fraud|corrupt|scandal|arrested|indicted)\b',
    r'\b(death toll|killed|murdered|shooting|attack)\b',
    r'\b(worst ever|terrible|horrible|awful|disgusting)\b',
]

# ── QUALITY SIGNALS ───────────────────────────────────────────
MIN_TITLE_LENGTH = 20   # Skip very short titles
MAX_TITLE_LENGTH = 200  # Skip truncated/broken titles
MIN_CONTENT_LENGTH = 50 # Skip stories with almost no content


def filter_stories(stories: list[dict]) -> list[dict]:
    """
    Apply all filters to the raw stories list.
    Returns clean, deduplicated, non-political, non-negative stories.
    """
    if not stories:
        return []

    original_count = len(stories)
    filtered = []

    for story in stories:
        title = story.get("title", "")
        content = story.get("raw_content", "")
        combined = (title + " " + content).lower()

        # 1. Title quality check
        if not _passes_title_check(title):
            log.debug(f"  Filtered (title quality): {title[:50]}")
            continue

        # 2. Political content check
        if _is_political(combined):
            log.debug(f"  Filtered (political): {title[:50]}")
            continue

        # 3. Negativity check (but allow neutral layoff reporting)
        if _is_too_negative(combined) and story.get("category") != "layoffs":
            log.debug(f"  Filtered (negative): {title[:50]}")
            continue

        # 4. Content length check
        if len(content) < MIN_CONTENT_LENGTH:
            log.debug(f"  Filtered (too short): {title[:50]}")
            continue

        filtered.append(story)

    # 5. Deduplication — remove near-identical stories
    filtered = _deduplicate(filtered)

    # 6. Category balance — don't flood with one category
    filtered = _balance_categories(filtered)

    log.info(f"  Filter: {original_count} → {len(filtered)} stories")
    return filtered


def _passes_title_check(title: str) -> bool:
    if not title:
        return False
    if len(title) < MIN_TITLE_LENGTH:
        return False
    if len(title) > MAX_TITLE_LENGTH:
        return False
    # Skip clickbait-y all-caps titles
    if title.isupper():
        return False
    return True


def _is_political(text: str) -> bool:
    """Check if text contains political content we want to avoid."""
    return any(keyword in text for keyword in POLITICAL_BLOCKLIST)


def _is_too_negative(text: str) -> bool:
    """Check if text is excessively negative."""
    negativity_count = 0
    for pattern in NEGATIVITY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            negativity_count += 1
    return negativity_count >= 2  # Allow single negative words, block multiple


def _deduplicate(stories: list[dict]) -> list[dict]:
    """Remove near-duplicate stories using TF-IDF cosine similarity."""
    if len(stories) <= 1:
        return stories

    try:
        titles = [s.get("title", "") for s in stories]
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        tfidf_matrix = vectorizer.fit_transform(titles)
        similarity_matrix = cosine_similarity(tfidf_matrix)

        keep = [True] * len(stories)
        for i in range(len(stories)):
            if not keep[i]:
                continue
            for j in range(i + 1, len(stories)):
                if similarity_matrix[i][j] > 0.7:  # 70% similar = duplicate
                    # Keep the one with more content
                    if len(stories[j].get("raw_content", "")) > len(stories[i].get("raw_content", "")):
                        keep[i] = False
                    else:
                        keep[j] = False

        return [s for s, k in zip(stories, keep) if k]

    except Exception as e:
        log.error(f"Deduplication error: {e}")
        return stories  # Return undeduped if sklearn fails


def _balance_categories(stories: list[dict], max_per_category: int = 3) -> list[dict]:
    """
    Ensure no single category dominates.
    Max 3 stories per category, prioritizing immigration and visa bulletin.
    """
    category_counts = {}
    balanced = []

    # Always keep visa bulletin first
    for story in stories:
        if story.get("is_visa_bulletin"):
            balanced.append(story)

    # Then fill other categories
    for story in stories:
        if story.get("is_visa_bulletin"):
            continue
        cat = story.get("category", "other")
        count = category_counts.get(cat, 0)
        if count < max_per_category:
            balanced.append(story)
            category_counts[cat] = count + 1

    return balanced
