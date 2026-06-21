# 🚙 Escalade Hunter

Automated bot that searches for a **Cadillac Escalade ESV** matching specific criteria and sends **Discord notifications** when new matches appear. Runs on GitHub Actions — no computer needed.

---

## Search Criteria

| Field | Value |
|---|---|
| Vehicle | Cadillac Escalade ESV |
| Year | 2023 or newer |
| Trim | Sport Platinum (preferred) or Premium Platinum |
| Price | $65,000 or less |
| Mileage | 60,000 miles or less |
| Drivetrain | 4WD or AWD |
| Required Features | Super Cruise, Rear Seat Entertainment |
| Title | Clean only |
| Primary Search Radius | 25 miles from 75032 |
| Fallback Radius | 50 miles if no results at 25 miles |
| Check Frequency | Every 6 hours |

## Deal Rating Scale

| Rating | Meaning |
|---|---|
| 🏆 PLATINUM DEAL | 15%+ below market median |
| ⭐ BEST DEAL | 10–15% below market median |
| 👍 GOOD DEAL | 5–10% below market median |
| ✅ OKAY DEAL | 0–5% below market median |
| ⚠️ ABOVE MARKET | Above market median |

Market median comes from MarketCheck's price statistics for the same year/model.

---

## Setup Instructions

### Step 1 — Create the GitHub repo

1. Go to [github.com](https://github.com) and sign in
2. Click the **+** icon → **New repository**
3. Name it `escalade-hunter`
4. Set it to **Public** (required for free GitHub Pages hosting)
5. **Do not** initialize with a README (you already have files to upload)
6. Click **Create repository**

### Step 2 — Upload these files

You can either use Git on your computer or use GitHub's web interface:

**Option A — GitHub web upload (easiest):**
1. On your new empty repo page, click **uploading an existing file**
2. Drag and drop ALL files from this folder maintaining the folder structure
3. Commit them

**Option B — Git command line:**
```bash
cd escalade-hunter
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/escalade-hunter.git
git push -u origin main
```

### Step 3 — Get a MarketCheck API key

1. Go to [marketcheck.com](https://www.marketcheck.com/api-portal)
2. Sign up for a free account
3. Create an API key (free tier: 1,000 calls/day — more than enough at 6-hour intervals)
4. Copy your API key

### Step 4 — Create a Discord webhook

1. Open Discord and go to the server/channel where you want alerts
2. Click the gear icon on the channel → **Integrations** → **Webhooks**
3. Click **New Webhook**, give it a name like "Escalade Hunter"
4. Click **Copy Webhook URL**
5. Save that URL

### Step 5 — Add secrets to GitHub

1. In your GitHub repo, go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add these two:

| Secret Name | Value |
|---|---|
| `MARKETCHECK_API_KEY` | Your MarketCheck API key |
| `DISCORD_WEBHOOK_URL` | Your Discord webhook URL |

### Step 6 — Test it manually

1. In your repo, go to **Actions** tab
2. Click **Escalade Hunter** in the left sidebar
3. Click **Run workflow** → **Run workflow**
4. Watch it run — you should see output in the logs within a minute

After that, it runs automatically every 6 hours.

---

## Notes on Super Cruise & RSE Detection

MarketCheck listings come from dealer feeds which vary in detail. Super Cruise and Rear Seat Entertainment will be flagged as **✅ confirmed** when the keywords appear in the listing description or options. If they show **⚠️ unconfirmed**, it doesn't mean the car lacks those features — it means the dealer's listing didn't mention them. Always verify on the VDP (vehicle detail page) before contacting the dealer.

For a 2023+ Escalade ESV Sport Platinum or Premium Platinum, both Super Cruise and RSE are standard equipment, so any matching trim is very likely to have them.

---

## Files

```
escalade-hunter/
├── .github/
│   └── workflows/
│       └── search.yml       # GitHub Actions schedule
├── data/
│   └── seen_listings.json   # Tracks already-alerted listings (auto-updated)
├── src/
│   └── search.py            # Main search + notification script
├── requirements.txt
└── README.md
```
