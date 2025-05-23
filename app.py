import os
import base64
from datetime import datetime
import numpy as np
import streamlit as st
import pandas as pd
import altair as alt
import pydeck as pdk
try:
    from fpdf import FPDF
except ImportError:
    st.error("`fpdf` module not found. Please add `fpdf` to your `requirements.txt` and Redeploy.")
    FPDF = None
from io import BytesIO
from supabase import create_client

# ───── Supabase Setup ─────
SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB3a2JzenNsamxweGhsZmN2ZGVyIiwicm9s"
    "ZSI6ImFub24iLCJpYXQiOjE3NDQzNDk4MDEsImV4cCI6MjA1OTkyNTgwMX0."
    "bjVMzL4X6dN6xBx8tV3lT7XPsOFIEqMLv0pG3y6N-4o"
)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ───── Helper Functions ─────
@st.cache_data(ttl=300)
def get_craigslist_data():
    resp = supabase.table("craigslist_leads").select("*").order("date_posted", desc=True).execute()
    df = pd.DataFrame(resp.data or [])
    if df.empty:
        return df
    df["date_posted"] = pd.to_datetime(df.get("date_posted"), errors="coerce")
    for col in ("price", "arv", "equity"): df[col] = pd.to_numeric(df.get(col), errors="coerce")
    if "title" not in df.columns: df["title"] = ""
    return df.dropna(subset=["title", "date_posted"])

@st.cache_data(ttl=300)
def get_propstream_data():
    resp = supabase.table("propstream_leads").select("*").order("date_posted", desc=True).execute()
    df = pd.DataFrame(resp.data or [])
    if df.empty:
        return df
    df["date_posted"] = pd.to_datetime(df.get("date_posted"), errors="coerce")
    for col in ("price", "arv", "equity"): df[col] = pd.to_numeric(df.get(col), errors="coerce")
    if "title" not in df.columns: df["title"] = ""
    if "category" not in df.columns: df["category"] = ""
    return df.dropna(subset=["title", "date_posted"])

def calculate_score(row):
    if pd.isna(row.get('arv')) or pd.isna(row.get('equity')):
        return 0
    return (row['equity'] / row['arv']) * 100 + row['arv'] / 1000

def tag_motivation(text):
    tags = ["vacant", "divorce", "fire", "urgent"]
    return ", ".join([t for t in tags if t in str(text).lower()])

# ───── Page Config & Styling ─────
st.set_page_config(page_title="Savory Realty Investments", page_icon="🏘️", layout="wide")

def _get_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()
bg = _get_base64("logo.png")
st.markdown(f"""
<style>
[data-testid=\"stAppViewContainer\"] {{
  background-image: linear-gradient(rgba(0,0,0,0.6),rgba(0,0,0,0.6)), url('data:image/png;base64,{bg}');
  background-repeat: no-repeat;
  background-position: center;
  background-size: contain;
}}
</style>
""", unsafe_allow_html=True)

# ───── Sidebar & Navigation ─────
st.sidebar.image("logo.png", width=48)
st.sidebar.title("Savory Realty Investments")
page = st.sidebar.radio("Navigate to:", [
    "Live Leads",
    "PropStream Leads",
    "Leads Dashboard",
    "Upload Leads",
    "Deal Tools",
    "Settings"
])

# ───── Live Leads ─────
if page == "Live Leads":
    st.header("📬 Live Leads")
    df = get_craigslist_data()
    if df.empty:
        st.warning("No leads found.")
        st.stop()
    df["Hot"] = df.get("hot_lead", False).map({True: "🔥", False: ""})
    df["Map"] = df.apply(lambda r: f"https://www.google.com/maps?q={r.latitude},{r.longitude}" if pd.notna(r.get('latitude')) else None, axis=1)
    df["Street View"] = df.get("street_view_url", "")
    df["Link"] = df.get("link", "").map(lambda u: f"[View Post]({u})" if u else "")
    st.dataframe(df[["id", "date_posted", "title", "price", "arv", "Hot", "Map", "Street View", "Link"]], use_container_width=True, height=500)
    to_del = st.multiselect("Select IDs to delete:", df["id"])
    if st.button("🗑️ Delete Selected") and to_del:
        supabase.table("craigslist_leads").delete().in_("id", to_del).execute()
        st.success(f"Deleted {len(to_del)} listings.")
    if st.button("🗑️ Delete ALL Listings"):
        all_ids = df["id"].tolist()
        supabase.table("craigslist_leads").delete().in_("id", all_ids).execute()
        st.success("Deleted all listings.")

# ───── PropStream Leads ─────
elif page == "PropStream Leads":
    st.header("📥 PropStream Leads")
    dfp = get_propstream_data()
    if dfp.empty:
        st.warning("No PropStream leads.")
        st.stop()
    dfp["Hot"] = dfp.get("hot_lead", False).map({True: "🔥", False: ""})
    st.dataframe(dfp[["id", "date_posted", "title", "price", "arv", "category", "Hot"]], use_container_width=True, height=500)
    sel = st.multiselect("Select IDs to delete:", dfp["id"])
    if st.button("🗑️ Delete Selected PropStream") and sel:
        supabase.table("propstream_leads").delete().in_("id", sel).execute()
        st.success(f"Deleted {len(sel)} listings.")
    if st.button("🧹 Delete ALL PropStream Listings"):
        all_ps = dfp["id"].tolist()
        supabase.table("propstream_leads").delete().in_("id", all_ps).execute()
        st.success("Deleted all PropStream listings.")

