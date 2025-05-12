import streamlit as st
import pandas as pd
import requests
from supabase import create_client, Client
from datetime import datetime
import base64

# ──────── CREDENTIALS ────────
SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."  # Full key here
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ──────── STYLING ────────
st.set_page_config(page_title="Savory Realty Investments", layout="wide")
st.markdown("""
    <style>
        body {background-color:#001F1F!important;color:#d9ffcc!important;}
        .stApp {background-color:#001F1F!important;}
        [data-testid="stHeader"] {background-color:#003333;color:#d9ffcc;}
        .stButton>button {background-color:#00ff00!important;color:#000;font-weight:bold;}
    </style>
""", unsafe_allow_html=True)

st.title("🏘️ Savory Realty Lead Engine")
st.markdown("Real-time leads, hot deals, ARV estimates, and Street View coverage across DFW.")

# ──────── LOAD LEADS ────────
st.subheader("Live Leads from Supabase")
try:
    data = supabase.table("leads").select("*").order("created_at", desc=True).limit(100).execute()
    df = pd.DataFrame(data.data)
    if not df.empty:
        # Hot lead detection
        df["hot_lead"] = df["description"].str.contains("motivated|asap|cash|urgent|must sell", case=False, na=False)
        df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(df)
    else:
        st.warning("No leads found yet.")
except Exception as e:
    st.error(f"Failed to load leads: {e}")

# ──────── FILTERS ────────
if not df.empty:
    with st.expander("🔍 Filter Leads"):
        city_filter = st.text_input("City contains:")
        zip_filter = st.text_input("ZIP code:")
        only_hot = st.checkbox("Only Hot Leads")

        filtered_df = df.copy()
        if city_filter:
            filtered_df = filtered_df[filtered_df["city"].str.contains(city_filter, case=False, na=False)]
        if zip_filter:
            filtered_df = filtered_df[filtered_df["zip"].astype(str).str.contains(zip_filter, na=False)]
        if only_hot:
            filtered_df = filtered_df[filtered_df["hot_lead"] == True]

        st.dataframe(filtered_df)

# ──────── EXPORT TO CSV ────────
def get_csv_download_link(df, filename="leads.csv"):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">📥 Download CSV</a>'
    return href

if not df.empty:
    st.markdown(get_csv_download_link(df), unsafe_allow_html=True)

# ──────── SCRAPER TRIGGER (Optional) ────────
st.subheader("Manual Scraper Trigger")
if st.button("Run Zillow/Craigslist/Facebook Scrapers"):
    st.info("Triggering scrapers... (This is a placeholder – GitHub Actions handles actual scheduling)")
