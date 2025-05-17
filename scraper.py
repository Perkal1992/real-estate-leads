import os
import requests
from bs4 import BeautifulSoup
from supabase import create_client
import pandas as pd
from datetime import datetime

# Supabase credentials from Streamlit secrets
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

REGION = "sfbay"  # ← change this to your Craigslist subdomain

@st.cache_data(ttl=300)
def fetch_and_store():
    # 1. Scrape
    resp = requests.get(f"https://{REGION}.craigslist.org/search/rea", timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select(".result-row")
    leads = []
    for it in items:
        title = it.select_one(".result-title").text
        link = it.select_one(".result-title")["href"]
        price_el = it.select_one(".result-price")
        price = float(price_el.text.replace("$", "")) if price_el else None
        date_posted = it.select_one("time")["datetime"]
        leads.append(
            {
                "date_posted": date_posted,
                "title": title,
                "link": link,
                "price": price,
                "fetched_at": datetime.utcnow().isoformat(),
            }
        )

    df = pd.DataFrame(leads)
    if df.empty:
        return df

    # 2. Upsert into Supabase
    supabase.table("craigslist_leads").insert(df.to_dict(orient="records")).execute()

    # 3. Fetch full table back
    result = supabase.table("craigslist_leads").select("*").execute()
    records = result.data or []
    return pd.DataFrame(records)

# Expose only fetch_and_store to app.py
