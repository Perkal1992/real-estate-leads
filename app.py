import streamlit as st
import pandas as pd
import altair as alt
from scraper import get_craigslist_leads, store_leads, get_all_leads

st.set_page_config(page_title="Real Estate Leads", page_icon="🏠", layout="wide")

st.markdown(
    "<h1 style='text-align:center; font-weight:bold;'>🏠 Real Estate Leads & Dashboard</h1>",
    unsafe_allow_html=True,
)

menu = st.sidebar.radio("Navigate", ["Leads", "Dashboard", "Settings"])

# ─── LEADS ─────────────────────────────────────────────────────────────────────
if menu == "Leads":
    st.header("🔎 Latest Craigslist Listings")
    region = st.sidebar.text_input("Craigslist subdomain", value="sfbay")

    if st.sidebar.button("Refresh now"):
        st.cache_data.clear()

    @st.cache_data(ttl=300)
    def fetch_and_store(r):
        raw = get_craigslist_leads(r)
        return store_leads(raw)

    leads = fetch_and_store(region)

    if leads:
        df = pd.DataFrame(leads)
        df["date_posted"] = pd.to_datetime(df["date_posted"])
        df["fetched_at"] = pd.to_datetime(df["fetched_at"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No new leads found.")

# ─── DASHBOARD ─────────────────────────────────────────────────────────────────
elif menu == "Dashboard":
    st.header("📊 Analytics Dashboard")
    all_leads = get_all_leads()

    if all_leads:
        df = pd.DataFrame(all_leads)
        df["date_posted"] = pd.to_datetime(df["date_posted"])
        df["price"] = pd.to_numeric(df["price"], errors="coerce")

        st.subheader("Leads Over Time")
        line = (
            alt.Chart(df)
            .mark_line(point=True)
            .encode(
                x=alt.X("date_posted:T", title="Date Posted"),
                y=alt.Y("count()", title="Number of Leads"),
                tooltip=["date_posted:T", "count()"]
            )
            .properties(width="100%", height=300)
        )
        st.altair_chart(line, use_container_width=True)

        st.subheader("Price Distribution")
        hist = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("price:Q", bin=alt.Bin(maxbins=40), title="Price ($)"),
                y=alt.Y("count()", title="Count"),
                tooltip=["count()", "price:Q"]
            )
            .properties(width="100%", height=300)
        )
        st.altair_chart(hist, use_container_width=True)
    else:
        st.info("No leads in the database yet.")

# ─── SETTINGS ──────────────────────────────────────────────────────────────────
else:
    st.header("⚙️ Settings & Setup")
    st.markdown(
        """
        - **Supabase table**: `craigslist_leads`  
        - **Columns**:  
          `id` (uuid primary key),  
          `date_posted` (timestamp),  
          `title` (text),  
          `link` (text UNIQUE),  
          `price` (numeric),  
          `fetched_at` (timestamp DEFAULT now())  
        - **Cache TTL**: 5 minutes (use “Refresh now” to override)  
        """
    )
