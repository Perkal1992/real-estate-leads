import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from supabase import create_client
from bs4 import BeautifulSoup

# ─────────── Credentials ───────────
SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB3a2JzenNsamxweGhsZmN2ZGVyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQzNDk4MDEsImV4cCI6MjA1OTkyNTgwMX0.bjVMzL4X6dN6xBx8tV3lT7XPsOFIEqMLv0pG3y6N-4o"
GOOGLE_MAPS_API_KEY = "AIzaSyDg-FHCdEFxZCZTy4WUmRryHmDdLto8Ezw"
RAPIDAPI_KEY = "88a3a41f80msh37d91f3065ad897p19f149jsnab96bb20afbc"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ─────────── UI Styling ───────────
st.set_page_config(page_title="Savory Realty Lead Engine", layout="wide")
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

# ─────────── Helpers ───────────

def check_street_view_available(lat, lon):
    url = f"https://maps.googleapis.com/maps/api/streetview/metadata?location={lat},{lon}&key={GOOGLE_MAPS_API_KEY}"
    response = requests.get(url)
    data = response.json()
    return data.get("status") == "OK"

def estimate_arv(lat, lon):
    url = "https://zillow-com1.p.rapidapi.com/soldProperty"
    query = {"lat": lat, "long": lon, "radius": "1"}
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
    }
    try:
        response = requests.get(url, headers=headers, params=query)
        comps = response.json().get("results", [])
        prices = [c.get("price") for c in comps if c.get("price")]
        return sum(prices) // len(prices) if prices else None
    except:
        return None

# ─────────── Scrapers ───────────

def scrape_zillow_fsbo():
    url = "https://zillow-com1.p.rapidapi.com/propertyExtendedSearch"
    querystring = {"location":"Dallas, TX", "status_type":"ForSaleByOwner"}
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
    }

    response = requests.get(url, headers=headers, params=querystring)
    results = []

    if response.status_code == 200:
        data = response.json()
        for prop in data.get("props", []):
            lat = prop.get("latLong", {}).get("latitude")
            lon = prop.get("latLong", {}).get("longitude")
            arv = estimate_arv(lat, lon)
            street_view = check_street_view_available(lat, lon)
            results.append({
                "source": "Zillow FSBO",
                "address": prop.get("address"),
                "price": prop.get("price"),
                "beds": prop.get("beds"),
                "baths": prop.get("baths"),
                "url": f"https://www.zillow.com/homedetails/{prop.get('zpid')}_zpid/",
                "arv": arv,
                "street_view": street_view
            })
    return results

def scrape_craigslist():
    url = "https://dallas.craigslist.org/search/rea"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    for listing in soup.find_all("li", class_="result-row"):
        title = listing.find("a", class_="result-title hdrlnk").text
        url = listing.find("a", class_="result-title hdrlnk")["href"]
        price = listing.find("span", class_="result-price")
        price = price.text if price else "N/A"
        results.append({
            "source": "Craigslist",
            "address": title,
            "price": price,
            "beds": "N/A",
            "baths": "N/A",
            "url": url,
            "arv": "N/A",
            "street_view": "N/A"
        })
    return results

def scrape_facebook():
    # Placeholder logic – scraping FB requires authentication or 3rd party tool
    return [{
        "source": "Facebook",
        "address": "123 Mockingbird Ln, Dallas TX",
        "price": "$120,000",
        "beds": 3,
        "baths": 1,
        "url": "https://www.facebook.com/marketplace",
        "arv": 140000,
        "street_view": True
    }]

def run_all_scrapers():
    zillow_data = scrape_zillow_fsbo()
    craigslist_data = scrape_craigslist()
    fb_data = scrape_facebook()
    all_data = zillow_data + craigslist_data + fb_data

    for lead in all_data:
        supabase.table("leads").insert(lead).execute()

    return pd.DataFrame(all_data)

# ─────────── UI ───────────
if st.button("Scrape New Leads"):
    with st.spinner("Scraping all sources..."):
        df = run_all_scrapers()
        st.success("Leads scraped and uploaded!")
        st.dataframe(df)

if st.checkbox("Show all stored leads"):
    data = supabase.table("leads").select("*").order("id", desc=True).limit(100).execute()
    df = pd.DataFrame(data.data)
    st.dataframe(df)
