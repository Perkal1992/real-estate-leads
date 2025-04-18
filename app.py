# app.py

import os
import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from supabase import create_client, Client
from bs4 import BeautifulSoup
from config import SUPABASE_URL, SUPABASE_KEY, GOOGLE_MAPS_API_KEY, RAPIDAPI_KEY

# ------------------------------------------------------------------------------
# Initialize Supabase client (uses env / secrets in config.py)
# ------------------------------------------------------------------------------
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ------------------------------------------------------------------------------
# Streamlit page config (MUST BE FIRST Streamlit COMMAND)
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="🏘️ Savory Realty Investments",
    layout="wide",
)

# ------------------------------------------------------------------------------
# Black‑marble background + form/theme styling
# ------------------------------------------------------------------------------
st.markdown(
    """
    <style>
      body, .stApp {
        background-color: #1c1c1c !important;
        background-image: url("https://www.transparenttextures.com/patterns/black-marble.png") !important;
        background-size: cover !important;
        color: #f0f0f0 !important;
      }
      .stFileUploader, .stTextInput, .stButton, .stSelectbox {
        background-color: rgba(0,0,0,0.4) !important;
        color: #f0f0f0 !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------------------
# Title + Description
# ------------------------------------------------------------------------------
st.title("🏘️ Savory Realty Investments")
st.markdown(
    "Upload a CSV of property addresses or run live scrapers for FSBO/off‑market deals in Dallas County."
)

# ------------------------------------------------------------------------------
# Utility: Geocode an address via Google Maps API
# ------------------------------------------------------------------------------
def geocode_address(address: str):
    """Returns (lat, lng) or (None, None)."""
    url = (
        "https://maps.googleapis.com/maps/api/geocode/json"
        f"?address={requests.utils.quote(address)}"
        f"&key={GOOGLE_MAPS_API_KEY}"
    )
    resp = requests.get(url)
    if resp.ok:
        data = resp.json()
        if data.get("status") == "OK":
            loc = data["results"][0]["geometry"]["location"]
            return loc["lat"], loc["lng"]
    return None, None

# ------------------------------------------------------------------------------
# Utility: Push a single lead record to Supabase
# ------------------------------------------------------------------------------
def push_to_supabase(record: dict):
    try:
        supabase.table("leads").insert(record).execute()
    except Exception as e:
        st.warning(f"❌ Failed to insert lead: {e}")

# ------------------------------------------------------------------------------
# Scraper: Zillow FSBO via RapidAPI
# ------------------------------------------------------------------------------
def scrape_zillow_rapidapi_fsbo(zip_code="75201", limit=20):
    endpoint = "https://zillow-com1.p.rapidapi.com/propertyListings"
    params = {
        "propertyStatus": "FOR_SALE",
        "homeType": ["Houses"],
        "sort": "Newest",
        "limit": str(limit),
        "zip": zip_code,
    }
    headers = {
        "x-rapidapi-host": "zillow-com1.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY,
    }
    r = requests.get(endpoint, headers=headers, params=params)
    leads = []
    if r.ok:
        data = r.json()
        for item in data.get("props", []):
            addr = item.get("address")
            price = item.get("price")
            lat, lng = geocode_address(addr) if addr else (None, None)
            if addr and lat and lng:
                leads.append({
                    "source": "Zillow FSBO (RapidAPI)",
                    "address": addr,
                    "city": "",
                    "state": "TX",
                    "zip": zip_code,
                    "latitude": lat,
                    "longitude": lng,
                    "price": price,
                    "google_maps": f"https://www.google.com/maps?q={lat},{lng}",
                    "street_view": (
                      f"https://maps.googleapis.com/maps/api/streetview"
                      f"?size=600x300&location={lat},{lng}"
                      f"&key={GOOGLE_MAPS_API_KEY}"
                    ),
                    "created_at": datetime.utcnow().isoformat(),
                })
    return leads

# ------------------------------------------------------------------------------
# Scraper: Craigslist Dallas real estate listings
# ------------------------------------------------------------------------------
def scrape_craigslist_dallas(limit=20):
    url = "https://dallas.craigslist.org/search/rea"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    leads = []
    if resp.ok:
        soup = BeautifulSoup(resp.text, "html.parser")
        postings = soup.select("li.result-row")[:limit]
        for post in postings:
            title = post.select_one("a.result-title")
            if not title:
                continue
            addr = title.get_text(strip=True)
            lat, lng = geocode_address(addr)
            if lat and lng:
                leads.append({
                    "source": "Craigslist DFW",
                    "address": addr,
                    "city": "Dallas",
                    "state": "TX",
                    "zip": "",
                    "latitude": lat,
                    "longitude": lng,
                    "price": None,
                    "google_maps": f"https://www.google.com/maps?q={lat},{lng}",
                    "street_view": (
                      f"https://maps.googleapis.com/maps/api/streetview"
                      f"?size=600x300&location={lat},{lng}"
                      f"&key={GOOGLE_MAPS_API_KEY}"
                    ),
                    "created_at": datetime.utcnow().isoformat(),
                })
    return leads

# ------------------------------------------------------------------------------
# Crawl both sources & push leads
# ------------------------------------------------------------------------------
def run_all_scrapers():
    z_leads = scrape_zillow_rapidapi_fsbo()
    c_leads = scrape_craigslist_dallas()
    all_leads = z_leads + c_leads
    for lead in all_leads:
        push_to_supabase(lead)
    return all_leads

# ------------------------------------------------------------------------------
# CSV Upload & Enrich ➞ push to Supabase
# ------------------------------------------------------------------------------
def upload_csv_and_push(file):
    df = pd.read_csv(file)
    if "Address" not in df.columns:
        st.error("❌ Your CSV must contain a column named 'Address'")
        return

    # Geocode each address
    df["Latitude"], df["Longitude"] = zip(
        *df["Address"].apply(lambda a: geocode_address(a))
    )
    df["Google Maps"] = df.apply(
        lambda r: f"https://www.google.com/maps?q={r.Latitude},{r.Longitude}",
        axis=1,
    )
    df["Street View"] = df.apply(
        lambda r: (
            f"https://maps.googleapis.com/maps/api/streetview"
            f"?size=600x300&location={r.Latitude},{r.Longitude}"
            f"&key={GOOGLE_MAPS_API_KEY}"
        ),
        axis=1,
    )

    # Show enriched DataFrame
    st.dataframe(df)

    # Push rows to Supabase
    for _, row in df.iterrows():
        push_to_supabase({
            "source": "CSV Upload",
            "address": row["Address"],
            "city": row.get("City", ""),
            "state": row.get("State", ""),
            "zip": row.get("Zip", ""),
            "latitude": row.Latitude,
            "longitude": row.Longitude,
            "price": row.get("Price", None),
            "google_maps": row["Google Maps"],
            "street_view": row["Street View"],
            "created_at": datetime.utcnow().isoformat(),
        })
    st.success("✅ CSV upload + enrich complete!")

# ------------------------------------------------------------------------------
# Streamlit Tabs: Upload CSV | Live Scrape | View Leads
# ------------------------------------------------------------------------------
tabs = st.tabs(["📁 Upload CSV", "🔄 Live Scrape", "📊 View Leads"])

with tabs[0]:
    uploaded_file = st.file_uploader("Upload property CSV", type="csv")
    if uploaded_file:
        upload_csv_and_push(uploaded_file)

with tabs[1]:
    if st.button("Run live scrapers now"):
        with st.spinner("Scraping Zillow FSBO & Craigslist..."):
            new_leads = run_all_scrapers()
            st.success(f"✅ {len(new_leads)} leads scraped & stored.")

with tabs[2]:
    st.subheader("Supabase — Most Recent Leads")
    resp = (
        supabase.table("leads")
        .select("*")
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    data = resp.data or []
    st.dataframe(pd.DataFrame(data))
