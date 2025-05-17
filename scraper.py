import os
import requests
from bs4 import BeautifulSoup
from supabase import create_client

# Grab your credentials from Streamlit Secrets
SUPABASE_URL = os.environ.get("SUPABASE_URL") or ""
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or ""
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_craigslist_leads():
    """
    Scrape the real-estate section of Craigslist for the latest postings.
    Returns a list of dicts: [{"title":..., "link":..., "price":...}, …]
    """
    # ← adjust to your city’s Craigslist real-estate URL
    url = "https://your-city.craigslist.org/search/rea"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    leads = []
    for row in soup.select(".result-row"):
        title_el = row.select_one(".result-title")
        price_el = row.select_one(".result-price")
        leads.append({
            "title": title_el.text.strip(),
            "link":  title_el["href"],
            "price": price_el.text.strip() if price_el else "",
        })
    return leads
