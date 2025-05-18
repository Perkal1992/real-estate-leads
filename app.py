import os
import base64
import streamlit as st
import pandas as pd
import altair as alt
import pydeck as pdk
from scraper import fetch_and_store

# ─── Helper to load a local image as Base64 ─────────────────────────────────────

def _get_base64(image_path: str) -> str:
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

# ─── Page config & styling ───────────────────────────────────────
background_base64 = _get_base64("logo.png")
st.set_page_config(
    page_title="Savory Realty Investments",
    page_icon="logo.png",
    layout="wide",
)

# ─── CSS Styles (Responsive Sidebar Toggle, Background, Mobile Fixes) ───
st.markdown(
    f"""
    <style>
      [data-testid="stAppViewContainer"] {{
        background-image: url("data:image/png;base64,{background_base64}");
        background-repeat: no-repeat;
        background-position: center center;
        background-attachment: fixed;
        background-size: cover;
        overflow: auto !important;
      }}
      [data-testid="stAppViewContainer"]::before {{
        content: "";
        position: absolute; top:0; left:0;
        width:100%; height:100%;
        background: rgba(0,0,0,0.6);
        z-index: 0;
        pointer-events: none;
      }}
      [data-testid="stAppViewContainer"] > * {{
        position: relative; z-index: 1;
      }}

      header [data-testid="collapsedControl"],
      header button[aria-label="Expand sidebar"],
      header button[aria-label="Collapse sidebar"] {{
        position: absolute !important;
        top: 10px !important;
        left: 10px !important;
        z-index: 1000 !important;
        transform: none !important;
      }}

      @media screen and (max-width: 768px) {{
        .stDataFrame, .stDataFrame > div {{
          overflow-x: auto !important;
          font-size: 14px !important;
        }}
        .stButton > button {{
          width: 100% !important;
          font-size: 16px !important;
        }}
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Dark theme tweaks (buttons/sidebar) ─────────────────────────
st.markdown(
    """
    <style>
      [data-testid="stSidebar"] { background-color: rgba(0,0,0,0.7); }
      .stButton>button { background-color: #0a84ff; color: #fff; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Opacity tweaks for panels ──────────────────────────
st.markdown(
    """
    <style>
      [data-testid="stDataFrame"],
      [data-testid="stDataFrame"] > div,
      [data-testid="stAltairChart"],
      [data-testid="stAltairChart"] > div {
        background-color: rgba(255,255,255,0.8) !important;
        backdrop-filter: blur(6px);
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Data caching ────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_data(region: str) -> pd.DataFrame:
    raw = fetch_and_store(region=region)
    return pd.DataFrame(raw)

region = os.getenv("CRAIGS_REGION", "dallas")

# ─── Sidebar navigation ───────────────────────────────
st.sidebar.image("logo.png", width=48)
st.sidebar.title("Savory Realty Investments")
page = st.sidebar.radio("", ["Leads", "Dashboard", "Settings"])

# ─── Leads page ──────────────────────────────────
if page == "Leads":
    st.header("Latest Craigslist Listings")
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

# ─── Dashboard page ─────────────────────────────
elif page == "Dashboard":
    st.header("Analytics Dashboard")
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
    c3.metric(
        "Date Range",
        f"{df.date_posted.min().date()} → {df.date_posted.max().date()}",
    )

    if st.checkbox("Show raw data preview"):
        st.write("DataFrame shape:", df.shape)
        st.dataframe(df.head(10))

    date_min, date_max = df.date_posted.min().date(), df.date_posted.max().date()
    if date_min < date_max:
        start_date, end_date = st.slider(
            "Filter by date posted", date_min, date_max, (date_min, date_max)
        )
    else:
        start_date = end_date = date_min
        st.write(f"Showing data for {date_min}")

    df_filtered = df[df.date_posted.between(
        pd.to_datetime(start_date), pd.to_datetime(end_date)
    )]

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

# ─── Settings page ──────────────────────────────
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
