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
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB3a2JzenNsamxweGhsZmN2ZGVyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQzNDk4MDEsImV4cCI6MjA1OTkyNTgwMX0.bjVMzL4X6dN6xBx8tV3lT7XPsOFIEqMLv0pG3y6N-4o"
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
# Run All Scrapers with ARV & Hot Lead Email
# ───────────────────────────────────────────────────────────
def run_all_scrapers():
    all_leads = []
    hot_leads = []
    for func in [scrape_zillow, scrape_craigslist]:
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
            print(f"❌ {func.__name__} failed: {e}")
    if hot_leads:
        lines = [f"{l['address']} - ${l['price']} ARV: ${l.get('arv', 'N/A')} ({l['source']})" for l in hot_leads]
        body = "\n".join(lines)
        send_email("🔥 Hot Leads Found", body)
    return all_leads

# ───────────────────────────────────────────────────────────
# Background Scraper Runner (Every 30 minutes)
# ───────────────────────────────────────────────────────────
def run_background():
    schedule.every(30).minutes.do(run_all_scrapers)
    while True:
        schedule.run_pending()
        time.sleep(1)

threading.Thread(target=run_background, daemon=True).start()

# ───────────────────────────────────────────────────────────
# Geocoding Helper
# ───────────────────────────────────────────────────────────
def geocode_address(address):
    url = (
        "https://maps.googleapis.com/maps/api/geocode/json"
        f"?address={requests.utils.quote(address)}&key={GOOGLE_MAPS_API_KEY}"
    )
    r = requests.get(url)
    if not r.ok:
        return None, None
    results = r.json().get("results", [])
    if results:
        loc = results[0]["geometry"]["location"]
        return loc["lat"], loc["lng"]
    return None, None

# ───────────────────────────────────────────────────────────
# Push to Supabase
# ───────────────────────────────────────────────────────────
def push_to_supabase(record):
    try:
        supabase.table("leads").insert(record).execute()
    except Exception as e:
        print(f"❌ Failed to push lead: {e}")

# ───────────────────────────────────────────────────────────
# Scraper: Zillow RapidAPI
# ───────────────────────────────────────────────────────────
def scrape_zillow():
    endpoint = "https://zillow-com1.p.rapidapi.com/propertyListings"
    headers = {
        "x-rapidapi-host": "zillow-com1.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY,
    }
    leads = []
    for zip_code in ["75201", "75001", "75006", "75019"]:
        params = {
            "propertyStatus": "FOR_SALE",
            "homeType": ["Houses"],
            "sort": "Newest",
            "limit": 20,
            "zip": zip_code,
        }
        r = requests.get(endpoint, headers=headers, params=params)
        if r.ok:
            for item in r.json().get("props", []):
                addr = item.get("address")
                price = item.get("price")
                lat, lng = geocode_address(addr)
                if addr and lat and lng:
                    leads.append({
                        "source": "Zillow",
                        "address": addr,
                        "latitude": lat,
                        "longitude": lng,
                        "price": price,
                        "created_at": datetime.utcnow().isoformat(),
                    })
    return leads

# ───────────────────────────────────────────────────────────
# Scraper: Craigslist Dallas
# ───────────────────────────────────────────────────────────
def scrape_craigslist():
    url = "https://dallas.craigslist.org/search/rea"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    leads = []
    if r.ok:
        soup = BeautifulSoup(r.text, "html.parser")
        for post in soup.select("li.result-row")[:20]:
            title = post.select_one("a.result-title")
            if not title:
                continue
            addr = title.get_text(strip=True)
            lat, lng = geocode_address(addr)
            if lat and lng:
                leads.append({
                    "source": "Craigslist",
                    "address": addr,
                    "latitude": lat,
                    "longitude": lng,
                    "price": None,
                    "created_at": datetime.utcnow().isoformat(),
                })
    return leads
# ───────────────────────────────────────────────────────────
# UI Setup
# ───────────────────────────────────────────────────────────
st.set_page_config(page_title="Savory Realty Leads", layout="wide")
st.markdown("""
<style>
body { background-color: #001F1F !important; color: #d9ffcc !important; }
.stApp { background-color: #001F1F !important; }
[data-testid="stHeader"] { background-color: #003333; color: #d9ffcc; }
.stButton > button { background-color: #00ff00 !important; color: #000000 !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("💚 Savory Realty Lead Engine")
st.markdown("Real-time leads, hot deals, and ARV estimates across Dallas-Fort Worth.")

# ───────────────────────────────────────────────────────────
# Leads Dashboard
# ───────────────────────────────────────────────────────────
with st.expander("📊 Live Leads Dashboard", expanded=True):
    st.markdown("### 🔍 Latest 100 Leads")
    data = supabase.table("leads").select("*").order("created_at", desc=True).limit(100).execute()
    df = pd.DataFrame(data.data or [])
    if not df.empty:
        df = df[["address", "price", "arv", "latitude", "longitude", "source", "created_at"]]
        df["Profit Potential"] = df.apply(lambda row: (row["arv"] - row["price"]) if row["price"] and row["arv"] else None, axis=1)
        st.dataframe(df)
    else:
        st.info("No leads available. Try running the scraper or wait for the next auto-run.")
