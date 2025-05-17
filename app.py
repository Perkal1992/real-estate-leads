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
    df = fetch_and_store()
    if df.empty:
        st.info("No leads found yet. Click Refresh below.")
    else:
        st.dataframe(df)

    if st.button("🔄 Refresh now"):
        st.cache_data.clear()
        df = fetch_and_store()
        st.experimental_rerun()

elif page == "Dashboard":
    st.header("📊 Analytics Dashboard")
    df = fetch_and_store()
    if df.empty:
        st.info("No data to chart.")
    else:
        df["date_posted"] = pd.to_datetime(df["date_posted"])
        # Price over time
        chart = (
            alt.Chart(df)
            .mark_line(point=True)
            .encode(
                x="date_posted:T",
                y="price:Q",
                tooltip=["title", "price", "date_posted"],
            )
            .properties(height=300, width="100%")
        )
        st.altair_chart(chart, use_container_width=True)

        # Map
        if "latitude" in df.columns and "longitude" in df.columns:
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
    st.write("– Make sure your Supabase table is named `craigslist_leads` with columns:")
    st.markdown(
        """
        - `id` (uuid primary key)  
        - `date_posted` (timestamptz)  
        - `title` (text)  
        - `link` (text unique)  
        - `price` (numeric)  
        - `fetched_at` (timestamptz default now())  
        - plus any of: latitude, longitude, etc.
        """
    )
    st.write("– Change your region/subdomain in `scraper.py` to your city")
