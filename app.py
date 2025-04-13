import os
import re
import requests
import pandas as pd
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from supabase import create_client, Client

# Load .env
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Streamlit UI setup
st.set_page_config(page_title="Savory Realty Investments — Wholesaling Dashboard", layout="wide")
st.title("🏘️ Savory Realty Investments")
st.markdown("Upload a CSV of property addresses or view live leads scraped every 30 min.")

# Upload CSV
uploaded_file = st.file_uploader("📁 Upload CSV", type=["csv"])

# Google Maps Geocoding
def geocode_address(address):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GOOGLE_MAPS_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        result = response.json()
        if result["status"] == "OK":
            location = result["results"][0]["geometry"]["location"]
            return location["lat"], location["lng"]
    return None, None

# Push to Supabase
def push_lead_to_supabase(lead):
    supabase.table("leads").insert(lead).execute()

# Zillow FSBO Scraper
def scrape_zillow_fsbo():
    headers = {"User-Agent": "Mozilla/5.0"}
    url = "https://www.zillow.com/dallas-tx/fsbo/"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    data_script = soup.find("script", text=re.compile("zpid"))

    if not data_script:
        return []

    try:
        json_text = re.search(r'<!--(.*?)-->', str(data_script), re.DOTALL).group(1)
        listings = re.findall(r'"streetAddress":"(.*?)","addressCity":"(.*?)","addressState":"(.*?)","addressZipcode":"(.*?)"', json_text)

        leads = []
        for address, city, state, zip_code in listings:
            full_address = f"{address}, {city}, {state} {zip_code}"
            lat, lng = geocode_address(full_address)
            if lat and lng:
                leads.append({
                    "source": "Zillow FSBO",
                    "address": full_address,
                    "city": city,
                    "state": state,
                    "zip": zip_code,
                    "latitude": lat,
                    "longitude": lng,
                    "google_maps": f"https://www.google.com/maps/search/?api=1&query={lat},{lng}",
                    "street_view": f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lng}",
                    "arv_estimate": None,
                    "created_at": datetime.utcnow().isoformat()
                })
        return leads
    except:
        return []

# Craigslist Scraper
def scrape_craigslist():
    url = "https://dallas.craigslist.org/search/rea"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    postings = soup.find_all("li", class_="result-row")

    leads = []
    for post in postings[:10]:
        title_elem = post.find("a", class_="result-title")
        if title_elem:
            address = title_elem.text
            lat, lng = geocode_address(address)
            if lat and lng:
                leads.append({
                    "source": "Craigslist",
                    "address": address,
                    "city": "Dallas",
                    "state": "TX",
                    "zip": "",
                    "latitude": lat,
                    "longitude": lng,
                    "google_maps": f"https://www.google.com/maps/search/?api=1&query={lat},{lng}",
                    "street_view": f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lng}",
                    "arv_estimate": None,
                    "created_at": datetime.utcnow().isoformat()
                })
    return leads

# Placeholder for FB Marketplace
def scrape_fb_marketplace():
    return []

# Run all scrapers
def run_all_scrapers():
    leads = scrape_zillow_fsbo() + scrape_craigslist() + scrape_fb_marketplace()
    for lead in leads:
        push_lead_to_supabase(lead)

# Pull from Supabase
def fetch_supabase_leads():
    result = supabase.table("leads").select("*").order("created_at", desc=True).limit(100).execute()
    return pd.DataFrame(result.data)

# CSV Upload Flow
if uploaded_file:
    df = pd.read_csv(uploaded_file)
    if "Address" not in df.columns:
        st.error("❌ Your CSV must contain a column named 'Address'")
    else:
        with st.spinner("Geocoding addresses..."):
            latitudes, longitudes, maps_links, street_views = [], [], [], []
            for address in df["Address"]:
                lat, lng = geocode_address(address)
                if lat and lng:
                    latitudes.append(lat)
                    longitudes.append(lng)
                    maps_links.append(f"https://www.google.com/maps/search/?api=1&query={lat},{lng}")
                    street_views.append(f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat},{lng}")
                else:
                    latitudes.append("")
                    longitudes.append("")
                    maps_links.append("")
                    street_views.append("")

            df["Latitude"] = latitudes
            df["Longitude"] = longitudes
            df["Google Maps"] = maps_links
            df["Street View"] = street_views

        for _, row in df.iterrows():
            if row["Latitude"]:
                lead = {
                    "source": "CSV Upload",
                    "address": row["Address"],
                    "city": "Dallas",
                    "state": "TX",
                    "zip": "",
                    "latitude": row["Latitude"],
                    "longitude": row["Longitude"],
                    "google_maps": row["Google Maps"],
                    "street_view": row["Street View"],
                    "arv_estimate": None,
                    "created_at": datetime.utcnow().isoformat()
                }
                push_lead_to_supabase(lead)

        st.success("✅ CSV processing complete")
        st.dataframe(df)

# Scrape Button
if st.button("🔄 Run Lead Scrapers Now"):
    run_all_scrapers()
    st.success("Scrapers ran successfully!")

# Display Supabase leads
st.subheader("🔍 Live Lead Feed")
st.dataframe(fetch_supabase_leads())
