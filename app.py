import os
import base64
import streamlit as st
import pandas as pd
import altair as alt
import pydeck as pdk
from supabase import create_client
from datetime import datetime

# ─── Supabase client ─────────────────────────────────────────────────────────
SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9…"
supabase    = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── Helper to load a local image as Base64 ─────────────────────────────────
def _get_base64(image_path: str) -> str:
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

# ─── Page config & styling ────────────────────────────────────────────────
background_base64 = _get_base64("logo.png")
st.set_page_config(page_title="Savory Realty Investments", page_icon="logo.png", layout="wide")
st.markdown(f"""
<style>
  [data-testid="stAppViewContainer"] {{
    background: linear-gradient(rgba(0,0,0,0.6),rgba(0,0,0,0.6)),
                url("data:image/png;base64,{background_base64}") center/cover fixed no-repeat;
  }}
  .block-container {{ position: relative; z-index: 2; }}
  [data-testid="collapsedControl"] {{ position: fixed!important; top:0; left:0; z-index:99999; background:black!important; border-radius:0!important; }}
  [data-testid="stSidebar"] {{ background-color:#000!important; }}
  .stButton>button {{ background-color:#0a84ff; color:#fff; }}
  [data-testid="stDataFrame"], [data-testid="stDataFrame"]>div,
  [data-testid="stAltairChart"], [data-testid="stAltairChart"]>div {{
    background-color:rgba(255,255,255,0.2)!important; backdrop-filter:blur(4px);
  }}
</style>
""", unsafe_allow_html=True)

# ─── Data loader (reads from Supabase) ─────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_data(region: str) -> pd.DataFrame:
    resp = supabase.table("craigslist_leads")\
                   .select("*")\
                   .order("date_posted", desc=True)\
                   .execute()
    df = pd.DataFrame(resp.data or [])
    if df.empty:
        return df

    # normalize & enrich
    df["price"]       = pd.to_numeric(df.get("price"), errors="coerce")
    df["date_posted"] = pd.to_datetime(df.get("date_posted"), errors="coerce")
    df["arv"]         = df.get("arv", df["price"] * 1.35)
    df["equity"]      = df["arv"] - df["price"]
    df["hot_lead"]    = df["equity"] / df["arv"] >= 0.25

    if "is_hot" not in df.columns:
        HOT = ["cash","as-is","must sell","motivated","investor"]
        df["is_hot"] = df["title"].str.lower().apply(lambda t: any(w in t for w in HOT))

    def mkmap(r):
        if pd.notna(r.latitude) and pd.notna(r.longitude):
            return f"https://www.google.com/maps/search/?api=1&query={r.latitude},{r.longitude}"
    def mksv(r):
        if pd.notna(r.latitude) and pd.notna(r.longitude):
            return (
              f"https://maps.googleapis.com/maps/api/streetview"
              f"?size=600x300&location={r.latitude},{r.longitude}"
              f"&key={os.getenv('GOOGLE_MAPS_API_KEY')}"
            )
    df["map_url"]         = df.apply(mkmap, axis=1)
    df["street_view_url"] = df.apply(mksv,  axis=1)

    return df

# ─── Sidebar & routing ────────────────────────────────────────────────────
region = os.getenv("CRAIGS_REGION", "dallas")
st.sidebar.image("logo.png", width=48)
st.sidebar.title("Savory Realty Investments")
page = st.sidebar.radio("", ["Leads", "Dashboard", "Upload PropStream", "Settings"])

