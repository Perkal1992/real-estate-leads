import os
import streamlit as st
import pandas as pd
import altair as alt
import pydeck as pdk
from scraper import fetch_and_store

st.set_page_config(page_title="🏠 Real Estate Leads", layout="wide")

# --- Sidebar navigation ---
st.sidebar.title("🏠 Real Estate Leads")
page = st.sidebar.radio("", ["Leads", "Dashboard", "Settings"])

if page == "Leads":
    st.header("🔎 Latest Craigslist Listings")
    df = fetch_and_store(region=os.getenv("CRAIGS_REGION", "dallas"))
    if not df:
        st.info("No leads found yet. Click Refresh below.")
    else:
        st.dataframe(pd.DataFrame(df))

    if st.button("🔄 Refresh now"):
        st.cache_data.clear()
        st.experimental_rerun()

elif page == "Dashboard":
    st.header("📊 Analytics Dashboard")
    df = fetch_and_store(region=os.getenv("CRAIGS_REGION", "dallas"))
    if not df:
        st.info("No data to chart.")
    else:
        df = pd.DataFrame(df)
        df["date_posted"] = pd.to_datetime(df["date_posted"])
        # Price over time
        line = (
            alt.Chart(df)
            .mark_line(point=True)
            .encode(
                x="date_posted:T",
                y="price:Q",
                tooltip=["title", "price", "date_posted"],
            )
            .properties(height=300, width="100%")
        )
        st.altair_chart(line, use_container_width=True)

        # Map
        if {"latitude", "longitude"}.issubset(df.columns):
            df_map = df.dropna(subset=["latitude", "longitude"])
            st.pydeck_chart(
                pdk.Deck(
                    initial_view_state=pdk.ViewState(
                        latitude=df_map["latitude"].mean(),
                        longitude=df_map["longitude"].mean(),
                        zoom=11,
                    ),
                    layers=[
                        pdk.Layer(
                            "ScatterplotLayer",
                            data=df_map,
                            get_position=["longitude", "latitude"],
                            get_radius=100,
                            pickable=True,
                        )
                    ],
                )
            )

elif page == "Settings":
    st.header("⚙️ Settings")
    st.markdown(
        """
        **Supabase table:** `craigslist_leads`  
        Columns:
        - `id` (uuid primary key)  
        - `date_posted` (timestamptz)  
        - `title` (text unique)  
        - `link` (text)  
        - `price` (numeric)  
        - `fetched_at` (timestamptz default now())  
        - *optional:* latitude, longitude, city, hot_lead, etc.
        """
    )
    st.write("– To change your Craigslist region, set the `CRAIGS_REGION` env var (default `dallas`).")
