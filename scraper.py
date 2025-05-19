import os
import requests
from datetime import datetime
from supabase import create_client, Client
from bs4 import BeautifulSoup

print("Scraper started...")

# ──────── ENV VARIABLES ────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ──────── CONFIG ────────
SOURCE = "craigslist"
TARGET_URL = "https://dallas.craigslist.org/search/rea?hasPic=1"
HOT_WORDS = ["cash", "as-is", "must sell", "motivated", "investor"]

def normalize_title(title: str) -> str:
    return title.strip().replace("\n", "").replace("\r", "")

def is_hot_lead(title: str) -> bool:
    title_lower = title.lower()
    return any(word in title_lower for word in HOT_WORDS)

def fetch_existing_titles() -> set:
    try:
        result = supabase.table("craigslist_leads").select("title").limit(1000).execute()
        return {item["title"] for item in result.data}
    except Exception as e:
        print("Error fetching existing titles:", e)
        return set()

def scrape():
    print(f"Scraping {TARGET_URL} ...")
    res = requests.get(TARGET_URL)
    soup = BeautifulSoup(res.text, "html.parser")
    listings = soup.select(".result-row")
    
    print(f"Found {len(listings)} listings.")
    existing_titles = fetch_existing_titles()

    for item in listings:
        title_elem = item.select_one(".result-title")
        if not title_elem:
            continue
        title = normalize_title(title_elem.text)
        if title in existing_titles:
            continue  # skip duplicates

        post = {
            "title": title,
            "date_posted": datetime.utcnow().isoformat(),
            "source": SOURCE,
            "is_hot": is_hot_lead(title)
        }

        try:
            supabase.table("craigslist_leads").insert(post).execute()
            print("✅ Inserted:", title)
        except Exception as err:
            print("❌ Insert error:", err)

if __name__ == "__main__":
    try:
        scrape()
        print("✅ Scraper finished successfully.")
    except Exception as e:
        print("❌ Critical error in scraper:", e)
