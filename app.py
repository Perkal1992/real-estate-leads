# app.py
import streamlit as st
import pandas as pd
from supabase import create_client, Client

# ─── LOAD CREDS FROM STREAMLIT SECRETS ──────────────────────────────────
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# ─── SUPABASE CLIENT ───────────────────────────────────────────────────
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── PAGE SETUP ────────────────────────────────────────────────────────
st.set_page_config(page_title="All Leads", layout="wide")
st.image("assets/logo.png", width=200)
st.title("📦 All Scraped Leads")
st.markdown("View and filter every lead we’ve pulled from Craigslist, Facebook & Zillow.")

# ─── FETCH DATA ────────────────────────────────────────────────────────
with st.spinner("Loading leads from Supabase..."):
    resp = supabase.table("leads")\
        .select("*")\
        .order("created_at", desc=True)\
        .execute()
    data = resp.data or []

if not data:
    st.warning("No leads found. Has your scraper run at least once?")
    st.stop()

df = pd.DataFrame(data)

# clickable “View” link
if "url" in df.columns:
    df["Link"] = df["url"].apply(lambda u: f"[🔗 View]({u})")

# normalize price
df["price"] = pd.to_numeric(df.get("price", 0), errors="coerce").fillna(0).astype(int)

# ─── SIDEBAR FILTERS ───────────────────────────────────────────────────
st.sidebar.header("Filters")
min_price, max_price = st.sidebar.slider(
    "Price range", 
    0, 
    int(df["price"].max()), 
    (0, int(df["price"].max())), 
    step=1000
)
title_search = st.sidebar.text_input("Title contains")

mask = df["price"].between(min_price, max_price)
if title_search:
    mask &= df["title"].str.contains(title_search, case=False, na=False)

filtered = df[mask]

# ─── DISPLAY & DOWNLOAD ────────────────────────────────────────────────
st.write(f"Showing **{len(filtered)}** of **{len(df)}** leads")
st.dataframe(filtered.drop(columns=["url"]), use_container_width=True, unsafe_allow_html=True)

st.download_button(
    "📥 Download CSV",
    filtered.to_csv(index=False),
    file_name="leads.csv",
    mime="text/csv"
)
