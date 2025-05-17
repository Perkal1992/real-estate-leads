import os
import streamlit as st
import pandas as pd
import altair as alt
import pydeck as pdk
from scraper import fetch_and_store

# ─── Page config & styling ────────────────────────────────────────────────────
SAS_BG_URL = (
    "https://sdmntprwestus3.oaiusercontent.com/files/"
    "00000000-1c14-61fd-8c9b-5286adab6799/raw?"
    "se=2025-05-17T15%3A11%3A06Z&sp=r&sv=2024-08-04&sr=b&"
    "scid=00000000-0000-0000-0000-000000000000&"
    "skoid=71e8fa5c-90a9-4c17-827b-14c3005164d6&"
    "sktid=a48cca56-e6da-484e-a814-9c849652bcb3&"
    "skt=2025-05-17T13%3A38%3A19Z&ske=2025-05-18T13%3A38%3A19Z&"
    "sks=b&skv=2024-08-04&sig=Fp4tNIXrj0xHYmf6ARoenQtZ6uVwdeIl7ZSlzTzzba4%3D"
)

st.set_page_config(
    page_title="Savory Realty Investments",
    page_icon=SAS_BG_URL,
    layout="wide",
)

# ─── Full-page background via CSS ────────────────────────────────────────────
st.markdown(
    f"""
    <style>
      .stApp {{
        background: url("{SAS_BG_URL}") no-repeat center center fixed;
        background-size: cover;
      }}
      .stApp::before {{
        content: "";
        position: absolute; top:0; left:0;
        width:100%; height:100%;
        background: rgba(0,0,0,0.6);
        z-index: 0;
      }}
      .main > div {{
        position: relative; z-index: 1;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Dark theme tweaks (buttons/sidebar) ─────────────────────────────────────
st.markdown(
    """
    <style>
      [data-testid="stSidebar"] { background-color:rgba(0,0,0,0.7); }
      .stButton>button { background-color:#0a84ff; color:#fff; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Opacity tweaks ───────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
      /* Restore sidebar opacity */
      [data-testid="stSidebar"] {
        background-color: rgba(0,0,0,0.7) !important;
      }
      /* Slightly translucent panels for tables and charts */
      [data-testid="stDataFrame"],
      [data-testid="stDataFrame"] > div,
      [data-testid="stAltairChart"],
      [data-testid="stAltairChart"] > div {
        background-color: rgba(255, 255, 255, 0.8) !important;
        backdrop-filter: blur(6px);
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Data caching ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_data(region: str) -> pd.DataFrame:
    raw = fetch_and_store(region=region)
    return pd.DataFrame(raw)

region = os.getenv("CRAIGS_REGION", "dallas")

# ─── Sidebar navigation ───────────────────────────────────────────────────────
st.sidebar.image(SAS_BG_URL, width=48)
st.sidebar.title("Savory Realty Investments")
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
        get_data.clear()
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

    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["date_posted"] = pd.to_datetime(df["date_posted"], errors="coerce")

    total = len(df)
    avg_price = df["price"].mean()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Leads", total)
    c2.metric("Average Price", f"${avg_price:,.0f}" if not pd.isna(avg_price) else "—")
    c3.metric("Date Range",
              f"{df.date_posted.min().date()} → {df.date_posted.max().date()}")

    if st.checkbox("Show raw data preview"):
        st.write("DataFrame shape:", df.shape)
        st.dataframe(df.head(10))

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

    df_filtered = df[df.date_posted.between(pd.to_datetime(start_date),
                                            pd.to_datetime(end_date))]

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
    st.write("To change your region/subdomain, edit the `region = os.getenv(...)` line or update `scraper.py`.")
