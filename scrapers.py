import os
import re
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from supabase import create_client

# ──────────────── ENV & INIT ────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

HOT_WORDS = ["cash", "as-is", "must sell", "motivated", "investor", "urgent", "cheap", "fast", "needs work"]

def normalize_price(val):
    if not val:
        return None
    digits = re.sub(r"[^\d]", "", str(val))
    return int(digits) if digits else None

def is_hot_lead(title):
    return any(word in title.lower() for word in HOT_WORDS)

def get_coords(address):
    g_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": GOOGLE_MAPS_API_KEY}
    res = requests.get(g_url, params=params).json()
    if res["status"] == "OK":
        loc = res["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"]
    return None, None

def get_street_view(lat, lng):
    return f"https://maps.googleapis.com/maps/api/streetview?size=600x400&location={lat},{lng}&key={GOOGLE_MAPS_API_KEY}"

def insert_lead(data):
    try:
        supabase.table("craigslist_leads").upsert(data).execute()
        print("✅", data["title"])
    except Exception as e:
        print("❌ Insert failed:", e)

# ──────────────── SCRAPERS ────────────────

# Craigslist
try:
    print("📡 Craigslist…")
    url = "https://dallas.craigslist.org/search/rea?hasPic=1"
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    existing = supabase.table("craigslist_leads").select("title").limit(1000).execute().data
    seen = {r["title"] for r in existing}

    for row in soup.select(".result-row"):
        title_tag = row.select_one(".result-title")
        title = title_tag.text.strip()
        if title in seen:
            continue
        link = title_tag["href"]
        hot = is_hot_lead(title)
        price_tag = row.select_one(".result-price")
        price = normalize_price(price_tag.text if price_tag else None)

        lat, lng = get_coords(title)
        street_url = get_street_view(lat, lng) if lat and lng else None
        arv = price * 1.35 if price else None
        equity = arv - price if price and arv else None
        hot_lead = (equity / arv >= 0.25) if equity and arv else hot

        post = {
            "title": title,
            "date_posted": datetime.utcnow().isoformat(),
            "source": "craigslist",
            "link": link,
            "price": price,
            "arv": arv,
            "equity": equity,
            "latitude": lat,
            "longitude": lng,
            "street_view_url": street_url,
            "hot_lead": hot_lead
        }
        insert_lead(post)
except Exception as e:
    print("❌ Craigslist error:", e)

# Zillow FSBO
try:
    print("📡 Zillow FSBO…")
    url = "https://zillow-com1.p.rapidapi.com/propertyExtendedSearch"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
    }
    params = {"location": "Dallas, TX", "status_type": "ForSaleByOwner"}
    res = requests.get(url, headers=headers, params=params).json()
    for p in res.get("props", []):
        address = p.get("address", "Unknown")
        price = normalize_price(p.get("price"))
        lat, lng = get_coords(address)
        street_url = get_street_view(lat, lng) if lat and lng else None
        arv = price * 1.35 if price else None
        equity = arv - price if price and arv else None
        hot_lead = (equity / arv >= 0.25) if equity and arv else False

        post = {
            "title": address,
            "date_posted": datetime.utcnow().isoformat(),
            "source": "zillow_fsbo",
            "link": None,
            "price": price,
            "arv": arv,
            "equity": equity,
            "latitude": lat,
            "longitude": lng,
            "street_view_url": street_url,
            "hot_lead": hot_lead
        }
        insert_lead(post)
except Exception as e:
    print("❌ Zillow FSBO error:", e)

# Facebook Marketplace
try:
    print("📡 Facebook Marketplace…")
    url = "https://facebook-marketplace1.p.rapidapi.com/search"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "facebook-marketplace1.p.rapidapi.com"
    }
    params = {"city": "Dallas", "daysSinceListed": 1, "sort": "newest"}
    res = requests.get(url, headers=headers, params=params).json()
    for p in res.get("listings", []):
        title = p.get("marketplace_listing_title", "No title")
        hot = is_hot_lead(title)
        lat, lng = get_coords(title)
        street_url = get_street_view(lat, lng) if lat and lng else None

        post = {
            "title": title,
            "date_posted": datetime.utcnow().isoformat(),
            "source": "facebook",
            "link": None,
            "price": None,
            "arv": None,
            "equity": None,
            "latitude": lat,
            "longitude": lng,
            "street_view_url": street_url,
            "hot_lead": hot
        }
        insert_lead(post)
except Exception as e:
    print("❌ Facebook error:", e)

print("✅ All scrapers done.")