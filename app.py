import os
import base64
import streamlit as st
import pandas as pd
import altair as alt
import pydeck as pdk
from scraper import fetch_and_store
from supabase import create_client

SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB3a2JzenNsamxweGhsZmN2ZGVyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQzNDk4MDEsImV4cCI6MjA1OTkyNTgwMX0.bjVMzL4X6dN6xBx8tV3lT7XPsOFIEqMLv0pG3y6N-4o"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── Helper to load a local image as Base64 ─────────────────────────────────────────
def _get_base64(image_path: str) -> str:
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

# ─── Page config & styling ──────────────────────────────────
background_base64 = _get_base64("logo.png")
st.set_page_config(
    page_title="Savory Realty Investments",
    page_icon="logo.png",
    layout="wide",
)

# ─── CSS Fix for Sidebar Toggle + Background ──────────────────
st.markdown(
    f"""
    <style>
      [data-testid="stAppViewContainer"] {{
        background: linear-gradient(rgba(0,0,0,0.6), rgba(0,0,0,0.6)),
                    url("data:image/png;base64,{background_base64}") center center / cover no-repeat fixed;
      }}

      .block-container {{
        position: relative;
        z-index: 2;
      }}

      [data-testid="collapsedControl"] {{
        position: fixed !important;
        top: 0px !important;
        left: 0px !important;
        z-index: 99999 !important;
        background: black !important;
        border-radius: 0 !important;
      }}

      [data-testid="stSidebar"] {{
        background-color: #000 !important;
      }}

      [data-testid="stDataFrame"],
      [data-testid="stAltairChart"] {{
        background-color: rgba(255, 255, 255, 0.2) !important;
        backdrop-filter: blur(4px);
        border: none !important;
        box-shadow: none !important;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Dark theme tweaks (buttons/sidebar) ──────────────────
st.markdown(
    """
    <style>
      .stButton>button { background-color: #0a84ff; color: #fff; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Data caching ─────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_data(region: str) -> pd.DataFrame:
    raw = fetch_and_store(region=region)
    return pd.DataFrame(raw)

region = os.getenv("CRAIGS_REGION", "dallas")

# ─── Sidebar navigation ────────────────────
st.sidebar.image("logo.png", width=48)
st.sidebar.title("Savory Realty Investments")
page = st.sidebar.radio("", ["Leads", "Dashboard", "Upload PropStream", "Settings"])

# ─── PropStream Upload ─────────────────
if page == "Upload PropStream":
    st.header("📤 Upload PropStream Leads")
    uploaded_file = st.file_uploader("Upload a CSV file from PropStream", type="csv")

    if uploaded_file:
        df_upload = pd.read_csv(uploaded_file)

        required_cols = {"Property Address", "City", "State", "Zip Code", "Amount Owed", "Estimated Value"}
        if not required_cols.issubset(set(df_upload.columns)):
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

# ─── Leads page ────────────────
if page == "Leads":
    st.header("🔍 Latest Craigslist Listings")
    df = get_data(region)
    if df.empty:
        st.info("No leads found yet. Click **Refresh** below.")
    else:
        st.dataframe(df)
    if st.button("Refresh now"):
        get_data.clear()
        df = get_data(region)
        if df.empty:
            st.warning("Still no leads.")
        else:
            st.success(f"Fetched {len(df)} leads.")
            st.dataframe(df)

# ─── Dashboard page ─────────────────
elif page == "Dashboard":
    st.header("📊 Analytics Dashboard")
    df = get_data(region)
    if df.empty:
        st.info("No data to chart.")
        st.stop()

    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["date_posted"] = pd.to_datetime(df["date_posted"], errors="coerce")

    df["arv"] = df.get("arv", df["price"] * 1.35)
    df["equity"] = df["arv"] - df["price"]
    df["hot_lead"] = df["equity"] / df["arv"] >= 0.25

    total = len(df)
    avg_price = df["price"].mean()
    avg_arv = df["arv"].mean()
    hot_leads = df["hot_lead"].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Leads", total)
    c2.metric("Average Price", f"${avg_price:,.0f}" if not pd.isna(avg_price) else "—")
    c3.metric("Average ARV", f"${avg_arv:,.0f}" if not pd.isna(avg_arv) else "—")
    c4.metric("Hot Leads", hot_leads)

    if st.checkbox("Show raw data preview"):
        st.write("DataFrame shape:", df.shape)
        st.dataframe(df.head(10))

    df_filtered = df.dropna(subset=["price", "arv", "date_posted"])

    chart = (
        alt.Chart(df_filtered)
        .mark_line(point=True)
        .encode(
            x=alt.X("date_posted:T", title="Date Posted"),
            y=alt.Y("price:Q", title="Price (USD)"),
            color=alt.condition("datum.hot_lead == true", alt.value("red"), alt.value("green")),
            tooltip=["title", "price", "date_posted", "arv", "equity", "hot_lead"]
        )
        .properties(height=350, width=800)
    )

    st.altair_chart(chart, use_container_width=True)

    if {"latitude", "longitude"}.issubset(df_filtered.columns):
        df_map = df_filtered.dropna(subset=["latitude", "longitude"])
        st.subheader("Lead Locations")
        view = pdk.ViewState(
            latitude=df_map["latitude"].mean(),
            longitude=df_map["longitude"].mean(),
            zoom=11,
        )
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=df_map,
            get_position=["longitude", "latitude"],
            get_radius=100,
            pickable=True,
        )
        st.pydeck_chart(pdk.Deck(initial_view_state=view, layers=[layer]))

# ─── Settings page ────────────────
elif page == "Settings":
    st.header("Settings")
    st.write("Make sure your Supabase table is named `craigslist_leads` with columns:")
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
    st.write(
        "To change your region/subdomain, edit the `region = os.getenv(...)` line or update `scraper.py`."
    )
