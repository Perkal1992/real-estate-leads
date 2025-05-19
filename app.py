import os
import base64
import streamlit as st
import pandas as pd
import altair as alt
import pydeck as pdk
from scrapers import fetch_and_store       # ← updated import
from supabase import create_client
from datetime import datetime

SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9…"
supabase    = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── Helper to load a local image as Base64 ─────────────────────────
def _get_base64(image_path: str) -> str:
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

# ─── Page config & styling ─────────────────────────────────────────
background_base64 = _get_base64("logo.png")
st.set_page_config(page_title="Savory Realty Investments", page_icon="logo.png", layout="wide")

st.markdown(f"""
<style>
  [data-testid="stAppViewContainer"] {{
    background: linear-gradient(rgba(0,0,0,0.6),rgba(0,0,0,0.6)),
      url("data:image/png;base64,{background_base64}") center/cover fixed no-repeat;
  }}
  .block-container {{ position: relative; z-index: 2; }}
  [data-testid="collapsedControl"] {{ position: fixed!important; top:0; left:0; z-index:99999; background:black!important; }}
  [data-testid="stSidebar"] {{ background-color:#000!important; }}
  .stButton>button {{ background-color:#0a84ff; color:#fff; }}
  [data-testid="stDataFrame"], [data-testid="stDataFrame"]>div,
  [data-testid="stAltairChart"], [data-testid="stAltairChart"]>div {{
    background-color:rgba(255,255,255,0.2)!important; backdrop-filter:blur(4px);
  }}
</style>
""", unsafe_allow_html=True)

# ─── Data caching ──────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_data(region: str) -> pd.DataFrame:
    raw = fetch_and_store(region=region)
    return pd.DataFrame(raw)

region = os.getenv("CRAIGS_REGION", "dallas")

# ─── Sidebar navigation ───────────────────────────────────────────
st.sidebar.image("logo.png", width=48)
st.sidebar.title("Savory Realty Investments")
page = st.sidebar.radio("", ["Leads", "Dashboard", "Upload PropStream", "Settings"])

# ─── PropStream Upload ───────────────────────────────────────────
if page == "Upload PropStream":
    st.header("📤 Upload PropStream Leads")
    uploaded_file = st.file_uploader("Upload a CSV file from PropStream", type="csv")
    if uploaded_file:
        df_upload = pd.read_csv(uploaded_file)
        required_cols = {"Property Address","City","State","Zip Code","Amount Owed","Estimated Value"}
        if not required_cols.issubset(df_upload.columns):
            st.error("❌ Missing required PropStream columns.")
        else:
            df_upload = df_upload.rename(columns={
                "Property Address":"address","City":"city","State":"state",
                "Zip Code":"zip","Amount Owed":"price","Estimated Value":"arv"
            })
            df_upload["equity"]   = df_upload["arv"] - df_upload["price"]
            df_upload["hot_lead"] = df_upload["equity"] / df_upload["arv"] >= 0.25
            for rec in df_upload.to_dict(orient="records"):
                supabase.table("craigslist_leads").upsert(rec).execute()
            st.success(f"✅ Uploaded {len(df_upload)} leads to Supabase.")

# ─── Leads page ─────────────────────────────────────────────────
if page == "Leads":
    st.header("Leads Dash Board")   # title updated
    df = get_data(region)
    if df.empty:
        st.info("No leads found yet. Click **Refresh** below.")
    else:
        st.dataframe(df)
    if st.button("Refresh now"):
        get_data.clear()
        df = get_data(region)
        st.success(f"Fetched {len(df)} leads.") if not df.empty else st.warning("Still no leads.")

# ─── Dashboard page ─────────────────────────────────────────────
elif page == "Dashboard":
    st.header("📊 Analytics Dashboard")
    df = get_data(region)
    if df.empty:
        st.info("No data to chart."); st.stop()

    df["price"]       = pd.to_numeric(df["price"], errors="coerce")
    df["date_posted"] = pd.to_datetime(df["date_posted"], errors="coerce")
    df["arv"]         = df.get("arv", df["price"] * 1.35)
    df["equity"]      = df["arv"] - df["price"]
    df["hot_lead"]    = df["equity"] / df["arv"] >= 0.25

    # metrics
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total Leads", len(df))
    c2.metric("Avg Price", f"${df['price'].mean():,.0f}" if not pd.isna(df["price"].mean()) else "—")
    c3.metric("Avg ARV", f"${df['arv'].mean():,.0f}"    if not pd.isna(df["arv"].mean())     else "—")
    c4.metric("🔥 Hot Leads", int(df["hot_lead"].sum()))

    # chart with thicker grid
    df_f = df.dropna(subset=["price","date_posted"])
    chart = (
        alt.Chart(df_f)
           .mark_line(point=True)
           .encode(
              x=alt.X("date_posted:T", title="Date Posted"),
              y=alt.Y("price:Q",      title="Price (USD)"),
              color=alt.condition("datum.hot_lead", alt.value("red"), alt.value("green")),
              tooltip=["title","price","arv","equity","hot_lead"]
           )
           .properties(height=350, width=800)
           .configure_axisX(gridWidth=2)
           .configure_axisY(gridWidth=2)
    )
    st.altair_chart(chart, use_container_width=True)

    # map view
    if {"latitude","longitude"}.issubset(df_f.columns):
        df_map = df_f.dropna(subset=["latitude","longitude"])
        st.subheader("Lead Locations")
        view = pdk.ViewState(latitude=df_map.latitude.mean(), longitude=df_map.longitude.mean(), zoom=11)
        layer = pdk.Layer("ScatterplotLayer", data=df_map,
                          get_position=["longitude","latitude"], get_radius=100, pickable=True)
        st.pydeck_chart(pdk.Deck(initial_view_state=view, layers=[layer]))

# ─── Settings page ─────────────────────────────────────────────
elif page == "Settings":
    st.header("Settings")
    st.write("Make sure your Supabase table `craigslist_leads` has these columns:")
    st.markdown("""
      - id (uuid primary key)  
      - date_posted (timestamptz)  
      - title (text)  
      - link (text unique)  
      - price (numeric)  
      - arv (numeric)  
      - equity (numeric)  
      - hot_lead (boolean)  
      - latitude, longitude (float)  
      - street_view_url (text)
    """)
    st.write("Settings is informational only—no runtime changes.")