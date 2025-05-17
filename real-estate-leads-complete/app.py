# app.py
import os
import streamlit as st
import pandas as pd

# 1) CONFIG: pull from Render’s Environment
SUPABASE_URL         = os.getenv("SUPABASE_URL")
SUPABASE_KEY         = os.getenv("SUPABASE_KEY")
GOOGLE_MAPS_API_KEY  = os.getenv("GOOGLE_MAPS_API_KEY")
RAPIDAPI_KEY         = os.getenv("RAPIDAPI_KEY")

if not (SUPABASE_URL and SUPABASE_KEY and GOOGLE_MAPS_API_KEY and RAPIDAPI_KEY):
    st.error("⚠️ Missing one or more environment variables. Please set SUPABASE_URL, SUPABASE_KEY, GOOGLE_MAPS_API_KEY and RAPIDAPI_KEY in your Render Dashboard.")
    st.stop()

# 2) Initialize Supabase client for your live feed
from supabase import create_client, Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 3) Import your Craigslist scraper and any enrichment utils
#    (adjust these imports to match your project layout)
from scraper import get_craigslist_leads
from utils.enrichment import enrich_addresses  # example

# 4) Functions to fetch your data
@st.cache_data(ttl=60)
def load_realtime_leads() -> pd.DataFrame:
    resp = supabase.table("leads").select("*").execute()
    data = resp.data or []
    return pd.DataFrame(data)

@st.cache_data(ttl=3600)
def load_craigslist() -> pd.DataFrame:
    leads = get_craigslist_leads(api_key=RAPIDAPI_KEY)
    return pd.DataFrame(leads)

# 5) Streamlit layout
st.set_page_config(
    page_title="Real Estate Leads Dashboard",
    layout="wide",
)

st.title("🏠 Real Estate Leads")

with st.sidebar:
    st.header("Controls")
    if st.button("Refresh All"):
        st.cache_data.clear()  # force reload

st.subheader("🔴 Live Redfin Feed")
df_live = load_realtime_leads()
if df_live.empty:
    st.write("No live data available.")
else:
    # optionally enrich
    df_live = enrich_addresses(df_live, GOOGLE_MAPS_API_KEY)
    st.dataframe(df_live)

st.subheader("📋 Craigslist Leads")
df_cl = load_craigslist()
if df_cl.empty:
    st.write("No Craigslist leads found.")
else:
    st.dataframe(df_cl)
