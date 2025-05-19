import os
import requests
import re
from datetime import datetime
from bs4 import BeautifulSoup
from supabase.client import create_client, Client  # FIXED import

print("Scraper started...")

# ─────────── CREDENTIALS ───────────
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
print("Connecting to Supabase...")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HOT_WORDS = ["motivated", "cash", "as-is", "urgent", "must sell", "investor", "fast", "cheap"]

def normalize_price(val):
    if not val:
        return None
    digits = re.sub(r"[^\d]", "", str(val))
    return int(digits) if digits else None

def get_existing_titles() -> set[str]:
    try:
        resp = supabase.table("craigslist_leads").select("title").limit(1000).execute()
        return {row["title"] for row in resp.data}
    except Exception as e:
        print("Error getting existing titles:", e)
        return set()

def fetch_and_store(region: str = "dallas") -> list[dict]:
    url = f"https://{region}.craigslist.org/search/rea?hasPic=1"
    print(f"Fetching from {url}")
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    posts = soup.find_all("li", class_="cl-static-search-result")

    all_leads = []
    for post in posts:
        title_el = post.select_one(".title")
        price_el = post.select_one(".priceinfo")
        link_el  = post.select_one("a")
        time_el  = post.select_one("time")

        title = title_el.text.strip() if title_el else "No title"
        link  = link_el["href"] if link_el else ""
        price = normalize_price(price_el.text) if price_el else None
        posted = time_el["datetime"] if time_el else datetime.utcnow().isoformat()
        fetched = datetime.utcnow().isoformat()

        lead = {
            "date_posted": posted,
            "title":       title,
            "link":        link,
            "price":       price,
            "fetched_at":  fetched,
        }
        all_leads.append(lead)

    print(f"Total leads fetched: {len(all_leads)}")

    existing = get_existing_titles()
    to_insert = [l for l in all_leads if l["title"] not in existing]
    print(f"New leads to insert: {len(to_insert)}")

    if to_insert:
        try:
            supabase.table("craigslist_leads").insert(to_insert).execute()
            print("Inserted new leads to Supabase.")
        except Exception as e:
            print("Error inserting to Supabase:", e)

    return all_leads

# Run it when the script is executed
if __name__ == "__main__":
    fetch_and_store()