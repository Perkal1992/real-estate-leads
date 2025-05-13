import requests
import json
from datetime import datetime
from bs4 import BeautifulSoup
from supabase import create_client, Client
import re

# ──────── CREDENTIALS ────────
SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {"User-Agent": "Mozilla/5.0"}
HOT_WORDS = ["motivated", "cash", "as-is", "urgent", "must sell", "investor", "fast", "cheap"]

def is_hot(description):
    if not description:
        return False
    return any(word in description.lower() for word in HOT_WORDS)

def normalize_price(value):
    if not value:
        return None
    return int(re.sub(r'[^0-9]', '', str(value))) if re.sub(r'[^0-9]', '', str(value)) else None

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
    leads = []
    try:
        response = requests.get(url, headers=headers, params=querystring)
        results = response.json().get("props", [])
        for prop in results:
            desc = f"{prop.get('bedrooms', '')}bd {prop.get('bathrooms', '')}ba {prop.get('livingArea', '')} sqft"
            leads.append({
                "title": prop.get("addressStreet", "Zillow FSBO"),
                "description": desc,
                "price": normalize_price(prop.get("price")),
                "city": prop.get("addressCity", "Dallas"),
                "zip": prop.get("addressZipcode", ""),
                "source": "Zillow FSBO",
                "hot_lead": is_hot(desc),
                "created_at": datetime.utcnow().isoformat(),
            })
    except Exception as e:
        print(f"Zillow error: {e}")
    return leads

def scrape_craigslist():
    print("Scraping Craigslist DFW...")
    url = "https://dallas.craigslist.org/search/rea?hasPic=1&availabilityMode=0"
    leads = []
    try:
        resp = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(resp.text, "html.parser")
        posts = soup.find_all("li", class_="result-row")
        for post in posts:
            title_elem = post.find("a", class_="result-title")
            price_elem = post.find("span", class_="result-price")
            hood_elem = post.find("span", class_="result-hood")
            date_elem = post.find("time", class_="result-date")

            title = title_elem.text.strip() if title_elem else "No title"
            link = title_elem["href"] if title_elem else ""
            price = normalize_price(price_elem.text if price_elem else None)
            city = hood_elem.text.strip(" ()") if hood_elem else "DFW"
            created = date_elem["datetime"] if date_elem else datetime.utcnow().isoformat()
            desc = f"Craigslist: {link}"

            leads.append({
                "title": title,
                "description": desc,
                "price": price,
                "city": city,
                "zip": "",
                "source": "Craigslist",
                "hot_lead": is_hot(title + " " + desc),
                "created_at": created,
            })
    except Exception as e:
        print(f"Craigslist error: {e}")
    return leads

def scrape_facebook_marketplace():
    print("Scraping Facebook Marketplace...")
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

    leads = []
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        for item in data.get("data", []):
            title = item.get("marketplace_listing_title", "Facebook Listing")
            desc = f"Facebook: {item.get('permalink')}"
            leads.append({
                "title": title,
                "description": desc,
                "price": normalize_price(item.get("listing_price")),
                "city": "Dallas",
                "zip": "",
                "source": "Facebook Marketplace",
                "hot_lead": is_hot(title + " " + desc),
                "created_at": datetime.utcnow().isoformat(),
            })
    except Exception as e:
        print(f"Facebook error: {e}")
    return leads

def main():
    zillow = scrape_zillow_fsbo()
    craigslist = scrape_craigslist()
    facebook = scrape_facebook_marketplace()
    all_leads = zillow + craigslist + facebook
    print(f"Total leads scraped: {len(all_leads)}")
    push_to_supabase(all_leads)

if __name__ == "__main__":
    main()
