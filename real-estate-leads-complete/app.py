import streamlit as st
import pandas as pd
from supabase import create_client, Client

# ─── PAGE & SECRETS ─────────────────────────────────────────────────────
st.set_page_config(page_title="SRI Leads Viewer", layout="wide")
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# ─── SUPABASE CLIENT ────────────────────────────────────────────────────
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─── HEADER with your logo ──────────────────────────────────────────────
col1, col2 = st.columns([1, 8])
with col1:
    st.image("assets/logo.png", width=60)
with col2:
    st.title("Savory Realty Investments")
    st.markdown("> Live pipeline of scraped leads")

# ─── DATA LOADING ────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_leads() -> pd.DataFrame:
    resp = supabase.table("leads") \
        .select("*") \
        .order("created_at", desc=True) \
        .execute()
    return pd.DataFrame(resp.data or [])

df = load_leads()
if df.empty:
    st.warning("No leads found. Make sure your scraper has run.")
    st.stop()

# ─── SIDEBAR FILTERS ─────────────────────────────────────────────────────
st.sidebar.header("Filter & View Options")

# 1) filter by source
sources = ["All"] + sorted(df["source"].dropna().unique().tolist())
choice = st.sidebar.selectbox("Source", sources)

# 2) price slider
min_p, max_p = st.sidebar.slider(
    "Price range",
    int(df["price"].min() or 0),
    int(df["price"].max() or 0),
    (int(df["price"].min() or 0), int(df["price"].max() or 0)),
    step=1000
)

# 3) hot-lead toggle (if you have a `hot_lead` boolean column)
hot_only = st.sidebar.checkbox("Only hot leads", False)

# ─── APPLY FILTERS ───────────────────────────────────────────────────────
filtered = df.copy()
if choice != "All":
    filtered = filtered[filtered["source"] == choice]

filtered = filtered[
    filtered["price"].fillna(0).between(min_p, max_p)
]

if hot_only and "hot_lead" in filtered.columns:
    filtered = filtered[filtered["hot_lead"] == True]

# ─── MAKE LINKS CLICKABLE ────────────────────────────────────────────────
if "url" in filtered.columns:
    filtered["View"] = filtered["url"].apply(
        lambda u: f'<a href="{u}" target="_blank">🔗</a>'
    )
    display_df = filtered.drop(columns=["url"])
    st.write(f"### Showing {len(filtered)} of {len(df)} leads")
    st.write(display_df.to_html(escape=False, index=False),
             unsafe_allow_html=True)
else:
    st.write(f"### Showing {len(filtered)} of {len(df)} leads")
    st.dataframe(filtered, use_container_width=True)

# ─── DOWNLOAD BUTTON ────────────────────────────────────────────────────
st.download_button(
    "📥 Download CSV",
    filtered.to_csv(index=False),
    file_name="leads.csv",
    mime="text/csv"
)
