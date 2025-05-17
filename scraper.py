import requests
from bs4 import BeautifulSoup
import streamlit as st
from supabase import create_client, Client

# ── Supabase client from secrets.toml ──────────────────────────────────────────
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_craigslist_leads(region: str = "sfbay") -> list[dict]:
    """Scrape first page of Craigslist real-estate listings."""
    url = f"https://{region}.craigslist.org/search/rea"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    leads = []
    for row in soup.select(".result-row"):
        title_el = row.select_one(".result-title")
        time_el = row.select_one("time")
        price_el = row.select_one(".result-price")

        leads.append({
            "date_posted": time_el["datetime"] if time_el else None,
            "title": title_el.text if title_el else None,
            "link": title_el["href"] if title_el else None,
            "price": float(price_el.text.strip("$")) if price_el else None,
        })
    return leads

def store_leads(leads: list[dict]) -> list[dict]:
    """Insert scraped leads into Supabase and return inserted rows."""
    if not leads:
        return []
    res = (
        supabase
        .from_("craigslist_leads")
        .insert(leads)
        .select("*")    # ← ensures PostgREST doesn’t send columns=()
        .execute()
    )
    return res.data or []

def get_all_leads() -> list[dict]:
    """Fetch all leads sorted by newest first."""
    res = (
        supabase
        .from_("craigslist_leads")
        .select("*")
        .order("date_posted", desc=True)
        .execute()
    )
    return res.data or []
