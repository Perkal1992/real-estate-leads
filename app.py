import os
import base64
from datetime import datetime
import numpy as np
import streamlit as st
import pandas as pd
import altair as alt
import pydeck as pdk
from io import BytesIO
from postgrest.exceptions import APIError

# Attempt to import FPDF for PDF generation
try:
    from fpdf import FPDF
except ImportError:
    st.error("`fpdf` module not found. Please add `fpdf` to your `requirements.txt` and redeploy.")
    FPDF = None

# Initialize Supabase client
from supabase import create_client
SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "YOUR_SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Helper to calculate lead score

def calculate_score(row):
    arv = row.get("arv", 0)
    equity = row.get("equity", 0)
    if arv <= 0 or equity <= 0:
        return 0
    return (equity / arv) * 100 + (arv / 1000)

# Helper to tag motivation keywords

def tag_motivation(text):
    tags = ["vacant", "divorce", "fire", "urgent"]
    text_lower = str(text).lower()
    matched = [t for t in tags if t in text_lower]
    return ", ".join(matched)

# ---------------------------------
# Data Fetching Functions
# ---------------------------------

@st.cache_data(ttl=300)
def get_craigslist_data():
    # Fetch data from Supabase
    resp = supabase.table("craigslist_leads").select("*").order("date_posted", desc=True).execute()
    df = pd.DataFrame(resp.data or [])

    # If empty return early
    if df.empty:
        return df

    # Ensure numeric columns exist
    for col in ["price", "arv", "equity"]:
        if col not in df.columns:
            df[col] = 0

    # Replace infinities and missing
    df = df.replace([np.inf, -np.inf], np.nan)
    df["date_posted"] = pd.to_datetime(df.get("date_posted"), errors="coerce")

    # Coerce numeric columns
    for col in ["price", "arv", "equity"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Fill title
    df["title"] = df.get("title", "").fillna("")

    # Compute additional fields
    df["score"] = df.apply(calculate_score, axis=1)
    df["motivation"] = df["title"].apply(tag_motivation)

    # Drop rows missing essentials
    return df.dropna(subset=["title", "date_posted"])

@st.cache_data(ttl=300)
def get_propstream_data():
    resp = supabase.table("propstream_leads").select("*").order("date_posted", desc=True).execute()
    df = pd.DataFrame(resp.data or [])

    if df.empty:
        return df

    # Ensure required columns
    for col in ["price", "arv", "equity", "category"]:
        if col not in df.columns:
            df[col] = 0 if col != "category" else ""

    df = df.replace([np.inf, -np.inf], np.nan)
    df["date_posted"] = pd.to_datetime(df.get("date_posted"), errors="coerce")

    for col in ["price", "arv", "equity"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["title"] = df.get("title", "").fillna("")
    df["score"] = df.apply(calculate_score, axis=1)
    df["motivation"] = df["title"].apply(tag_motivation)

    return df.dropna(subset=["title", "date_posted"])

# ---------------------------------
# Streamlit Page Setup
# ---------------------------------

st.set_page_config(page_title="Savory Realty Investments", page_icon="🏘️", layout="wide")

# Load background image

def _get_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

bg = _get_base64("logo.png")
st.markdown(
    f"""
    <style>
    [data-testid="stAppViewContainer"] {{
      background-image: linear-gradient(rgba(0,0,0,0.6), rgba(0,0,0,0.6)), url('data:image/png;base64,{bg}');
      background-repeat: no-repeat;
      background-position: center;
      background-size: contain;
    }}
    </style>
    """, unsafe_allow_html=True
)

# Sidebar navigation
nst.image("logo.png", width=48)
st.sidebar.title("Savory Realty Investments")
page = st.sidebar.radio(
    "Navigate to:",
    [
        "Live Leads",
        "PropStream Leads",
        "Leads Dashboard",
        "Upload Leads",
        "Deal Tools",
        "Settings",
    ],
)

# ---------------------------------
# Live Leads Page
# ---------------------------------
if page == "Live Leads":
    st.header("📬 Live Leads")
    df = get_craigslist_data()
    if df.empty:
        st.warning("No leads found.")
        st.stop()

    # Format markers
    df["Hot"] = df.get("hot_lead", False).map({True: "🔥", False: ""})
    df["Map"] = df.apply(
        lambda r: f"https://www.google.com/maps?q={r.latitude},{r.longitude}" if pd.notna(r.latitude) else None,
        axis=1,
    )
    df["Street View"] = df.get("street_view_url", "")
    df["Link"] = df.get("link", "").map(lambda u: f"[View Post]({u})" if u else "")

    # Deletion controls
    to_delete = st.multiselect("Delete Craigslist IDs:", df["id"].tolist())
    if st.button("🗑️ Delete Selected") and to_delete:
        supabase.table("craigslist_leads").delete().in_("id", to_delete).execute()
        st.success("Deleted selected.")
    if st.button("🗑️ Delete All"):
        supabase.table("craigslist_leads").delete().neq("id", "").execute()
        st.success("Cleared all.")

    # Display
    st.dataframe(
        df[
            [
                "id",
                "date_posted",
                "title",
                "price",
                "arv",
                "score",
                "motivation",
                "Hot",
                "Map",
                "Street View",
                "Link",
            ]
        ],
        use_container_width=True,
        height=600,
    )

# ---------------------------------
# PropStream Leads Page
# ---------------------------------
elif page == "PropStream Leads":
    st.header("📥 PropStream Leads")
    df = get_propstream_data()
    if df.empty:
        st.warning("No PropStream leads.")
        st.stop()

    df["Hot"] = df.get("hot_lead", False).map({True: "🔥", False: ""})
    sel = st.multiselect("Delete PropStream IDs:", df["id"].tolist())
    if st.button("🗑️ Delete Selected") and sel:
        supabase.table("propstream_leads").delete().in_("id", sel).execute()
        st.success("Deleted selected.")
    if st.button("🧹 Delete All"):
        supabase.table("propstream_leads").delete().neq("id", "").execute()
        st.success("Cleared all.")

    df["Map"] = df.apply(
        lambda r: f"https://www.google.com/maps?q={r.latitude},{r.longitude}" if pd.notna(r.latitude) else None,
        axis=1,
    )
    df["Street View"] = df.get("street_view_url", "")

    st.dataframe(
        df[
            ["id", "date_posted", "title", "price", "arv", "category", "score", "motivation", "Hot", "Map", "Street View"]
        ],
        use_container_width=True,
        height=600,
    )

# ---------------------------------
# Leads Dashboard
# ---------------------------------
elif page == "Leads Dashboard":
    st.header("📊 Leads Dashboard")
    show_cr = st.sidebar.checkbox("Show Craigslist Leads", value=False)
    show_ps = st.sidebar.checkbox("Show PropStream Leads", value=True)

    dfs = []
    if show_cr:
        df_cr = get_craigslist_data()
        df_cr["source"] = "Craigslist"
        dfs.append(df_cr)

    if show_ps:
        df_ps = get_propstream_data()
        df_ps["source"] = "PropStream"
        dfs.append(df_ps)

    if not dfs:
        st.warning("Pick at least one source.")
        st.stop()

    combined = pd.concat(dfs, ignore_index=True)

    # Ensure numeric columns
    for col in ["price", "arv", "equity"]:
        if col not in combined.columns:
            combined[col] = 0

    combined = combined.replace([np.inf, -np.inf], np.nan).fillna({"price": 0, "arv": 0, "equity": 0})
    combined["equity"] = combined["arv"] - combined["price"]
    combined["hot_lead"] = (
        (combined["equity"] / combined["arv"] >= 0.25) &
        (combined["arv"] >= 100000) &
        (combined["equity"] >= 30000)
    )

    if "category" in combined.columns:
        cats = sorted(combined[combined["source"] == "PropStream"]["category"].dropna().unique())
        chosen = st.multiselect("Filter PropStream categories:", cats, default=cats)
        combined = combined[~((combined["source"] == "PropStream") & (~combined["category"].isin(chosen)))]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Leads", len(combined))
    c2.metric("Avg Price", f"${combined['price'].mean():,.0f}")
    c3.metric("Avg ARV", f"${combined['arv'].mean():,.0f}")
    c4.metric("Hot Leads", int(combined['hot_lead'].sum()))

    if st.checkbox("Show Price over Time"):
        chart = alt.Chart(combined).mark_line(point=True).encode(
            x="date_posted:T",
            y="price:Q",
            color="source:N",
            tooltip=["source", "title", "price", "arv", "equity"],
        ).properties(width=800)
        st.altair_chart(chart)

    if {"latitude", "longitude"}.issubset(combined.columns):
        dfm = combined.dropna(subset=["latitude", "longitude"])
        view = pdk.ViewState(
            latitude=dfm.latitude.mean(),
            longitude=dfm.longitude.mean(),
            zoom=11,
        )
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=dfm,
            get_position=["longitude", "latitude"],
            radiusScale=10,
            get_fill_color="datum.source=='Craigslist' ? [255,0,0] : [0,128,0]",
        )
        st.pydeck_chart(pdk.Deck(initial_view_state=view, layers=[layer]))

# ---------------------------------
# Upload Leads
# ---------------------------------
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
        dfc.rename(
            columns={
                "Property Address": "address",
                "City": "city",
                "State": "state",
                "Zip Code": "zip",
                "Amount Owed": "price",
                "Estimated Value": "arv",
            },
            inplace=True,
        )

        # Sanitize numeric columns
        dfc = dfc.replace([np.inf, -np.inf], np.nan)
        dfc["arv"] = pd.to_numeric(dfc.get("arv"), errors="coerce").fillna(0)
        dfc["price"] = pd.to_numeric(dfc.get("price"), errors="coerce").fillna(0)

        # Apply filters
        if zf:
            dfc = dfc[dfc["zip"].astype(str).isin(zf.split(","))]
        if cf:
            dfc = dfc[dfc["city"].str.lower() == cf.lower()]

        # Compute equity and hot flag
        dfc["equity"] = dfc["arv"] - dfc["price"]
        dfc["hot_lead"] = (dfc["equity"] / dfc["arv"].replace({0: np.nan})) >= 0.25
        dfc["hot_lead"] = dfc["hot_lead"].fillna(False)

        # Clean and upsert records
        raw_records = dfc.to_dict("records")
        clean_records = []
        for rec in raw_records:
            cleaned = {}
            for key, val in rec.items():
                if isinstance(val, (np.generic,)):
                    cleaned[key] = val.item()
                else:
                    cleaned[key] = val
                if isinstance(cleaned[key], float) and (np.isnan(cleaned[key]) or np.isinf(cleaned[key])):
                    cleaned[key] = None
            clean_records.append(cleaned)

        for i in range(0, len(clean_records), 1000):
            supabase.table("propstream_leads").upsert(clean_records[i:i+1000]).execute()

        st.success(f"Uploaded {len(clean_records)} leads; {int(dfc['hot_lead'].sum())} hot.")

        if im:
            dfc["Map"] = dfc.apply(
                lambda r: f"https://www.google.com/maps?q={r.latitude},{r.longitude}" if hasattr(r, "latitude") else None,
                axis=1,
            )
            dfc["Street View"] = dfc.get("street_view_url", "")

        st.dataframe(dfc.head(10), use_container_width=True)

        if ae:
            st.write("✉️ Email alert stub sent.")
        if asms:
            st.write("📱 SMS alert stub sent.")

# ---------------------------------
# Deal Tools & Status Tracker
# ---------------------------------
elif page == "Deal Tools":
    st.header("🧮 Deal Tools & Contracts")

    # Offer Calculator
    st.subheader("🔢 Offer Calculator (MAO)")
    arv_val = st.number_input("ARV", min_value=0.0, value=150000.0)
    repairs_val = st.number_input("Repair Costs", min_value=0.0, value=30000.0)
    offer_pct = st.slider("Offer % of ARV", 0.0, 1.0, 0.7)
    mao = (arv_val * offer_pct) - repairs_val
    st.metric("MAO", f"${mao:,.2f}")

    # Assignment Contract Generator
    st.subheader("📄 Real Estate Assignment Contract")
    assignor = st.text_input("Assignor Name")
    assignor_addr = st.text_input("Assignor Address")
    assignee_name = st.text_input("Assignee Name")
    assignee_addr = st.text_input("Assignee Address")
    original_date = st.date_input("Original Agreement Date")
    property_addr = st.text_input("Property Address")
    effective_date = st.date_input("Effective Date", datetime.utcnow().date())
    consideration_text = st.text_area(
        "Consideration Description", value="Assignment Fee of $XXXX or other good and valuable consideration."
    )

    if st.button("Generate Assignment Contract PDF") and FPDF:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "REAL ESTATE ASSIGNMENT CONTRACT", ln=True, align="C")
        pdf.ln(5)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(
            0,
            6,
            f"1. THE PARTIES: This Assignment is entered into on {effective_date.strftime('%m/%d/%Y')} by {assignor} (Assignor) of {assignor_addr}, and {assignee_name} (Assignee) of {assignee_addr}.",
        )
        pdf.ln(4)
        pdf.multi_cell(
            0,
            6,
            f"2. ORIGINAL AGREEMENT: Assignor is the purchasing party to that certain agreement dated {original_date.strftime('%m/%d/%Y')} for property at {property_addr}.",
        )
        pdf.ln(4)
        pdf.multi_cell(
            0,
            6,
            f"3. ASSIGNMENT: Assignor transfers all rights and obligations of the original agreement to Assignee as of {effective_date.strftime('%m/%d/%Y')}.",
        )
        pdf.ln(4)
        pdf.multi_cell(
            0,
            6,
            f"4. CONSIDERATION: {consideration_text}",
        )
        pdf.ln(10)
        pdf.cell(0, 8, f"Assignor Signature: ___________________  Date: {effective_date.strftime('%m/%d/%Y')}", ln=True)
        pdf.cell(0, 8, f"Assignee Signature: ___________________  Date: {effective_date.strftime('%m/%d/%Y')}", ln=True)
        buffer = BytesIO(pdf.output(dest='S').encode('latin-1'))
        buffer.seek(0)
        st.download_button(
            "📄 Download Assignment Contract",
            data=buffer,
            file_name="assignment_contract.pdf",
            mime="application/pdf",
        )

    # Lead Status Tracker
    st.subheader("📌 Lead Status Tracker")
    lead_id_input = st.text_input("Lead ID to update:")
    new_status_option = st.selectbox("Update Status To:", ["New", "Contacted", "Warm", "Offer Sent", "Under Contract"])
    if st.button("✅ Update Status"):
        try:
            supabase.table("propstream_leads").update({"status": new_status_option}).eq("id", lead_id_input).execute()
            st.success(f"Lead {lead_id_input} set to {new_status_option}.")
        except APIError as ex:
            st.error(f"Could not update status: {ex}")

    # Today's Offer Metrics
    st.subheader("📊 Today's Offer Metrics")
    offers_sent = 0  # Placeholder: Replace with real data source
    st.write(f"Offers sent today: {offers_sent}")

else:
    st.header("Settings")
    st.markdown(
        """
        • Supabase tables: craigslist_leads, propstream_leads  
        • Required schema for PropStream: id, title, link, date_posted, price, arv, equity, hot_lead, category, address, city, state, zip, latitude, longitude
        """
    )
