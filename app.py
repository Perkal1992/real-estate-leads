import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# Supabase credentials
SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB3a2JzenNsamxweGhsZmN2ZGVyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQzNDk4MDEsImV4cCI6MjA1OTkyNTgwMX0.bjVMzL4X6dN6xBx8tV3lT7XPsOFIEqMLv0pG3y6N-4o"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Savory Lead Machine", layout="wide")

# Add your logo at the top
st.image("https://raw.githubusercontent.com/Perkal1992/real-estate-leads/main/assets/sri_logo_header.png", width=300)

st.title("🏘️ Savory Realty Lead Machine")

# Sidebar filters
st.sidebar.header("🔍 Filter Leads")
status_filter = st.sidebar.selectbox("Status", ["All", "New", "Hot", "Follow-up", "Dead"])
source_filter = st.sidebar.selectbox("Source", ["All", "FSBO", "Craigslist", "Driving for Dollars", "Manual", "Other"])

# Add new lead
with st.expander("➕ Add New Lead"):
    with st.form("lead_form"):
        name = st.text_input("Lead Name")
        phone = st.text_input("Phone Number")
        email = st.text_input("Email")
        address = st.text_input("Property Address")
        city = st.text_input("City")
        zip_code = st.text_input("ZIP Code")
        source = st.selectbox("Lead Source", ["FSBO", "Craigslist", "Driving for Dollars", "Manual", "Other"])
        status = st.selectbox("Status", ["New", "Hot", "Follow-up", "Dead"])
        follow_up_date = st.date_input("Next Follow-up Date")
        notes = st.text_area("Lead Notes")
        submitted = st.form_submit_button("✅ Add Lead")

    if submitted:
        new_data = {
            "name": name,
            "phone": phone,
            "email": email,
            "address": address,
            "city": city,
            "zip": zip_code,
            "source": source,
            "status": status,
            "follow_up_date": follow_up_date.strftime("%Y-%m-%d"),
            "notes": notes,
            "created_at": datetime.now().isoformat()
        }
        supabase.table("leads").insert(new_data).execute()
        st.success("🚀 Lead added to your pipeline!")

# Load leads from Supabase
leads_data = supabase.table("leads").select("*").order("created_at", desc=True).execute()
leads_df = pd.DataFrame(leads_data.data)

# Apply filters
if status_filter != "All":
    leads_df = leads_df[leads_df["status"] == status_filter]
if source_filter != "All":
    leads_df = leads_df[leads_df["source"] == source_filter]

# Display leads dashboard
st.subheader("📈 Live Leads Dashboard")
if not leads_df.empty:
    all_columns = ["id", "name", "phone", "city", "status", "source", "follow_up_date", "notes", "created_at"]
    available_columns = [col for col in all_columns if col in leads_df.columns]
    leads_df = leads_df[available_columns]

    # Inline editing
    if "name" in leads_df.columns:
        selected_lead = st.selectbox("Select a lead to edit/delete", leads_df["name"])
        lead_row = leads_df[leads_df["name"] == selected_lead].iloc[0]

        with st.expander("✏️ Edit Lead"):
            with st.form("edit_form"):
                new_status = st.selectbox("Update Status", ["New", "Hot", "Follow-up", "Dead"], index=["New", "Hot", "Follow-up", "Dead"].index(lead_row["status"]))
                new_notes = st.text_area("Update Notes", value=lead_row["notes"])
                update_btn = st.form_submit_button("💾 Save Changes")

                if update_btn:
                    supabase.table("leads").update({"status": new_status, "notes": new_notes}).eq("id", lead_row["id"]).execute()
                    st.success("✅ Lead updated successfully!")
                    st.experimental_rerun()

        if st.button("🗑️ Delete Lead"):
            supabase.table("leads").delete().eq("id", lead_row["id"]).execute()
            st.success("❌ Lead deleted!")
            st.experimental_rerun()

    st.dataframe(leads_df.drop(columns=["id"]) if "id" in leads_df.columns else leads_df, use_container_width=True)

    # HOT Leads Alert
    if "status" in leads_df.columns and "name" in leads_df.columns and "phone" in leads_df.columns and "address" in leads_df.columns and "follow_up_date" in leads_df.columns:
        hot_leads = leads_df[leads_df["status"] == "Hot"]
        if not hot_leads.empty:
            st.markdown("### 🔥 HOT LEADS ALERT")
            st.table(hot_leads[["name", "phone", "address", "follow_up_date"]])
else:
    st.info("No leads match your filter. Add a new lead above.")
