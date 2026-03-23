# NRIBeat Automation Pipeline

Fully automated content pipeline for nribeat.com.
Runs daily at 5 AM EST via GitHub Actions — zero manual work after setup.

## What it does every morning

1. **Fetches** real data from:
   - `travel.state.gov` — Visa Bulletin PDF (scraped automatically)
   - `NewsAPI.org` — AI and tech headlines
   - `ESPN Cricinfo RSS` — India cricket news (free, no key needed)
   - `Reddit` — Trending r/h1b, r/immigration posts (free, no key needed)
   - `Bollywood Hungama RSS` — OTT and movie news (free)

2. **Filters** stories:
   - Removes political content automatically
   - Removes excessive negativity
   - Deduplicates similar stories (TF-IDF cosine similarity)
   - Balances categories (max 3 per category)

3. **Generates** articles with Claude Haiku 4.5 (~$0.006/article)
   - Category-specific prompts for each section
   - Always includes "What this means for you"
   - Layoff articles always include H1B grace period section

4. **Publishes** to GitHub:
   - Commits HTML files to your repo
   - Updates `data/latest-articles.json` for the homepage
   - GitHub Pages auto-deploys

5. **Sends** daily digest email via ConvertKit

---

## Setup (15 minutes)

### Step 1: Add pipeline folder to your nribeat repo

Copy this entire `pipeline/` folder into your nribeat GitHub repo root.

### Step 2: Add GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | Value | Where to get it |
|-------------|-------|-----------------|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | console.anthropic.com → API Keys |
| `NEWS_API_KEY` | your key | newsapi.org (free tier) |
| `CONVERTKIT_API_KEY` | your secret | app.convertkit.com → Settings → API |

`GITHUB_TOKEN` is automatic — GitHub provides it, no action needed.

### Step 3: Enable GitHub Actions

The workflow file is at `.github/workflows/daily-pipeline.yml`.
It runs automatically at 5 AM EST every day.

To test it immediately:
1. Go to your repo → **Actions** tab
2. Click **NRIBeat Daily Pipeline**
3. Click **Run workflow** → set `dry_run: false` → **Run workflow**

### Step 4: Get free API keys (5 minutes)

**NewsAPI.org** (free, 100 requests/day):
- Go to newsapi.org → Register → Copy your API key
- Free tier is enough for the pipeline

**ConvertKit** (free up to 1,000 subscribers):
- Go to app.convertkit.com → Sign up
- Settings → API → Copy your API Secret
- Skip this for now if you don't have subscribers yet

---

## Costs

| Service | Cost |
|---------|------|
| Claude Haiku 4.5 API (8 articles/day) | ~$0.05/day = ~$1.50/month |
| NewsAPI (free tier) | $0 |
| ConvertKit (free tier) | $0 |
| GitHub Actions (free tier) | $0 |
| **Total** | **~$1.50/month** |

---

## File structure

```
pipeline/
├── pipeline.py              # Main orchestrator
├── requirements.txt
├── fetchers/
│   ├── visa_bulletin.py     # Scrapes travel.state.gov
│   ├── news.py              # NewsAPI + RSS fallback
│   ├── cricket.py           # ESPN Cricinfo RSS
│   ├── reddit.py            # Reddit trending (no key needed)
│   └── movies.py            # Bollywood RSS feeds
├── filters/
│   └── content_filter.py    # Political/negativity/dedup filter
├── generator/
│   ├── article_gen.py       # Claude Haiku article writer
│   └── visa_predict.py      # Visa Bulletin AI predictor
└── publisher/
    ├── github_publisher.py  # Commits HTML to GitHub
    └── email_digest.py      # ConvertKit email sender
```

---

## Monitoring

Pipeline logs are saved as GitHub Actions artifacts for 7 days.
Check the Actions tab in your repo to see each run's output.

Cost monitoring: Check `console.anthropic.com/settings/usage` — 
create a separate API key named `nribeat-pipeline` to track costs separately
from your Aitoolprice.com usage.
