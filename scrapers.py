#!/usr/bin/env python3
import os
import requests
import re
from datetime import datetime
from bs4 import BeautifulSoup   # ← fixed typo here
from supabase import create_client, Client

# ──────── DEBUG: Sanity‐check CI env & working dir ────────
print("🔍 RUNNING scrapers.py from:", os.getcwd())
for var in ("SUPABASE_URL","SUPABASE_KEY","RAPIDAPI_KEY","GOOGLE_MAPS_API_KEY"):
    val = os.getenv(var, "") or ""
    print(f"🔑 {var:21} length:", len(val))

# ──────── Credentials & Supabase Init ────────
try:
    import config
    _local = True
except ImportError:
    _local = False

# Strip any accidental whitespace/newlines from secrets
raw_url = os.getenv("SUPABASE_URL", config.SUPABASE_URL if _local else None)
raw_key = os.getenv("SUPABASE_KEY", config.SUPABASE_KEY if _local else None)
raw_rapid = os.getenv("RAPIDAPI_KEY", config.RAPIDAPI_KEY if _local else None)
raw_maps = os.getenv("GOOGLE_MAPS_API_KEY", config.GOOGLE_MAPS_API_KEY if _local else None)

SUPABASE_URL        = raw_url.strip() if isinstance(raw_url, str) else raw_url
SUPABASE_KEY        = raw_key.strip() if isinstance(raw_key, str) else raw_key
RAPIDAPI_KEY        = raw_rapid.strip() if isinstance(raw_rapid, str) else raw_rapid
GOOGLE_MAPS_API_KEY = raw_maps.strip() if isinstance(raw_maps, str) else raw_maps

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {"User-Agent": "Mozilla/5.0"}
HOT_WORDS = ["motivated", "cash", "as-is", "urgent", "must sell", "investor", "fast", "cheap"]

def is_hot(text: str) -> bool:
    return any(w in text.lower() for w in HOT_WORDS) if text else False

def normalize_price(val) -> int|None:
    if not val: return None
    digits = re.sub(r'[^0-9]', '', str(val))
    return int(digits) if digits else None

def push_to_supabase(leads: list[dict]):
    for lead in leads:
        try:
            supabase.table("leads").insert(lead).execute()
            print("✅ Pushed:", lead.get("title"))
        except Exception as e:
            print("❌ Push failed:", e)

def scrape_zillow() -> list[dict]:
    print("📡 Scraping Zillow…")
    url = "https://zillow-com1.p.rapidapi.com/propertyExtendedSearch"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
    }
    leads = []
    try:
        params = {"location": "Dallas, TX", "status_type": "ForSaleByOwner"}
        print(f"🔗 Zillow → GET {url} params={params}")
        resp = requests.get(url, headers=headers, params=params)
        print("📥 Zillow status:", resp.status_code)
        j = resp.json()
        print("📦 Zillow JSON keys:", list(j.keys()))
        data = j.get("props", [])
        print("📊 Zillow 'props' count:", len(data))
        for prop in data:
            desc = f"{prop.get('bedrooms','')}bd {prop.get('bathrooms','')}ba {prop.get('livingArea','')} sqft"
            leads.append({
                "title": prop.get("addressStreet", "Zillow FSBO"),
                "description": desc,
                "price": normalize_price(prop.get("price")),
                "city": prop.get("addressCity", "Dallas"),
                "zip": prop.get("addressZipcode", ""),
                "source": "Zillow FSBO",
                "hot_lead": is_hot(desc),
                "created_at": datetime.utcnow().isoformat()
            })
    except Exception as e:
        print("⚠ Zillow error:", e)
    return leads

def scrape_craigslist() -> list[dict]:
    print("📡 Scraping Craigslist…")
    leads = []
    try:
        url = "https://dallas.craigslist.org/search/rea?hasPic=1"
        print(f"🔗 Craigslist → GET {url}")
        resp = requests.get(url, headers=HEADERS)
        print("📥 Craigslist status:", resp.status_code)
        soup = BeautifulSoup(resp.text, "html.parser")
        posts = soup.select("li.result-row")
        print("📊 Craigslist result-row count:", len(posts))
        for post in posts:
            title = post.select_one("a.result-title").text.strip()
            link = post.select_one("a.result-title")["href"]
            price = post.select_one("span.result-price")
            desc = f"Craigslist link: {link}"
            leads.append({
                "title": title,
                "description": desc,
                "price": normalize_price(price.text if price else None),
                "city": "DFW",
                "zip": "",
                "source": "Craigslist",
                "hot_lead": is_hot(title + " " + desc),
                "created_at": datetime.utcnow().isoformat()
            })
    except Exception as e:
        print("⚠ Craigslist error:", e)
    return leads

def scrape_facebook() -> list[dict]:
    print("📡 Scraping Facebook Marketplace…")
    url = "https://facebook-marketplace1.p.rapidapi.com/search"
    headers = {
        "x-rapidapi-host": "facebook-marketplace1.p.rapidapi.com",
        "x-rapidapi-key":  RAPIDAPI_KEY
    }
    leads = []
    try:
        params = {"sort": "newest", "city": "Dallas", "daysSinceListed": "1"}
        print(f"🔗 Facebook → GET {url} params={params}")
        resp = requests.get(url, headers=headers, params=params)
        print("📥 Facebook status:", resp.status_code)
        j = resp.json()
        print("📦 Facebook JSON keys:", list(j.keys()))
        listings = j.get("listings", j.get("data", []))
        print("📊 Facebook listings count:", len(listings))
        for item in listings:
            title = item.get("marketplace_listing_title", "FB Listing")
            desc = f"FB: {item.get('permalink')}"
            leads.append({
                "title": title,
                "description": desc,
                "price": normalize_price(item.get("listing_price")),
                "city": "Dallas",
                "zip": "",
                "source": "Facebook Marketplace",
                "hot_lead": is_hot(title + " " + desc),
                "created_at": datetime.utcnow().isoformat()
            })
    except Exception as e:
        print("⚠ Facebook error:", e)
    return leads

def main():
    all_leads = scrape_zillow() + scrape_craigslist() + scrape_facebook()
    print(f"📊 Total scraped: {len(all_leads)}")
    push_to_supabase(all_leads)

if __name__ == "__main__":
    main()
