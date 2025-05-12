import requests
import json
from datetime import datetime
from bs4 import BeautifulSoup
from supabase import create_client, Client

# ──────── CREDENTIALS ────────
SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."  # Full key here
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {"User-Agent": "Mozilla/5.0"}

def push_to_supabase(leads):
    for lead in leads:
        try:
            supabase.table("leads").insert(lead).execute()
            print(f"Pushed: {lead['title']}")
        except Exception as e:
            print(f"Failed to push lead: {e}")

def scrape_zillow_fsbo():
    print("Scraping Zillow FSBO...")
    url = "https://zillow-com1.p.rapidapi.com/propertyExtendedSearch"
    querystring = {"location":"Dallas, TX", "status_type":"ForSaleByOwner"}
    headers = {
        "X-RapidAPI-Key": "88a3a41f80msh37d91f3065ad897p19f149jsnab96bb20afbc",
        "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
    }
    try:
        response = requests.get(url, headers=headers, params=querystring)
        results = response.json().get("props", [])
        leads = []
        for prop in results:
            leads.append({
                "title": prop.get("addressStreet", "Zillow FSBO"),
                "description": f"{prop.get('bedrooms', '')}bd {prop.get('bathrooms', '')}ba {prop.get('livingArea', '')} sqft",
                "price": prop.get("price"),
                "city": prop.get("addressCity", "Dallas"),
                "zip": prop.get("addressZipcode", ""),
                "source": "Zillow FSBO",
                "created_at": datetime.utcnow().isoformat(),
            })
        return leads
    except Exception as e:
        print(f"Zillow error: {e}")
        return []

def scrape_craigslist():
    print("Scraping Craigslist DFW...")
    base_url = "https://dallas.craigslist.org"
    search_url = f"{base_url}/search/rea?hasPic=1&availabilityMode=0"
    leads = []
    try:
        resp = requests.get(search_url, headers=HEADERS)
        soup = BeautifulSoup(resp.text, "html.parser")
        posts = soup.find_all("li", class_="result-row")
        for post in posts:
            title_elem = post.find("a", class_="result-title")
            price_elem = post.find("span", class_="result-price")
            hood_elem = post.find("span", class_="result-hood")
            date_elem = post.find("time", class_="result-date")

            title = title_elem.text.strip() if title_elem else "No title"
            link = title_elem["href"] if title_elem else None
            price = price_elem.text.strip().replace("$", "") if price_elem else None
            city = hood_elem.text.strip(" ()") if hood_elem else "DFW"
            created = date_elem["datetime"] if date_elem else datetime.utcnow().isoformat()

            leads.append({
                "title": title,
                "description": f"Posted on Craigslist: {link}",
                "price": price,
                "city": city,
                "zip": "",
                "source": "Craigslist",
                "created_at": created,
            })
        return leads
    except Exception as e:
        print(f"Craigslist error: {e}")
        return []

def scrape_facebook_marketplace():
    print("Scraping Facebook Marketplace via RapidAPI...")
    url = "https://facebook-marketplace1.p.rapidapi.com/search"
    params = {
        "sort": "newest",
        "city": "Dallas",
        "daysSinceListed": "1"
    }
    headers = {
        "x-rapidapi-host": "facebook-marketplace1.p.rapidapi.com",
        "x-rapidapi-key": "88a3a41f80msh37d91f3065ad897p19f149jsnab96bb20afbc"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        leads = []
        for item in data.get("data", []):
            leads.append({
                "title": item.get("marketplace_listing_title", "Facebook Listing"),
                "description": f"Posted on Facebook: {item.get('permalink')}",
                "price": item.get("listing_price"),
                "city": "Dallas",
                "zip": "",
                "source": "Facebook Marketplace",
                "created_at": datetime.utcnow().isoformat(),
            })
        return leads
    except Exception as e:
        print(f"Facebook error: {e}")
        return []

def main():
    zillow_leads = scrape_zillow_fsbo()
    craigslist_leads = scrape_craigslist()
    facebook_leads = scrape_facebook_marketplace()
    all_leads = zillow_leads + craigslist_leads + facebook_leads
    print(f"Total scraped: {len(all_leads)} leads")
    push_to_supabase(all_leads)

if __name__ == "__main__":
    main()
