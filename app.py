import streamlit as st
import pandas as pd
import numpy as np
import os, time, threading
import requests
from datetime import datetime
import schedule
import smtplib
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
from supabase import create_client

# --- Page Config and Styling ---
st.set_page_config(page_title="Savory Realty Leads", page_icon="🏡", layout="centered")
st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background-color: #0e1117;
    color: #FFFFFF;
    padding: 1rem;
}
[data-testid="stDataFrame"] table {
    color: #FFFFFF;
    overflow-x: auto;
    border-radius: 8px;
}
button[kind="secondary"] {
    width: 100%;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background-color: #0e1117;
    color: #FFFFFF;
}
[data-testid="stDataFrame"] table {
    color: #FFFFFF;
    border-radius: 8px;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)

# --- Your Inline Credentials ---
SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB3a2JzenNsamxweGhsZmN2ZGVyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQzNDk4MDEsImV4cCI6MjA1OTkyNTgwMX0.bjVMzL4X6dN6xBx8tV3lT7XPsOFIEqMLv0pG3y6N-4o"
GOOGLE_MAPS_API_KEY = "AIzaSyDg-FHCdEFxZCZTy4WUmRryHmDdLto8Ezw"
RAPIDAPI_KEY = "88a3a41f80msh37d91f3065ad897p19f149jsnab96bb20afbc"
EMAIL_USER = "Perkal1992@gmail.com"
EMAIL_PASS = "your_app_password"  # Replace with your real Gmail App Password
ALERT_EMAIL = "Perkal1992@gmail.com"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
# --- TEMPORARY FORCE SCRAPER ---
if st.button("🔄 Force Scrape (Dev Only)"):
    st.write("Scraping now...")
    run_all_scrapers()
    st.success("✅ Scrape completed.")

# --- Geocoding ---
def geocode_address(address):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={requests.utils.quote(address)}&key={GOOGLE_MAPS_API_KEY}"
    try:
        r = requests.get(url)
        if r.ok:
            results = r.json().get("results", [])
            if results:
                loc = results[0]["geometry"]["location"]
                return loc["lat"], loc["lng"]
    except:
        pass
    return None, None

# --- Scrapers ---
def scrape_zillow():
    leads = []
    endpoint = "https://zillow-com1.p.rapidapi.com/propertyListings"
    headers = {
        "x-rapidapi-host": "zillow-com1.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY,
    }
    for zip_code in ["75201", "75001", "75006", "75019"]:
        params = {
            "propertyStatus": "FOR_SALE",
            "homeType": ["Houses"],
            "sort": "Newest",
            "limit": 20,
            "zip": zip_code,
        }
        try:
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
        except Exception as e:
            print(f"Zillow scrape failed: {e}")
    return leads

def scrape_craigslist():
    leads = []
    url = "https://dallas.craigslist.org/search/rea"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers)
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
    except Exception as e:
        print(f"Craigslist scrape failed: {e}")
    return leads

# --- Push to Supabase ---
def push_to_supabase(record):
    try:
        supabase.table("leads").insert(record).execute()
    except Exception as e:
        print(f"❌ Failed to push lead: {e}")

# --- Email Alerts ---
def send_email(subject, body):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_USER
        msg["To"] = ALERT_EMAIL
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        print("✅ Email sent")
    except Exception as e:
        print(f"❌ Email failed: {e}")

# --- Run All Scrapers ---
def run_all_scrapers():
    all_leads = []
    hot_leads = []
    for func in [scrape_zillow, scrape_craigslist]:
        try:
            leads = func()
            for lead in leads:
                push_to_supabase(lead)
                all_leads.append(lead)
                if lead.get("price") and isinstance(lead["price"], (int, float)) and int(lead["price"]) < 200000:
                    hot_leads.append(lead)
        except Exception as e:
            print(f"❌ {func.__name__} failed: {e}")
    if hot_leads:
        lines = [f"{l['address']} - ${l['price']} ({l['source']})" for l in hot_leads]
        body = "\n".join(lines)
        send_email("🔥 Hot Leads Found", body)
    return all_leads

