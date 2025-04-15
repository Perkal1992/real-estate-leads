import streamlit as st
import pandas as pd
import requests
from supabase import create_client, Client
import googlemaps
from datetime import datetime

# ====================================================================
# HARD-CODED CREDENTIALS (No manual input required!)
# ====================================================================
SUPABASE_URL = "https://rjeoymnwzsmnbjffqzpl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJqZW95bW53enNtbmJqZmZxenBsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MTI3MjQyMDYsImV4cCI6MjAyODMwMDIwNn0.Z_3Af0SC8L6-4QypLaDihMAln3PHU3NUKyVnWdfciI4"
GOOGLE_MAPS_API_KEY = "AIzaSyDg-FHCdEFxZCZTy4WUmRryHmDdLto8Ezw"

# Initialize Supabase and Google Maps clients
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# ====================================================================
# CUSTOM CSS - Black Marble Background & Modern Styling
# ====================================================================
st.set_page_config(page_title="Savory Realty Investments", page_icon="🏘️", layout="wide")
st.markdown(
    """
    <style>
    body {
        background-image: url("https://www.transparenttextures.com/patterns/black-marble.png");
        background-size: cover;
        background-attachment: fixed;
        color: white;
        font-family: 'Arial', sans-serif;
    }
    .css-1qfqu09 { background-color: #333333; }
    .stTextInput>div>div>input { background-color: #222222; color: white; }
    .stButton>button { background-color: #555555; color: white; }
    .stSelectbox, .stMultiselect, .stTextInput { background-color: #222222; color: white; }
    .stFileUploader { background-color: #444444; color: white; }
    .stMarkdown { color: white; }
    </style>
    """, unsafe_allow_html=True
)

# ====================================================================
# UTILITY FUNCTIONS
# ====================================================================

def estimate_arv(lead):
    """Estimate ARV as 1.25 times the asking price (simple stub)."""
    if "price" in lead and lead["price"]:
        try:
            # Assume price is numeric; if it's a string, remove $ and commas.
            price = float(str(lead["price"]).replace("$", "").replace(",", ""))
            return round(price * 1.25, 2)
        except Exception:
            return None
    return None

def enrich_with_google_maps_data(lead):
    """
    Use Google Maps API to geocode an address and generate map links.
    Updates the lead dictionary with 'latitude', 'longitude', 
    'google_maps' (display link), and 'street_view' (image link).
    """
    address = lead.get("address")
    if address:
        geocode_result = gmaps.geocode(address)
        if geocode_result:
            lat = geocode_result[0]['geometry']['location']['lat']
            lng = geocode_result[0]['geometry']['location']['lng']
            lead["latitude"] = lat
            lead["longitude"] = lng
            lead["google_maps"] = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
            lead["street_view"] = f"https://maps.googleapis.com/maps/api/streetview?size=600x300&location={lat},{lng}&key={GOOGLE_MAPS_API_KEY}"
        else:
            lead["latitude"] = None
            lead["longitude"] = None
            lead["google_maps"] = None
            lead["street_view"] = None
    return lead

def push_leads_to_supabase(leads):
    """Push a list of lead dictionaries to the 'leads' table in Supabase."""
    for lead in leads:
        try:
            # Enrich the lead with Google Maps info
            enriched = enrich_with_google_maps_data(lead)
            # Estimate ARV based on 'price'
            arv = estimate_arv(enriched)
            enriched["arv"] = arv
            # Calculate discount to ARV and flag hot lead if discount is 30% or more
            if arv and "price" in enriched and enriched["price"]:
                try:
                    price = float(str(enriched["price"]).replace("$", "").replace(",", ""))
                    discount = round((1 - price/arv), 2)
                    enriched["discount_to_arv"] = discount
                    enriched["is_hot"] = discount >= 0.3
                except Exception:
                    enriched["discount_to_arv"] = None
                    enriched["is_hot"] = False
            else:
                enriched["discount_to_arv"] = None
                enriched["is_hot"] = False

            supabase.table("leads").insert(enriched).execute()
        except Exception as e:
            print(f"❌ Error pushing lead: {e}")
    print(f"Pushed {len(leads)} leads to Supabase.")

# ====================================================================
# SCRAPER FUNCTIONS (for DFW market)
# ====================================================================

