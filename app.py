import os
import base64
from datetime import datetime
import numpy as np
import streamlit as st
import pandas as pd
import altair as alt
import pydeck as pdk
from io import BytesIO
from postgrest.exceptions import APIError

# Attempt to import FPDF for PDF generation
try:
    from fpdf import FPDF
except ImportError:
    st.error("`fpdf` module not found. Please add `fpdf` to your `requirements.txt` and redeploy.")
    FPDF = None

# Initialize Supabase client
from supabase import create_client
SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "YOUR_SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Helper to calculate lead score

def calculate_score(row):
    arv = row.get("arv", 0)
    equity = row.get("equity", 0)
    if arv <= 0 or equity <= 0:
        return 0
    return (equity / arv) * 100 + (arv / 1000)

# Helper to tag motivation keywords

def tag_motivation(text):
    tags = ["vacant", "divorce", "fire", "urgent"]
    text_lower = str(text).lower()
    matched = [t for t in tags if t in text_lower]
    return ", ".join(matched)

# ---------------------------------
# Data Fetching Functions
# ---------------------------------

@st.cache_data(ttl=300)
def get_craigslist_data():
    # Fetch data from Supabase
    resp = supabase.table("craigslist_leads").select("*").order("date_posted", desc=True).execute()
    df = pd.DataFrame(resp.data or [])

    # If empty return early
    if df.empty:
        return df

    # Ensure numeric columns exist
    for col in ["price", "arv", "equity"]:
        if col not in df.columns:
            df[col] = 0

    # Replace infinities and missing
    df = df.replace([np.inf, -np.inf], np.nan)
    df["date_posted"] = pd.to_datetime(df.get("date_posted"), errors="coerce")

    # Coerce numeric columns
    for col in ["price", "arv", "equity"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Fill title
    df["title"] = df.get("title", "").fillna("")

    # Compute additional fields
    df["score"] = df.apply(calculate_score, axis=1)
    df["motivation"] = df["title"].apply(tag_motivation)

    # Drop rows missing essentials
    return df.dropna(subset=["title", "date_posted"])

@st.cache_data(ttl=300)
def get_propstream_data():
    resp = supabase.table("propstream_leads").select("*").order("date_posted", desc=True).execute()
    df = pd.DataFrame(resp.data or [])

    if df.empty:
        return df

    # Ensure required columns
    for col in ["price", "arv", "equity", "category"]:
        if col not in df.columns:
            df[col] = 0 if col != "category" else ""

    df = df.replace([np.inf, -np.inf], np.nan)
    df["date_posted"] = pd.to_datetime(df.get("date_posted"), errors="coerce")

    for col in ["price", "arv", "equity"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["title"] = df.get("title", "").fillna("")
    df["score"] = df.apply(calculate_score, axis=1)
    df["motivation"] = df["title"].apply(tag_motivation)

    return df.dropna(subset=["title", "date_posted"])

# ---------------------------------
# Streamlit Page Setup
# ---------------------------------

st.set_page_config(page_title="Savory Realty Investments", page_icon="🏘️", layout="wide")

# Load background image

def _get_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

bg = _get_base64("logo.png")
st.markdown(
    f"""
    <style>
    [data-testid="stAppViewContainer"] {{
      background-image: linear-gradient(rgba(0,0,0,0.6), rgba(0,0,0,0.6)), url('data:image/png;base64,{bg}');
      background-repeat: no-repeat;
      background-position: center;
      background-size: contain;
    }}
    </style>
    """, unsafe_allow_html=True
)

# Sidebar navigation
st.sidebar.image("logo.png", width=48)

st.sidebar.title("Savory Realty Investments")
page = st.sidebar.radio(
    "Navigate to:",
    [
        "Live Leads",
        "PropStream Leads",
        "Leads Dashboard",
        "Upload Leads",
        "Deal Tools",
        "Settings",
    ],
)

# ---------------------------------
# Live Leads Page
# ---------------------------------

if page == "Live Leads":
    st.header("📬 Live Leads")
    df = get_craigslist_data()
    if df.empty:
        st.warning("No leads found.")
        st.stop()

    # Format markers
    df["Hot"] = df.get("hot_lead", False).map({True: "🔥", False: ""})
    df["Map"] = df.apply(
        lambda r: f"https://www.google.com/maps?q={r.latitude},{r.longitude}" if pd.notna(r.latitude) else None,
        axis=1,
    )
    df["Street View"] = df.get("street_view_url", "")
    df["Link"] = df.get("link", "").map(lambda u: f"[View Post]({u})" if u else "")

    # Deletion controls
    to_delete = st.multiselect("Delete Craigslist IDs:", df["id"].tolist())
    if st.button("🗑️ Delete Selected") and to_delete:
        supabase.table("craigslist_leads").delete().in_("id", to_delete).execute()
        st.success("Deleted selected.")
    if st.button("🗑️ Delete All"):
        supabase.table("craigslist_leads").delete().neq("id", "").execute()
        st.success("Cleared all.")

    # Display
    st.dataframe(
        df[
            [
                "id",
                "date_posted",
                "title",
                "price",
                "arv",
                "score",
                "motivation",
                "Hot",
                "Map",
                "Street View",
                "Link",
            ]
        ],
        use_container_width=True,
        height=600,
    )

# ---------------------------------
# PropStream Leads Page
# ---------------------------------

elif page == "PropStream Leads":
    st.header("📥 PropStream Leads")
    df = get_propstream_data()
    if df.empty:
        st.warning("No PropStream leads.")
        st.stop()

    df["Hot"] = df.get("hot_lead", False).map({True: "🔥", False: ""})
    sel = st.multiselect("Delete PropStream IDs:", df["id"].tolist())
    if st.button("🗑️ Delete Selected") and sel:
        supabase.table("propstream_leads").delete().in_("id", sel).execute()
        st.success("Deleted selected.")
    if st.button("🧹 Delete All"):
        supabase.table("propstream_leads").delete().neq("id", "").execute()
        st.success("Cleared all.")

    df["Map"] = df.apply(
        lambda r: f"https://www.google.com/maps?q={r.latitude},{r.longitude}" if pd.notna(r.latitude) else None,
        axis=1,
    )
    df["Street View"] = df.get("street_view_url", "")

    st.dataframe(
        df[
            ["id", "date_posted", "title", "price", "arv", "category", "score", "motivation", "Hot", "Map", "Street View"]
        ],
        use_container_width=True,
        height=600,
    )

# ---------------------------------
# Leads Dashboard
# ---------------------------------

elif page == "Leads Dashboard":
    st.header("📊 Leads Dashboard")
    show_cr = st.sidebar.checkbox("Show Craigslist Leads", value=False)
    show_ps = st.sidebar.checkbox("Show PropStream Leads", value=True)

    dfs = []
    if show_cr:
        df_cr = get_craigslist_data()
        df_cr["source"] = "Craigslist"
        dfs.append(df_cr)

    if show_ps:
        df_ps = get_propstream_data()
        df_ps["source"] = "PropStream"
        dfs.append(df_ps)

    if not dfs:
        st.warning("Pick at least one source.")
        st.stop()

    combined = pd.concat(dfs, ignore_index=True)

    # Ensure numeric columns
    for col in ["price", "arv", "equity"]:
        if col not in combined.columns:
            combined[col] = 0

    combined = combined.replace([np.inf, -np.inf], np.nan).fillna({"price": 0, "arv": 0, "equity": 0})
    combined["equity"] = combined["arv"] - combined["price"]
    combined["hot_lead"] = (
        (combined["equity"] / combined["arv"] >= 0.25) &
        (combined["arv"] >= 100000) &
        (combined["equity"] >= 30000)
    )

    if "category" in combined.columns:
        cats = sorted(combined[combined["source"] == "PropStream"]["category"].dropna().unique())
        chosen = st.multiselect("Filter PropStream categories:", cats, default=cats)
        combined = combined[~((combined["source"] == "PropStream") & (~combined["category"].isin(chosen)))]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Leads", len(combined))
    c2.metric("Avg Price", f"${combined['price'].mean():,.0f}")
    c3.metric("Avg ARV", f"${combined['arv'].mean():,.0f}")
    c4.metric("Hot Leads", int(combined['hot_lead'].sum()))

    if st.checkbox("Show Price over Time"):
        chart = alt.Chart(combined).mark_line(point=True).encode(
            x="date_posted:T",
            y="price:Q",
            color="source:N",
            tooltip=["source", "title", "price", "arv", "equity"],
        ).properties(width=800)
        st.altair_chart(chart)

    if {"latitude", "longitude"}.issubset(combined.columns):
        dfm = combined.dropna(subset=["latitude", "longitude"])
        view = pdk.ViewState(
            latitude=dfm.latitude.mean(),
            longitude=dfm.longitude.mean(),
            zoom=11,
        )
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=dfm,
            get_position=["longitude", "latitude"],
            radiusScale=10,
            get_fill_color="datum.source=='Craigslist' ? [255,0,0] : [0,128,0]",
        )
        st.pydeck_chart(pdk.Deck(initial_view_state=view, layers=[layer]))

# ---------------------------------
# Upload Leads
# ---------------------------------

elif page == "Upload Leads":
    st.header("📤 Upload PropStream Leads")
    zf = st.sidebar.text_input("ZIP filter:
