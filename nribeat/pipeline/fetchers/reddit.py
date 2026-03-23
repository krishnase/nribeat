"""
Reddit Trending Fetcher
Uses Reddit's free JSON API (no key needed for read-only).
Monitors r/immigration, r/h1b, r/f1visa, r/indiansInAmerica for trending questions.
"""

import logging
import requests
from datetime import datetime

log = logging.getLogger(__name__)

SUBREDDITS = [
    "immigration",
    "h1b",
    "f1visa",
    "USCIS",
    "IndiansinAmerica",
]

HEADERS = {
    "User-Agent": "NRIBeat/1.0 (news aggregator; contact@nribeat.com)"
}


def fetch_reddit_trending() -> list[dict]:
    """
    Fetch top posts from immigration-related subreddits.
    Reddit allows free read-only JSON access — no API key needed.
    """
    stories = []

    for subreddit in SUBREDDITS[:3]:  # Check top 3 subreddits
        try:
            url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=10"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()

            data = resp.json()
            posts = data.get("data", {}).get("children", [])

            for post in posts:
                p = post.get("data", {})

                # Skip stickied posts, pinned announcements
                if p.get("stickied") or p.get("pinned"):
                    continue

                title = p.get("title", "").strip()
                score = p.get("score", 0)
                num_comments = p.get("num_comments", 0)
                selftext = p.get("selftext", "")[:300]
                permalink = p.get("permalink", "")

                # Only pick genuinely trending posts (score > 50)
                if score < 50:
                    continue

                if _is_newsworthy(title, subreddit):
                    stories.append({
                        "category": "immigration",
                        "subcategory": "community",
                        "title": _clean_reddit_title(title),
                        "raw_content": f"Trending on r/{subreddit}: {title}. {selftext}",
                        "source": f"r/{subreddit}",
                        "url": f"https://reddit.com{permalink}",
                        "reddit_score": score,
                        "reddit_comments": num_comments,
                        "subreddit": subreddit,
                        "published_at": datetime.now().isoformat(),
                        "tags": _extract_reddit_tags(title, subreddit),
                    })

        except Exception as e:
            log.error(f"Reddit fetch error for r/{subreddit}: {e}")

    # Sort by score — highest trending first
    stories.sort(key=lambda x: x.get("reddit_score", 0), reverse=True)

    return stories[:2]  # Max 2 Reddit-inspired articles per day


def _is_newsworthy(title: str, subreddit: str) -> bool:
    """
    Filter for genuinely newsworthy or educational posts.
    Skip rants, personal venting, or low-quality posts.
    """
    title_lower = title.lower()

    # Skip personal rants
    skip_patterns = [
        "i hate", "screw", "wtf", "rant", "venting",
        "frustrated", "angry", "depressed about"
    ]
    if any(p in title_lower for p in skip_patterns):
        return False

    # Good signals — questions the community wants answered
    good_patterns = [
        "what happens", "how long", "timeline", "approved",
        "denied", "update", "tips", "advice", "guide",
        "when", "how to", "experience", "success", "finally",
        "processing time", "rfe", "noid", "interview", "lottery"
    ]
    return any(p in title_lower for p in good_patterns)


def _clean_reddit_title(title: str) -> str:
    """Clean Reddit title for use as article title."""
    import re
    # Remove common Reddit formatting artifacts
    title = re.sub(r'\[.*?\]', '', title).strip()
    # Capitalize properly
    if title and not title[0].isupper():
        title = title[0].upper() + title[1:]
    return title[:120]


def _extract_reddit_tags(title: str, subreddit: str) -> list[str]:
    tags = []
    title_lower = title.lower()

    tag_map = {
        "h1b": "H1B", "opt": "OPT", "stem opt": "STEM OPT",
        "green card": "Green Card", "i-140": "I-140", "i-485": "I-485",
        "perm": "PERM", "priority date": "Priority Date",
        "uscis": "USCIS", "rfe": "RFE", "lottery": "H1B Lottery",
        "f1": "F1 Visa", "cpt": "CPT",
    }

    for kw, tag in tag_map.items():
        if kw in title_lower:
            tags.append(tag)

    # Add subreddit as context
    if subreddit == "h1b":
        tags.insert(0, "H1B")
    elif subreddit == "f1visa":
        tags.insert(0, "F1 Visa")

    return list(dict.fromkeys(tags))[:4]  # dedupe, max 4
