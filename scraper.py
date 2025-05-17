# scraper.py
import os
import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st
from supabase import create_client, Client

# ─── CONFIG ────────────────────────────────────────────────────────────────────

# e.g. "sfbay", "newyork", "dfw", etc.
REGION = "DFW"

# pull these from your Streamlit secrets.toml
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TABLE = "craigslist_leads"

# ─── FETCH ─────────────────────────────────────────────────────────────────────

def fetch_craigslist():
    url = f"https://{REGION}.craigslist.org/search/rea"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    items = []
    for result in soup.select(".result-row")[:50]:
        # date
        date = result.select_one("time.result-date")["datetime"]

        # title + link
        link_el = result.select_one("a.result-title")
        title = link_el.text.strip()
        link  = link_el["href"]

        # price, may be missing
        price_el = result.select_one(".result-price")
        price = float(price_el.text.strip().replace("$","")) if price_el else None

        items.append({
            "date_posted": date,
            "title":       title,
            "link":        link,
            "price":       price,
            "fetched_at":  pd.Timestamp.utcnow().isoformat(),
        })

    return items

# ─── STORE / UPSET ─────────────────────────────────────────────────────────────

def store_leads(records):
    # upsert on the unique link
    res = (
        supabase
        .table(TABLE)
        .insert(records, upsert=True)
        .execute()
    )
    if res.error:
        raise Exception(f"Supabase error: {res.error.message}")
    return res.data

# ─── PUBLIC API ────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def fetch_and_store():
    raw = fetch_craigslist()
    if not raw:
        # nothing new to fetch
        data = supabase.table(TABLE).select("*").execute().data
    else:
        store_leads(raw)
        data = supabase.table(TABLE).select("*").execute().data

    # convert to DataFrame
    df = pd.DataFrame(data)
    if "date_posted" in df:
        df["date_posted"] = pd.to_datetime(df["date_posted"])
    return df
