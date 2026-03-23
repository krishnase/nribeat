# NRIBeat.com — Daily Pulse for Indian Americans

A fully static, production-ready website for the Indian-American community covering:
- 🛂 Visa Bulletin & Immigration (H1B, OPT, Green Card)
- 🤖 AI & Tech News
- 🏏 Cricket
- 🎬 Bollywood & OTT
- 💼 Tech Layoffs (with H1B Grace Period guides)

## Pages
| File | Page |
|------|------|
| `index.html` | Homepage |
| `visa-bulletin.html` | Visa Bulletin Dashboard + AI Predictor |
| `immigration.html` | Immigration Hub & Guides |
| `ai-tools.html` | AI Tools Finder with Filters |
| `cricket.html` | Cricket Hub with Live Scores |
| `movies.html` | Movies & OTT Calendar |
| `layoffs.html` | Tech Layoffs Tracker |
| `article.html` | Article Template |
| `css/style.css` | Shared Stylesheet |

## Deploy to GitHub Pages

1. Push this repo to GitHub
2. Go to **Settings → Pages**
3. Set Source to **Deploy from a branch**
4. Select **main** branch, **/ (root)** folder
5. Click **Save** — your site will be live at `https://yourusername.github.io/nribeat/`

## Deploy to Custom Domain (nribeat.com)

1. In GitHub Pages settings, add custom domain: `nribeat.com`
2. At your domain registrar (Namecheap), add these DNS records:
   - `A` record: `@` → `185.199.108.153`
   - `A` record: `@` → `185.199.109.153`
   - `A` record: `@` → `185.199.110.153`
   - `A` record: `@` → `185.199.111.153`
   - `CNAME` record: `www` → `yourusername.github.io`
3. Enable **Enforce HTTPS** in GitHub Pages settings

## Next Steps (Automation)
- Connect ConvertKit for newsletter signups
- Add Google Analytics (replace `GA_MEASUREMENT_ID` in each page)
- Set up Python automation pipeline to auto-update content daily
- Replace placeholder affiliate links in `ai-tools.html`
- Add Ezoic/AdSense ad units in the `ad-placeholder` divs

## Tech Stack
- Pure HTML + CSS + Vanilla JS (no frameworks, no build step)
- Google Fonts: DM Serif Display, DM Sans, JetBrains Mono
- Fully responsive — mobile, tablet, desktop
- Dark theme with saffron accent color system

---
Made with ❤️ for the Indian-American community · NRIBeat.com
