import streamlit as st
import pandas as pd
from supabase import create_client, Client
from scraper import get_craigslist_leads
from datetime import datetime

# ——————————————————————————————
# 1) Supabase setup via secrets.toml
# ——————————————————————————————
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ——————————————————————————————
# 2) Page layout
# ——————————————————————————————
st.set_page_config(
    page_title="🏠 Real Estate Leads Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.sidebar.title("🏠 Real Estate Leads")
page = st.sidebar.radio("Go to", ["🔎 Leads", "📊 Dashboard", "⚙️ Settings"])

# ——————————————————————————————
# 3) Global inputs
# ——————————————————————————————
city = st.sidebar.text_input(
    "Craigslist region",
    value="sfbay",
    help="Subdomain only (e.g. ‘sfbay’, ‘newyork’, ‘losangeles’…)"
)

# ——————————————————————————————
# 4) Helper to push to Supabase
# ——————————————————————————————
def save_leads_to_db(df: pd.DataFrame):
    # Assumes a table 'craigslist_leads' with matching schema exists
    records = df.to_dict(orient="records")
    # upsert so we don’t duplicate on reruns
    supabase.table("craigslist_leads").upsert(records).execute()


# ——————————————————————————————
# 5) Page: Leads
# ——————————————————————————————
if page == "🔎 Leads":
    st.title("🔎 Latest Craigslist Listings")

    if not city.strip():
        st.error("Please enter a Craigslist city subdomain in Settings.")
        st.stop()

    if st.button("⟳ Refresh now"):
        st.experimental_memo.clear()  # clear cache on-demand

    @st.experimental_memo(ttl=300, show_spinner=False)
    def fetch():
        return get_craigslist_leads(city)

    try:
        leads = fetch()
    except Exception as e:
        st.error(f"Could not fetch listings: {e}")
        st.stop()

    df = pd.DataFrame(leads)
    if not df.empty:
        df_display = df.copy()
        df_display["date_posted"] = df_display["date_posted"].dt.strftime("%Y-%m-%d %H:%M")
        df_display["fetched_at"] = df_display["fetched_at"].dt.strftime("%Y-%m-%d %H:%M:%S")
        st.dataframe(df_display[["fetched_at", "date_posted", "title", "price", "link"]], height=500)

        # persist
        save_leads_to_db(df)
        st.success(f"Saved {len(df)} leads to Supabase!")

    else:
        st.warning("No listings found.")

# ——————————————————————————————
# 6) Page: Dashboard
# ——————————————————————————————
elif page == "📊 Dashboard":
    st.title("📊 Analytics Dashboard")

    # pull last 1000 rows
    data = supabase.table("craigslist_leads") \
        .select("*") \
        .order("fetched_at", desc=True) \
        .limit(1000) \
        .execute() \
        .data

    if not data:
        st.info("No data in Supabase yet—run a fetch first.")
        st.stop()

    df = pd.DataFrame(data)
    df["fetched_at"] = pd.to_datetime(df["fetched_at"])
    df["date_posted"] = pd.to_datetime(df["date_posted"])

    st.subheader("Leads over time")
    counts = df.groupby(df["fetched_at"].dt.date).size().rename("count")
    st.bar_chart(counts)

    st.subheader("Price distribution")
    st.histogram = None
    st.pyplot(__import__("matplotlib.pyplot").figure().add_subplot(111).hist(df["price"].dropna(), bins=20),
              use_container_width=True)

    st.subheader("Recent entries")
    st.table(df.sort_values("fetched_at", ascending=False)
             .head(10)[["fetched_at", "title", "price", "link"]])

# ——————————————————————————————
# 7) Page: Settings
# ——————————————————————————————
else:
    st.title("⚙️ Settings")
    st.write("""
    - **Craigslist region**: Change the subdomain (e.g. `sfbay`, `newyork`, etc.).
    - **Cache TTL**: Listings are cached for 5m; hit “Refresh now” to force a refetch.
    - **Supabase table**: Ensure you’ve created a table named `craigslist_leads` with columns:
        - `date_posted` (timestamp)
        - `title` (text)
        - `link` (text)
        - `price` (numeric)
        - `fetched_at` (timestamp)
    """)

