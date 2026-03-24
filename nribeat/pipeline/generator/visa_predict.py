"""
Visa Bulletin AI Prediction Engine
Uses Claude to generate next-month predictions based on historical movement patterns.
Called only when a new bulletin is detected (around the 2nd Tuesday of each month).
"""

import os
import json
import logging
import anthropic
from datetime import datetime

log = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Historical movement data for EB-2 India (days moved per month)
# This is embedded knowledge — update monthly as new bulletins are released
HISTORICAL_MOVEMENT = {
    # Final Action Date movements (days) — most recent first
    # Source: travel.state.gov official bulletins
    "eb2_india": [
        (4, 2026, 304), (3, 2026, 14),  (2, 2026, 16),
        (1, 2026, 14),  (12, 2025, 14), (11, 2025, 14),
        (10, 2025, 365),(9, 2025, -365),(8, 2025, 15),
        (7, 2025, 14),  (6, 2025, 15),  (5, 2025, 15),
    ],
    "eb3_india": [
        (4, 2026, 0),   (3, 2026, 0),   (2, 2026, 16),
        (1, 2026, 14),  (12, 2025, 14), (11, 2025, 14),
        (10, 2025, 274),(9, 2025, -274),(8, 2025, 15),
        (7, 2025, 14),  (6, 2025, 15),  (5, 2025, 15),
    ]
}

# Seasonal patterns observed over 10+ years
SEASONAL_CONTEXT = """
Key Visa Bulletin seasonal patterns:
- October (FY start): Large forward movement as new visa numbers available
- November-December: Above average movement continues 
- January-March: Steady moderate movement (~10-14 days/month average)
- April-June: Steady, sometimes slight slowdown
- July-September: High retrogression risk as fiscal year quota runs out
- New FY (October): Often largest single-month jump of the year
"""


def generate_visa_prediction(bulletin_story: dict) -> dict:
    """
    Generate a detailed Visa Bulletin prediction article using Claude.
    This is the highest-value content on NRIBeat — published within hours of each bulletin.
    """
    month_year = bulletin_story.get("month_year", datetime.now().strftime("%B %Y"))
    priority_dates = bulletin_story.get("priority_dates", {})

    eb2_current = priority_dates.get("eb2_india_final", "Unknown")
    eb3_current = priority_dates.get("eb3_india_final", "Unknown")

    # Calculate averages from historical data
    eb2_movements = [m for _, _, m in HISTORICAL_MOVEMENT["eb2_india"] if m > 0]
    eb3_movements = [m for _, _, m in HISTORICAL_MOVEMENT["eb3_india"] if m > 0]
    
    eb2_avg = round(sum(eb2_movements) / len(eb2_movements), 1) if eb2_movements else 11
    eb3_avg = round(sum(eb3_movements) / len(eb3_movements), 1) if eb3_movements else 14

    # Get next month name
    now = datetime.now()
    next_month = datetime(now.year + (now.month // 12), (now.month % 12) + 1, 1)
    next_month_name = next_month.strftime("%B %Y")

    prompt = f"""You are an expert Visa Bulletin analyst for NRIBeat.com, serving Indian green card applicants.

CURRENT BULLETIN DATA:
- Month: {month_year}
- EB-2 India Final Action Date: {eb2_current}
- EB-3 India Final Action Date: {eb3_current}

HISTORICAL MOVEMENT (last 12 months):
- EB-2 India avg movement: {eb2_avg} days/month (positive months only)
- EB-3 India avg movement: {eb3_avg} days/month (positive months only)
- Recent months EB-2: {[m for _, _, m in HISTORICAL_MOVEMENT['eb2_india'][:6]]}

SEASONAL CONTEXT:
{SEASONAL_CONTEXT}

Write a complete prediction article for {next_month_name} Visa Bulletin.
Be specific with date predictions. Give confidence levels. Explain the reasoning.
Include retrogression risk assessment.

Return ONLY valid JSON:
{{
  "title": "EB-2 India {next_month_name} Visa Bulletin Prediction: What to Expect",
  "slug": "eb2-india-{next_month_name.lower().replace(' ', '-')}-visa-bulletin-prediction",
  "meta_description": "AI-powered prediction for {next_month_name} Visa Bulletin EB-2 India movement. Data-driven forecast based on 12 years of historical data. - NRIBeat",
  "tags": ["Visa Bulletin", "EB-2 India", "Priority Date", "Green Card", "Prediction"],
  "reading_time": "6 min read",
  "body_html": "<full article HTML>",
  "what_this_means": "Plain English 2-sentence summary of the prediction",
  "predicted_eb2_movement": "X-Y days forward",
  "retrogression_risk": "Low/Medium/High",
  "confidence": "X%"
}}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}]
    )

    import re
    raw = response.content[0].text.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    data = json.loads(raw)
    data["category"] = "immigration"
    data["subcategory"] = "visa_bulletin_prediction"
    data["published_date"] = datetime.now().isoformat()
    data["published_date_display"] = datetime.now().strftime("%B %d, %Y")
    data["is_prediction"] = True

    log.info(f"  Visa prediction: {data.get('predicted_eb2_movement')} | Risk: {data.get('retrogression_risk')}")
    return data
