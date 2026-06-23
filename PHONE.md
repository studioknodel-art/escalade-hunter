# 📱 Updating Escalade Hunter from your phone

Everything lives on GitHub and the site **auto-deploys after every push**, so you
never need your computer. Any change committed to the repo goes live on its own.

---

## ✏️ Make changes (add features, tweak criteria, fix things)

Use **Claude Code on the web** — works right in your phone's browser, no Mac needed.

1. Open **https://claude.ai/code** and sign in
2. Connect **GitHub** if prompted and open the **`studioknodel-art/escalade-hunter`** repo
3. Just type what you want in plain English, e.g.:
   - "Change the search radius to 150 miles"
   - "Lower the price ceiling to $63,000"
   - "Add a dealer-fees field to the finance calculator"

Claude edits the files, commits, and pushes. The bot auto-deploys the site in ~2 min.

---

## 🔄 Force a search run right now (don't wait 6 hours)

1. Go to **https://github.com/studioknodel-art/escalade-hunter** in your phone browser
   (or the **GitHub mobile app**)
2. Tap the **Actions** tab
3. Tap **Escalade Hunter** → **Run workflow** → **Run workflow**

New matches will hit Discord and the site within a minute or two.

---

## ⚡ Edit one value fast (no Claude needed)

1. On github.com, open the file (e.g. `src/search.py`)
2. Tap the ✏️ pencil icon → make the edit → **Commit changes**

Common values in `src/search.py` near the top:
- `RADII` — search distances (currently `[25, 50, 100]`)
- `year_min` — oldest model year (currently `2022`)
- `price_max` — budget ceiling (currently `65000`)
- `miles_max` — mileage cap (currently `75000`)
- `NEAR_MISS_PRICE_MAX` — upper limit for "near miss" listings (currently `75000`)

---

## 🔑 Update API key or Discord webhook

github.com → repo → **Settings** → **Secrets and variables** → **Actions**
- `MARKETCHECK_API_KEY`
- `DISCORD_WEBHOOK_URL`

---

## 🔗 Quick links

- **Live site:** https://studioknodel-art.github.io/escalade-hunter/
- **Repo:** https://github.com/studioknodel-art/escalade-hunter
- **Run a search / view logs:** https://github.com/studioknodel-art/escalade-hunter/actions

---

## Reference

| I want to… | Where |
|---|---|
| Make code/feature changes | claude.ai/code (browser) |
| Force a search run now | github.com → Actions → Run workflow |
| Edit a single value fast | github.com → open file → ✏️ → commit |
| Update API keys / Discord webhook | github.com → Settings → Secrets → Actions |
| See what the bot found | the live site, or Discord |

> Note: the regular Claude chat app can *discuss* the repo, but for actually
> editing-and-pushing code, **claude.ai/code** is the tool that has the file +
> git capabilities built in.
