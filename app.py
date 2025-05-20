import os
import base64
import streamlit as st
import pandas as pd
import altair as alt
import pydeck as pdk
from supabase import create_client

SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB3a2JzenNsamxweGhsZmN2ZGVyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQzNDk4MDEsImV4cCI6MjA1OTkyNTgwMX0.bjVMzL4X6dN6xBx8tV3lT7XPsOFIEqMLv0pG3y6N-4o"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── Background styling ─────────────────────────────
def _get_base64(image_path: str) -> str:
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

background_base64 = _get_base64("logo.png")
st.set_page_config(page_title="Savory Realty Investments", page_icon="logo.png", layout="wide")
st.markdown(
    f"""
    <style>
      [data-testid="stAppViewContainer"] {{
        background: linear-gradient(rgba(0,0,0,0.6), rgba(0,0,0,0.6)),
                    url("data:image/png;base64,{background_base64}") center center / cover no-repeat fixed;
      }}
      .block-container {{ position: relative; z-index: 2; }}
      [data-testid="collapsedControl"] {{
        position: fixed !important; top: 0px !important; left: 0px !important;
        z-index: 99999 !important; background: black !important; border-radius: 0 !important;
      }}
      [data-testid="stSidebar"] {{ background-color: #000 !important; }}
      [data-testid="stDataFrame"],
      [data-testid="stAltairChart"] {{
        background-color: rgba(255, 255, 255, 0.2) !important;
        backdrop-filter: blur(4px); border: none !important; box-shadow: none !important;
      }}
    </style>
    """, unsafe_allow_html=True,
)
st.markdown(
    """<style>.stButton>button { background-color: #0a84ff; color: #fff; }</style>""",
    unsafe_allow_html=True,
)

# ─── Cached Supabase pull ─────────────────────────────
@st.cache_data(ttl=300)
def get_data() -> pd.DataFrame:
    resp = supabase.table("craigslist_leads").select("*").order("date_posted", desc=True).execute()
    return pd.DataFrame(resp.data)

# ─── Sidebar navigation ─────────────────────────────
st.sidebar.image("logo.png", width=48)
st.sidebar.title("Savory Realty Investments")
page = st.sidebar.radio("", ["Live Leads", "Leads Dashboard", "Upload PropStream", "Settings"])

# ─── Live Leads Table ───────────────────────────────
if page == "Live Leads":
    st.header("📥 Live Leads")
    df = get_data()
    if df.empty:
        st.warning("No data yet.")
    else:
        df["map_url"] = df.apply(lambda r: f"https://www.google.com/maps?q={r.get('latitude')},{r.get('longitude')}" if pd.notna(r.get("latitude")) else "", axis=1)
        df["Street View"] = df.apply(lambda r: f"https://maps.googleapis.com/maps/api/streetview?size=600x300&location={r.get('latitude')},{r.get('longitude')}&key=YOUR_GOOGLE_MAPS_API_KEY" if pd.notna(r.get("latitude")) else "", axis=1)
        df["Hot"] = df.get("hot_lead", False).apply(lambda x: "🔥" if x else "")
        st.dataframe(df[["date_posted", "title", "price", "arv", "equity", "Hot", "map_url", "Street View"]], use_container_width=True)
        st.download_button("📤 Download CSV", df.to_csv(index=False), "leads.csv")

# ─── Leads Dashboard ─────────────────────────────
elif page == "Leads Dashboard":
    st.header("📊 Leads Dashboard")
    df = get_data()
    if df.empty:
        st.warning("No data available."); st.stop()

    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["date_posted"] = pd.to_datetime(df["date_posted"], errors="coerce")
    df["arv"] = df.get("arv", df["price"] * 1.35)
    df["equity"] = df["arv"] - df["price"]
    df["hot_lead"] = df["equity"] / df["arv"] >= 0.25

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Leads", len(df))
    c2.metric("Avg. Price", f"${df['price'].mean():,.0f}")
    c3.metric("Avg. ARV", f"${df['arv'].mean():,.0f}")
    c4.metric("Hot Leads", int(df["hot_lead"].sum()))

    chart = (
        alt.Chart(df.dropna(subset=["price", "arv", "date_posted"]))
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x="date_posted:T",
            y="price:Q",
            color=alt.condition("datum.hot_lead == true", alt.value("red"), alt.value("green")),
            tooltip=["title", "price", "date_posted", "arv", "equity", "hot_lead"]
        )
        .properties(height=350)
    )
    st.altair_chart(chart, use_container_width=True)

    if {"latitude", "longitude"}.issubset(df.columns):
        st.subheader("Lead Locations")
        df_map = df.dropna(subset=["latitude", "longitude"])
        view = pdk.ViewState(latitude=df_map["latitude"].mean(), longitude=df_map["longitude"].mean(), zoom=11)
        layer = pdk.Layer("ScatterplotLayer", data=df_map, get_position=["longitude", "latitude"], get_radius=100, pickable=True)
        st.pydeck_chart(pdk.Deck(initial_view_state=view, layers=[layer]))

# ─── Upload PropStream ─────────────────────────────
elif page == "Upload PropStream":
    st.header("📤 Upload PropStream Leads")
    uploaded_file = st.file_uploader("Upload a CSV file from PropStream", type="csv")
    if uploaded_file:
        df_upload = pd.read_csv(uploaded_file)
        required_cols = {"Property Address", "City", "State", "Zip Code", "Amount Owed", "Estimated Value"}
        if not required_cols.issubset(df_upload.columns):
            st.error("❌ Missing required PropStream columns.")
        else:
            df_upload = df_upload.rename(columns={
                "Property Address": "address",
                "City": "city",
                "State": "state",
                "Zip Code": "zip",
                "Amount Owed": "price",
                "Estimated Value": "arv"
            })
            df_upload["equity"] = df_upload["arv"] - df_upload["price"]
            df_upload["hot_lead"] = df_upload["equity"] / df_upload["arv"] >= 0.25
            for row in df_upload.to_dict(orient="records"):
                supabase.table("craigslist_leads").upsert(row).execute()
            st.success(f"✅ Uploaded {len(df_upload)} leads to Supabase.")

# ─── Settings Page ─────────────────────────────
elif page == "Settings":
    st.header("Settings")
    st.markdown("""
    Your Supabase table `craigslist_leads` should include:
    - `id` (uuid primary key)  
    - `date_posted` (timestamptz)  
    - `title` (text)  
    - `price` (numeric)  
    - `arv`, `equity`, `hot_lead`, `latitude`, `longitude`, `street_view_url`  
    - `fetched_at` (timestamptz default now())  
    """)
    st.write("Edit `scraper.py` to change how leads are gathered.")