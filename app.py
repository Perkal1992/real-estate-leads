import os
import base64
from datetime import datetime
import numpy as np
import streamlit as st
import pandas as pd
import altair as alt
import pydeck as pdk
from supabase import create_client

SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB3a2JzenNsamxweGhsZmN2ZGVyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQzNDk4MDEsImV4cCI6MjA1OTkyNTgwMX0.bjVMzL4X6dN6xBx8tV3lT7XPsOFIEqMLv0pG3y6N-4o"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

KNOWN_COLUMNS = {
    'address', 'city', 'state', 'zip', 'price', 'arv', 'equity', 'hot_lead',
    'category', 'title', 'link', 'date_posted', 'map_link', 'street_view_link',
    'latitude', 'longitude'
}

def get_craigslist_data():
    resp = supabase.table("craigslist_leads").select("*").order("date_posted", desc=True).execute()
    df = pd.DataFrame(resp.data or [])
    if df.empty:
        return df
    df["date_posted"] = pd.to_datetime(df.get("date_posted"), errors="coerce")
    for col in ("price", "arv", "equity"):
        df[col] = pd.to_numeric(df.get(col), errors="coerce")
    if "title" not in df.columns:
        df["title"] = ""
    return df.dropna(subset=["title", "date_posted"])

def get_propstream_data():
    resp = supabase.table("propstream_leads").select("*").order("date_posted", desc=True).execute()
    df = pd.DataFrame(resp.data or [])
    if df.empty:
        return df
    df["date_posted"] = pd.to_datetime(df.get("date_posted"), errors="coerce")
    for col in ("price", "arv", "equity"):
        df[col] = pd.to_numeric(df.get(col), errors="coerce")
    if "title" not in df.columns:
        df["title"] = ""
    if "category" not in df.columns:
        df["category"] = ""
    return df.dropna(subset=["title", "date_posted"])

st.set_page_config(page_title="Savory Realty Investments", page_icon="🏘️", layout="wide")

def _get_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

