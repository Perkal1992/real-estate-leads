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

# ───── Page config MUST be first Streamlit call ─────
st.set_page_config(
    page_title="Savory Realty Investments",
    page_icon="🏘️",
    layout="wide",
)

def summary_dashboard(df: pd.DataFrame):
    st.header("📊 Summary Dashboard")
    
    # Compute metrics
    total_leads = len(df)
    avg_equity_pct = df["Equity%"].mean()
    avg_est_value = df["Estimated Value"].mean()
    
    # Display KPIs
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Total Leads", f"{total_leads}")
    kpi2.metric("Avg Equity %", f"{avg_equity_pct:.1f}%")
    kpi3.metric("Avg Est. Value", f"${avg_est_value:,.0f}")
    
    st.markdown("---")
    
    # Leads by ZIP Code
    zip_counts = df.groupby("Zip Code").size().reset_index(name="Count")
    bar = (
        alt.Chart(zip_counts)
           .mark_bar()
           .encode(
               x=alt.X("Zip Code:O", title="ZIP Code"),
               y=alt.Y("Count:Q", title="Lead Count")
           )
           .properties(title="Leads by ZIP Code")
    )
    st.altair_chart(bar, use_container_width=True)
    
    st.markdown("---")
    
    # Equity% distribution
    hist = (
        alt.Chart(df)
           .mark_bar()
           .encode(
               alt.X("Equity%:Q", bin=alt.Bin(maxbins=30), title="Equity %"),
               y="count()"
           )
           .properties(title="Equity % Distribution")
    )
    st.altair_chart(hist, use_container_width=True)

# --- Demo nav for summary dashboard ---
st.sidebar.title("Navigation")
demo_page = st.sidebar.radio("Go to", [
    "Upload CSV",
    "Summary Dashboard",
    "Qualified Leads",
    "Top 50 Leads",
    "Downloads"
])

if demo_page == "Upload CSV":
    uploaded = st.file_uploader("Upload PropStream CSV", type=["csv"])
    if uploaded:
        df = pd.read_csv(uploaded)
        df["Equity"] = df["Estimated Value"] - df["Amount Owed"]
        df["Equity%"] = df["Equity"] / df["Estimated Value"] * 100
        st.success("CSV loaded!")
elif demo_page == "Summary Dashboard":
    if "df" in locals():
        summary_dashboard(df)
    else:
        st.info("First upload your PropStream CSV on the “Upload CSV” tab.")

# ──────────────────────────────────────────────────────────────────────────────
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
    resp = supabase.table("craigslist_leads").select("*").order("date_posted", desc=True).execute()
    df = pd.DataFrame(resp.data or [])
    if df.empty:
        return df
    for col in ["price", "arv", "equity"]:
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0)
    df["date_posted"] = pd.to_datetime(df.get("date_posted"), errors="coerce")
    df["title"] = df.get("title", "").fillna("")
    df["score"] = df.apply(calculate_score, axis=1)
    df["motivation"] = df["title"].apply(tag_motivation)
    return df.dropna(subset=["title", "date_posted"])

