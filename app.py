import os
import base64
import streamlit as st
import pandas as pd
import altair as alt
import pydeck as pdk
from supabase import create_client
from datetime import datetime

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
st.markdown(
    """
    <style>
      [data-testid="stSidebar"] { background-color: rgba(0,0,0,0.7); }
      .stButton>button { background-color: #0a84ff; color: #fff; }
    </style>
    """,
    unsafe_allow_html=True,
)
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

# ─── Data fetching & processing ────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def get_data() -> pd.DataFrame:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    resp = supabase.table("craigslist_leads") \
                    .select("*") \
                    .order("date_posted", desc=True) \
                    .execute()
    df = pd.DataFrame(resp.data)
    if df.empty:
        return df

    df["date_posted"] = pd.to_datetime(df["date_posted"], errors="coerce")
    df["price"]       = pd.to_numeric(df["price"], errors="coerce")

    if "arv" not in df.columns:
        df["arv"] = df["price"].apply(lambda x: int(x * 1.1) if pd.notna(x) else None)

    if "is_hot" not in df.columns:
        HOT_WORDS = ["cash", "as-is", "must sell", "motivated", "investor"]
        df["is_hot"] = df["title"].str.lower().apply(lambda t: any(w in t for w in HOT_WORDS))

    def make_map(r):
        if pd.notna(r.get("latitude")) and pd.notna(r.get("longitude")):
            return f"https://www.google.com/maps/search/?api=1&query={r.latitude},{r.longitude}"
        return None

    def make_sv(r):
        if pd.notna(r.get("latitude")) and pd.notna(r.get("longitude")):
            key = os.getenv("GOOGLE_MAPS_API_KEY")
            return (
                f"https://maps.googleapis.com/maps/api/streetview"
                f"?size=600x300&location={r.latitude},{r.longitude}&key={key}"
            )
        return None

    df["map_url"]         = df.apply(make_map, axis=1)
    df["street_view_url"] = df.apply(make_sv, axis=1)

    return df

# ─── Sidebar & Navigation ─────────────────────────────────────────
st.sidebar.image("logo.png", width=48)
st.sidebar.title("Savory Realty Investments")
page = st.sidebar.radio("", ["Leads", "Dashboard", "Settings"])

# ─── Leads page ───────────────────────────────────────────────────
if page == "Leads":
    st.header("Latest Listings")

    # CSV Upload
    st.markdown("---\n#### 📂 Upload Your Own Lead File (CSV)")
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded_file:
        try:
            uploaded_df = pd.read_csv(uploaded_file)
            st.success(f"✅ Uploaded {len(uploaded_df)} rows.")
            st.dataframe(uploaded_df)
        except Exception as e:
            st.error(f"❌ Error reading file: {e}")

    # Fetch & display from Supabase
    df = get_data()
    if df.empty:
        st.info("No leads found yet. Click **Refresh** below.")
    else:
        display = df.copy()
        display["Hot"]         = display["is_hot"].apply(lambda v: "🔥" if v else "")
        display["Map"]         = display["map_url"].apply(lambda u: f"[Map]({u})" if u else "")
        display["Street View"] = display["street_view_url"].apply(lambda u: f"[SV]({u})" if u else "")

        st.dataframe(display[[
            "date_posted", "source", "title", "price", "arv", "Hot", "Map", "Street View"
        ]], use_container_width=True)

        # Download button
        csv = display.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name="leads.csv",
            mime="text/csv",
        )

    if st.button("🔄 Refresh now"):
        get_data.clear()
        st.experimental_rerun()

# ─── Dashboard page ────────────────────────────────────────────────
elif page == "Dashboard":
    st.header("Analytics Dashboard")
    df = get_data()
    if df.empty:
        st.info("No data to chart.")
        st.stop()

    # Source filter
    sources    = df["source"].unique().tolist()
    sel_sources = st.multiselect("Filter by source", sources, default=sources)
    df = df[df["source"].isin(sel_sources)] if sel_sources else df

    # Hot-deal filter
    hot_only = st.checkbox("Hot deals only", value=False)
    if hot_only:
        df = df[df["is_hot"] == True]

    # Date-range slider
    min_date = df["date_posted"].dt.date.min()
    max_date = df["date_posted"].dt.date.max()
    start_date, end_date = st.slider(
        "Filter by date posted",
        min_date,
        max_date,
        (min_date, max_date)
    )
    df = df[df["date_posted"].dt.date.between(start_date, end_date)]

    # Metrics
    total     = len(df)
    avg_price = df["price"].mean()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Leads", total)
    c2.metric("Average Price", f"${avg_price:,.0f}" if not pd.isna(avg_price) else "—")
    c3.metric("Date Range", f"{start_date} → {end_date}")

    # Time series chart
    chart = (
        alt.Chart(df)
           .mark_line(point=True)
           .encode(
               x=alt.X("date_posted:T", title="Date Posted"),
               y=alt.Y("price:Q", title="Price (USD)"),
               tooltip=["title", "price", "date_posted"],
           )
           .properties(height=350)
    )
    st.altair_chart(chart, use_container_width=True)

    # Map view
    if {"latitude", "longitude"}.issubset(df.columns):
        df_map = df.dropna(subset=["latitude", "longitude"])
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

# ─── Settings page ───────────────────────────────────────────────
else:  # Settings
    st.header("Settings")
    st.write("Make sure your Supabase table `craigslist_leads` has these columns:")
    st.markdown("""
    - `id` (uuid primary key)
    - `date_posted` (timestamptz)
    - `title` (text)
    - `source` (text)
    - `price` (numeric)
    - `arv` (numeric)
    - `is_hot` (boolean)
    - `latitude` (float), `longitude` (float)
    - `street_view_url` (text)
    """)
    st.write("To change region, set the `CRAIGS_REGION` env var or edit the code.")