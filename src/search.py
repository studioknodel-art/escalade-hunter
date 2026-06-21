"""
Cadillac Escalade ESV Hunter
Searches MarketCheck API for matching listings and sends Discord notifications.
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ── Configuration ─────────────────────────────────────────────────────────────

MARKETCHECK_API_KEY = os.environ["MARKETCHECK_API_KEY"]
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

SEARCH_ZIP = "75032"
RADII = [25, 50]

CRITERIA = {
    "make": "Cadillac",
    "model": "Escalade ESV",
    "year_min": 2023,
    "price_max": 65000,
    "miles_max": 60000,
    "trims": ["Sport Platinum", "Premium Luxury Platinum", "Premium Platinum"],
    "drivetrain": ["4WD", "AWD"],
}

REQUIRED_KEYWORDS = {
    "super_cruise": ["super cruise"],
    "rear_entertainment": [
        "rear seat entertainment",
        "second row entertainment",
        "rear entertainment",
        "rse",
        "rear video",
        "rear screen",
    ],
}

SEEN_FILE     = Path(__file__).parent.parent / "data" / "seen_listings.json"
LISTINGS_FILE = Path(__file__).parent.parent / "docs" / "listings.json"

DEAL_TIERS = [
    (15, "🏆 PLATINUM DEAL", 0x7B2D8B),
    (10, "⭐ BEST DEAL",     0x00AA44),
    (5,  "👍 GOOD DEAL",     0x3399FF),
    (0,  "✅ OKAY DEAL",     0xFFA500),
]

COLOR_HEX = {
    0x7B2D8B: "#7B2D8B",
    0x00AA44: "#00AA44",
    0x3399FF: "#3399FF",
    0xFFA500: "#FFA500",
    0xFF3333: "#FF3333",
}

# ── Field helpers (MarketCheck nests vehicle specs inside "build") ─────────────

def _build(listing: dict) -> dict:
    return listing.get("build") or {}

def get_year(l):         return _build(l).get("year") or l.get("year")
def get_make(l):         return _build(l).get("make") or l.get("make", "Cadillac")
def get_model(l):        return _build(l).get("model") or l.get("model", "Escalade ESV")
def get_trim(l):         return _build(l).get("trim") or l.get("trim", "")
def get_drivetrain(l):   return _build(l).get("drivetrain") or l.get("drivetrain", "")
def get_transmission(l): return _build(l).get("transmission") or l.get("transmission", "")
def get_engine(l):       return _build(l).get("engine") or l.get("engine", "")
def get_fuel(l):         return _build(l).get("fuel_type") or l.get("fuel_type", "")
def get_city(l):         return (l.get("dealer") or {}).get("city") or l.get("city", "")
def get_state(l):        return (l.get("dealer") or {}).get("state") or l.get("state", "")

# ── Persistence ────────────────────────────────────────────────────────────────

def load_seen() -> set:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()

def save_seen(seen: set) -> None:
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(sorted(seen), indent=2))

def load_listings() -> list[dict]:
    if LISTINGS_FILE.exists():
        return json.loads(LISTINGS_FILE.read_text())
    return []

def save_listings(listings: list[dict]) -> None:
    LISTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    LISTINGS_FILE.write_text(json.dumps(listings, indent=2))

# ── Deal rating ────────────────────────────────────────────────────────────────

def deal_label(asking: float, market_median: float) -> tuple[str, int]:
    if market_median <= 0:
        return "✅ OKAY DEAL", 0xFFA500
    pct_below = (market_median - asking) / market_median * 100
    for threshold, label, color in DEAL_TIERS:
        if pct_below >= threshold:
            return label, color
    return "⚠️ ABOVE MARKET", 0xFF3333

# ── Feature detection ──────────────────────────────────────────────────────────

def check_required_features(listing: dict) -> dict[str, bool]:
    searchable = " ".join([
        listing.get("seller_comments") or "",
        json.dumps(listing.get("media") or {}),
        listing.get("heading") or "",
        json.dumps(_build(listing)),
    ]).lower()

    return {
        key: any(kw in searchable for kw in keywords)
        for key, keywords in REQUIRED_KEYWORDS.items()
    }

def is_clean_title(listing: dict) -> bool:
    # Use Carfax field if available, otherwise text-scan
    if listing.get("carfax_clean_title") is True:
        return True
    if listing.get("carfax_clean_title") is False:
        return False
    dirty = ["salvage", "rebuilt", "flood", "lemon", "fire", "hail", "junk", "branded"]
    return not any(f in json.dumps(listing).lower() for f in dirty)

# ── API calls ──────────────────────────────────────────────────────────────────

def fetch_listings(radius: int) -> list[dict]:
    url = "https://mc-api.marketcheck.com/v2/search/car/active"
    params = {
        "api_key":   MARKETCHECK_API_KEY,
        "make":      CRITERIA["make"],
        "model":     CRITERIA["model"],
        "year_min":  CRITERIA["year_min"],
        "price_max": CRITERIA["price_max"],
        "miles_max": CRITERIA["miles_max"],
        "zip":       SEARCH_ZIP,
        "radius":    radius,
        "rows":      50,
        "start":     0,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("listings", [])

def fetch_market_stats(year: int) -> float:
    url = "https://mc-api.marketcheck.com/v2/price_stats/car/active"
    params = {
        "api_key": MARKETCHECK_API_KEY,
        "make":    CRITERIA["make"],
        "model":   CRITERIA["model"],
        "year":    year,
    }
    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return float(data.get("median") or 0)
    except Exception:
        return 0.0

# ── Filters ────────────────────────────────────────────────────────────────────

def passes_trim_filter(listing: dict) -> bool:
    trim = get_trim(listing).strip()
    return any(t.lower() in trim.lower() for t in CRITERIA["trims"])

def passes_drivetrain_filter(listing: dict) -> bool:
    dr = get_drivetrain(listing).upper()
    return any(d in dr for d in CRITERIA["drivetrain"])

def passes_hard_specs(listing: dict) -> bool:
    """Re-verify year/price/miles ourselves — MarketCheck's query params are
    not always strictly enforced, so don't trust them alone."""
    year  = get_year(listing) or 0
    price = listing.get("price") or 0
    miles = listing.get("miles")
    if year < CRITERIA["year_min"]:
        return False
    if price <= 0 or price > CRITERIA["price_max"]:
        return False
    if miles is not None and miles > CRITERIA["miles_max"]:
        return False
    # Model must actually be an ESV (not a standard Escalade)
    if "esv" not in get_model(listing).lower():
        return False
    return True

def filter_listings(listings: list[dict]) -> list[dict]:
    passed = []
    for l in listings:
        if not passes_hard_specs(l):
            continue
        if not passes_trim_filter(l):
            continue
        if not passes_drivetrain_filter(l):
            continue
        if not is_clean_title(l):
            continue
        l["_features_confirmed"] = check_required_features(l)
        passed.append(l)
    return passed

# ── Discord notification ───────────────────────────────────────────────────────

def send_discord(listing: dict, deal_text: str, deal_color: int, market_median: float, radius: int) -> None:
    price     = listing.get("price") or 0
    miles     = listing.get("miles") or 0
    vin       = listing.get("vin", "N/A")
    dealer    = (listing.get("dealer") or {}).get("name", "Unknown Dealer")
    vdp       = listing.get("vdp_url") or (listing.get("dealer") or {}).get("website", "")
    features  = listing.get("_features_confirmed", {})
    photos    = (listing.get("media") or {}).get("photo_links", [])

    savings = market_median - price if market_median > 0 else 0
    savings_line = f"${savings:,.0f} below market" if savings > 0 else ("above market" if savings < 0 else "at market")

    embed = {
        "title":       f"{get_year(listing)} {get_make(listing)} {get_model(listing)} — {get_trim(listing)}",
        "color":       deal_color,
        "description": f"**{deal_text}**  |  Found within **{radius} miles** of 75032",
        "fields": [
            {"name": "💰 Asking Price",    "value": f"${price:,}",                                    "inline": True},
            {"name": "📊 Market Median",   "value": f"${market_median:,.0f}" if market_median else "N/A", "inline": True},
            {"name": "📉 vs. Market",      "value": savings_line,                                     "inline": True},
            {"name": "🛣️ Mileage",         "value": f"{miles:,} miles",                               "inline": True},
            {"name": "🎨 Exterior",        "value": listing.get("exterior_color", "N/A"),              "inline": True},
            {"name": "🪑 Interior",        "value": listing.get("interior_color", "N/A"),              "inline": True},
            {"name": "🚗 Super Cruise",    "value": "✅" if features.get("super_cruise") else "⚠️ unconfirmed", "inline": True},
            {"name": "📺 Rear Entertainment", "value": "✅" if features.get("rear_entertainment") else "⚠️ unconfirmed", "inline": True},
            {"name": "🔑 VIN",             "value": vin,                                               "inline": False},
            {"name": "📍 Location",        "value": f"{get_city(listing)}, {get_state(listing)}",      "inline": True},
            {"name": "🏢 Dealer",          "value": dealer,                                            "inline": True},
        ],
        "timestamp": datetime.utcnow().isoformat(),
        "footer":    {"text": "Escalade Hunter Bot"},
    }
    if vdp:
        embed["url"] = vdp
        embed["fields"].append({"name": "🔗 Listing", "value": f"[View on Dealer Site]({vdp})", "inline": False})
    if photos:
        embed["image"] = {"url": photos[0]}

    requests.post(DISCORD_WEBHOOK_URL, json={"username": "🚙 Escalade Hunter", "embeds": [embed]}, timeout=15).raise_for_status()

