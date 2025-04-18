# Your app.py content goes here...import os
import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from supabase import create_client, Client
from bs4 import BeautifulSoup

# ── CONFIG / CREDENTIALS ────────────────────────────────────────────────────────
# These values are read from your Repo Secrets or .env (Render / Streamlit Cloud)
SUPABASE_URL       = os.getenv("SUPABASE_URL")
SUPABASE_KEY       = os.getenv("SUPABASE_KEY")
GOOGLE_MAPS_API_KEY= os.getenv("GOOGLE_MAPS_API_KEY")
RAPIDAPI_KEY       = os.getenv("RAPIDAPI_KEY")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── PAGE CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🏘️ Savory Realty Lead Engine",
    page_icon="🏠",
    layout="wide",
)

# ── CUSTOM STYLING (BLACK MARBLE) ───────────────────────────────────────────────
st.markdown(
    """
    <style>
      body      { background-color: #1c1c1c; color: white; }
      .stApp    { 
        background-image: url("https://www.transparenttextures.com/patterns/black-marble.png");
        background-size: cover; 
      }
      .css-1qfqu09 { background-color: #1c1c1c; }
      .stFileUploader, .stButton>button {
        background-color: #333333; color: white;
      }
      .stTextInput>div>div>input,
      .stSelectbox, .stMultiselect {
        background-color: #222222; color: white;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🏘️ Savory Realty Lead Engine")
st.markdown("Upload CSV or run live scrapers for Dallas FSBO & Craigslist every 30 min.")

# ── UTILITIES ───────────────────────────────────────────────────────────────────

def geocode_address(address: str):
    """Return (lat, lng) or (None, None)."""
    url = f"https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": GOOGLE_MAPS_API_KEY}
    resp = requests.get(url, params=params)
    if resp.ok:
        data = resp.json()
        if data["status"] == "OK":
            loc = data["results"][0]["geometry"]["location"]
            return loc["lat"], loc["lng"]
    return None, None

def push_to_supabase(lead: dict):
    """Insert a single lead dict into Supabase."""
    try:
        supabase.table("leads").insert(lead).execute()
    except Exception as e:
        st.warning(f"Failed to push lead: {e}")

# ── SCRAPERS ────────────────────────────────────────────────────────────────────

def scrape_zillow_fsbo(zipcode="75201"):
    """Fetch FSBO listings via RapidAPI Zillow endpoint."""
    url = "https://zillow-com1.p.rapidapi.com/propertyListings"
    headers = {
        "x-rapidapi-host": "zillow-com1.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY
    }
    params = {
        "propertyStatus":"FOR_SALE",
        "homeType":["Houses"],
        "sort":"Newest",
        "limit":"10",
        "zip": zipcode
    }
    resp = requests.get(url, headers=headers, params=params)
    leads = []
    if resp.ok:
        data = resp.json().get("props", [])
        for item in data:
            addr  = item.get("address")
            price = item.get("price")
            if not addr:
                continue
            lat,lng = geocode_address(addr)
            if lat and lng:
                leads.append({
                    "source":       "Zillow FSBO",
                    "address":      addr,
                    "city":         "",
                    "state":        "TX",
                    "zip":          zipcode,
                    "price":        price,
                    "latitude":     lat,
                    "longitude":    lng,
                    "google_maps":  f"https://www.google.com/maps?q={lat},{lng}",
                    "street_view":  f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lng}",
                    "created_at":   datetime.utcnow().isoformat()
                })
    return leads

def scrape_craigslist():
    """Scrape DFW Craigslist REA category."""
    url = "https://dallas.craigslist.org/search/rea"
    headers = {"User-Agent":"Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    leads = []
    if resp.ok:
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select("li.result-row")[:10]
        for row in rows:
            title = row.select_one("a.result-title")
            if not title:
                continue
            addr = title.text.strip()
            lat,lng = geocode_address(addr)
            if lat and lng:
                leads.append({
                    "source":       "Craigslist",
                    "address":      addr,
                    "city":         "Dallas",
                    "state":        "TX",
                    "zip":          "",
                    "price":        None,
                    "latitude":     lat,
                    "longitude":    lng,
                    "google_maps":  f"https://www.google.com/maps/search/?api=1&query={lat},{lng}",
                    "street_view":  f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lng}",
                    "created_at":   datetime.utcnow().isoformat()
                })
    return leads

# ── WORKFLOWS ───────────────────────────────────────────────────────────────────

def run_scrapers_and_push():
    z = scrape_zillow_fsbo()
    c = scrape_craigslist()
    combined = z + c
    for lead in combined:
        push_to_supabase(lead)
    return combined

def upload_csv_flow(uploaded_file):
    df = pd.read_csv(uploaded_file)
    for idx,row in df.iterrows():
        addr = row["Address"]
        lat,lng = geocode_address(addr)
        lead = {
            "source":      "CSV Upload",
            "address":     addr,
            "city":        "Dallas",
            "state":       "TX",
            "zip":         "",
            "price":       row.get("Price", None),
            "latitude":    lat,
            "longitude":   lng,
            "google_maps": f"https://www.google.com/maps?q={lat},{lng}" if lat else None,
            "street_view": f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lng}" if lat else None,
            "created_at":  datetime.utcnow().isoformat()
        }
        push_to_supabase(lead)
    return df

# ── UI TABS ─────────────────────────────────────────────────────────────────────

tabs = st.tabs(["📁 Upload CSV", "🔄 Scrape Now", "📊 View Leads"])

# Tab 1: CSV upload
with tabs[0]:
    file = st.file_uploader("Upload CSV (must have 'Address' column)", type="csv")
    if file:
        df_out = upload_csv_flow(file)
        st.success("CSV processed & pushed!")
        st.dataframe(df_out)

# Tab 2: Manual scrape
with tabs[1]:
    if st.button("Run Live Scrapers"):
        with st.spinner("Scraping Zillow & Craigslist…"):
            new_leads = run_scrapers_and_push()
            st.success(f"{len(new_leads)} leads scraped & saved.")

# Tab 3: View from Supabase
with tabs[2]:
    st.markdown("### Live Lead Feed")
    resp = supabase.table("leads").select("*").order("created_at", desc=True).limit(100).execute()
    data = resp.data or []
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df)
    else:
        st.info("No leads found yet. Run scrapers or upload CSV.")
