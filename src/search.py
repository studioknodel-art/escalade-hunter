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
RADII = [25, 50]  # Search 25mi first, expand to 50mi if no results

CRITERIA = {
    "make": "Cadillac",
    "model": "Escalade ESV",
    "year_min": 2023,
    "price_max": 65000,
    "miles_max": 60000,
    "trims": ["Sport Platinum", "Premium Luxury Platinum", "Premium Platinum"],
    "drivetrain": ["4WD", "AWD"],
}

# Keywords that must appear in features/options/description for core requirements
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

# Deal rating thresholds vs. market median (% below market)
DEAL_TIERS = [
    (15, "🏆 PLATINUM DEAL", 0x7B2D8B),   # purple
    (10, "⭐ BEST DEAL",     0x00AA44),    # green
    (5,  "👍 GOOD DEAL",     0x3399FF),    # blue
    (0,  "✅ OKAY DEAL",     0xFFA500),    # orange
]

# ── Helpers ────────────────────────────────────────────────────────────────────

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


def deal_label(asking: float, market_median: float) -> tuple[str, int]:
    """Return (label, discord_color) based on % below market median."""
    if market_median <= 0:
        return "✅ OKAY DEAL", 0xFFA500
    pct_below = (market_median - asking) / market_median * 100
    for threshold, label, color in DEAL_TIERS:
        if pct_below >= threshold:
            return label, color
    return "⚠️ ABOVE MARKET", 0xFF3333


def check_required_features(listing: dict) -> dict[str, bool]:
    """Check if listing mentions Super Cruise and Rear Entertainment."""
    searchable = " ".join([
        listing.get("seller_comments", "") or "",
        listing.get("features", "") or "",
        json.dumps(listing.get("options", []) or []),
        listing.get("heading", "") or "",
    ]).lower()

    results = {}
    for key, keywords in REQUIRED_KEYWORDS.items():
        results[key] = any(kw in searchable for kw in keywords)
    return results


def is_clean_title(listing: dict) -> bool:
    dom = json.dumps(listing).lower()
    dirty_flags = ["salvage", "rebuilt", "flood", "lemon", "fire", "hail", "junk", "branded"]
    return not any(flag in dom for flag in dirty_flags)


