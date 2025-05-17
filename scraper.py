import streamlit as st
import requests
from bs4 import BeautifulSoup
from supabase import Client, create_client
from datetime import datetime
import pandas as pd

# load your Supabase creds from Streamlit secrets
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# initialize supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# change this to your Craigslist subdomain (e.g. "sfbay", "newyork", etc.)
CRAIGSLIST_SUBDOMAIN = "sfbay"

def get_craigslist_leads():
    url = f"https://{CRAIGSLIST_SUBDOMAIN}.craigslist.org/search/rea"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    rows = []
    for post in soup.select(".result-row"):
        title_el = post.select_one(".result-title")
        price_el = post.select_one(".result-price")
        date_el  = post.select_one("time")

        item = {
            "date_posted": datetime.fromisoformat(date_el["datetime"]),
            "title": title_el.text,
            "link":   title_el["href"],
            "price":  float(price_el.text.replace("$", "")) if price_el else None,
            "fetched_at": datetime.utcnow(),
        }
        rows.append(item)
    return rows

def store_leads(rows: list[dict]):
    if not rows:
        return

    # upsert into your `craigslist_leads` table
    supabase.table("craigslist_leads") \
        .upsert(rows, on_conflict="link") \
        .execute()

def fetch_and_store() -> pd.DataFrame:
    """Fetch fresh leads, store in Supabase, then return a DataFrame."""
    rows = get_craigslist_leads()
    store_leads(rows)

    # now pull everything back out
    data = supabase.table("craigslist_leads") \
        .select("*") \
        .order("date_posted", desc=True) \
        .execute() \
        .data

    return pd.DataFrame(data)
