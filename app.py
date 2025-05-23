import os
import base64
from datetime import datetime
import numpy as np
import streamlit as st
import pandas as pd
import altair as alt
import pydeck as pdk
from io import BytesIO
try:
    from fpdf import FPDF
except ImportError:
    st.error("`fpdf` module not found. Please add `fpdf` to your `requirements.txt` and redeploy.")
    FPDF = None
from supabase import create_client

# ───── Supabase Setup ─────
SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB3a2JzenNsamxweGhsZmN2ZGVyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQzNDk4MDEsImV4cCI6MjA1OTkyNTgwMX0.bjVMzL4X6dN6xBx8tV3lT7XPsOFIEqMLv0pG3y6N-4o"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ───── Helper Functions ─────
@st.cache_data(ttl=300)
def get_craigslist_data():
    resp = supabase.table("craigslist_leads").select("*").order("date_posted", desc=True).execute()
    df = pd.DataFrame(resp.data or [])
    if df.empty:
        return df
    df["date_posted"] = pd.to_datetime(df["date_posted"], errors="coerce")
    for col in ("price", "arv", "equity"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if "title" not in df.columns:
        df["title"] = ""
    df["score"] = df.apply(calculate_score, axis=1)
    df["motivation"] = df["title"].apply(tag_motivation)
    return df.dropna(subset=["title", "date_posted"])

@st.cache_data(ttl=300)
def get_propstream_data():
    resp = supabase.table("propstream_leads").select("*").order("date_posted", desc=True).execute()
    df = pd.DataFrame(resp.data or [])
    if df.empty:
        return df
    df["date_posted"] = pd.to_datetime(df["date_posted"], errors="coerce")
    for col in ("price", "arv", "equity"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if "title" not in df.columns:
        df["title"] = ""
    if "category" not in df.columns:
        df["category"] = ""
    df["score"] = df.apply(calculate_score, axis=1)
    df["motivation"] = df["title"].apply(tag_motivation)
    return df.dropna(subset=["title", "date_posted"])

def calculate_score(row):
    if pd.isna(row.get('arv')) or pd.isna(row.get('equity')):
        return 0
    return (row['equity'] / row['arv']) * 100 + row['arv'] / 1000

def tag_motivation(text):
    tags = ["vacant", "divorce", "fire", "urgent"]
    return ", ".join([t for t in tags if t in str(text).lower()])

# ───── Page Config & Styling ─────
st.set_page_config(page_title="Savory Realty Investments", page_icon="🏘️", layout="wide")

def _get_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

bg = _get_base64("logo.png")
st.markdown(f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: linear-gradient(rgba(0,0,0,0.6),rgba(0,0,0,0.6)), url('data:image/png;base64,{bg}');
  background-repeat: no-repeat;
  background-position: center;
  background-size: contain;
}}
</style>
""", unsafe_allow_html=True)

# ───── Sidebar & Navigation ─────
st.sidebar.image("logo.png", width=48)
st.sidebar.title("Savory Realty Investments")
page = st.sidebar.radio("Navigate to:", [
    "Live Leads",
    "PropStream Leads",
    "Leads Dashboard",
    "Upload Leads",
    "Deal Tools",
    "Settings"
])

# ───── Live Leads ─────
if page == "Live Leads":
    st.header("📬 Live Leads")
    df = get_craigslist_data()
    if df.empty:
        st.warning("No leads found.")
        st.stop()
    df["Hot"] = df.get("hot_lead", False).map({True: "🔥", False: ""})
    df["Map"] = df.apply(lambda r: f"https://www.google.com/maps?q={r.latitude},{r.longitude}" if pd.notna(r.latitude) else None, axis=1)
    df["Street View"] = df.get("street_view_url", "")
    df["Link"] = df.get("link", "").map(lambda u: f"[View Post]({u})" if u else "")
    to_del = st.multiselect("Delete Craigslist IDs:", df["id"])
    if st.button("🗑️ Delete Selected") and to_del:
        supabase.table("craigslist_leads").delete().in_("id", to_del).execute()
        st.success("Deleted selected.")
    if st.button("🗑️ Delete ALL"):
        supabase.table("craigslist_leads").delete().neq("id", "").execute()
        st.success("Cleared all.")
    st.dataframe(df[["id", "date_posted", "title", "price", "arv", "score", "motivation", "Hot", "Map", "Street View", "Link"]], use_container_width=True, height=500)

# ───── PropStream Leads ─────
elif page == "PropStream Leads":
    st.header("📥 PropStream Leads")
    df = get_propstream_data()
    if df.empty:
        st.warning("No PropStream leads.")
        st.stop()
    df["Hot"] = df.get("hot_lead", False).map({True: "🔥", False: ""})
    sel = st.multiselect("Delete PropStream IDs:", df["id"])
    if st.button("🗑️ Delete Selected PropStream") and sel:
        supabase.table("propstream_leads").delete().in_("id", sel).execute()
        st.success("Deleted selected.")
    if st.button("🧹 Delete ALL PropStream"):
        supabase.table("propstream_leads").delete().neq("id", "").execute()
        st.success("Cleared all.")
    df["Map"] = df.apply(lambda r: f"https://www.google.com/maps?q={r.latitude},{r.longitude}" if pd.notna(r.latitude) else None, axis=1)
    df["Street View"] = df.get("street_view_url", "")
    st.dataframe(df[["id", "date_posted", "title", "price", "arv", "category", "score", "motivation", "Hot", "Map", "Street View"]], use_container_width=True, height=500)

# ───── Leads Dashboard ─────
elif page == "Leads Dashboard":
    st.header("📊 Leads Dashboard")
    df = get_propstream_data()
    if df.empty:
        st.warning("No data available.")
        st.stop()
    df["equity"] = df["arv"] - df["price"]
    df["hot_lead"] = (df["equity"] / df["arv"] >= 0.25) & (df["arv"] >= 100000) & (df["equity"] >= 30000)
    categories = sorted(df["category"].dropna().unique().tolist())
    chosen = st.multiselect("Filter categories:", categories, default=categories)
    df = df[df["category"].isin(chosen)]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Leads", len(df))
    c2.metric("Avg Price", f"${df['price'].mean():,.0f}")
    c3.metric("Avg ARV", f"${df['arv'].mean():,.0f}")
    c4.metric("Hot Leads", int(df['hot_lead'].sum()))
    if st.checkbox("Show chart"):
        chart = alt.Chart(df).mark_line(point=True).encode(
            x="date_posted:T", y="price:Q",
            color=alt.condition("datum.hot_lead", alt.value("red"), alt.value("green"))
        ).properties(width=800)
        st.altair_chart(chart)
    if {"latitude", "longitude"}.issubset(df.columns):
        dfm = df.dropna(subset=["latitude", "longitude"])
        view = pdk.ViewState(latitude=dfm.latitude.mean(), longitude=dfm.longitude.mean(), zoom=11)
        layer = pdk.Layer("ScatterplotLayer", data=dfm, get_position=["longitude","latitude"], radiusScale=10)
        st.pydeck_chart(pdk.Deck(initial_view_state=view, layers=[layer]))

# ───── Upload Leads ─────
elif page == "Upload Leads":
    st.header("📤 Upload PropStream Leads")
    zf = st.sidebar.text_input("ZIP filter:", "")
    cf = st.sidebar.text_input("City filter:", "")
    im = st.sidebar.checkbox("🔗 Map & Street View", False)
    ae = st.sidebar.checkbox("✉️ Email Alert", False)
    asms = st.sidebar.checkbox("📱 SMS Alert", False)
    file = st.file_uploader("CSV", type=["csv"])
    if file:
        dfc = pd.read_csv(file)
        dfc.rename(columns={
            "Property Address":"address",
            "City":"city",
            "State":"state",
            "Zip Code":"zip",
            "Amount Owed":"price",
            "Estimated Value":"arv"
        }, inplace=True)
        if zf:
            dfc = dfc[dfc["zip"].astype(str).isin(zf.split(","))]
        if cf:
            dfc = dfc[dfc["city"].str.lower() == cf.lower()]
        dfc["equity"] = dfc["arv"] - dfc["price"]
        dfc["hot_lead"] = dfc["equity"] / dfc["arv"] >= 0.25
        records = dfc.to_dict("records")
        for i in range(0, len(records), 1000):
            supabase.table("propstream_leads").upsert(records[i:i+1000]).execute()
        st.success(f"Uploaded {len(records)} leads; {int(dfc['hot_lead'].sum())} hot.")
        if im:
            dfc["Map"] = dfc.apply(lambda r: f"https://www.google.com/maps?q={r.latitude},{r.longitude}" if hasattr(r, 'latitude') else None, axis=1)
            dfc["Street View"] = dfc.get("street_view_url", "")
        st.dataframe(dfc.head(10), use_container_width=True)
        if ae:
            st.write("✉️ Email alert stub sent.")
        if asms:
            st.write("📱 SMS alert stub sent.")
        updf = get_propstream_data()
        del_ids = st.multiselect("Delete uploaded IDs:", updf["id"].tolist())
        if st.button("🗑️ Delete Selected PropStream") and del_ids:
            supabase.table("propstream_leads").delete().in_("id", del_ids).execute()
            st.success("Deleted selected.")

# ───── Deal Tools ─────
elif page == "Deal Tools":
    st.header("🧮 Deal Tools & Contracts")
    st.subheader("🔢 Offer Calculator (MAO)")
    arv = st.number_input("ARV", min_value=0.0, value=150000.0)
    repairs = st.number_input("Repair Costs", min_value=0.0, value=30000.0)
    offer_pct = st.slider("Offer % of ARV", 0.0, 1.0, 0.7)
    mao = (arv * offer_pct) - repairs
    st.metric("MAO", f"${mao:,.2f}")

    st.subheader("📄 Real Estate Assignment Contract")
    seller = st.text_input("Assignor Name")
    seller_addr = st.text_input("Assignor Address")
    assignee = st.text_input("Assignee Name")
    assignee_addr = st.text_input("Assignee Address")
    orig_date = st.date_input("Original Agreement Date")
    prop_addr = st.text_input("Property Address")
    effective_date = st.date_input("Effective Date", datetime.utcnow().date())
    consideration = st.text_area("Consideration Description", value="Assignment Fee of $XXXX or other good and valuable consideration.")
    if st.button("Generate Assignment Contract PDF") and FPDF:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "REAL ESTATE ASSIGNMENT CONTRACT", ln=True, align="C")
        pdf.ln(5)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 6, f"1. THE PARTIES. This Real Estate Assignment Contract (\"Assignment\") is entered into on {effective_date.strftime('%m/%d/%Y')} (\"Effective Date\"), by and between:\nAssignor: {seller} (\"Assignor\") with a mailing address of {seller_addr}; and Assignee: {assignee} (\"Assignee\") with a mailing address of {assignee_addr}.\nThe Parties are each referred to herein as a \"Party\" and collectively as the \"Parties.\"")
        pdf.ln(2)
        pdf.multi_cell(0, 6, f"2. ORIGINAL AGREEMENT. The Assignor is the purchasing party to that certain purchase and sale agreement, dated {orig_date.strftime('%m/%d/%Y')}, for the real property located at {prop_addr}, as more particularly described therein (\"Original Agreement\").")
        pdf.ln(2)
        pdf.multi_cell(0, 6, "3. ASSIGNMENT. The Assignor hereby transfers all rights and obligations under the Original Agreement to the Assignee on the Effective Date, pursuant to its terms.")
        pdf.ln(2)
        pdf.multi_cell(0, 6, f"4. CONSIDERATION. For the sum of {consideration}, the receipt and sufficiency of which are acknowledged, the Parties agree to the terms set forth herein.")
        pdf.ln(2)
        pdf.multi_cell(0, 6, "5. ASSUMPTION. By executing this Assignment, the Assignee accepts and assumes all liabilities, obligations, and claims under the Original Agreement.")
        pdf.ln(2)
        pdf.multi_cell(0, 6, "6. REPRESENTATIONS. The Assignor warrants that the Original Agreement is valid, in full force, and assignable. Written consent of the selling party (if required) shall be attached.")
        pdf.ln(2)
        for clause in [
            "7. Assignee shall indemnify and hold Assignor harmless from liabilities arising post-assignment.",
            "8. This Assignment terminates if the Original Agreement is terminated or voided.",
            "9. Neither Party is liable for delays due to force majeure events.",
            "10. Both Parties acknowledge the opportunity to consult legal counsel prior to signing."
        ]:
            pdf.multi_cell(0, 6, clause)
        pdf.ln(10)
        pdf.cell(0, 8, f"Assignor Signature: ___________________  Date: {effective_date.strftime('%m/%d/%Y')}", ln=True)
        pdf.cell(0, 8, f"Print Name: {seller}", ln=True)
        pdf.ln(5)
        pdf.cell(0, 8, f"Assignee Signature: ___________________  Date: {effective_date.strftime('%m/%d/%Y')}", ln=True)
        pdf.cell(0, 8, f"Print Name: {assignee}", ln=True)
        data = pdf.output(dest='S').encode('latin-1')
        buf = BytesIO(data)
        buf.seek(0)
        st.download_button("📄 Download Assignment Contract", data=buf, file_name="assignment_contract.pdf", mime="application/pdf")

    st.subheader("📌 Lead Status Tracker")
    lid = st.text_input("Lead ID to update:")
    new_status = st.selectbox("Update Status To:", ["New","Contacted","Warm","Offer Sent","Under Contract"])
    if st.button("✅ Update Status"):
        if lid:
            supabase.table("propstream_leads").update({"status": new_status}).eq("id", lid).execute()
            st.success(f"Lead {lid} set to {new_status}.")
        else:
            st.warning("Enter a valid Lead ID.")

    st.subheader("📊 Today's Offer Metrics")
    offers_sent = 0
    st.write(f"Offers sent today: {offers_sent}")

# ───── Settings ─────
else:
    st.header("Settings")
    st.markdown("""
    • Supabase tables: craigslist_leads, propstream_leads  
    • Required schema: id, title, link, date_posted, price, arv, equity, hot_lead, category, address, city, state, zip, map_link, street_view_link, latitude, longitude, status
    """)
