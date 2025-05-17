import os
from dotenv import load_dotenv
import streamlit as st
from supabase import create_client, Client
from scraper import get_craigslist_leads

# ─── CONFIG ───────────────────────────────────────────────────────────────────
# Load local .env in dev; on Render these come from the environment directly
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Safety check
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error(
        "Supabase credentials not found. "
        "Please set SUPABASE_URL and SUPABASE_KEY "
        "in your .env or Render dashboard."
    )
    st.stop()

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ─── DATA LAYER ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_listings():
    """Fetches your real‐estate listings from Supabase."""
    resp = supabase.table("listings").select("*").execute()
    if resp.error:
        st.error(f"Error fetching listings: {resp.error.message}")
        return []
    return resp.data


@st.cache_data(ttl=300)
def fetch_craigslist_leads():
    """Scrape craigslist leads via your scraper.py module."""
    try:
        return get_craigslist_leads()
    except Exception as e:
        st.error(f"Error scraping Craigslist: {e}")
        return []


# ─── UI ────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Real Estate Leads", layout="wide")
st.title("🏠 Real Estate Leads Dashboard")

st.header("📋 Your Supabase Listings")
listings = fetch_listings()
if listings:
    st.dataframe(listings)
else:
    st.write("No listings found yet.")

st.header("📣 Craigslist Leads")
if st.button("Load Craigslist Leads"):
    leads = fetch_craigslist_leads()
    if leads:
        st.dataframe(leads)
    else:
        st.write("No leads returned.")

