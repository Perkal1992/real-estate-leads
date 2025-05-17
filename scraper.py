# scraper.py
import os
import requests
from bs4 import BeautifulSoup
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# ─── CONFIGURE YOUR REGION HERE ────────────────────────────────────────────────
# e.g. "sfbay", "newyork", "denver", "dfw", etc.
REGION = "sfbay"
# ────────────────────────────────────────────────────────────────────────────────

# load Supabase creds from the environment
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Please set SUPABASE_URL and SUPABASE_KEY in the environment")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def scrape_craigslist():
    """
    Fetch the latest real-estate ads from Craigslist for REGION,
    parse out date_posted, title, price, link.
    """
    url = f"https://{REGION}.craigslist.org/search/rea?sort=date"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    out = []
    for row in soup.select(".result-row"):
        # date
        dt = row.select_one("time")
        date_posted = dt["datetime"] if dt else None

        # title & link
        link_el = row.select_one(".result-title")
        title = link_el.get_text(strip=True) if link_el else None
        link  = link_el["href"] if link_el else None

        # price
        price_el = row.select_one(".result-price")
        price = price_el.get_text(strip=True).replace("$","") if price_el else None

        if link and title and date_posted:
            out.append({
                "date_posted": date_posted,
                "title": title,
                "link": link,
                "price": float(price) if price and price.isdigit() else None,
                "fetched_at": datetime.utcnow().isoformat()
            })

    return out

def store_leads(records):
    """
    Upsert the scraped records into Supabase.
    Assumes a table named `craigslist_leads` with a UNIQUE constraint on `link`.
    """
    if not records:
        return

    # Insert with on_conflict = "link" to dedupe
    supabase.table("craigslist_leads") \
            .insert(records, on_conflict="link") \
            .execute()

def fetch_and_store():
    """
    Scrape + store, then pull everything back into a pandas DataFrame.
    """
    # 1) scrape & push
    leads = scrape_craigslist()
    store_leads(leads)

    # 2) fetch from Supabase
    resp = supabase.table("craigslist_leads") \
                   .select("*") \
                   .order("date_posted", desc=True) \
                   .execute()
    data = resp.data or []
    df = pd.DataFrame(data)
    return df

if __name__ == "__main__":
    # quick smoke test
    df = fetch_and_store()
    print(df.head())
