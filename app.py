import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from supabase import create_client, Client
from bs4 import BeautifulSoup
import time
import logging
import smtplib
from email.mime.text import MIMEText
import schedule
import threading

# ───────────────────────────────────────────────────────────
# Email Setup
# ───────────────────────────────────────────────────────────
EMAIL_SENDER = "Perkal1992@gmail.com"
EMAIL_PASSWORD = "your_app_password"
EMAIL_RECEIVER = "Perkal1992@gmail.com"

# ───────────────────────────────────────────────────────────
# Configuration (inline credentials)
SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
GOOGLE_MAPS_API_KEY = "AIzaSyDg-FHCdEFxZCZTy4WUmRryHmDdLto8Ezw"
RAPIDAPI_KEY = "88a3a41f80msh37d91f3065ad897p19f149jsnab96bb20afbc"
ZILLOW_COMP_API = "https://zillow-com1.p.rapidapi.com/propertyExtendedSearch"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ───────────────────────────────────────────────────────────
# Hot Lead Filter (price < $200,000)
# ───────────────────────────────────────────────────────────
def is_hot_lead(lead):
    try:
        return lead.get("price") and int(lead["price"]) < 200000
    except:
        return False

# ───────────────────────────────────────────────────────────
# ARV Estimator using Zillow comps (basic average of nearby solds)
# ───────────────────────────────────────────────────────────
def estimate_arv(address):
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com",
    }
    params = {
        "location": address,
        "status_type": "recently_sold",
        "home_type": "Houses",
        "sort": "sold_date",
        "limit": 10
    }
    try:
        r = requests.get(ZILLOW_COMP_API, headers=headers, params=params)
        if r.status_code != 200:
            return None
        comps = r.json().get("props", [])
        sold_prices = [c.get("price") for c in comps if c.get("price")]
        if not sold_prices:
            return None
        return int(sum(sold_prices) / len(sold_prices))
    except:
        return None

# ───────────────────────────────────────────────────────────
# Email Notification
# ───────────────────────────────────────────────────────────
def send_email(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("✅ Email sent")
    except Exception as e:
        print(f"❌ Email failed: {e}")

# ───────────────────────────────────────────────────────────
# Modified run_all_scrapers with ARV + hot lead filter + email
# ───────────────────────────────────────────────────────────
def run_all_scrapers():
    all_leads = []
    hot_leads = []
    for func in [scrape_zillow, scrape_craigslist, scrape_redfin, scrape_realtor]:
        try:
            leads = func()
            for lead in leads:
                arv = estimate_arv(lead.get("address", ""))
                if arv:
                    lead["arv"] = arv
                push_to_supabase(lead)
                all_leads.append(lead)
                if is_hot_lead(lead):
                    hot_leads.append(lead)
        except Exception as e:
            st.error(f"❌ {func.__name__} failed: {e}")
    # Only send email if hot leads exist
    if hot_leads:
        lines = [f"{l['address']} - ${l['price']} ARV: ${l.get('arv', 'N/A')} ({l['source']})" for l in hot_leads]
        body = "\n".join(lines)
        send_email("🔥 Hot Leads Found", body)
    return all_leads

# ───────────────────────────────────────────────────────────
# Background Scheduler
# ───────────────────────────────────────────────────────────
def run_background():
    schedule.every(30).minutes.do(run_all_scrapers)
    while True:
        schedule.run_pending()
        time.sleep(1)

threading.Thread(target=run_background, daemon=True).start()

# ───────────────────────────────────────────────────────────
# Streamlit UI & Dashboard
# ───────────────────────────────────────────────────────────
st.set_page_config(page_title="Savory Realty Engine", layout="wide")

st.markdown("""
<style>
body { background-color: #001F1F !important; color: #d9ffcc !important; }
.stApp { background-color: #001F1F !important; }
[data-testid="stHeader"] { background-color: #003333; color: #d9ffcc; }
.stButton > button { background-color: #00ff00 !important; color: #000000 !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("💚 Savory Realty Lead Engine")
st.markdown("Pulling fresh leads across Dallas–Fort Worth. ARV estimates included. 🔥")

tabs = st.tabs(["📁 Upload CSV", "🔄 Scrape Now", "📊 View Leads"])

with tabs[0]:
    csv_file = st.file_uploader("Upload CSV of Property Leads", type="csv")
    if csv_file:
        df = pd.read_csv(csv_file)
        df["Latitude"], df["Longitude"] = zip(*df["Address"].map(lambda a: geocode_address(a)))
        df["ARV"] = df["Address"].map(lambda a: estimate_arv(a))
        st.dataframe(df)
        for _, row in df.iterrows():
            record = {
                "source": "CSV Upload",
                "address": row["Address"],
                "latitude": row.Latitude,
                "longitude": row.Longitude,
                "price": row.get("Price", None),
                "arv": row.get("ARV"),
                "created_at": datetime.utcnow().isoformat(),
            }
            push_to_supabase(record)
        st.success("✅ CSV uploaded, enriched, and leads pushed.")

with tabs[1]:
    if st.button("Run DFW Scrapers (All Sources)"):
        with st.spinner("Scraping..."):
            new_leads = run_all_scrapers()
            st.success(f"✅ {len(new_leads)} leads scraped & pushed.")

with tabs[2]:
    st.subheader("📊 Live Lead Feed (latest 100)")
    data = supabase.table("leads").select("*").order("created_at", desc=True).limit(100).execute()
    df = pd.DataFrame(data.data or [])
    if not df.empty:
        df = df[["address", "price", "arv", "latitude", "longitude", "source", "created_at"]]
        st.dataframe(df)
    else:
        st.info("No leads yet – upload CSV or run scraper.")
