import os
import base64
import streamlit as st
import pandas as pd
import altair as alt
import pydeck as pdk
from scraper import fetch_and_store
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
    background: linear-gradient(rgba(0,0,0,0.6), rgba(0,0,0,0.6)),
                url("data:image/png;base64,{background_base64}") center/cover fixed no-repeat;
  }}
  .block-container {{ position: relative; z-index: 2; }}
  [data-testid="collapsedControl"] {{ position: fixed!important; top:0; left:0; z-index:99999; background:black!important; }}
  [data-testid="stSidebar"] {{ background-color:#000!important; }}
  .stButton>button {{ background-color:#0a84ff; color:#fff; }}
  [data-testid="stDataFrame"], [data-testid="stDataFrame"]>div,
  [data-testid="stAltairChart"], [data-testid="stAltairChart"]>div {{
    background-color:rgba(255,255,255,0.2)!important; backdrop-filter:blur(4px);
    border:none!important; box-shadow:none!important;
  }}
</style>
""", unsafe_allow_html=True)

# ─── Data fetching & enrichment ─────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_data(region: str) -> pd.DataFrame:
    raw = fetch_and_store(region=region)
    df  = pd.DataFrame(raw)
    if df.empty:
        return df

    # normalize types
    df["price"]       = pd.to_numeric(df.get("price"), errors="coerce")
    df["date_posted"] = pd.to_datetime(df.get("date_posted"), errors="coerce")

    # compute ARV if missing
    if "arv" not in df.columns:
        df["arv"] = df["price"] * 1.35

    # compute equity & hot_lead
    df["equity"]   = df["arv"] - df["price"]
    df["hot_lead"] = df["equity"] / df["arv"] >= 0.25

    # compute hot flag if needed
    if "is_hot" not in df.columns:
        HOT = ["cash","as-is","must sell","motivated","investor"]
        df["is_hot"] = df["title"].str.lower().apply(lambda t: any(w in t for w in HOT))

    # maps & street-view URLs
    def mkmap(r):
        if pd.notna(r.latitude) and pd.notna(r.longitude):
            return f"https://www.google.com/maps/search/?api=1&query={r.latitude},{r.longitude}"
    def mksv(r):
        if pd.notna(r.latitude) and pd.notna(r.longitude):
            key = os.getenv("GOOGLE_MAPS_API_KEY")
            return (f"https://maps.googleapis.com/maps/api/streetview"
                    f"?size=600x300&location={r.latitude},{r.longitude}&key={key}")
    df["map_url"]         = df.apply(mkmap, axis=1)
    df["street_view_url"] = df.apply(mksv, axis=1)

    return df

# ─── Sidebar & Routing ─────────────────────────────────────────────────────
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
        required = {"Property Address","City","State","Zip Code","Amount Owed","Estimated Value"}
        if not required.issubset(df_up.columns):
            st.error("❌ Missing required columns.")
        else:
            df_up = df_up.rename(columns={
                "Property Address":"address","City":"city","State":"state",
                "Zip Code":"zip","Amount Owed":"price","Estimated Value":"arv"
            })
            df_up["equity"]   = df_up["arv"] - df_up["price"]
            df_up["hot_lead"] = df_up["equity"] / df_up["arv"] >= 0.25
            for record in df_up.to_dict(orient="records"):
                supabase.table("craigslist_leads").upsert(record).execute()
            st.success(f"✅ Uploaded {len(df_up)} PropStream leads.")

# ─── Leads page ───────────────────────────────────────────────────────────
if page == "Leads":
    st.header("🔍 Latest Craigslist Listings")
    df = get_data(region)
    if df.empty:
        st.info("No leads found yet. Click **Refresh** below.")
    else:
        disp = df.copy()
        disp["Hot"] = disp["hot_lead"].apply(lambda v: "🔥" if v else "")
        disp["Map"] = disp["map_url"].apply(lambda u: f"[Map]({u})" if u else "")
        disp["SV"]  = disp["street_view_url"].apply(lambda u: f"[SV]({u})" if u else "")

        cols = ["date_posted"]
        if "source" in disp.columns: cols.append("source")
        cols += ["title","price","arv","equity","Hot","Map","SV"]

        st.dataframe(disp[cols], use_container_width=True)

        csv_bytes = disp.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download CSV", csv_bytes, "leads.csv", "text/csv", mime="text/csv")

    if st.button("🔄 Refresh now"):
        get_data.clear()
        st.experimental_rerun()

# ─── Dashboard page ────────────────────────────────────────────────────────
elif page == "Dashboard":
    st.header("📊 Analytics Dashboard")
    df = get_data(region)
    if df.empty:
        st.info("No data to chart.")
        st.stop()

    # source filter
    if "source" in df.columns:
        sources = df["source"].unique().tolist()
        sel     = st.multiselect("Filter by source", sources, default=sources)
        if sel:
            df = df[df["source"].isin(sel)]

    # hot-deals only
    if st.checkbox("Hot leads only", value=False):
        df = df[df["hot_lead"]]

    # date-range slider
    mn, mx = df["date_posted"].dt.date.min(), df["date_posted"].dt.date.max()
    start, end = st.slider("Date range", mn, mx, (mn, mx))
    df = df[df["date_posted"].dt.date.between(start, end)]

    # metrics
    total     = len(df)
    avg_price = df["price"].mean()
    avg_arv   = df["arv"].mean()
    hot_count = df["hot_lead"].sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Leads", total)
    c2.metric("Avg Price", f"${avg_price:,.0f}" if pd.notna(avg_price) else "—")
    c3.metric("Avg ARV", f"${avg_arv:,.0f}" if pd.notna(avg_arv) else "—")
    c4.metric("🔥 Hot Leads", int(hot_count))

    # time series chart
    chart = (
        alt.Chart(df)
           .mark_line(point=True)
           .encode(
             x="date_posted:T", y="price:Q",
             color=alt.condition("datum.hot_lead", alt.value("red"), alt.value("green")),
             tooltip=["title","price","date_posted","arv","equity","hot_lead"]
           )
           .properties(height=350, width=800)
    )
    st.altair_chart(chart, use_container_width=True)

    # map view
    if {"latitude","longitude"}.issubset(df.columns):
        df_map = df.dropna(subset=["latitude","longitude"])
        st.subheader("Lead Locations")
        view  = pdk.ViewState(latitude=df_map.latitude.mean(), longitude=df_map.longitude.mean(), zoom=11)
        layer = pdk.Layer("ScatterplotLayer", df_map, get_position=["longitude","latitude"], get_radius=100, pickable=True)
        st.pydeck_chart(pdk.Deck(initial_view_state=view, layers=[layer]))

# ─── Settings page ───────────────────────────────────────────────────────
else:
    st.header("⚙️ Settings")
    st.write("Supabase table `craigslist_leads` should include:")
    st.markdown("""
    - `id` (uuid primary key)  
    - `date_posted` (timestamptz)  
    - `title` (text)  
    - `source` (text)  
    - `price` (numeric)  
    - `arv` (numeric)  
    - `equity` (numeric)  
    - `hot_lead` (boolean)  
    - `latitude`, `longitude` (floats)  
    - `street_view_url` (text)  
    """)
    st.write("Edit `CRAIGS_REGION` env var to change region.")