# ─── PropStream Upload ─────────────────────────────────────────────────────
if page == "Upload PropStream":
    st.header("📤 Upload PropStream Leads")
    uploaded = st.file_uploader("Upload a CSV file from PropStream", type="csv")
    if uploaded:
        df_up = pd.read_csv(uploaded)
        req = {"Property Address","City","State","Zip Code","Amount Owed","Estimated Value"}
        if not req.issubset(df_up.columns):
            st.error("❌ Missing required columns.")
        else:
            df_up = df_up.rename(columns={
                "Property Address":"address","City":"city","State":"state",
                "Zip Code":"zip","Amount Owed":"price","Estimated Value":"arv"
            })
            df_up["equity"]   = df_up["arv"] - df_up["price"]
            df_up["hot_lead"] = df_up["equity"] / df_up["arv"] >= 0.25
            for rec in df_up.to_dict("records"):
                supabase.table("craigslist_leads").upsert(rec).execute()
            st.success(f"✅ Uploaded {len(df_up)} leads.")

# ─── Leads Dash Board ────────────────────────────────────────────────────────
elif page == "Leads":
    st.header("Leads Dash Board")
    df = get_data(region)
    if df.empty:
        st.info("No leads yet. Click **Refresh**.")
    else:
        st.dataframe(df, use_container_width=True)
    if st.button("🔄 Refresh now"):
        get_data.clear()
        st.experimental_rerun()

# ─── Analytics Dashboard ─────────────────────────────────────────────────────
elif page == "Dashboard":
    st.header("📊 Analytics Dashboard")
    df = get_data(region)
    if df.empty:
        st.info("No data to chart."); st.stop()

    # filters
    if "source" in df.columns:
        sel = st.multiselect("Filter by source", df["source"].unique().tolist(), default=None)
        if sel:
            df = df[df["source"].isin(sel)]
    if st.checkbox("Hot deals only"):
        df = df[df["hot_lead"]]

    # date-range slider
    mn, mx = df["date_posted"].dt.date.min(), df["date_posted"].dt.date.max()
    start, end = st.slider("Date range", mn, mx, (mn, mx))
    df = df[df["date_posted"].dt.date.between(start, end)]

    # metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Leads", len(df))
    c2.metric("Avg Price", f"${df['price'].mean():,.0f}" if not pd.isna(df["price"].mean()) else "—")
    c3.metric("Avg ARV",   f"${df['arv'].mean():,.0f}"   if not pd.isna(df["arv"].mean())   else "—")
    c4.metric("🔥 Hot Leads", int(df["hot_lead"].sum()))

    # time-series chart with thicker grid
    df2 = df.dropna(subset=["price", "date_posted"])
    chart = (
        alt.Chart(df2)
           .mark_line(point=True)
           .encode(
             x=alt.X("date_posted:T", title="Date Posted"),
             y=alt.Y("price:Q", title="Price (USD)"),
             color=alt.condition("datum.hot_lead", alt.value("red"), alt.value("green")),
             tooltip=["title","price","arv","equity","hot_lead"]
           )
           .properties(height=350, width=800)
           .configure_axisX(gridWidth=2)
           .configure_axisY(gridWidth=2)
    )
    st.altair_chart(chart, use_container_width=True)

    # map view
    if {"latitude","longitude"}.issubset(df2.columns):
        dfm = df2.dropna(subset=["latitude","longitude"])
        st.subheader("Lead Locations")
        view = pdk.ViewState(latitude=dfm.latitude.mean(), longitude=dfm.longitude.mean(), zoom=11)
        layer = pdk.Layer("ScatterplotLayer", data=dfm,
                          get_position=["longitude","latitude"], get_radius=100, pickable=True)
        st.pydeck_chart(pdk.Deck(initial_view_state=view, layers=[layer]))

# ─── Settings (informational only) ─────────────────────────────────────────
else:
    st.header("Settings")
    st.write("Your Supabase table `craigslist_leads` must have these columns:")
    st.markdown("""
      - id (uuid primary key)  
      - date_posted (timestamptz)  
      - title (text)  
      - source (text)  
      - price (numeric)  
      - arv (numeric)  
      - equity (numeric)  
      - hot_lead (boolean)  
      - latitude, longitude (float)  
      - street_view_url (text)
    """)
    st.write("Settings is informational only—no runtime changes happen here.")