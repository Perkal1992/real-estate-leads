from dotenv import load_dotenv
load_dotenv()
from supabase import create_client, Client
import streamlit as st
import pandas as pd
import requests
import os
from bs4 import BeautifulSoup
import re
from datetime import datetime
from config import GOOGLE_MAPS_API_KEY, SUPABASE_URL, SUPABASE_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Savory Realty Investments — Wholesaling Dashboard", layout="wide")

st.title("🏘️ Savory Realty Investments")
st.markdown("Upload a CSV of property addresses or view live leads scraped every 30 min.")

uploaded_file = st.file_uploader("📁 Upload CSV", type=["csv"])

def geocode_address(address):
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GOOGLE_MAPS_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        result = response.json()
        if result["status"] == "OK":
            location = result["results"][0]["geometry"]["location"]
            return location["lat"], location["lng"]
    return None, None

def push_lead_to_supabase(lead):
    supabase.table("leads").insert(lead).execute()

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

def scrape_fb_marketplace():
    return []

def run_all_scrapers():
    leads = scrape_zillow_fsbo() + scrape_craigslist() + scrape_fb_marketplace()
    for lead in leads:
        push_lead_to_supabase(lead)

def fetch_supabase_leads():
    result = supabase.table("leads").select("*").order("created_at", desc=True).limit(100).execute()
    return pd.DataFrame(result.data)

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

        st.success("✅ Processing complete")
        st.dataframe(df)

st.subheader("🔍 Live Lead Feed")
st.dataframe(fetch_supabase_leads())