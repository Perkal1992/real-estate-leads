import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from supabase import create_client

# ───── Config ─────
TARGET_URL           = "https://dallas.craigslist.org/search/rea?hasPic=1"
HOT_WORDS            = ["cash", "as-is", "must sell", "motivated", "investor"]

SUPABASE_URL         = os.getenv("SUPABASE_URL")
SUPABASE_KEY         = os.getenv("SUPABASE_KEY")
GOOGLE_MAPS_API_KEY  = os.getenv("GOOGLE_MAPS_API_KEY")
RAPIDAPI_KEY         = os.getenv("RAPIDAPI_KEY")
AIRTABLE_API_KEY     = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID     = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME  = os.getenv("AIRTABLE_TABLE_NAME")

# ───── Clients ─────
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("🚀 Scraper started at", datetime.utcnow().isoformat())

def geocode(address):
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": GOOGLE_MAPS_API_KEY}
    res = requests.get(url, params=params).json()
    if res.get("status") == "OK":
        loc = res["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"]
    return None, None

def get_street_view_url(lat, lng):
    return (
        f"https://maps.googleapis.com/maps/api/streetview"
        f"?size=600x300&location={lat},{lng}&key={GOOGLE_MAPS_API_KEY}"
    ) if lat and lng else None

def insert_supabase(record):
    try:
        supabase.table("craigslist_leads").insert(record).execute()
    except Exception as e:
        print("❌ Supabase insert error:", e)

def insert_airtable(record):
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {"fields": record}
    try:
        r = requests.post(url, json=payload, headers=headers)
        if not r.ok:
            print("❌ Airtable error:", r.text)
    except Exception as e:
        print("❌ Airtable request failed:", e)

def process_lead(title, source, price=None):
    is_hot = any(w in title.lower() for w in HOT_WORDS)
    lat, lng = geocode(title)
    arv = int(price * 1.1) if price else None
    sv_url = get_street_view_url(lat, lng)
    
    record = {
        "title":         title,
        "source":        source,
        "date_posted":   datetime.utcnow().isoformat(),
        "is_hot":        is_hot,
        **({"price": price} if price else {}),
        **({"arv": arv} if arv else {}),
        **({"latitude": lat, "longitude": lng} if lat else {}),
        **({"street_view_url": sv_url} if sv_url else {})
    }
    print(f"✅ {source} lead:", title)
    insert_supabase(record)
    insert_airtable(record)

# ───── Craigslist ─────
try:
    print("📡 Scraping Craigslist…")
    res  = requests.get(TARGET_URL)
    soup = BeautifulSoup(res.text, "html.parser")
    existing = supabase.table("craigslist_leads").select("title").limit(1000).execute().data
    seen = {r["title"] for r in existing}
    for item in soup.select(".result-row"):
        title_elem = item.select_one(".result-title")
        price_elem = item.select_one(".result-price")
        if not title_elem: continue
        title = title_elem.text.strip()
        if title in seen: continue
        price = int(price_elem.text.replace("$","").replace(",","")) if price_elem else None
        process_lead(title, "craigslist", price)
except Exception as e:
    print("❌ Craigslist failed:", e)

# ───── Zillow FSBO ─────
try:
    print("📡 Scraping Zillow FSBO…")
    z = requests.get(
        "https://zillow-com1.p.rapidapi.com/propertyExtendedSearch",
        headers={
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
        },
        params={"location":"Dallas, TX","status_type":"ForSaleByOwner"}
    ).json()
    for p in z.get("props", []):
        address = p.get("address", "Unknown address")
        price   = p.get("price") if p.get("price") else None
        process_lead(address, "zillow_fsbo", price)
except Exception as e:
    print("❌ Zillow FSBO failed:", e)

# ───── Facebook Marketplace ─────
try:
    print("📡 Scraping Facebook Marketplace…")
    f = requests.get(
        "https://facebook-marketplace1.p.rapidapi.com/search",
        headers={
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": "facebook-marketplace1.p.rapidapi.com"
        },
        params={"city":"Dallas","daysSinceListed":1,"sort":"newest"}
    ).json()
    for l in f.get("listings", []):
        title = l.get("marketplace_listing_title","No title")
        process_lead(title, "facebook")
except Exception as e:
    print("❌ Facebook Marketplace failed:", e)

print("✅ All scrapers done.")