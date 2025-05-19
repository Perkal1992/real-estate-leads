print("🔥 scrapers.py is running latest logic...")
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

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("🚀 Scraper started at", datetime.utcnow().isoformat())

def geocode(address):
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": GOOGLE_MAPS_API_KEY}
    r = requests.get(url, params=params).json()
    if r.get("status") == "OK":
        loc = r["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"]
    return None, None

def get_street_view_url(lat, lng):
    if not lat or not lng: return None
    return (
      f"https://maps.googleapis.com/maps/api/streetview"
      f"?size=600x300&location={lat},{lng}&key={GOOGLE_MAPS_API_KEY}"
    )

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
    try:
        resp = requests.post(url, json={"fields": record}, headers=headers)
        if not resp.ok:
            print("❌ Airtable error:", resp.text)
    except Exception as e:
        print("❌ Airtable request failed:", e)

def process_lead(title, source, price=None):
    is_hot = any(w in title.lower() for w in HOT_WORDS)
    lat, lng = geocode(title)
    arv = int(price * 1.1) if price else None
    sv_url = get_street_view_url(lat, lng)
    rec = {
        "title":            title,
        "source":           source,
        "date_posted":      datetime.utcnow().isoformat(),
        "is_hot":           is_hot,
        **({"price": price} if price else {}),
        **({"arv": arv} if arv else {}),
        **({"latitude": lat, "longitude": lng} if lat else {}),
        **({"street_view_url": sv_url} if sv_url else {})
    }
    print(f"✅ {source} lead:", title)
    insert_supabase(rec)
    insert_airtable(rec)

# ───── Craigslist ─────
try:
    print("📡 Scraping Craigslist…")
    res  = requests.get(TARGET_URL)
    soup = BeautifulSoup(res.text, "html.parser")
    seen = {r["title"] for r in supabase.table("craigslist_leads").select("title").limit(1000).execute().data}
    for item in soup.select(".result-row"):
        te = item.select_one(".result-title")
        pe = item.select_one(".result-price")
        if not te: continue
        title = te.text.strip()
        if title in seen: continue
        price = int(pe.text.replace("$","").replace(",","")) if pe else None
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
        addr  = p.get("address","Unknown")
        price = p.get("price") or None
        process_lead(addr, "zillow_fsbo", price)
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
        process_lead(l.get("marketplace_listing_title","No title"), "facebook")
except Exception as e:
    print("❌ Facebook Marketplace failed:", e)

print("✅ All scrapers done.")