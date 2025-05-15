import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# Configure your Google Maps API key via Streamlit secrets
GOOGLE_MAPS_API_KEY = st.secrets["GOOGLE_MAPS_API_KEY"]  # Ensure this is set in your Streamlit secrets

# Page setup
st.set_page_config(
    page_title="Savory Realty Investments Lead Engine",
    layout="wide"
)

# Custom styling
st.markdown("""
<style>
body {background-color:#001F1F!important;color:#d9ffcc!important;}
.stApp {background-color:#001F1F!important;}
[data-testid=\"stHeader\"] {background-color:#003333;color:#d9ffcc;}
.stButton>button {background-color:#00ff00!important;color:#000;font-weight:bold;}
</style>
""", unsafe_allow_html=True)

# App title and description
st.title("🏘️ Savory Realty Investments Lead Engine")
st.markdown("Drag & drop CSV files to process leads with ARV estimates and map & Street View links for DFW properties.")

# File uploader
uploaded_files = st.file_uploader(
    "Drag & drop CSV files here",
    type="csv",
    accept_multiple_files=True
)

if uploaded_files:
    # Read and concatenate all uploaded CSVs
    df_list = [pd.read_csv(file) for file in uploaded_files]
    df = pd.concat(df_list, ignore_index=True)
    st.write(f"Loaded {len(df)} records from {len(uploaded_files)} file(s)")

    # Organization & filtering options
    st.subheader("🛠️ Organize & Filter Leads")
    col1, col2 = st.columns(2)
    with col1:
        # Remove duplicates
        if st.checkbox("Remove duplicate addresses"):
            before = len(df)
            df = df.drop_duplicates(subset=["Address"] if "Address" in df.columns else df.columns.tolist())
            dropped = before - len(df)
            st.write(f"Dropped {dropped} duplicates.")

        # Remove specific items
        if "Address" in df.columns:
            options = df["Address"].dropna().unique().tolist()
            to_remove = st.multiselect("Select addresses to remove", options)
            if to_remove:
                df = df[~df["Address"].isin(to_remove)]
                st.write(f"Removed {len(to_remove)} items; {len(df)} remaining.")
    with col2:
        # Sort options
        if st.checkbox("Sort by ARV estimate"):
            arv_col = "ARV_Estimate" if "ARV_Estimate" in df.columns else ("arv" if "arv" in df.columns else None)
            if arv_col:
                df = df.sort_values(by=arv_col, ascending=False, ignore_index=True)
                st.write("Sorted by ARV estimate.")
            else:
                st.warning("No ARV column found to sort by.")

    # Display the organized DataFrame
    st.dataframe(df)

    # Process button
    if st.button("Process Leads"):
        results = []
        for _, row in df.iterrows():
            address = row.get("Address") or row.get("address") or ""

            # Geocode via Google Maps API
            geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {"address": address, "key": GOOGLE_MAPS_API_KEY}
            resp = requests.get(geocode_url, params=params).json()
            if resp.get("status") == "OK":
                loc = resp["results"][0]["geometry"]["location"]
                lat, lng = loc["lat"], loc["lng"]
                map_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
                street_view = f"https://maps.googleapis.com/maps/api/streetview?location={lat},{lng}&size=600x400&key={GOOGLE_MAPS_API_KEY}"
            else:
                lat = lng = None
                map_link = street_view = None

            # ARV estimation stub
            arv_input = row.get("ARV_Estimate") or row.get("arv") or ""
            try:
                arv = float(arv_input)
            except:
                arv = None

            results.append({
                "Address": address,
                "Latitude": lat,
                "Longitude": lng,
                "Map Link": map_link,
                "Street View URL": street_view,
                "ARV Estimate": arv
            })

        res_df = pd.DataFrame(results)
        st.dataframe(res_df)
        csv_data = res_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download Processed Leads CSV",
            data=csv_data,
            file_name="processed_leads.csv",
            mime="text/csv"
        )
else:
    st.info("Awaiting CSV file upload. Drag and drop your CSV files to get started.")
