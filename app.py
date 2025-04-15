import os
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client
from lead_sources.zillow_scraper import fetch_zillow_fsbo
from lead_sources.craigslist_scraper import fetch_craigslist
import googlemaps

# Load environment variables
load_dotenv()

# Load Supabase and Google API credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize Google Maps API client
gmaps = googlemaps.Client(key=GOOGLE_API_KEY)

# Custom CSS for black marble background
st.markdown(
    """
    <style>
    body {
        background-image: url("https://www.transparenttextures.com/patterns/black-marble.png");
        background-size: cover;
        color: white;
        font-family: 'Arial', sans-serif;
    }
    .css-1qfqu09 {
        background-color: #333333;
    }
    .stTextInput>div>div>input {
        color: white;
        background-color: #222222;
    }
    .stButton>button {
        background-color: #555555;
        color: white;
    }
    .stSelectbox, .stMultiselect, .stTextInput {
        background-color: #222222;
        color: white;
    }
    .stFileUploader {
        background-color: #444444;
        color: white;
    }
    .stMarkdown {
        color: white;
    }
    </style>
    """, unsafe_allow_html=True
)

def push_to_supabase(leads):
    """Push leads to Supabase"""
    for lead in leads:
        # Insert each lead into Supabase
        supabase.table("leads").insert(lead).execute()
    print(f"Pushed {len(leads)} leads to Supabase.")

def enrich_with_google_maps_data(lead):
    """Enrich lead with latitude, longitude, and Google Maps data"""
    address = lead['address']
    if address:
        geocode_result = gmaps.geocode(address)
        if geocode_result:
            lead['latitude'] = geocode_result[0]['geometry']['location']['lat']
            lead['longitude'] = geocode_result[0]['geometry']['location']['lng']
            lead['google_maps'] = f"https://www.google.com/maps?q={lead['latitude']},{lead['longitude']}"
            lead['street_view'] = f"https://maps.googleapis.com/maps/api/streetview?size=600x300&location={lead['latitude']},{lead['longitude']}&key={GOOGLE_API_KEY}"
        else:
            lead['latitude'] = None
            lead['longitude'] = None
            lead['google_maps'] = None
            lead['street_view'] = None
    return lead

def display_leads():
    """Display leads in the Streamlit app"""
    leads_data = supabase.table("leads").select("*").execute().data
    if leads_data:
        st.write("**Leads:**")
        for lead in leads_data:
            st.write(f"**Address:** {lead['address']}")
            st.write(f"**Source:** {lead['source']}")
            if lead['google_maps']:
                st.write(f"[Google Maps Link]({lead['google_maps']})")
            if lead['street_view']:
                st.image(lead['street_view'])
            st.write(f"**Latitude:** {lead['latitude']}, **Longitude:** {lead['longitude']}")
            st.write("---")
    else:
        st.write("No leads found.")

def upload_csv(file):
    """Process uploaded CSV and insert data into Supabase"""
    import pandas as pd
    from io import StringIO

    # Read CSV file into a DataFrame
    df = pd.read_csv(StringIO(file.getvalue().decode("utf-8")))
    
    for _, row in df.iterrows():
        lead = {
            'address': row['address'],
            'source': 'CSV',
            'arv': row.get('arv', None),
            'discount_to_arv': row.get('discount_to_arv', None),
            'is_hot': False
        }
        
        # Enrich lead with Google Maps data
        enriched_lead = enrich_with_google_maps_data(lead)
        
        # Insert enriched lead into Supabase
        push_to_supabase([enriched_lead])

def main():
    """Main Streamlit app logic"""
    st.set_page_config(page_title="Real Estate Leads Enrichment", layout="wide")
    
    # Title and description
    st.title("Real Estate Leads Enrichment")
    st.write("This app allows you to upload CSV files of property leads and enrich them with geolocation and map data. It integrates with Google Maps API and Supabase.")

    # Upload CSV
    st.subheader("Upload CSV of Property Leads")
    uploaded_file = st.file_uploader("No file chosen", type=["csv"])
    
    if uploaded_file:
        upload_csv(uploaded_file)
        st.success("CSV uploaded and leads enriched successfully!")
    
    # View leads button
    if st.button("View Leads"):
        display_leads()

if __name__ == "__main__":
    main()
