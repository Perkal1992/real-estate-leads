import os
import streamlit as st
import pandas as pd
from supabase import create_client, Client

# ──────── Credentials & Supabase Init ────────
# Try env-vars first (for CI/GitHub Actions), fall back to local config.py
try:
    import config
    _local = True
except ImportError:
    _local = False

SUPABASE_URL        = os.getenv("SUPABASE_URL",        config.SUPABASE_URL        if _local else None)
SUPABASE_KEY        = os.getenv("SUPABASE_KEY",        config.SUPABASE_KEY        if _local else None)
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", config.GOOGLE_MAPS_API_KEY if _local else None)
RAPIDAPI_KEY        = os.getenv("RAPIDAPI_KEY",        config.RAPIDAPI_KEY        if _local else None)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ──────── Streamlit Config & Theme ────────
st.set_page_config(page_title="Savory Realty Lead Engine", layout="wide")
st.markdown(
    """
    <style>
        body { background-color: #001F1F !important; color: #d9ffcc !important; }
        .stApp { background-color: #001F1F !important; }
        [data-testid="stHeader"] { background-color: #003333; color: #d9ffcc; }
        .stButton > button {
            background-color: #00ff00 !important;
            color: black !important;
            font-weight: bold;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ──────── UI Header ────────
st.title("🏘️ Savory Realty Lead Engine")
st.caption("Real-time leads. Flagged hot deals. Instant updates from DFW sources.")

# ──────── Fetch & Display Leads ────────
st.subheader("Latest Leads (Supabase Synced)")

try:
    response = (
        supabase
        .table("leads")
        .select("*")
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    df = pd.DataFrame(response.data)

    if df.empty:
        st.warning("No leads found yet.")
    else:
        df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(df, use_container_width=True)

except Exception as err:
    st.error(f"Failed to retrieve leads: {err}")
