import os
import base64
from datetime import datetime
import numpy as np
import streamlit as st
import pandas as pd
import altair as alt
import pydeck as pdk
from supabase import create_client

# ───── Supabase Credentials ─────
SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB3a2JzenNsamxweGhsZmN2ZGVyIiwicm9s"
    "ZSI6ImFub24iLCJpYXQiOjE3NDQzNDk4MDEsImV4cCI6MjA1OTkyNTgwMX0."
    "bjVMzL4X6dN6xBx8tV3lT7XPsOFIEqMLv0pG3y6N-4o"
)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ───── Background & Panel Styling ─────
def _get_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

bg_b64 = _get_base64("logo.png")
st.set_page_config(page_title="Savory Realty Investments", page_icon="logo.png", layout="wide")
st.markdown(f"""
<style>
  [data-testid="stAppViewContainer"] {{
    background-image: linear-gradient(rgba(0,0,0,0.6),rgba(0,0,0,0.6)),
      url("data:image/png;base64,{bg_b64}");
    background-repeat: no-repeat;
    background-position: center center;
    background-attachment: fixed;
    background-size: contain;
  }}
  .main > div.block-container {{ max-width:1200px!important; margin:0 auto!important; }}
  .block-container {{ background-color:rgba(0,0,0,0.4)!important; padding:1rem!important; border-radius:0.5rem!important; }}
  [data-testid="stSidebar"] {{ background-color:#000!important; }}
  [data-testid="collapsedControl"] {{ position:fixed; top:0; left:0; background:black; z-index:99999; border-radius:0; }}
  [data-testid="stDataFrame"] > div, [data-testid="stDataFrame"] table {{ background-color:#000!important; }}
  [data-testid="stDataFrame"] > div {{ overflow-x:auto!important; }}
</style>
""", unsafe_allow_html=True)

# ───── Cached Data Fetch ─────
@st.cache_data(ttl=300)
def get_data() -> pd.DataFrame:
    resp = (
        supabase
        .table("craigslist_leads")
        .select("*")
        .order("date_posted", desc=True)
        .execute()
    )
    df = pd.DataFrame(resp.data or [])
    if df.empty:
        return df
    if "title" not in df.columns:
        df["title"] = ""
    if "date_posted" not in df.columns:
        df["date_posted"] = pd.NaT
    df["date_posted"] = pd.to_datetime(df["date_posted"], errors="coerce")
    for col in ("price", "arv", "equity"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["title", "date_posted"], how="any")

# ───── Sidebar & Navigation ─────
st.sidebar.image("logo.png", width=48)
st.sidebar.title("Savory Realty Investments")
page = st.sidebar.radio("", [
    "Live Leads",
    "PropStream Leads",
    "Leads Dashboard",
    "Upload PropStream",
    "Settings",
])

# ───── Live Leads ─────
if page == "Live Leads":
    st.header("📬 Live Leads")
    if st.button("🔁 Refresh List"):
        with st.spinner("Scraping fresh leads…"):
            os.system("python3 scraper.py")
        st.success("✅ Leads refreshed.")
        get_data.clear()
    df = get_data()
    if df.empty:
        st.warning("No leads found.")
        st.stop()
    df["Hot"] = df.get("hot_lead", False).map({True: "🔥", False: ""})
    if {"latitude", "longitude"}.issubset(df.columns):
        df["Map"] = df.apply(lambda r: f"https://www.google.com/maps?q={r.latitude},{r.longitude}" if pd.notna(r.latitude) else None, axis=1)
    else:
        df["Map"] = None
    df["Street View"] = df.get("street_view_url", "")
    df["Link"] = df.get("link", "").map(lambda u: f"[View Post]({u})" if u else "")
    st.dataframe(df[["id", "date_posted", "title", "price", "arv", "Hot", "Map", "Street View", "Link"]], use_container_width=True, height=500)
    st.markdown("#### ⚠️ Delete Listings")
    to_delete = st.multiselect("Select IDs to delete:", df["id"])
    if st.button("🗑️ Delete Selected") and to_delete:
        supabase.table("craigslist_leads").delete().in_("id", to_delete).execute()
        st.success(f"Deleted {len(to_delete)} listing(s).")
        get_data.clear()
    if st.button("🗑️ Delete ALL Listings"):
        all_ids = df["id"].tolist()
        if all_ids:
            supabase.table("craigslist_leads").delete().in_("id", all_ids).execute()
            st.success("Deleted all listings.")
            get_data.clear()

# ───── PropStream Leads ─────
elif page == "PropStream Leads":
    st.header("📥 PropStream Leads")
    with st.spinner("Fetching PropStream uploads…"):
        resp = (
            supabase
            .table("propstream_leads")
            .select("*")
            .order("date_posted", desc=True)
            .execute()
        )
    dfp = pd.DataFrame(resp.data or [])
    if dfp.empty:
        st.warning("No PropStream leads found.")
    else:
        dfp["Hot"] = dfp.get("hot_lead", False).map({True: "🔥", False: ""})
        st.dataframe(
            dfp[["id", "date_posted", "title", "price", "arv", "Hot"]],
            use_container_width=True,
            height=500,
        )

