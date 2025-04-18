# app.py
import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from supabase import create_client, Client
from bs4 import BeautifulSoup
from config import SUPABASE_URL, SUPABASE_KEY, GOOGLE_MAPS_API_KEY, RAPIDAPI_KEY

# ───────────────────────────────────────────────────────────
# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ───────────────────────────────────────────────────────────
# MUST be the first Streamlit command
st.set_page_config(
    page_title="🏘️ Savory Realty Lead Engine",
    layout="wide",
)

# ───────────────────────────────────────────────────────────
# Black marble background + white text styling
st.markdown(
    """
    <style>
    body {
      background-color: #1c1c1c;
      color: white;
      font-family: Arial, sans-serif;
    }
    .stApp {
      background-image: url("https://www.transparenttextures.com/patterns/black-marble.png");
      background-size: cover;
    }
    /* Inputs and buttons */
    .stFileUploader, .stTextInput, .stSelectbox, .stButton>button {
      background: rgba(0,0,0,0.3) !important;
      color: white !important;
    }
    /* Dataframe cells */
    .stDataFrame div[role="cell"] {
      color: white !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🏘️ Savory Realty Lead Engine")
st.markdown("Upload a CSV or run live scrapers for FSBO/off‑market deals in Dallas County.")

# ───────────────────────────────────────────────────────────
# UTILITIES
# ───────────────────────────────────────────────────────────

def geocode_address(address: str):
    """Return (lat, lng) or (None, None)."""
    url = (
        "https://maps.googleapis.com/maps/api/geocode/json"
        f"?address={requests.utils.quote(address)}"
        f"&key={GOOGLE_MAPS_API_KEY}"
    )
    r = requests.get(url)
    if not r.ok:
        return None, None
    result = r.json()
    if result.get("status") == "OK":
        loc = result["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"]
    return None, None

def push_to_supabase(record: dict):
    """Insert a single lead into Supabase."""
    try:
        supabase.table("leads").insert(record).execute()
    except Exception as e:
        st.warning(f"⚠️ Supabase insert failed: {e}")

# ───────────────────────────────────────────────────────────
# SCRAPERS
# ───────────────────────────────────────────────────────────

def scrape_zillow_rapidapi_fsbo(zip_code="75201", limit=20):
    """Fetch FSBO listings from RapidAPI Zillow."""
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
    if not r.ok:
        return []
    data = r.json() or {}
    leads = []
    for item in data.get("props", []):
        addr  = item.get("address")
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

def scrape_craigslist_dallas(limit=20):
    """Scrape Dallas Craigslist real estate."""
    url = "https://dallas.craigslist.org/search/rea"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    if not r.ok:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("li.result-row")[:limit]
    leads = []
    for post in items:
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

# ───────────────────────────────────────────────────────────
# RUN & PUSH LOGIC
# ───────────────────────────────────────────────────────────

def run_all_scrapers():
    zillow     = scrape_zillow_rapidapi_fsbo()
    craigslist = scrape_craigslist_dallas()
    all_leads  = zillow + craigslist
    for lead in all_leads:
        push_to_supabase(lead)
    return all_leads

# ───────────────────────────────────────────────────────────
# CSV UPLOAD FLOW
# ───────────────────────────────────────────────────────────

def upload_and_push_csv(csv_file):
    df = pd.read_csv(csv_file)
    if "Address" not in df.columns:
        st.error("❌ Your CSV must contain a column named 'Address'")
        return

    # Geocode every address
    df["Latitude"], df["Longitude"] = zip(
        *df["Address"].map(lambda a: geocode_address(a))
    )
    df["Google Maps"] = df.apply(
        lambda r: f"https://www.google.com/maps?q={r.Latitude},{r.Longitude}", axis=1
    )
    df["Street View"] = df.apply(
        lambda r: (
            f"https://maps.googleapis.com/maps/api/streetview"
            f"?size=600x300&location={r.Latitude},{r.Longitude}"
            f"&key={GOOGLE_MAPS_API_KEY}"
        ),
        axis=1
    )
    st.dataframe(df)

    # Push each row
    for _, row in df.iterrows():
        record = {
            "source":   "CSV Upload",
            "address":  row["Address"],
            "city":     row.get("City", ""),
            "state":    row.get("State", ""),
            "zip":      row.get("Zip", ""),
            "latitude": row.Latitude,
            "longitude":row.Longitude,
            "price":    row.get("Price", None),
            "google_maps": row["Google Maps"],
            "street_view": row["Street View"],
            "created_at": datetime.utcnow().isoformat(),
        }
        push_to_supabase(record)
    st.success("✅ CSV upload + Enrich complete.")

# ───────────────────────────────────────────────────────────
# STREAMLIT TABS
# ───────────────────────────────────────────────────────────

tabs = st.tabs(["📁 Upload CSV", "🔄 Scrape Now", "📊 View Leads"])

with tabs[0]:
    csv_file = st.file_uploader("Upload CSV of Property Leads", type="csv")
    if csv_file:
        upload_and_push_csv(csv_file)

with tabs[1]:
    if st.button("Scrape FSBO + Craigslist Now"):
        with st.spinner("Scraping…"):
            scraped = run_all_scrapers()
            st.success(f"✅ {len(scraped)} new leads scraped & pushed.")

with tabs[2]:
    st.markdown("### Live Lead Feed (latest 100)")
    resp = supabase.table("leads")\
        .select("*")\
        .order("created_at", desc=True)\
        .limit(100)\
        .execute()
    df = pd.DataFrame(resp.data or [])
    if not df.empty:
        st.dataframe(df)
    else:
        st.info("No leads yet. Upload or scrape above.")

