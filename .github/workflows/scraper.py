import os
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# Local fallback for dev; in CI these come from GitHub Secrets
try:
    import config
    _local = True
except ImportError:
    _local = False

SUPABASE_URL        = os.getenv("SUPABASE_URL",        config.SUPABASE_URL if _local else None)
SUPABASE_KEY        = os.getenv("SUPABASE_KEY",        config.SUPABASE_KEY if _local else None)
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", config.GOOGLE_MAPS_API_KEY if _local else None)
RAPIDAPI_KEY        = os.getenv("RAPIDAPI_KEY",        config.RAPIDAPI_KEY if _local else None)

from supabase import create_client, Client
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

def push_to_supabase(record: dict):
    supabase.table("leads").insert(record).execute()

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
    r = requests.get(endpoint, headers=headers, params=params)
    data = r.json() if r.ok else {}
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

def run_all_scrapers():
    all_leads = []
    all_leads += scrape_zillow_rapidapi_fsbo()
    all_leads += scrape_craigslist_dallas()
    for lead in all_leads:
        push_to_supabase(lead)
    print(f"✅ Scraped & pushed {len(all_leads)} leads")
    return all_leads

if __name__ == "__main__":
    run_all_scrapers()