@st.cache_data(ttl=300)
def get_propstream_data():
    resp = supabase.table("propstream_leads").select("*").order("date_posted", desc=True).execute()
    df = pd.DataFrame(resp.data or [])
    if df.empty:
        return df
    for col in ["price", "arv", "equity", "category"]:
        df[col] = df.get(col, 0 if col != "category" else "").fillna(0)
    df = df.replace([np.inf, -np.inf], np.nan)
    df["date_posted"] = pd.to_datetime(df.get("date_posted"), errors="coerce")
    for col in ["price", "arv", "equity"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["title"] = df.get("title", "").fillna("")
    df["score"] = df.apply(calculate_score, axis=1)
    df["motivation"] = df["title"].apply(tag_motivation)
    return df.dropna(subset=["title", "date_posted"])

# ---------------------------------
# Main Sidebar Navigation
# ---------------------------------
st.sidebar.image("logo.png", width=48)
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
    df["Hot"] = df.get("hot_lead", False).map({True: "🔥", False: ""})
    df["Map"] = df.apply(
        lambda r: f"https://www.google.com/maps?q={r.latitude},{r.longitude}" if pd.notna(r.latitude) else None,
        axis=1,
    )
    df["Street View"] = df.get("street_view_url", "")
    df["Link"] = df.get("link", "").map(lambda u: f"[View Post]({u})" if u else "")
    to_delete = st.multiselect("Delete Craigslist IDs:", df["id"].tolist())
    if st.button("🗑️ Delete Selected") and to_delete:
        supabase.table("craigslist_leads").delete().in_("id", to_delete).execute()
        st.success("Deleted selected.")
    if st.button("🗑️ Delete All"):
        supabase.table("craigslist_leads").delete().neq("id", "").execute()
        st.success("Cleared all.")
    st.dataframe(
        df[["id","date_posted","title","price","arv","score","motivation","Hot","Map","Street View","Link"]],
        use_container_width=True, height=600
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
    df["Hot"] = df.get("hot_lead", False).map({True:"🔥", False:""})
    sel = st.multiselect("Delete PropStream IDs:", df["id"].tolist())
    if st.button("🗑️ Delete Selected") and sel:
        supabase.table("propstream_leads").delete().in_("id", sel).execute()
        st.success("Deleted selected.")
    if st.button("🧹 Delete All"):
        supabase.table("propstream_leads").delete().neq("id","").execute()
        st.success("Cleared all.")
    df["Map"] = df.apply(
        lambda r: f"https://www.google.com/maps?q={r.latitude},{r.longitude}" if pd.notna(r.latitude) else None,
        axis=1,
    )
    df["Street View"] = df.get("street_view_url","")
    st.dataframe(
        df[["id","date_posted","title","price","arv","category","score","motivation","Hot","Map","Street View"]],
        use_container_width=True, height=600
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
        df_cr = get_craigslist_data(); df_cr["source"]="Craigslist"; dfs.append(df_cr)
    if show_ps:
        df_ps = get_propstream_data(); df_ps["source"]="PropStream"; dfs.append(df_ps)
    if not dfs:
        st.warning("Pick at least one source."); st.stop()
    combined = pd.concat(dfs, ignore_index=True)
    for col in ["price","arv","equity"]:
        combined[col] = pd.to_numeric(combined.get(col,0), errors="coerce").fillna(0)
    combined["equity"] = combined["arv"] - combined["price"]
    combined["hot_lead"] = (
        (combined["equity"]/combined["arv"] >= 0.25) &
        (combined["arv"] >= 100000) &
        (combined["equity"] >= 30000)
    )
    if "category" in combined.columns:
        cats = sorted(combined[combined["source"]=="PropStream"]["category"].dropna().unique())
        chosen = st.multiselect("Filter PropStream categories:", cats, default=cats)
        combined = combined[~((combined["source"]=="PropStream") & (~combined["category"].isin(chosen)))]
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total Leads", len(combined))
    c2.metric("Avg Price", f"${combined['price'].mean():,.0f}")
    c3.metric("Avg ARV", f"${combined['arv'].mean():,.0f}")
    c4.metric("Hot Leads", int(combined['hot_lead'].sum()))
    if st.checkbox("Show Price over Time"):
        chart = alt.Chart(combined).mark_line(point=True).encode(
            x="date_posted:T", y="price:Q", color="source:N",
            tooltip=["source","title","price","arv","equity"]
        ).properties(width=800)
        st.altair_chart(chart)
    if {"latitude","longitude"}.issubset(combined.columns):
        dfm = combined.dropna(subset=["latitude","longitude"])
        view = pdk.ViewState(latitude=dfm.latitude.mean(), longitude=dfm.longitude.mean(), zoom=11)
        layer = pdk.Layer("ScatterplotLayer", data=dfm,
                          get_position=["longitude","latitude"],
                          radiusScale=10,
                          get_fill_color="datum.source=='Craigslist' ? [255,0,0] : [0,128,0]")
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
        dfc.rename(columns={
            "Property Address":"address","City":"city","State":"state",
            "Zip Code":"zip","Amount Owed":"price","Estimated Value":"arv"
        }, inplace=True)
        dfc = dfc.replace([np.inf,-np.inf], np.nan)
        dfc["arv"] = pd.to_numeric(dfc["arv"], errors="coerce").fillna(0)
        dfc["price"] = pd.to_numeric(dfc["price"], errors="coerce").fillna(0)
        if zf:
            dfc = dfc[dfc["zip"].astype(str).isin(zf.split(","))]
        if cf:
            dfc = dfc[dfc["city"].str.lower()==cf.lower()]
        dfc["equity"] = dfc["arv"] - dfc["price"]
        dfc["hot_lead"] = (dfc["equity"]/dfc["arv"].replace({0:np.nan}))>=0.25
        dfc["hot_lead"] = dfc["hot_lead"].fillna(False)
        raw_records = dfc.to_dict("records")
        clean_records = []
        for rec in raw_records:
            clean = {}
            for k,v in rec.items():
                clean[k] = v.item() if isinstance(v, (np.generic,)) else v
                if isinstance(clean[k], float) and (np.isnan(clean[k]) or np.isinf(clean[k])):
                    clean[k] = None
            clean_records.append(clean)
        for i in range(0,len(clean_records),1000):
            supabase.table("propstream_leads").upsert(clean_records[i:i+1000]).execute()
        st.success(f"Uploaded {len(clean_records)} leads; {int(dfc['hot_lead'].sum())} hot.")
        if im:
            dfc["Map"] = dfc.apply(
                lambda r: f"https://www.google.com/maps?q={r.latitude},{r.longitude}"
                if hasattr(r,"latitude") else None, axis=1
            )
            dfc["Street View"] = dfc.get("street_view_url","")
        st.dataframe(dfc.head(10), use_container_width=True)
        if ae: st.write("✉️ Email alert stub sent.")
        if asms: st.write("📱 SMS alert stub sent.")

# ---------------------------------
# Deal Tools & Assignment Contract
# ---------------------------------
elif page == "Deal Tools":
    st.header("🧮 Deal Tools & Contracts")
    st.subheader("🔢 Offer Calculator (MAO)")
    arv_val = st.number_input("ARV", min_value=0.0, value=150000.0)
    repairs_val = st.number_input("Repair Costs", min_value=0.0, value=30000.0)
    offer_pct = st.slider("Offer % of ARV", 0.0, 1.0, 0.7)
    mao = (arv_val * offer_pct) - repairs_val
    st.metric("MAO", f"${mao:,.2f}")
    st.subheader("📄 Real Estate Assignment Contract")
    assignor = st.text_input("Assignor Name")
    assignor_addr = st.text_input("Assignor Address")
    assignee_name = st.text_input("Assignee Name")
    assignee_addr = st.text_input("Assignee Address")
    original_date = st.date_input("Original Agreement Date")
    property_addr = st.text_input("Property Address")
    effective_date = st.date_input("Effective Date", datetime.utcnow().date())
    consideration_text = st.text_area(
        "Consideration & Deposit Details:",
        value="Assignment Fee of $XXXX and Good Faith Deposit of $XXXX."
    )
    if st.button("Generate Assignment Contract PDF") and FPDF:
        pdf = FPDF()
        pdf.add_page()
        try: pdf.image("logo.png", 10, 8, 33)
        except: pass
        pdf.ln(25)
        pdf.set_font("Arial","B",14)
        pdf.cell(0,10,"REAL ESTATE ASSIGNMENT CONTRACT",ln=True, align="C")
        pdf.ln(5)
        pdf.set_font("Arial",size=12)
        clauses = [
            f"1. ORIGINAL AGREEMENT: Assignor is party to Purchase & Sale Agreement dated {original_date.strftime('%m/%d/%Y')} for {property_addr}.",
            f"2. ASSIGNMENT: Assignor assigns all rights under the Original Agreement to Assignee, effective {effective_date.strftime('%m/%d/%Y')}.",
            f"3. CONSIDERATION & DEPOSIT: {consideration_text}.",
            "4. DUE DILIGENCE: Assignee may inspect title, HOA docs, and property. Deposit refundable until inspection period end.",
            "5. CLOSING: Closing at agreed escrow/title agent no later than dates in Original Agreement.",
            "6. REPRESENTATIONS & WARRANTIES: Parties have authority; Original Agreement is assignable.",
            "7. COVENANTS & INDEMNIFICATION: Assignee assumes obligations and indemnifies Assignor for post-assignment liabilities.",
            "8. DEFAULT & REMEDIES: On Assignee default, Assignor may retain deposit or seek specific performance.",
            "9. NOTICES: Written notices to addresses above via certified mail or courier, effective upon receipt.",
            "10. CONFIDENTIALITY: Terms and identities confidential except as required.",
            "11. CHOICE OF LAW: Texas law governs; venue in Dallas County.",
            "12. ENTIRE AGREEMENT: This Assignment and Original Agreement (and amendments) are the entire agreement.",
            "13. SEVERABILITY: Invalid provisions do not affect remainder.",
            "14. COUNTERPARTS & ELECTRONIC SIGNATURES: Binding in counterparts with electronic signatures."
        ]
        for clause in clauses:
            pdf.multi_cell(0,6,clause); pdf.ln(2)
        pdf.ln(10)
        pdf.cell(0,8,f"Assignor: ________________________    Date: {effective_date.strftime('%m/%d/%Y')}", ln=True)
        pdf.cell(0,8,f"Assignee: ________________________    Date: {effective_date.strftime('%m/%d/%Y')}", ln=True)
        buffer = BytesIO(pdf.output(dest='S').encode('latin-1'))
        buffer.seek(0)
        st.download_button(
            "Download Assignment Contract PDF",
            data=buffer,
            file_name="assignment_contract.pdf",
            mime="application/pdf"
        )
    st.subheader("📌 Lead Status Tracker")
    lead_id_input = st.text_input("Lead ID to update:")
    new_status_option = st.selectbox(
        "Update Status To:",
        ["New","Contacted","Warm","Offer Sent","Under Contract"]
    )
    if st.button("✅ Update Status"):
        try:
            supabase.table("propstream_leads")\
                .update({"status": new_status_option})\
                .eq("id", lead_id_input)\
                .execute()
            st.success(f"Lead {lead_id_input} set to {new_status_option}.")
        except APIError as ex:
            st.error(f"Could not update status: {ex}")
    st.subheader("📊 Today's Offer Metrics")
    offers_sent = 0  # Placeholder
    st.write(f"Offers sent today: {offers_sent}")

# ---------------------------------
# Settings Page
# ---------------------------------
else:
    st.header("Settings")
    st.markdown("""
        • Supabase tables: craigslist_leads, propstream_leads  
        • Required schema for PropStream: id, title, link, date_posted, price, arv, equity, hot_lead, category, address, city, state, zip, latitude, longitude
    """)
