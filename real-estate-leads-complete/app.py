import os
import streamlit as st
import pandas as pd
import altair as alt
import pydeck as pdk
from scraper import fetch_and_store

# ─── Page config must be first Streamlit call ────────────────────────────────
st.set_page_config(
    page_title="🏠 Savory Realty Investments",
    layout="wide",
)

# ─── DEBUG: now list files to verify logo.png is here ────────────────────────
st.write("Files in working dir:", os.listdir())

# ─── Logo + Title Header ─────────────────────────────────────────────────────
col1, col2 = st.columns([1, 8])
with col1:
    st.image("logo.png", width=80)   # ← ensure logo.png is in this same folder
with col2:
    st.markdown(
        "<h1 style='margin:0; color:#eee;'>Savory Realty Investments</h1>",
        unsafe_allow_html=True,
    )

# ─── Dark theme tweaks ────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
      body { background-color:#111; color:#eee; }
      .stApp { background-color:#111; }
      [data-testid="stSidebar"] { background-color:#222; }
      .stButton>button { background-color:#0a84ff; color:#fff; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Data caching & coercion ───────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_data(region: str) -> pd.DataFrame:
    raw = fetch_and_store(region=region)
    df = pd.DataFrame(raw)
    if "price" in df.columns:
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
    return df

region = os.getenv("CRAIGS_REGION", "dallas")

# ─── Sidebar navigation ───────────────────────────────────────────────────────
st.sidebar.title("🏠 Savory Realty Investments")
page = st.sidebar.radio("", ["Leads", "Dashboard", "Settings"])

# ─── Leads page ───────────────────────────────────────────────────────────────
if page == "Leads":
    st.header("🔎 Latest Craigslist Listings")
    df = get_data(region)

    if df.empty:
        st.info("No leads found yet. Click **Refresh** below.")
    else:
        st.dataframe(df)

    if st.button("🔄 Refresh now"):
        st.cache_data.clear()
        df = get_data(region)
        if df.empty:
            st.warning("Still no leads.")
        else:
            st.success(f"Fetched {len(df)} leads.")
            st.dataframe(df)

# ─── Dashboard page ──────────────────────────────────────────────────────────
elif page == "Dashboard":
    st.header("📊 Analytics Dashboard")
    df = get_data(region)

    if df.empty:
        st.info("No data to chart.")
        st.stop()

    # Convert dates & compute metrics
    df["date_posted"] = pd.to_datetime(df["date_posted"], errors="coerce")
    total = len(df)
    avg_price = df["price"].dropna().mean()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Leads", total)
    c2.metric("Average Price", f"${avg_price:,.0f}" if not pd.isna(avg_price) else "—")
    c3.metric(
        "Date Range",
        f"{df.date_posted.min().date()} → {df.date_posted.max().date()}",
    )

    # Raw-data toggle
    if st.checkbox("Show raw data preview"):
        st.write("DataFrame shape:", df.shape)
        st.dataframe(df.head(10))

    # DATE FILTER (with guard)
    date_min = df.date_posted.min().date()
    date_max = df.date_posted.max().date()

    if date_min < date_max:
        start_date, end_date = st.slider(
            "Filter by date posted",
            min_value=date_min,
            max_value=date_max,
            value=(date_min, date_max),
        )
    else:
        start_date = end_date = date_min
        st.write(f"Showing data for {date_min}")

    mask = df.date_posted.between(
        pd.to_datetime(start_date), pd.to_datetime(end_date)
    )
    df_filtered = df.loc[mask]

    # Plot chart
    chart = (
        alt.Chart(df_filtered)
           .mark_line(point=True)
           .encode(
               x=alt.X("date_posted:T", title="Date Posted"),
               y=alt.Y("price:Q", title="Price (USD)"),
               tooltip=["title", "price", "date_posted"],
           )
           .properties(height=350, width=800)
    )
    st.altair_chart(chart, use_container_width=True)

    # Map view if we have coordinates
    if {"latitude", "longitude"}.issubset(df_filtered.columns):
        df_map = df_filtered.dropna(subset=["latitude", "longitude"])
        st.subheader("📍 Lead Locations")
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

# ─── Settings page ───────────────────────────────────────────────────────────
elif page == "Settings":
    st.header("⚙️ Settings")
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
    st.write("To change your region/subdomain, edit `region = os.getenv(...)` or update `scraper.py`.")