# ── Web record builder ─────────────────────────────────────────────────────────

def build_web_record(listing: dict, deal_text: str, deal_color_hex: str, market_median: float, radius: int) -> dict:
    price    = float(listing.get("price") or 0)
    photos   = (listing.get("media") or {}).get("photo_links", [])
    features = listing.get("_features_confirmed", {})
    savings_pct = round((market_median - price) / market_median * 100, 1) if market_median > 0 else None

    return {
        "id":               listing.get("id"),
        "vin":              listing.get("vin"),
        "year":             get_year(listing),
        "make":             get_make(listing),
        "model":            get_model(listing),
        "trim":             get_trim(listing),
        "price":            price,
        "miles":            listing.get("miles"),
        "exterior_color":   listing.get("exterior_color"),
        "interior_color":   listing.get("interior_color"),
        "drivetrain":       get_drivetrain(listing),
        "transmission":     get_transmission(listing),
        "engine":           get_engine(listing),
        "fuel_type":        get_fuel(listing),
        "city":             get_city(listing),
        "state":            get_state(listing),
        "dealer_name":      (listing.get("dealer") or {}).get("name"),
        "dealer_phone":     (listing.get("dealer") or {}).get("phone"),
        "dealer_website":   (listing.get("dealer") or {}).get("website"),
        "vdp_url":          listing.get("vdp_url"),
        "photos":           photos,
        "description":      listing.get("seller_comments"),
        "super_cruise":     features.get("super_cruise", False),
        "rear_entertainment": features.get("rear_entertainment", False),
        "deal_label":       deal_text,
        "deal_color":       deal_color_hex,
        "market_median":    market_median,
        "savings_pct":      savings_pct,
        "search_radius":    radius,
        "first_seen":       datetime.utcnow().isoformat(),
    }

# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    seen         = load_seen()
    web_listings = load_listings()
    web_ids      = {r["id"] for r in web_listings}
    new_count    = 0
    market_cache: dict[int, float] = {}

    for radius in RADII:
        print(f"[{datetime.utcnow().isoformat()}] Searching {radius}mi radius from {SEARCH_ZIP}...")
        raw = fetch_listings(radius)
        print(f"  → {len(raw)} raw listings returned")

        filtered = filter_listings(raw)
        print(f"  → {len(filtered)} passed trim/drivetrain/title filters")

        new_listings = [l for l in filtered if l.get("id") not in seen]
        print(f"  → {len(new_listings)} new (not previously alerted)")

        if new_listings:
            for listing in new_listings:
                lid  = listing.get("id")
                year = get_year(listing) or 2023

                if year not in market_cache:
                    market_cache[year] = fetch_market_stats(year)
                    time.sleep(0.5)

                median    = market_cache[year]
                price     = float(listing.get("price") or 0)
                label, color_int = deal_label(price, median)
                color_hex = COLOR_HEX.get(color_int, "#FFA500")

                print(f"  📬 Alerting: {year} {get_trim(listing)} — ${price:,.0f} — {label}")
                try:
                    send_discord(listing, label, color_int, median, radius)
                    seen.add(lid)
                    new_count += 1
                    time.sleep(1)
                except Exception as e:
                    print(f"  ⚠️  Discord error for {lid}: {e}", file=sys.stderr)

                if lid not in web_ids:
                    web_listings.append(build_web_record(listing, label, color_hex, median, radius))
                    web_ids.add(lid)

            break  # found results at this radius, don't expand

        if radius == RADII[0]:
            print(f"  No new listings at {radius}mi — expanding to {RADII[1]}mi...")

    web_listings.sort(key=lambda r: r.get("first_seen", ""), reverse=True)
    save_seen(seen)
    save_listings(web_listings)
    print(f"\nDone. {new_count} new alert(s) sent. Web UI has {len(web_listings)} total listings.")


if __name__ == "__main__":
    main()
