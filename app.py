import streamlit as st
from scraper import get_craigslist_leads, supabase

st.set_page_config(
    page_title="🏠 Real Estate Leads",
    layout="wide",
)

st.title("🏠 Real Estate Leads & Dashboard")

# Sidebar menu
menu = st.sidebar.radio("Navigate to", ["Craigslist Leads", "Database Dashboard"])

if menu == "Craigslist Leads":
    st.header("🔎 Latest Craigslist Listings")
    leads = get_craigslist_leads()
    if not leads:
        st.warning("No leads found—check your URL or network.")
    else:
        # Display each lead
        for lead in leads:
            st.markdown(f"- [{lead['title']}]({lead['link']}) • {lead['price']}")

else:
    st.header("📊 Supabase-Backed Dashboard")
    try:
        # Pull all rows from a "leads" table
        data = supabase.table("leads").select("*").execute().data
        st.dataframe(data)
    except Exception as e:
        st.error(f"Failed to fetch from Supabase: {e}")