def fetch_listings(radius: int) -> list[dict]:
    """Fetch used ESV listings from MarketCheck within radius."""
    url = "https://mc-api.marketcheck.com/v2/search/car/used"
    params = {
        "api_key": MARKETCHECK_API_KEY,
        "make": CRITERIA["make"],
        "model": "Escalade+ESV",
        "year_min": CRITERIA["year_min"],
        "price_max": CRITERIA["price_max"],
        "miles_max": CRITERIA["miles_max"],
        "zip": SEARCH_ZIP,
        "radius": radius,
        "car_type": "used",
        "rows": 50,
        "start": 0,
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("listings", [])


def fetch_market_stats(year: int) -> float:
    """Return median asking price for this year ESV from MarketCheck stats."""
    url = "https://mc-api.marketcheck.com/v2/price_stats/car/used"
    params = {
        "api_key": MARKETCHECK_API_KEY,
        "make": CRITERIA["make"],
        "model": "Escalade+ESV",
        "year": year,
        "car_type": "used",
    }
    try:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return float(data.get("median", 0) or 0)
    except Exception:
        return 0.0


def passes_trim_filter(listing: dict) -> bool:
    trim = (listing.get("trim") or "").strip()
    return any(t.lower() in trim.lower() for t in CRITERIA["trims"])


def passes_drivetrain_filter(listing: dict) -> bool:
    drivetrain = (listing.get("drivetrain") or "").upper()
    return any(d in drivetrain for d in CRITERIA["drivetrain"])


def filter_listings(listings: list[dict]) -> list[dict]:
    """Apply all hard filters."""
    passed = []
    for l in listings:
        if not passes_trim_filter(l):
            continue
        if not passes_drivetrain_filter(l):
            continue
        if not is_clean_title(l):
            continue
        features = check_required_features(l)
        # Flag listings missing required features but still include them as
        # "unconfirmed" so the buyer can check manually — Super Cruise may
        # not appear in every listing's text even when present on the vehicle.
        l["_features_confirmed"] = features
        passed.append(l)
    return passed


# ── Discord Notification ───────────────────────────────────────────────────────

def send_discord(listing: dict, deal_text: str, deal_color: int, market_median: float, radius: int) -> None:
    year  = listing.get("year", "")
    make  = listing.get("make", "")
    model = listing.get("model", "")
    trim  = listing.get("trim", "")
    price = listing.get("price", 0) or 0
    miles = listing.get("miles", 0) or 0
    vin   = listing.get("vin", "N/A")
    city  = listing.get("city", "")
    state = listing.get("state", "")
    vdp   = listing.get("vdp_url") or listing.get("dealer", {}).get("website", "")
    dealer= listing.get("dealer", {}).get("name", "Unknown Dealer")
    color_ext = listing.get("exterior_color", "N/A")
    color_int = listing.get("interior_color", "N/A")

    features = listing.get("_features_confirmed", {})
    sc_icon  = "✅" if features.get("super_cruise") else "⚠️ unconfirmed"
    rse_icon = "✅" if features.get("rear_entertainment") else "⚠️ unconfirmed"

    market_line = f"${market_median:,.0f} median" if market_median > 0 else "N/A"
    savings = market_median - price if market_median > 0 else 0
    savings_line = f"${savings:,.0f} below market" if savings > 0 else ("above market" if savings < 0 else "at market")

    embed = {
        "title": f"{year} {make} {model} — {trim}",
        "color": deal_color,
        "description": f"**{deal_text}**  |  Found within **{radius} miles** of 75032",
        "fields": [
            {"name": "💰 Asking Price", "value": f"${price:,}", "inline": True},
            {"name": "📊 Market Median", "value": market_line, "inline": True},
            {"name": "📉 vs. Market", "value": savings_line, "inline": True},
            {"name": "🛣️ Mileage", "value": f"{miles:,} miles", "inline": True},
            {"name": "🎨 Exterior", "value": color_ext, "inline": True},
            {"name": "🪑 Interior", "value": color_int, "inline": True},
            {"name": "🚗 Super Cruise", "value": sc_icon, "inline": True},
            {"name": "📺 Rear Entertainment", "value": rse_icon, "inline": True},
            {"name": "🔑 VIN", "value": vin, "inline": False},
            {"name": "📍 Location", "value": f"{city}, {state}", "inline": True},
            {"name": "🏢 Dealer", "value": dealer, "inline": True},
        ],
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": "Escalade Hunter Bot • github.com"},
    }

    if vdp:
        embed["url"] = vdp
        embed["fields"].append({"name": "🔗 Listing", "value": f"[View on Dealer Site]({vdp})", "inline": False})

    # Try to attach first photo
    photos = listing.get("media", {}).get("photo_links", [])
    if photos:
        embed["image"] = {"url": photos[0]}

    payload = {
        "username": "🚙 Escalade Hunter",
        "embeds": [embed],
    }
    resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
    resp.raise_for_status()


# ── Main ───────────────────────────────────────────────────────────────────────

def build_web_record(listing: dict, deal_text: str, deal_color_hex: str,
                     market_median: float, radius: int) -> dict:
    """Build a clean dict suitable for the web UI listings.json."""
    price  = float(listing.get("price") or 0)
    photos = listing.get("media", {}).get("photo_links", [])
    features = listing.get("_features_confirmed", {})
    savings_pct = round((market_median - price) / market_median * 100, 1) if market_median > 0 else None

    return {
        "id":              listing.get("id"),
        "vin":             listing.get("vin"),
        "year":            listing.get("year"),
        "make":            listing.get("make"),
        "model":           listing.get("model"),
        "trim":            listing.get("trim"),
        "price":           price,
        "miles":           listing.get("miles"),
        "exterior_color":  listing.get("exterior_color"),
        "interior_color":  listing.get("interior_color"),
        "drivetrain":      listing.get("drivetrain"),
        "transmission":    listing.get("transmission"),
        "engine":          listing.get("engine"),
        "fuel_type":       listing.get("fuel_type"),
        "city":            listing.get("city"),
        "state":           listing.get("state"),
        "zip":             listing.get("zip"),
        "dealer_name":     listing.get("dealer", {}).get("name"),
        "dealer_phone":    listing.get("dealer", {}).get("phone"),
        "dealer_website":  listing.get("dealer", {}).get("website"),
        "vdp_url":         listing.get("vdp_url"),
        "photos":          photos,
        "features":        listing.get("options", []),
        "description":     listing.get("seller_comments"),
        "super_cruise":    features.get("super_cruise", False),
        "rear_entertainment": features.get("rear_entertainment", False),
        "deal_label":      deal_text,
        "deal_color":      deal_color_hex,
        "market_median":   market_median,
        "savings_pct":     savings_pct,
        "search_radius":   radius,
        "first_seen":      datetime.utcnow().isoformat(),
    }


# Map discord int color → CSS hex string
COLOR_HEX = {
    0x7B2D8B: "#7B2D8B",
    0x00AA44: "#00AA44",
    0x3399FF: "#3399FF",
    0xFFA500: "#FFA500",
    0xFF3333: "#FF3333",
}


def main() -> None:
    seen = load_seen()
    web_listings = load_listings()
    web_ids = {r["id"] for r in web_listings}
    new_count = 0

    market_cache: dict[int, float] = {}

    for radius in RADII:
        print(f"[{datetime.utcnow().isoformat()}] Searching {radius}mi radius from {SEARCH_ZIP}...")
        raw = fetch_listings(radius)
        print(f"  → {len(raw)} raw listings returned")

        filtered = filter_listings(raw)
        print(f"  → {len(filtered)} listings passed filters")

        new_listings = [l for l in filtered if l.get("id") not in seen]
        print(f"  → {len(new_listings)} new (not previously alerted)")

        if new_listings:
            for listing in new_listings:
                lid  = listing.get("id")
                year = listing.get("year", 2023)

                if year not in market_cache:
                    market_cache[year] = fetch_market_stats(year)
                    time.sleep(0.5)

                median      = market_cache[year]
                price       = float(listing.get("price") or 0)
                label, color_int = deal_label(price, median)
                color_hex   = COLOR_HEX.get(color_int, "#FFA500")

                print(f"  📬 Notifying: {listing.get('year')} {listing.get('trim')} — ${price:,.0f} — {label}")
                try:
                    send_discord(listing, label, color_int, median, radius)
                    seen.add(lid)
                    new_count += 1
                    time.sleep(1)
                except Exception as e:
                    print(f"  ⚠️  Discord error for {lid}: {e}", file=sys.stderr)

                if lid not in web_ids:
                    rec = build_web_record(listing, label, color_hex, median, radius)
                    web_listings.append(rec)
                    web_ids.add(lid)

            break

        if radius == RADII[0]:
            print(f"  No new listings at {radius}mi — expanding to {RADII[1]}mi...")

    # Sort web listings newest-found first
    web_listings.sort(key=lambda r: r.get("first_seen", ""), reverse=True)

    save_seen(seen)
    save_listings(web_listings)
    print(f"\nDone. {new_count} new alert(s) sent. Web UI has {len(web_listings)} total listings.")


if __name__ == "__main__":
    main()