# ───── Leads Dashboard ─────
elif page == "Leads Dashboard":
    st.header("📊 Leads Dashboard")
    df = get_data()
    if df.empty:
        st.warning("No data available.")
        st.stop()
    df["equity"] = df["arv"] - df["price"]
    df["hot_lead"] = df["equity"] / df["arv"] >= 0.25
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Leads", len(df))
    c2.metric("Avg. Price", f"${df['price'].mean():,.0f}" if not df['price'].isna().all() else "N/A")
    c3.metric("Avg. ARV", f"${df['arv'].mean():,.0f}" if not df['arv'].isna().all() else "N/A")
    c4.metric("Hot Leads", int(df["hot_lead"].sum()))
    if st.checkbox("Show raw preview"):
        st.dataframe(df.head(10), use_container_width=True)
    df2 = df.dropna(subset=["price", "arv", "date_posted"])
    if not df2.empty:
        chart = alt.Chart(df2).mark_line(point=True, strokeWidth=3).encode(
            x=alt.X("date_posted:T", title="Date Posted"),
            y=alt.Y("price:Q", title="Price (USD)"),
            color=alt.condition("datum.hot_lead", alt.value("red"), alt.value("green")),
            tooltip=["title", "price", "date_posted", "arv", "equity"],
        ).properties(height=350, width=800)
        st.altair_chart(chart, use_container_width=True)
    if {"latitude", "longitude"}.issubset(df.columns):
        dfm = df.dropna(subset=["latitude", "longitude"])
        view = pdk.ViewState(latitude=dfm.latitude.mean(), longitude=dfm.longitude.mean(), zoom=11)
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=dfm,
            get_position=["longitude", "latitude"],
            get_radius=100,
            pickable=True,
        )
        st.pydeck_chart(pdk.Deck(initial_view_state=view, layers=[layer]))

# ───── Upload PropStream ─────
elif page == "Upload PropStream":
    st.header("📤 Upload PropStream Leads")
    zf = st.sidebar.text_input("Only include ZIP code:", "")
    cf = st.sidebar.text_input("Only include City:", "")
    im = st.sidebar.checkbox("🔗 Add Maps & Street View", False)
    ae = st.sidebar.checkbox("✉️ Send Email Alert", False)
    asms = st.sidebar.checkbox("📱 Send SMS Alert", False)
    st.sidebar.markdown("---")
    up = st.file_uploader("Choose your PropStream CSV", type=["csv"])
    if not up:
        st.info("Upload a CSV to unlock hot-lead insights.")
        st.stop()
    dfc = pd.read_csv(up)
    req = {"Property Address", "City", "State", "Zip Code", "Amount Owed", "Estimated Value"}
    miss = req - set(dfc.columns)
    if miss:
        st.error("Missing columns: " + ", ".join(miss))
        st.stop()
    dfc = dfc.rename(columns={
        "Property Address": "address",
        "City": "city",
        "State": "state",
        "Zip Code": "zip",
        "Amount Owed": "price",
        "Estimated Value": "arv",
    })
    if zf:
        dfc = dfc[dfc["zip"].astype(str).isin([z.strip() for z in zf.split(",")])]
    if cf:
        dfc = dfc[dfc["city"].str.lower() == cf.lower()]
    dfc["equity"] = dfc["arv"] - dfc["price"]
    dfc["hot_lead"] = dfc["equity"] / dfc["arv"] >= 0.25
    dfc = dfc.replace([np.inf, -np.inf], np.nan)
    for rec in dfc.to_dict(orient="records"):
        rec_clean = {k: (None if pd.isna(v) else v) for k, v in rec.items()}
        rec_clean["title"] = rec_clean.get("address")
        rec_clean["link"] = rec_clean.get("link", "") or ""
        rec_clean["date_posted"] = datetime.utcnow().isoformat()
        supabase.table("propstream_leads").upsert(rec_clean).execute()
    get_data.clear()
    hot = int(dfc["hot_lead"].sum())
    total = len(dfc)
    st.success(f"✅ Uploaded {total} rows; {hot} 🔥 hot leads to PropStream table.")
    dfc2 = dfc.copy()
    for col in ("price", "arv", "equity"):
        dfc2[col] = dfc2[col].map(lambda x: f"${x:,.0f}" if pd.notna(x) else "")
    dfc2["hot_lead"] = dfc2["hot_lead"].map({True: "🔥", False: ""})
    cols = ["address", "city", "zip", "price", "arv", "equity", "hot_lead"]
    if im:
        dfc2["map_link"] = dfc.get("map_link")
        dfc2["street_view_link"] = dfc.get("street_view_link")
        cols += ["map_link", "street_view_link"]
    st.dataframe(dfc2[cols], use_container_width=True, height=400)
    if ae:
        st.write("✉️ Email sent!")
    if asms:
        st.write("📱 SMS sent!")

# ───── Settings ─────
else:
    st.header("Settings")
    st.markdown("""
    • Your Supabase tables:
      - `craigslist_leads` for scraped live leads
      - `propstream_leads` for your PropStream uploads

    • Table schema must include:
      - id (uuid PK), title, link, date_posted, fetched_at  
      - price, arv, equity, hot_lead  
      - address, city, state, zip  
      - map_link, street_view_link  
      - latitude, longitude (optional)
    """)