bg_b64 = _get_base64("logo.png")
st.markdown(f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: linear-gradient(rgba(0,0,0,0.6),rgba(0,0,0,0.6)), url("data:image/png;base64,{bg_b64}");
  background-repeat: no-repeat;
  background-position: center;
  background-size: contain;
}}
</style>
""", unsafe_allow_html=True)

st.sidebar.image("logo.png", width=48)
st.sidebar.title("Savory Realty Investments")
page = st.sidebar.radio("", [
    "Live Leads",
    "PropStream Leads",
    "Leads Dashboard",
    "Upload PropStream",
    "Settings",
])

if page == "Live Leads":
    st.header("📬 Live Leads")
    df = get_craigslist_data()
    if df.empty:
        st.warning("No leads found.")
        st.stop()
    df["Hot"] = df.get("hot_lead", False).map({True: "🔥", False: ""})
    if {"latitude","longitude"}.issubset(df.columns):
        df["Map"] = df.apply(lambda r: f"https://www.google.com/maps?q={r.latitude},{r.longitude}" if pd.notna(r.latitude) else None, axis=1)
    else:
        df["Map"] = None
    df["Street View"] = df.get("street_view_url", "")
    df["Link"] = df.get("link", "").map(lambda u: f"[View Post]({u})" if u else "")
    st.dataframe(df[["id","date_posted","title","price","arv","Hot","Map","Street View","Link"]], use_container_width=True, height=500)
    to_delete = st.multiselect("Select IDs to delete:", df["id"])
    if st.button("🗑️ Delete Selected") and to_delete:
        supabase.table("craigslist_leads").delete().in_("id", to_delete).execute()
        st.success(f"Deleted {len(to_delete)} listing(s).")
    if st.button("🗑️ Delete ALL Listings"):
        all_ids = df["id"].tolist()
        if all_ids:
            supabase.table("craigslist_leads").delete().in_("id", all_ids).execute()
            st.success("Deleted all listings.")

elif page == "PropStream Leads":
    st.header("📥 PropStream Leads")
    dfp = get_propstream_data()
    if dfp.empty:
        st.warning("No PropStream leads found.")
        st.stop()
    dfp["Hot"] = dfp.get("hot_lead", False).map({True: "🔥", False: ""})
    st.dataframe(dfp[["id","date_posted","title","price","arv","category","Hot"]], use_container_width=True, height=500)
    ps_delete = st.multiselect("Select IDs to delete:", dfp["id"])
    if st.button("🗑️ Delete Selected PropStream") and ps_delete:
        supabase.table("propstream_leads").delete().in_("id", ps_delete).execute()
        st.success(f"Deleted {len(ps_delete)} PropStream listing(s).")
    if st.button("🧹 Delete ALL PropStream Listings"):
        all_ps_ids = dfp["id"].tolist()
        if all_ps_ids:
            supabase.table("propstream_leads").delete().in_("id", all_ps_ids).execute()
            st.success("Deleted all PropStream listings.")

elif page == "Leads Dashboard":
    st.header("📊 Leads Dashboard")
    source = st.sidebar.selectbox("Data Source:", ["Craigslist Leads", "PropStream Leads"])
    df = get_craigslist_data() if source == "Craigslist Leads" else get_propstream_data()
    if "category" not in df.columns:
        df["category"] = ""
    if source == "PropStream Leads":
        categories = sorted(df["category"].dropna().unique().tolist())
        chosen = st.sidebar.multiselect("Filter categories:", categories, default=categories)
        df = df[df["category"].isin(chosen)]
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
            tooltip=["title","price","date_posted","arv","equity","category"]
        ).properties(height=350, width=800)
        st.altair_chart(chart, use_container_width=True)
    if {"latitude", "longitude"}.issubset(df.columns):
        dfm = df.dropna(subset=["latitude","longitude"])
        view = pdk.ViewState(latitude=dfm.latitude.mean(), longitude=dfm.longitude.mean(), zoom=11)
        layer = pdk.Layer("ScatterplotLayer", data=dfm, get_position=["longitude","latitude"], get_radius=100, pickable=True)
        st.pydeck_chart(pdk.Deck(initial_view_state=view, layers=[layer]))

elif page == "Upload PropStream":
    st.header("📤 Upload PropStream Leads")
    zf = st.sidebar.text_input("Only include ZIP code:", "")
    cf = st.sidebar.text_input("Only include City:", "")
    im = st.sidebar.checkbox("🔗 Add Maps & Street View", False)
    ae = st.sidebar.checkbox("✉️ Send Email Alert", False)
    asms = st.sidebar.checkbox("📱 Send SMS Alert", False)
    st.sidebar.markdown("---")
    category = st.sidebar.selectbox("What type of PropStream list is this?", ["Pre-Foreclosure", "Fix & Flip", "Auction", "Tax Lien", "Other"])
    up = st.file_uploader("Choose your PropStream CSV", type=["csv"])
    if not up:
        st.info("Upload a CSV to unlock hot-lead insights.")
        st.stop()
    if st.button("🧹 Delete ALL PropStream Leads"):
        supabase.table("propstream_leads").delete().neq("id", "").execute()
        st.success("🧹 All PropStream leads deleted.")
    dfc = pd.read_csv(up)
    required_cols = {"Property Address","City","State","Zip Code","Amount Owed","Estimated Value"}
    missing = required_cols - set(dfc.columns)
    if missing:
        st.error("Missing columns: " + ", ".join(missing))
        st.stop()
    dfc = dfc.rename(columns={"Property Address":"address","City":"city","State":"state","Zip Code":"zip","Amount Owed":"price","Estimated Value":"arv"})
    if zf:
        dfc = dfc[dfc["zip"].astype(str).isin([z.strip() for z in zf.split(",")])]
    if cf:
        dfc = dfc[dfc["city"].str.lower() == cf.lower()]
    dfc["equity"] = dfc["arv"] - dfc["price"]
    dfc["hot_lead"] = (dfc["equity"] / dfc["arv"] >= 0.25) & (dfc["arv"] >= 100000) & (dfc["equity"] >= 30000)
    dfc = dfc.replace([np.inf,-np.inf],np.nan)
    for rec in dfc.to_dict(orient="records"):
        rc = {k:(None if pd.isna(v) else v) for k,v in rec.items()}
        rc["title"] = rc.get("address")
        rc["link"] = rc.get("link","") or ""
        rc["date_posted"] = datetime.utcnow().isoformat()
        rc["category"] = rec.get("category", category)
        rc = {k: v for k, v in rc.items() if k in KNOWN_COLUMNS}
        supabase.table("propstream_leads").upsert(rc).execute()
    hot = int(dfc["hot_lead"].sum())
    total = len(dfc)
    st.success(f"✅ Uploaded {total} rows; {hot} 🔥 hot leads to PropStream table.")
    st.write("Hot lead count based on criteria:")
    st.write(dfc.query("(equity / arv >= 0.25) & (arv >= 100000) & (equity >= 30000)").shape[0])
    st.write("Total uploaded:", dfc.shape[0])
    st.write("Preview of uploaded leads:")
    st.dataframe(dfc[["address", "price", "arv", "equity", "hot_lead"]].head(10), use_container_width=True)

else:
    st.header("Settings")
    st.markdown("""
    • Your Supabase tables:
      - `craigslist_leads` for scraped live leads
      - `propstream_leads` for your PropStream uploads (with `category` column)
    • Table schema must include:
      - id (uuid PK), title, link, date_posted, fetched_at
      - price, arv, equity, hot_lead, category
      - address, city, state, zip
      - map_link, street_view_link
      - latitude, longitude (optional)
    """)