# --- Background Scheduler ---
if "scheduler_thread" not in st.session_state:
    st.session_state.scheduler_thread = True
    schedule.every(30).minutes.do(run_all_scrapers)
    def scheduler_runner():
        while True:
            schedule.run_pending()
            time.sleep(1)
    threading.Thread(target=scheduler_runner, daemon=True).start()

# --- Streamlit UI ---
st.title("🏡 Savory Realty Lead Engine")
st.markdown("Real-time leads, hot deals, and ARV estimates across Dallas-Fort Worth.")

# --- Refresh Leads Button ---
if st.button("🔄 Refresh Leads Now"):
    st.info("Scraping in progress...")
    run_all_scrapers()
    st.success("Scrape completed! Check dashboard below 👇")

# --- Live Leads Dashboard ---
with st.expander("📊 Live Leads Dashboard", expanded=True):
    try:
        res = supabase.table("leads").select("*").order("created_at", desc=True).limit(100).execute()
        leads_data = res.data
    except Exception as e:
        st.error(f"Error fetching leads: {e}")
        leads_data = None

    if not leads_data or len(leads_data) == 0:
        st.info("No leads available yet.")
    else:
        df = pd.DataFrame(leads_data)
        for col in ["price"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        if "price" in df.columns and "latitude" in df.columns and "longitude" in df.columns:
            df["Google Maps"] = df.apply(lambda row: f"https://www.google.com/maps/search/?api=1&query={row['latitude']},{row['longitude']}", axis=1)
        expected_cols = ["address", "price", "latitude", "longitude", "source", "created_at", "Google Maps"]
        available_cols = [col for col in expected_cols if col in df.columns]
        st.dataframe(df[available_cols], use_container_width=True)
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
# ───────────────────────────────────────────────────────────
SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB3a2JzenNsamxweGhsZmN2ZGVyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQzNDk4MDEsImV4cCI6MjA1OTkyNTgwMX0.bjVMzL4X6dN6xBx8tV3lT7XPsOFIEqMLv0pG3y6N-4o"
GOOGLE_MAPS_API_KEY = "AIzaSyDg-FHCdEFxZCZTy4WUmRryHmDdLto8Ezw"
RAPIDAPI_KEY = "88a3a41f80msh37d91f3065ad897p19f149jsnab96bb20afbc"
ZILLOW_COMP_API = "https://zillow-com1.p.rapidapi.com/propertyExtendedSearch"

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ───────────────────────────────────────────────────────────
# Helper Functions
# ───────────────────────────────────────────────────────────
def geocode_address(address: str):
    url = (
        "https://maps.googleapis.com/maps/api/geocode/json"
        f"?address={requests.utils.quote(address)}&key={GOOGLE_MAPS_API_KEY}"
    )
    r = requests.get(url)
    if r.ok:
        res = r.json().get("results")
        if res:
            loc = res[0]["geometry"]["location"]
            return loc["lat"], loc["lng"]
    return None, None

def push_to_supabase(record: dict):
    try:
        supabase.table("leads").insert(record).execute()
    except Exception as e:
        logging.warning(f"Supabase insert failed: {e}")

# ───────────────────────────────────────────────────────────
# Scrapers
# ───────────────────────────────────────────────────────────
def scrape_zillow():
    endpoint = "https://zillow-com1.p.rapidapi.com/propertyListings"
    headers = {"x-rapidapi-host": "zillow-com1.p.rapidapi.com", "x-rapidapi-key": RAPIDAPI_KEY}
    leads = []
    for zip_code in ["75201", "75001", "75006", "75019"]:
        params = {"propertyStatus": "FOR_SALE", "homeType": ["Houses"], "sort": "Newest", "limit": "20", "zip": zip_code}
        r = requests.get(endpoint, headers=headers, params=params)
        if r.ok:
            for item in r.json().get("props", []):
                addr = item.get("address")
                price = item.get("price")
                if not addr:
                    continue
                lat, lng = geocode_address(addr)
                if lat and lng:
                    leads.append({"source": "Zillow", "address": addr, "latitude": lat, "longitude": lng, "price": price, "created_at": datetime.utcnow().isoformat()})
    return leads

def scrape_craigslist():
    url = "https://dallas.craigslist.org/search/rea"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    leads = []
    if r.ok:
        soup = BeautifulSoup(r.text, "html.parser")
        for post in soup.select("li.result-row")[:20]:
            title = post.select_one("a.result-title")
            addr = title.get_text(strip=True) if title else None
            lat, lng = geocode_address(addr) if addr else (None, None)
            if addr and lat and lng:
                leads.append({"source": "Craigslist", "address": addr, "latitude": lat, "longitude": lng, "price": None, "created_at": datetime.utcnow().isoformat()})
    return leads

# ───────────────────────────────────────────────────────────
# ARV & Hot Lead Logic
# ───────────────────────────────────────────────────────────
def estimate_arv(address: str):
    headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"}
    params = {"location": address, "status_type": "recently_sold", "home_type": "Houses", "sort": "sold_date", "limit": 10}
    try:
        r = requests.get(ZILLOW_COMP_API, headers=headers, params=params)
        if r.ok:
            sold = [c.get("price") for c in r.json().get("props",[]) if c.get("price")]
            if sold:
                return int(sum(sold)/len(sold))
    except:
        pass
    return None


def is_hot_lead(lead: dict):
    try:
        return lead.get("price") and int(lead["price"]) < 200000
    except:
        return False

# ───────────────────────────────────────────────────────────
# Main Scraper Runner
# ───────────────────────────────────────────────────────────
def run_all_scrapers():
    all_leads, hot_leads = [], []
    for func in (scrape_zillow, scrape_craigslist):
        for lead in func():
            arv = estimate_arv(lead["address"])
            lead["arv"] = arv
            push_to_supabase(lead)
            all_leads.append(lead)
            if is_hot_lead(lead): hot_leads.append(lead)
    if hot_leads:
        body = "\n".join([f"{l['address']} - ${l['price']} ARV: ${l['arv']}" for l in hot_leads])
        send_email("🔥 Hot Leads Found", body)
    return all_leads

# ───────────────────────────────────────────────────────────
# Background Scheduler
# ───────────────────────────────────────────────────────────
def run_background():
    schedule.every(30).minutes.do(run_all_scrapers)
    while True:
        schedule.run_pending(); time.sleep(1)
threading.Thread(target=run_background, daemon=True).start()

# ───────────────────────────────────────────────────────────
# UI Setup
# ───────────────────────────────────────────────────────────
st.set_page_config(page_title="Savory Realty Lead Engine", layout="wide")
# Theme CSS
st.markdown("""
<style>
body {background-color:#001F1F!important;color:#d9ffcc!important;}
.stApp {background-color:#001F1F!important;}
[data-testid="stHeader"] {background-color:#003333;color:#d9ffcc;}
.stButton>button {background-color:#00ff00!important;color:#000;font-weight:bold;}
</style>
""", unsafe_allow_html=True)

st.title("🏘️ Savory Realty Lead Engine")
st.markdown("Real-time leads, hot deals, and ARV estimates across Dallas-Fort Worth.")

# Force Scrape Button
if st.button("🔄 Refresh Leads Now"):
    with st.spinner("Scraping and updating leads..."):
        count = len(run_all_scrapers())
        st.success(f"✅ {count} leads scraped & updated.")

# Live Leads Dashboard
st.subheader("📊 Live Leads Dashboard")
data = supabase.table("leads").select("*").order("created_at",desc=True).limit(100).execute()
df = pd.DataFrame(data.data or [])
if not df.empty:
    cols = [c for c in ["address","price","arv","latitude","longitude","source","created_at"] if c in df.columns]
    df = df[cols]
    if "price" in df.columns and "arv" in df.columns:
        df["Profit Potential"] = df.apply(lambda r: (r["arv"]-r["price"]) if r["arv"] and r["price"] else None, axis=1)
    st.dataframe(df)
else:
    st.info("No leads yet. Click 'Refresh Leads Now' to load.")
