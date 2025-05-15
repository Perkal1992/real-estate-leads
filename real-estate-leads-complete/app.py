import os
import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# ---------- Configuration ----------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
BG_IMAGE_PATH = "assets/sri_dallas_skyline.png"

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- Streamlit Setup ----------
st.set_page_config(page_title="Savory Lead Machine", layout="wide")

# ---------- Background Styling ----------
st.markdown(
    f"""
    <style>
    .stApp {{
        background: url('{BG_IMAGE_PATH}') no-repeat center center fixed;
        background-size: cover;
    }}
    .block-container {{
        background-color: rgba(0, 0, 0, 0.6) !important;
        padding: 2rem;
        border-radius: 0.5rem;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# ---------- Header with Drag-and-Drop Logo ----------
st.markdown(
    """
    <div style='text-align:center; margin-bottom:1rem;'>
        <h1 style='color: gold;'>🏘️ Savory Realty Lead Machine</h1>
    </div>
    """,
    unsafe_allow_html=True
)
uploaded_logo = st.file_uploader("Drag & drop your custom logo (PNG/JPG)", type=["png", "jpg", "jpeg"])
if uploaded_logo:
    st.image(uploaded_logo, use_column_width=True)
else:
    st.image(BG_IMAGE_PATH, use_column_width=True)

# ---------- Sidebar Controls ----------
st.sidebar.header("🔍 Controls")
status_filter = st.sidebar.selectbox("Filter Status", ["All", "New", "Hot", "Follow-up", "Dead"], index=0)
source_filter = st.sidebar.selectbox("Filter Source", ["All", "FSBO", "Craigslist", "Driving for Dollars", "Manual", "Other"], index=0)
if st.sidebar.button("Clear All Leads"):
    supabase.table("leads").delete().execute()
    st.sidebar.success("All leads cleared!")
    st.experimental_rerun()

# ---------- Add New Lead ----------
with st.expander("➕ Add New Lead"):
    with st.form("lead_form"):
        name = st.text_input("Name")
        phone = st.text_input("Phone")
        email = st.text_input("Email")
        address = st.text_input("Property Address")
        city = st.text_input("City")
        zip_code = st.text_input("ZIP Code")
        source = st.selectbox("Lead Source", ["FSBO", "Craigslist", "Driving for Dollars", "Manual", "Other"])
        status = st.selectbox("Status", ["New", "Hot", "Follow-up", "Dead"])
        follow_up_date = st.date_input("Next Follow-up Date")
        notes = st.text_area("Notes")
        if st.form_submit_button("Add Lead"):
            supabase.table("leads").insert({
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
            }).execute()
            st.success("Lead added!")

# ---------- Fetch Leads ----------
res = supabase.table("leads").select("*").order("created_at", desc=True).execute()
leads_df = pd.DataFrame(res.data)
if status_filter != "All": leads_df = leads_df[leads_df["status"] == status_filter]
if source_filter != "All": leads_df = leads_df[leads_df["source"] == source_filter]

# ---------- Remove Leads ----------
if "name" in leads_df.columns and "id" in leads_df.columns:
    st.subheader("🗑️ Remove Leads")
    select_all = st.checkbox("Select All Leads")
    options = [f"{r['name']} (ID: {r['id']})" for _, r in leads_df.iterrows()]
    default = options if select_all else []
    selected = st.multiselect("Select leads to delete:", options, default=default)
    if st.button("Delete Selected"):
        ids = [int(item.split("ID:")[1].rstrip(")").strip()) for item in selected]
        if ids:
            supabase.table("leads").delete().in_("id", ids).execute()
            st.success(f"Deleted {len(ids)} leads")
            st.experimental_rerun()

# ---------- Dashboard ----------
st.subheader("📈 Live Leads Dashboard")
if not leads_df.empty:
    st.dataframe(leads_df.drop(columns=["id"]), use_container_width=True)
    hot = leads_df[leads_df["status"] == "Hot"]
    if not hot.empty:
        st.markdown("### 🔥 HOT LEADS ALERT")
        st.table(hot[["name","phone","address","follow_up_date"]])
else:
    st.info("No leads to display.")
