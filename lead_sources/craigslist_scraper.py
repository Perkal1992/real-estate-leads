import requests
from bs4 import BeautifulSoup
from datetime import datetime
from supabase import create_client, Client
import time

# ==== YOUR SUPABASE CONFIG ====
SUPABASE_URL = "https://msvnjpgnkdcfgedgqzkl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1zdm5qcGdua2RjZmdlZGd6a2wiLCJyb2xlIjoiYW5vbiIsImlhdCI6MTcxMjk5ODk4MywiZXhwOjE3MTU1OTA5ODN9.PQmnIE9A-cfAV9yX8Yp4GUbAd7EPvJzvYirKvV0EUkM"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==== SCRAPER CONFIG ====
BASE_URL = "https://dallas.craigslist.org"
CATEGORIES = ["/search/apa", "/search/rea", "/search/roo", "/search/sub"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def get_posts(category_url):
    response = requests.get(BASE_URL + category_url, headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")
    posts = soup.find_all("li", class_="result-row")
    results = []

    for post in posts:
        try:
            title = post.find("a", class_="result-title").text.strip()
            link = post.find("a", class_="result-title")["href"]
            price_tag = post.find("span", class_="result-price")
            price = price_tag.text.strip() if price_tag else "N/A"
            hood_tag = post.find("span", class_="result-hood")
            location = hood_tag.text.strip(" ()") if hood_tag else "N/A"

            if not any(city in location.lower() for city in ["dallas", "ft worth", "fort worth", "dfw"]):
                continue  # skip if not in DFW

            results.append({
                "title": title,
                "price": price,
                "location": location,
                "link": link,
                "source": "craigslist",
                "created_at": datetime.utcnow().isoformat()
            })
        except Exception as e:
            print(f"Error parsing post: {e}")
            continue
    return results

def insert_leads(leads):
    for lead in leads:
        # Check for duplicates by link
        existing = supabase.table("leads").select("id").eq("link", lead["link"]).execute()
        if not existing.data:
            supabase.table("leads").insert(lead).execute()
            print(f"✅ New lead added: {lead['title']}")
        else:
            print(f"⚠️ Duplicate skipped: {lead['title']}")

def run_scraper():
    all_leads = []
    for category in CATEGORIES:
        print(f"🔍 Scraping {category}...")
        leads = get_posts(category)
        all_leads.extend(leads)
        time.sleep(2)  # polite delay
    insert_leads(all_leads)
    print(f"✅ Done. {len(all_leads)} leads scraped.")

if __name__ == "__main__":
    run_scraper()
