#!/usr/bin/env python3
"""
NRIBeat Static Content Audit
Scans all HTML pages for hardcoded/stale content that should be dynamic.
Run: python pipeline/tests/test_static_content.py
"""

import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup
from datetime import datetime

SITE_DIR = Path(__file__).parent.parent.parent
PAGES = [
    "index.html",
    "cricket.html",
    "immigration.html",
    "layoffs.html",
    "movies.html",
    "ai-tools.html",
    "visa-bulletin.html",
    "article.html",
]

# ── Test definitions ────────────────────────────────────────────────────────
# Each test: (name, pattern, allow_in_scripts, pages, severity)
# severity: FAIL = must fix, WARN = should fix

TESTS = [
    # Hardcoded old years in visible text
    ("old_copyright_year", r"© 202[0-4]", False, "all", "FAIL"),

    # Hardcoded month + year combos
    ("hardcoded_nov_2025", r"November\s+2025", False, "all", "FAIL"),
    ("hardcoded_oct_2025", r"October\s+2025", False, "all", "FAIL"),
    ("hardcoded_dec_2025", r"December\s+2025", False, "all", "FAIL"),
    ("hardcoded_month_2025", r"(January|February|March|April|May|June|July|August|September)\s+2025", False, "all", "WARN"),

    # Hardcoded fake subscriber counts
    ("fake_subscriber_count", r"12,400\s+NRIs", False, "all", "WARN"),
    ("fake_subscriber_count2", r"8,200\s+green card", False, "all", "WARN"),

    # Hardcoded cricket scores
    ("hardcoded_cricket_score", r"IND\s+3\d\d/\d|AUS\s+\d+", False, ["cricket.html"], "FAIL"),
    ("hardcoded_match_day", r"Day\s+[0-9]\s+Live", False, ["cricket.html"], "FAIL"),

    # Hardcoded visa bulletin dates in non-script content
    ("hardcoded_eb2_date", r"Jan\s+01,\s+2013", False, "all", "FAIL"),
    ("hardcoded_eb3_date", r"Feb\s+15,\s+2013", False, "all", "FAIL"),
    ("hardcoded_vb_movement", r"\+15\s+days|\+22\s+days|\+30\s+days", False, "all", "FAIL"),

    # Hardcoded immigration stats
    ("hardcoded_immigration_stat", r"Nov\s+2025\s*<br\s*/>Movement", False, ["immigration.html"], "FAIL"),

    # Hardcoded OTT calendar date
    ("hardcoded_ott_date", r"November\s+11.{1,5}17,\s*2025", False, ["movies.html"], "FAIL"),

    # Hardcoded layoffs tracker dates
    ("hardcoded_layoff_nov2025", r"Nov\s+2025.*3,600", False, ["layoffs.html"], "FAIL"),

    # Hardcoded "2 hours ago" / "5 hours ago" style timestamps
    ("hardcoded_relative_time", r"\d+\s+hrs?\s+ago|\d+\s+hours?\s+ago", False, "all", "WARN"),
    ("hardcoded_yesterday", r">Yesterday\s+·", False, "all", "WARN"),

    # News headlines that are clearly hardcoded sample data
    ("hardcoded_stree3", r"Stree\s+3\s+Officially\s+Confirmed", False, "all", "WARN"),
    ("hardcoded_kohli89", r"Kohli.{1,20}89\s+Seals", False, "all", "WARN"),
    ("hardcoded_gpt5", r"OpenAI.{1,20}GPT-5\s+Is\s+Here", False, "all", "WARN"),
    ("hardcoded_meta_layoffs", r"Meta\s+Confirms\s+3,600", False, "all", "WARN"),

    # Hardcoded "Next bulletin" date
    ("hardcoded_next_bulletin", r"Next bulletin.*December\s+10", False, "all", "FAIL"),

    # Copyright year not current
    ("copyright_not_dynamic", r"©\s+2025\s+NRIBeat", False, "all", "FAIL"),
]

# ── Allowed static pages (tools, FAQ, guides — intentionally static) ──────
STATIC_OK_PAGES = {"ai-tools.html"}  # curated tools, static is intentional


def get_visible_text_and_html(page_path: Path):
    """Return raw HTML (for regex) and visible text (for context)."""
    html = page_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    # Remove script and style tags for visible-text checks
    for tag in soup(["script", "style"]):
        tag.decompose()

    visible = soup.get_text(separator=" ")
    return html, visible


def run_tests():
    failures = []
    warnings = []
    passes = []

    current_year = datetime.now().year

    for page_name in PAGES:
        page_path = SITE_DIR / page_name
        if not page_path.exists():
            print(f"  SKIP  {page_name} (not found)")
            continue

        html, visible = get_visible_text_and_html(page_path)

        for test_name, pattern, allow_in_scripts, target_pages, severity in TESTS:
            # Check if this test applies to this page
            if target_pages != "all" and page_name not in target_pages:
                continue
            if page_name in STATIC_OK_PAGES:
                continue

            # Search in visible text (scripts stripped)
            text_to_search = visible
            matches = re.findall(pattern, text_to_search, re.IGNORECASE)

            if matches:
                msg = f"[{severity}] {page_name} :: {test_name} — found: {matches[0]!r}"
                if severity == "FAIL":
                    failures.append(msg)
                else:
                    warnings.append(msg)
            else:
                passes.append(f"[PASS] {page_name} :: {test_name}")

    return failures, warnings, passes


def main():
    print("\n" + "="*60)
    print("NRIBeat Static Content Audit")
    print("="*60 + "\n")

    failures, warnings, passes = run_tests()

    print(f"PASSED: {len(passes)}")
    print(f"WARNINGS: {len(warnings)}")
    print(f"FAILURES: {len(failures)}\n")

    if warnings:
        print("── WARNINGS (should fix) ─────────────────────────────────")
        for w in warnings:
            print(" ", w)
        print()

    if failures:
        print("── FAILURES (must fix) ───────────────────────────────────")
        for f in failures:
            print(" ", f)
        print()

    if not failures and not warnings:
        print("All checks passed! No static content detected.")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
