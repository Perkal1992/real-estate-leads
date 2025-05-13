#!/usr/bin/env python3
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from supabase import create_client, Client

# ──────── DEBUG: Check that our Secrets are loaded ────────
print("🔑 RAPIDAPI_KEY length:", len(os.getenv("RAPIDAPI_KEY", "")))
print("🔑 GOOGLE_MAPS_API_KEY length:", len(os.getenv("GOOGLE_MAPS_API_KEY", "")))

# ──────── Credentials & Supabase Init ────────
# Try env-vars first (CI/GitHub Actions), fall back to local config.py
try:
    import config
    _local = True
except ImportError:
    _local = False

SUPABASE_URL        = os.getenv("SUPABASE_URL",        config.SUPABASE_URL        if _local else None)
SUPABASE_KEY        = os.getenv("SUPABASE_KEY",        config.SUPABASE_KEY        if _local else None)
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", config.GOOGLE_MAPS_API_KEY if _local else None)
RAPIDAPI_KEY        = os.getenv("RAPIDAPI_KEY",        config.RAPIDAPI_KEY        if _local else None)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def geocode_address(address: str):
    url = (
        "https://maps.googleapis.com/maps/api/geocode/json"
        f"?address={requests.utils.quote(address)}&key={GOOGLE_MAPS_API_KEY}"
    )
    resp = requests.get(url)
    data = resp.json() if resp.ok else {}
    if data.get("status") == "OK":
        loc = data["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"]
    return None, None

def scrape_zillow_rapidapi_fsbo(zip_code="75201", limit=20):
    endpoint = "https://zillow-com1.p.rapidapi.com/propertyListings"
    params = {
        "propertyStatus": "FOR_SALE",
        "homeType": ["Houses"],
        "sort": "Newest",
        "limit": str(limit),
        "zip": zip_code,
    }
    headers = {
        "x-rapidapi-host": "zillow-com1.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY,
    }
    resp = requests.get(endpoint, headers=headers, params=params)
    data = resp.json() if resp.ok else {}
    leads = []
    for item in data.get("props", []):
        addr = item.get("address")
        price = item.get("price")
        lat, lng = geocode_address(addr) if addr else (None, None)
        if addr and lat and lng:
            leads.append({
                "source": "Zillow FSBO (RapidAPI)",
                "address": addr,
                "city": "",
                "state": "TX",
                "zip": zip_code,
                "latitude": lat,
                "longitude": lng,
                "price": price,
                "google_maps": f"https://www.google.com/maps?q={lat},{lng}",
                "street_view": (
                    f"https://maps.googleapis.com/maps/api/streetview"
                    f"?size=600x300&location={lat},{lng}&key={GOOGLE_MAPS_API_KEY}"
                ),
                "created_at": datetime.utcnow().isoformat(),
            })
    return leads

def scrape_craigslist_dallas(limit=20):
    url = "https://dallas.craigslist.org/search/rea"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, "html.parser")
    postings = soup.select("li.result-row")[:limit]
    leads = []
    for post in postings:
        title = post.select_one("a.result-title")
        if not title:
            continue
        addr = title.get_text(strip=True)
        lat, lng = geocode_address(addr)
        if lat and lng:
            leads.append({
                "source": "Craigslist DFW",
                "address": addr,
                "city": "Dallas",
                "state": "TX",
                "zip": "",
                "latitude": lat,
                "longitude": lng,
                "price": None,
                "google_maps": f"https://www.google.com/maps?q={lat},{lng}",
                "street_view": (
                    f"https://maps.googleapis.com/maps/api/streetview"
                    f"?size=600x300&location={lat},{lng}&key={GOOGLE_MAPS_API_KEY}"
                ),
                "created_at": datetime.utcnow().isoformat(),
            })
    return leads

def scrape_facebook_marketplace(city="Dallas", days_since=1, limit=20):
    url = "https://facebook-marketplace1.p.rapidapi.com/search"
    params = {
        "sort": "newest",
        "city": city,
        "daysSinceListed": str(days_since),
        "limit": str(limit),
    }
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "facebook-marketplace1.p.rapidapi.com"
    }
    resp = requests.get(url, headers=headers, params=params)
    data = resp.json().get("listings", []) if resp.ok else []
    leads = []
    for item in data:
        addr = item.get("location", {}).get("address")
        price = item.get("price", {}).get("amount")
        if not addr:
            continue
        lat, lng = geocode_address(addr)
        if not lat:
            continue
        leads.append({
            "source": "Facebook Marketplace",
            "address": addr,
            "city": city,
            "state": "TX",
            "zip": "",
            "latitude": lat,
            "longitude": lng,
            "price": f"${price}" if price else None,
            "google_maps": f"https://www.google.com/maps?q={lat},{lng}",
            "street_view": (
                f"https://maps.googleapis.com/maps/api/streetview"
                f"?size=600x300&location={lat},{lng}&key={GOOGLE_MAPS_API_KEY}"
            ),
            "created_at": datetime.utcnow().isoformat(),
        })
    return leads

def run_all_scrapers(zip_codes=None, limit=20):
    if zip_codes is None:
        zip_codes = ["75201"]

    # 1) Scrape each source separately
    z_leads = []
    for z in zip_codes:
        print(f"Scraping Zillow for ZIP {z}…")
        chunk = scrape_zillow_rapidapi_fsbo(zip_code=z, limit=limit)
        print(f"  → Zillow returned {len(chunk)} leads")
        z_leads.extend(chunk)

    print("Scraping Craigslist…")
    c_leads = scrape_craigslist_dallas(limit=limit)
    print(f"  → Craigslist returned {len(c_leads)} leads")

    print("Scraping Facebook Marketplace…")
