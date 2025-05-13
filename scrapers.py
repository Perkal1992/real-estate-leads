import requests, re
from datetime import datetime
from bs4 import BeautifulSoup
from supabase import create_client, Client

SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB3a2JzenNsamxweGhsZmN2ZGVyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQzNDk4MDEsImV4cCI6MjA1OTkyNTgwMX0.bjVMzL4X6dN6xBx8tV3lT7XPsOFIEqMLv0pG3y6N-4o"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HEADERS = {"User-Agent": "Mozilla/5.0"}
HOT_WORDS = ["motivated", "cash", "as-is", "urgent", "must sell", "investor", "fast", "cheap"]

def is_hot(text): return any(w in text.lower() for w in HOT_WORDS) if text else False
def normalize_price(val): return int(re.sub(r'[^0-9]', '', str(val))) if val else None

def push_to_supabase(leads):
    for lead in leads:
        try:
            supabase.table("leads").insert(lead).execute()
            print("Pushed:", lead['title'])
        except Exception as e:
            print("Failed:", e)

def scrape_zillow():
    print("Scraping Zillow...")
    url = "https://zillow-com1.p.rapidapi.com/propertyExtendedSearch"
    headers = {
        "X-RapidAPI-Key": "88a3a41f80msh37d91f3065ad897p19f149jsnab96bb20afbc",
        "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
    }
    leads = []
    try:
        r = requests.get(url, headers=headers, params={"location":"Dallas, TX", "status_type":"ForSaleByOwner"})
        for prop in r.json().get("props", []):
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
        print("Zillow error:", e)
    return leads

def scrape_craigslist():
    print("Scraping Craigslist...")
    leads = []
    try:
        r = requests.get("https://dallas.craigslist.org/search/rea?hasPic=1", headers=HEADERS)
        soup = BeautifulSoup(r.text, "html.parser")
        for post in soup.find_all("li", class_="result-row"):
            title = post.find("a", class_="result-title").text.strip()
            link = post.find("a", class_="result-title")["href"]
            price = post.find("span", class_="result-price")
            desc = f"Craigslist: {link}"
            leads.append({
                "title": title,
                "description": desc,
                "price": normalize_price(price.text) if price else None,
                "city": "DFW",
                "zip": "",
                "source": "Craigslist",
                "hot_lead": is_hot(title + desc),
                "created_at": datetime.utcnow().isoformat()
            })
    except Exception as e:
        print("Craigslist error:", e)
    return leads

def scrape_facebook():
    print("Scraping Facebook Marketplace...")
    url = "https://facebook-marketplace1.p.rapidapi.com/search"
    headers = {
        "x-rapidapi-host": "facebook-marketplace1.p.rapidapi.com",
        "x-rapidapi-key": "88a3a41f80msh37d91f3065ad897p19f149jsnab96bb20afbc"
    }
    leads = []
    try:
        r = requests.get(url, headers=headers, params={"sort": "newest", "city": "Dallas", "daysSinceListed": "1"})
        for i in r.json().get("data", []):
            title = i.get("marketplace_listing_title", "FB Listing")
            desc = f"Facebook: {i.get('permalink')}"
            leads.append({
                "title": title,
                "description": desc,
                "price": normalize_price(i.get("listing_price")),
                "city": "Dallas",
                "zip": "",
                "source": "Facebook Marketplace",
                "hot_lead": is_hot(title + desc),
                "created_at": datetime.utcnow().isoformat()
            })
    except Exception as e:
        print("Facebook error:", e)
    return leads

def main():
    all_leads = scrape_zillow() + scrape_craigslist() + scrape_facebook()
    print(f"Total scraped: {len(all_leads)}")
    push_to_supabase(all_leads)

if __name__ == "__main__":
    main()