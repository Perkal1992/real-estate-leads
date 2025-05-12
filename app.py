import streamlit as st
import pandas as pd
from supabase import create_client, Client

# ──────── Supabase Configuration ────────
SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB3a2JzenNsamxweGhsZmN2ZGVyIiwicm9sZSI6ImFub24iLC"
    "JpYXQiOjE3NDQzNDk4MDEsImV4cCI6MjA1OTkyNTgwMX0."
    "bjVMzL4X6dN6xBx8tV3lT7XPsOFIEqMLv0pG3y6N-4o"
)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ──────── Streamlit Config & Theme ────────
st.set_page_config("Savory Realty Lead Engine", layout="wide")
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
    response = supabase.table("leads").select("*").order("created_at", desc=True).limit(100).execute()
    df = pd.DataFrame(response.data)

    if df.empty:
        st.warning("No leads found yet.")
    else:
        df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(df, use_container_width=True)
except Exception as err:
    st.error(f"Failed to retrieve leads: {err}")