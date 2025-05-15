import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# ---------- Configuration ----------
# Replace these paths/keys with your actual values or use Streamlit secrets
SUPABASE_URL = st.secrets.get("SUPABASE_URL")  # e.g., "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")  # your anon key
LOGO_PATH = "/mnt/data/A_logo_for_Savory_Realty_Investments_(SRI)_is_set_.png"  # local logo file path

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- Streamlit Page Setup ----------
st.set_page_config(page_title="Savory Lead Machine", layout="wide")

# Header
st.image(LOGO_PATH, width=250)
st.title("🏘️ Savory Realty Lead Machine")

# ---------- Sidebar Filters ----------
st.sidebar.header("🔍 Filter Leads")
status_filter = st.sidebar.selectbox(
    "Status", ["All", "New", "Hot", "Follow-up", "Dead"], index=0
)
source_filter = st.sidebar.selectbox(
    "Source", ["All", "FSBO", "Craigslist", "Driving for Dollars", "Manual", "Other"], index=0
)

# ---------- Add New Lead Form ----------
with st.expander("➕ Add New Lead"):
    with st.form(key="lead_form"):
        name = st.text_input("Name")
        phone = st.text_input("Phone")
        email = st.text_input("Email")
        address = st.text_input("Property Address")
        city = st.text_input("City")
        zip_code = st.text_input("ZIP Code")
        source = st.selectbox(
            "Lead Source", ["FSBO", "Craigslist", "Driving for Dollars", "Manual", "Other"]
        )
        status = st.selectbox(
            "Status", ["New", "Hot", "Follow-up", "Dead"]
        )
        follow_up_date = st.date_input("Next Follow-up Date")
        notes = st.text_area("Notes")
        submit = st.form_submit_button(label="Add Lead")

        if submit:
            new_lead = {
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
                "created_at": datetime.utcnow().isoformat()
            }
            supabase.table("leads").insert(new_lead).execute()
            st.success("🚀 Lead added to your pipeline!")

# ---------- Fetch & Filter Leads ----------
response = supabase.table("leads").select("*").order("created_at", desc=True).execute()
leads_df = pd.DataFrame(response.data)

if status_filter != "All":
    leads_df = leads_df[leads_df["status"] == status_filter]
if source_filter != "All":
    leads_df = leads_df[leads_df["source"] == source_filter]

# ---------- Remove Leads UI ----------
st.subheader("🗑️ Remove Leads")
select_all = st.checkbox("Select All", key="select_all")
options = [f"{row['name']} (ID: {row['id']})" for _, row in leads_df.iterrows()] if not leads_df.empty else []
default = options if select_all else []
selected = st.multiselect("Select leads to delete:", options, default=default)
if st.button("Delete Selected"):
    ids_to_delete = [int(item.split("ID:")[1].rstrip(")").strip() ) for item in selected]
    if ids_to_delete:
        supabase.table("leads").delete().in_("id", ids_to_delete).execute()
        st.success(f"Deleted {len(ids_to_delete)} lead(s). Refreshing...")
        st.experimental_rerun()

# ---------- Live Leads Dashboard ----------
st.subheader("📈 Live Leads Dashboard")
if not leads_df.empty:
    # Drop internal columns or re-order as desired
display_df = leads_df.drop(columns=["id"]) if "id" in leads_df.columns else leads_df
    st.dataframe(display_df, use_container_width=True)

    # Hot Leads Alert
    hot_leads = leads_df[leads_df["status"] == "Hot"]
    if not hot_leads.empty:
        st.markdown("## 🔥 HOT LEADS ALERT")
        st.table(hot_leads[["name", "phone", "address", "follow_up_date"]])
else:
    st.info("No leads found. Use the form above to add new leads.")