# ───── Leads Dashboard ─────
elif page == "Leads Dashboard":
    st.header("📊 Leads Dashboard")
    df = get_propstream_data()
    if df.empty:
        st.warning("No data available.")
        st.stop()
    df["equity"] = df["arv"] - df["price"]
    df["hot_lead"] = (df["equity"] / df["arv"] >= 0.25) & (df["arv"] >= 100000) & (df["equity"] >= 30000)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Leads", len(df))
    c2.metric("Avg Price", f"${df['price'].mean():,.0f}")
    c3.metric("Avg ARV", f"${df['arv'].mean():,.0f}")
    c4.metric("Hot Leads", int(df['hot_lead'].sum()))
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
        dfm = df.dropna(subset=["latitude", "longitude"])
        view = pdk.ViewState(latitude=dfm.latitude.mean(), longitude=dfm.longitude.mean(), zoom=11)
        layer = pdk.Layer("ScatterplotLayer", data=dfm, get_position=["longitude","latitude"], get_radius=100, pickable=True)
        st.pydeck_chart(pdk.Deck(initial_view_state=view, layers=[layer]))

# ───── Upload Leads ─────
elif page == "Upload Leads":
    st.header("📤 Upload PropStream Leads")
    zf = st.sidebar.text_input("Only include ZIP code:", "")
    cf = st.sidebar.text_input("Only include City:", "")
    im = st.sidebar.checkbox("🔗 Add Maps & Street View", False)
    ae = st.sidebar.checkbox("✉️ Send Email Alert", False)
    asms = st.sidebar.checkbox("📱 Send SMS Alert", False)
    st.sidebar.markdown("---")
    category = st.sidebar.selectbox("Category", ["Pre-Foreclosure","Fix & Flip","Auction","Tax Lien","Other"])
    up = st.file_uploader("Choose your CSV file", type=["csv"])
    if not up:
        st.info("Upload a CSV to unlock hot-lead insights.")
        st.stop()
    if st.button("🧹 Delete ALL PropStream Leads"):
        supabase.table("propstream_leads").delete().neq("id","").execute()
        st.success("Deleted all PropStream leads.")
    dfc = pd.read_csv(up)
    required_cols = {"Property Address","City","State","Zip Code","Amount Owed","Estimated Value"}
    missing = required_cols - set(dfc.columns)
    if missing:
        st.error("Missing: " + ", ".join(missing))
        st.stop()
    dfc = dfc.rename(columns={"Property Address":"address","City":"city","State":"state","Zip Code":"zip","Amount Owed":"price","Estimated Value":"arv"})
    if zf:
        dfc = dfc[dfc["zip"].astype(str).isin([z.strip() for z in zf.split(",")])]
    if cf:
        dfc = dfc[dfc["city"].str.lower() == cf.lower()]
    dfc["equity"] = dfc["arv"] - dfc["price"]
    dfc["hot_lead"] = (dfc["equity"]/dfc["arv"]>=0.25)&(dfc["arv"]>=100000)&(dfc["equity"]>=30000)
    dfc = dfc.replace([np.inf,-np.inf], np.nan)
    for rec in dfc.to_dict(orient="records"):
        rc = {k:(None if pd.isna(v) else v) for k,v in rec.items()}
        rc["title"] = rc.get("address")
        rc["link"] = rc.get("link","") or ""
        rc["date_posted"] = datetime.utcnow().isoformat()
        rc["category"] = rec.get("category", category)
        supabase.table("propstream_leads").upsert(rc).execute()
    hot = int(dfc["hot_lead"].sum())
    total = len(dfc)
    st.success(f"Uploaded {total} rows; {hot} hot leads.")
    st.write(f"Hot count: {hot} of {total}")
    st.dataframe(dfc[["address","price","arv","equity","hot_lead"]].head(10), use_container_width=True)

# ───── Deal Tools ─────
elif page == "Deal Tools":
    st.header("🧮 Deal Tools & Contracts")
    # Offer Calculator
    st.subheader("🔢 Offer Calculator (MAO)")
    arv = st.number_input("ARV", min_value=0.0, value=150000.0)
    repairs = st.number_input("Repair Costs", min_value=0.0, value=30000.0)
    offer_pct = st.slider("Offer % of ARV", 0.0, 1.0, 0.7)
    mao = (arv * offer_pct) - repairs
    st.metric("MAO", f"${mao:,.2f}")
    # Contract PDF
    st.subheader("📄 Generate Contract PDF")
    seller = st.text_input("Seller Name")
    prop_addr = st.text_input("Property Address")
    offer_price = st.number_input("Offer Price", value=round(mao,2))
    if st.button("Generate PDF Contract"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial","B",16)
        pdf.cell(0,10,"Real Estate Purchase Contract",ln=True,align="C")
        pdf.ln(10)
        pdf.set_font("Arial",size=12)
        for label, val in [("Date", datetime.utcnow().date()), ("Seller", seller), ("Property", prop_addr), ("Offer Price", f"${offer_price:,.2f}")]:
            pdf.multi_cell(0,8,f"{label}: {val}")
        pdf.ln(10)
        pdf.multi_cell(0,8,"This contract is subject to customary inspections and approvals.")
        buf = BytesIO()
        pdf_bytes = pdf.output(dest='S').encode('latin-1')
        buf = BytesIO(pdf_bytes)
        buf.seek(0)
        st.download_button("Download Contract PDF", data=buf, file_name="offer_contract.pdf", mime="application/pdf")

# ───── Settings ─────
else:
    st.header("Settings")
    st.markdown("""
    • Supabase tables: craigslist_leads, propstream_leads
    • Required schema: id, title, link, date_posted, price, arv, equity, hot_lead, category, address, city, state, zip, map_link, street_view_link, latitude, longitude
    """)