def fetch_zillow_fsbo():
    """
    Fetch FSBO listings from Zillow for the DFW area.
    (This example uses a dummy URL and stub logic; replace with real scraping code.)
    """
    url = "https://www.zillow.com/dfw-tx/fsbo/"
    headers = { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" }
    response = requests.get(url, headers=headers)
    # Here you would parse the HTML. We'll return a dummy list for now.
    return [
        {
            "address": "123 Main St, Dallas, TX",
            "price": 200000,
            "source": "Zillow FSBO",
            "status": "Active"
        }
    ]

def fetch_craigslist_leads():
    """
    Fetch leads from Craigslist for the DFW area.
    """
    url = "https://dallas.craigslist.org/search/rea?purveyor=owner"
    response = requests.get(url)
    if response.status_code != 200:
        return []
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')
    leads = []
    for listing in soup.find_all('li', class_='result-row'):
        try:
            title = listing.find('a', class_='result-title hdrlnk')
            price_tag = listing.find('span', class_='result-price')
            lead = {
                "address": title.text.strip(),
                "price": float(price_tag.text.replace("$", "").replace(",", "")) if price_tag else None,
                "url": title["href"],
                "source": "Craigslist",
                "status": "Active"
            }
            leads.append(lead)
        except Exception:
            continue
    return leads

def fetch_facebook_leads():
    """
    Scrape Facebook Marketplace for DFW leads.
    Note: Facebook generally does not allow scraping through simple requests.
    This function provides a placeholder.
    """
    # For production, consider using browser automation (e.g., Selenium) if allowed.
    return [
        {
            "address": "789 Elm Dr, Fort Worth, TX",
            "price": 250000,
            "source": "Facebook Marketplace",
            "status": "Active"
        }
    ]

def scrape_and_push_all():
    """Scrape all sources, enrich the data, and push to Supabase."""
    all_leads = []
    all_leads.extend(fetch_zillow_fsbo())
    all_leads.extend(fetch_craigslist_leads())
    all_leads.extend(fetch_facebook_leads())
    push_leads_to_supabase(all_leads)
    return all_leads

# ====================================================================
# STREAMLIT UI
# ====================================================================
st.set_page_config(page_title="Savory Realty Investments: Lead Engine", layout="wide")
st.title("🏠 Savory Realty Investments: Lead Engine")

st.markdown("""
Upload fresh CSVs of property addresses or use the live scraper to find deals now. Leads are enriched with geolocation, ARV is estimated, and hot leads are flagged automatically.
""")

# Create a tabbed interface for CSV upload, live scraping, and viewing leads
tabs = st.tabs(["📤 Upload CSV", "🔄 Scrape Leads", "📊 View Leads"])

with tabs[0]:
    st.subheader("Upload CSV of Property Leads")
    uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])
    if uploaded_file:
        # Process the CSV and push leads to Supabase
        from io import StringIO
        df = pd.read_csv(StringIO(uploaded_file.getvalue().decode("utf-8")))
        for _, row in df.iterrows():
            lead = {
                "address": row.get("address", ""),
                "price": row.get("price", None),
                "source": "CSV",
                "status": row.get("status", "New")
            }
            enriched_lead = enrich_with_google_maps_data(lead)
            push_leads_to_supabase([enriched_lead])
        st.success("CSV uploaded and leads enriched successfully!")

with tabs[1]:
    st.subheader("Manual Scrape and Enrichment")
    if st.button("Scrape All Sources Now"):
        with st.spinner("Scraping Zillow FSBO, Craigslist, and Facebook Marketplace..."):
            leads = scrape_and_push_all()
            st.success(f"✅ {len(leads)} leads scraped and added to Supabase!")

with tabs[2]:
    st.subheader("Latest Leads from Supabase")
    result = supabase.table("leads").select("*").order("created_at", desc=True).limit(50).execute()
    if result and result.data:
        for lead in result.data:
            st.markdown(f"""
            **Address:** {lead.get('address', 'N/A')}  
            **Price:** ${lead.get('price', 'N/A')}  
            **Lat, Lng:** {lead.get('latitude', 'N/A')}, {lead.get('longitude', 'N/A')}  
            **Source:** {lead.get('source', 'N/A')}, **Status:** {lead.get('status', 'N/A')}  
            **Street View:** [{lead.get('street_view', 'N/A')}]({lead.get('street_view', '#')})  
            **Google Maps:** [{lead.get('google_maps_link', 'N/A')}]({lead.get('google_maps_link', '#')})  
            **ARV:** ${lead.get('arv', 'N/A')}, **Discount:** {lead.get('discount_to_arv', 0)*100:.1f}%  
            🔥 **Hot Lead:** {'Yes' if lead.get('is_hot') else 'No'}
            """)
            st.markdown("---")
    else:
        st.info("No leads found yet.")
