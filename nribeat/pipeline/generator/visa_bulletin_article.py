from __future__ import annotations
"""
Visa Bulletin Article Generator
Auto-generates the monthly Visa Bulletin article HTML from fetched bulletin data.
Called by publish_visa_bulletin_data() — no manual step needed.

Covers both:
  - Final Action Dates (FAD)  — when USCIS will approve your green card
  - Dates for Filing  (DFF)  — when you can file I-485 / EAD / AP early
"""

import logging
from datetime import datetime

log = logging.getLogger(__name__)


def generate_visa_bulletin_article(vb_data: dict, prev_data: dict | None = None) -> dict:
    """
    Generate a complete article dict for the current month's Visa Bulletin.

    Args:
        vb_data:   output from fetch_visa_bulletin() with priority_dates, month_year, url
        prev_data: previous month's visa-bulletin.json dict (for movement calculation)

    Returns an article dict compatible with _render_article_html() + article-index.json.
    """
    month_year = vb_data.get("month_year", datetime.now().strftime("%B %Y"))
    dates = vb_data.get("priority_dates", {})
    source_url = vb_data.get("url", "https://travel.state.gov")

    # ── Final Action Dates ──────────────────────────────────────────────────
    eb2_fad = dates.get("eb2_india_final", "—")
    eb3_fad = dates.get("eb3_india_final", "—")
    eb1_fad = dates.get("eb1_india_final", "Current")

    # ── Dates for Filing ────────────────────────────────────────────────────
    eb2_dff = dates.get("eb2_india_filing", "")
    eb3_dff = dates.get("eb3_india_filing", "")
    eb1_dff = dates.get("eb1_india_filing", "Current")
    dff_authorized = bool(eb2_dff or eb3_dff)

    # ── Movement vs previous month ──────────────────────────────────────────
    prev = prev_data or {}
    eb2_fad_move = _calc_movement(eb2_fad,  prev.get("eb2_india_final"))
    eb3_fad_move = _calc_movement(eb3_fad,  prev.get("eb3_india_final"))
    eb2_dff_move = _calc_movement(eb2_dff,  prev.get("eb2_india_filing"))
    eb3_dff_move = _calc_movement(eb3_dff,  prev.get("eb3_india_filing"))

    slug = f"{month_year.lower().replace(' ', '-')}-visa-bulletin-eb2-india-priority-date"
    title = (
        f"{month_year} Visa Bulletin: EB-2 India Final Action Date "
        f"{_title_suffix(eb2_fad_move)} to {eb2_fad}"
    )
    meta_desc = (
        f"{month_year} Visa Bulletin: EB-2 India Final Action Date {eb2_fad_move['label']} to {eb2_fad}. "
        f"EB-3 India Final Action {eb3_fad_move['label']} to {eb3_fad}. "
        f"{'DFF chart authorized. ' if dff_authorized else ''}"
        f"Full analysis — NRIBeat"
    )
    what_this_means = (
        f"{month_year} Visa Bulletin: EB-2 India Final Action Date {eb2_fad_move['label']} to {eb2_fad}; "
        f"EB-3 India to {eb3_fad}. "
        + (f"Dates for Filing: EB-2 {eb2_dff}, EB-3 {eb3_dff}. " if dff_authorized else "DFF chart not authorized this month. ")
        + _current_advice(eb2_fad_move, eb2_fad)
    )

    body_html = _render_body(
        month_year, eb2_fad, eb3_fad, eb1_fad,
        eb2_dff, eb3_dff, eb1_dff, dff_authorized,
        eb2_fad_move, eb3_fad_move, eb2_dff_move, eb3_dff_move,
        source_url,
    )

    return {
        "title": title,
        "slug": slug,
        "category": "immigration",
        "subcategory": "visa_bulletin",
        "meta_description": meta_desc,
        "body_html": body_html,
        "tags": ["Visa Bulletin", "EB-2 India", "EB-3 India",
                 "Final Action Date", "Dates for Filing", month_year],
        "reading_time": "5 min read",
        "published_date": datetime.now().isoformat(),
        "published_date_display": datetime.now().strftime("%B %d, %Y"),
        "source_url": source_url,
        "source_name": "travel.state.gov",
        "seo_score": 88,
        "what_this_means": what_this_means,
        "is_visa_bulletin": True,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_vb_date(s: str) -> datetime | None:
    """Parse 'November 22, 2014' → datetime. Returns None on failure / 'Current'."""
    if not s or s in ("—", "C", "U", "Current", ""):
        return None
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


def _calc_movement(current: str, previous: str | None) -> dict:
    """Compare two date strings; return movement dict."""
    cur  = _parse_vb_date(current)
    prev = _parse_vb_date(previous) if previous else None
    if cur is None or prev is None:
        return {"days": 0, "label": "updated", "arrow": "—", "pill_class": "move-same"}
    delta = (cur - prev).days
    if delta > 0:
        return {"days": delta,  "label": f"advances +{delta} days",
                "arrow": f"▲ +{delta} days", "pill_class": "move-up"}
    if delta < 0:
        return {"days": delta, "label": f"retrogresses {abs(delta)} days",
                "arrow": f"▼ {abs(delta)} days", "pill_class": "move-down"}
    return {"days": 0, "label": "holds steady", "arrow": "— No change", "pill_class": "move-same"}


def _title_suffix(move: dict) -> str:
    if move["days"] > 0:
        return f"Advances +{move['days']} Days"
    if move["days"] < 0:
        return "Retrogresses"
    return "Holds Steady"


def _current_advice(move: dict, date_str: str) -> str:
    if move["days"] > 0:
        return f"If your priority date is on or before {date_str}, you are now current — contact your attorney."
    if move["days"] < 0:
        return "Retrogression this month — check with your attorney if your date was previously current."
    return "No movement this month — monitor the next bulletin closely."


def _date_card(label: str, date_val: str, move: dict, accent: str = "var(--saffron)") -> str:
    arrow_color = (
        "var(--green)" if move["pill_class"] == "move-up"
        else "var(--pink)" if move["pill_class"] == "move-down"
        else "var(--amber)"
    )
    display = date_val if date_val else "Not authorized"
    return (
        f'<div style="background:var(--navy-card);border:1px solid var(--navy-border);'
        f'border-radius:10px;padding:16px;text-align:center;border-top:3px solid {accent}">'
        f'<div style="font-size:11px;font-weight:600;color:var(--white-muted);text-transform:uppercase;letter-spacing:.4px;margin-bottom:6px">{label}</div>'
        f'<div style="font-family:\'DM Serif Display\',serif;font-size:17px;color:var(--white);margin-bottom:6px">{display}</div>'
        f'<div style="font-size:12px;color:{arrow_color};font-weight:600">{move["arrow"]}</div>'
        f'</div>'
    )


def _date_gap(date_a: str, date_b: str) -> str:
    a = _parse_vb_date(date_a)
    b = _parse_vb_date(date_b)
    if a and b:
        return str(abs((a - b).days))
    return "some"


def _render_body(
    month_year: str,
    eb2_fad: str, eb3_fad: str, eb1_fad: str,
    eb2_dff: str, eb3_dff: str, eb1_dff: str,
    dff_authorized: bool,
    eb2_fad_move: dict, eb3_fad_move: dict,
    eb2_dff_move: dict, eb3_dff_move: dict,
    source_url: str,
) -> str:
    """Render full article body with clearly separated FAD and DFF sections."""

    eb1_display = "Current" if eb1_fad in ("C", "Current") else eb1_fad
    eb1_dff_display = "Current" if eb1_dff in ("C", "Current", "") else eb1_dff

    dff_status_note = (
        "<strong>USCIS has authorized the Dates for Filing chart this month.</strong> "
        "You may be able to file your I-485 / EAD / Advance Parole using the dates below, "
        "even if the Final Action Date has not yet been reached."
        if dff_authorized else
        "<strong>USCIS has NOT authorized the Dates for Filing chart this month.</strong> "
        "Only the Final Action Dates (above) apply. "
        "Check <a href='https://www.uscis.gov' target='_blank' rel='noopener'>USCIS.gov</a> each month."
    )

    # ── FAD cards ──
    fad_cards = (
        _date_card("EB-2 India · Final Action Date", eb2_fad, eb2_fad_move, "var(--saffron)") +
        _date_card("EB-3 India · Final Action Date", eb3_fad, eb3_fad_move, "var(--green)") +
        _date_card("EB-1 India · Final Action Date", eb1_display,
                   {"days": 0, "arrow": "Advancing", "pill_class": "move-same"}, "var(--blue)")
    )

    # ── DFF cards ──
    if dff_authorized:
        dff_cards = (
            _date_card("EB-2 India · Dates for Filing", eb2_dff, eb2_dff_move, "var(--saffron)") +
            _date_card("EB-3 India · Dates for Filing", eb3_dff, eb3_dff_move, "var(--green)") +
            _date_card("EB-1 India · Dates for Filing", eb1_dff_display,
                       {"days": 0, "arrow": "Current", "pill_class": "move-same"}, "var(--blue)")
        )
    else:
        dff_cards = (
            '<div style="grid-column:1/-1;padding:20px;text-align:center;'
            'color:var(--white-muted);font-size:14px">'
            'Dates for Filing chart not authorized by USCIS for this month.</div>'
        )

    callout = _current_advice(eb2_fad_move, eb2_fad)
    dff_gap = _date_gap(eb2_dff, eb2_fad) if dff_authorized and eb2_dff else "N/A"

    body = f"""
<p>The U.S. Department of State has released the <strong>{month_year} Visa Bulletin</strong>.
For EB-2 India, the <strong>Final Action Date {eb2_fad_move['label']}</strong> to <strong>{eb2_fad}</strong>.
EB-3 India Final Action Date {eb3_fad_move['label']} to <strong>{eb3_fad}</strong>.
{"The Dates for Filing chart has been authorized by USCIS this month." if dff_authorized else "USCIS has not authorized the Dates for Filing chart this month."}</p>

<div class="callout">
  <div class="callout-title">Key Takeaway for {month_year}</div>
  <p style="margin:0;font-size:14px">{callout}</p>
</div>

<h2>Table A — Final Action Dates (FAD)</h2>
<p>The <strong>Final Action Date</strong> is the hard cutoff. Your I-485 adjustment of status (or immigrant visa) can only be <em>approved</em> once your priority date is on or before this date and a visa number is available. This is the date that determines when your green card is actually granted.</p>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0">
  {fad_cards}
</div>

<h2>Table B — Dates for Filing (DFF)</h2>
<p>The <strong>Dates for Filing</strong> is an <em>earlier</em> date that, when USCIS authorizes it, lets you <strong>file your I-485, EAD (work permit), and Advance Parole</strong> before your Final Action Date is reached. Filing earlier means getting work authorization and travel documents sooner — even though your green card won't be approved until the FAD is current. <strong>USCIS decides each month whether to authorize this chart.</strong></p>
<div style="background:rgba(232,102,26,.08);border:1px solid rgba(232,102,26,.25);border-radius:10px;padding:14px 18px;margin:12px 0 20px;font-size:13px;color:var(--white-dim)">{dff_status_note}</div>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:0 0 20px">
  {dff_cards}
</div>
{"<p>The Dates for Filing for EB-2 India (<strong>" + eb2_dff + "</strong>) is approximately <strong>" + dff_gap + " days ahead</strong> of the Final Action Date — meaning eligible applicants can file I-485 that much earlier and get EAD/AP while waiting for FAD to catch up.</p>" if dff_authorized and eb2_dff else ""}

<h2>FAD vs DFF — What Is the Difference?</h2>
<table>
  <tr><th>Concept</th><th>Final Action Date (FAD)</th><th>Dates for Filing (DFF)</th></tr>
  <tr><td>What it controls</td><td>Green card <strong>approval</strong></td><td>I-485 <strong>filing</strong> eligibility</td></tr>
  <tr><td>Who sets it</td><td>U.S. Department of State</td><td>U.S. Department of State</td></tr>
  <tr><td>Who authorizes use</td><td>Always applies</td><td>USCIS must authorize each month</td></tr>
  <tr><td>Benefit if current</td><td>Green card granted</td><td>Can file I-485 + get EAD &amp; Advance Parole earlier</td></tr>
  <tr><td>EB-2 India this month</td><td><strong>{eb2_fad}</strong></td><td><strong>{"Not authorized" if not dff_authorized else (eb2_dff or "—")}</strong></td></tr>
  <tr><td>EB-3 India this month</td><td><strong>{eb3_fad}</strong></td><td><strong>{"Not authorized" if not dff_authorized else (eb3_dff or "—")}</strong></td></tr>
</table>

<h2>What This Movement Means for Your Case</h2>
<p>EB-2 India Final Action Date is advancing roughly <strong>15–20 days per month</strong> in normal months, translating to 6–8 months of progress per year. If your priority date is within 18–24 months of the current FAD, start preparing now: ensure your I-140 is approved, I-485 medical (Form I-693) is current, and employer sponsorship is active.</p>
<p>For applicants with priority dates after 2016, the wait remains long. Use the <a href="/visa-bulletin.html">NRIBeat AI-powered predictor</a> to estimate your specific timeline. The October fiscal year reset typically delivers the year's largest single-month jump.</p>

<h2>EB-2 vs EB-3 India: Which Is Ahead?</h2>
<p>This month, EB-2 India FAD ({eb2_fad}) is approximately {_date_gap(eb2_fad, eb3_fad)} days ahead of EB-3 India FAD ({eb3_fad}). If you hold an advanced degree, upgrading from EB-3 to EB-2 may be worth discussing with your attorney — but category changes have significant implications for your I-140 and PERM. Never switch without comprehensive legal advice.</p>

<h3>Frequently Asked Questions</h3>
<h3>What is the EB-2 India Final Action Date for {month_year}?</h3>
<p>The EB-2 India Final Action Date for {month_year} is <strong>{eb2_fad}</strong> — {eb2_fad_move['label']} from the previous month.</p>

<h3>What is the EB-2 India Dates for Filing for {month_year}?</h3>
<p>{"The EB-2 India Dates for Filing for " + month_year + " is <strong>" + eb2_dff + "</strong> — " + eb2_dff_move['label'] + " from the previous month. USCIS has authorized use of this chart." if dff_authorized and eb2_dff else "USCIS has not authorized the Dates for Filing chart for " + month_year + ". Only the Final Action Date applies this month."}</p>

<h3>What is the EB-3 India Final Action Date for {month_year}?</h3>
<p>The EB-3 India Final Action Date for {month_year} is <strong>{eb3_fad}</strong> — {eb3_fad_move['label']} from the previous month.</p>

<h3>Can I file my I-485 this month using Dates for Filing?</h3>
<p>{"Yes — USCIS has authorized the DFF chart for " + month_year + ". If your priority date is on or before <strong>" + eb2_dff + "</strong> (EB-2) or <strong>" + eb3_dff + "</strong> (EB-3), you may be eligible to file I-485 this month and receive your EAD and Advance Parole while waiting for the FAD to become current." if dff_authorized and eb2_dff else "No — USCIS has not authorized the Dates for Filing chart for " + month_year + ". You can only file I-485 if your priority date is on or before the Final Action Date."}</p>

<h3>When will my EB-2 India priority date become current?</h3>
<p>Use the <a href="/visa-bulletin.html">NRIBeat AI-powered predictor</a> to get a personalized estimate based on your specific priority date and category.</p>

<p><em>Source: <a href="{source_url}" target="_blank" rel="noopener">U.S. Department of State Visa Bulletin</a> · Last updated {datetime.now().strftime("%B %d, %Y")}</em></p>
"""
    return body.strip()
