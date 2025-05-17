import os
import streamlit as st
from supabase import create_client, Client
from scraper import get_craigslist_leads

def init_supabase() -> Client:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("🚨 Missing SUPABASE_URL or SUPABASE_KEY in environment")
        st.stop()
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"❌ Supabase initialization error:\n{e}")
        st.stop()

def run_scraper_view(supabase: Client):
    st.header("🔄 Scrape & Save Craigslist Leads")
    if st.button("Fetch latest leads"):
        leads = get_craigslist_leads()
        if not leads:
            st.warning("No leads found.")
            return
        st.write(f"Found **{len(leads)}** new leads.")
        st.table(leads)
        with st.spinner("Saving to Supabase…"):
            for lead in leads:
                supabase.table("leads").insert(lead).execute()
        st.success("✅ All leads saved!")

def run_dashboard_view(supabase: Client):
    st.header("📈 Stored Leads Dashboard")
    resp = (
        supabase.table("leads")
                .select("*")
                .order("created_at", desc=True)
                .limit(50)
                .execute()
    )
    if resp.error:
        st.error(f"Error fetching data: {resp.error.message}")
    elif resp.data:
        st.dataframe(resp.data, use_container_width=True)
    else:
        st.info("No leads in your database yet.")

def main():
    st.set_page_config(page_title="Real-Estate Leads", layout="wide")
    supabase = init_supabase()

    choice = st.sidebar.selectbox(
        "Navigation",
        ["Scrape Leads", "View Dashboard"]
    )

    if choice == "Scrape Leads":
        run_scraper_view(supabase)
    else:
        run_dashboard_view(supabase)

if __name__ == "__main__":
    main()
