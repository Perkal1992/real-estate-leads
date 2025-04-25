import streamlit as st
import pandas as pd
import numpy as np
import os, time, threading
import requests
from datetime import datetime

# Optional: for scheduling tasks and sending emails
import schedule
import smtplib
from email.mime.text import MIMEText
from bs4 import BeautifulSoup  # for parsing Craigslist results

from supabase import create_client

# --- Page Config and Custom UI Styling ---
st.set_page_config(page_title="DFW Real Estate Leads", page_icon="📊", layout="wide")
# Custom CSS for dark theme and styling
st.markdown("""
<style>
/* Set background color and text color */
[data-testid="stAppViewContainer"] {
    background-color: #0e1117;
    color: #FFFFFF;
}
/* Style for DataFrame header and cells */
[data-testid="stDataFrame"] table {
    color: #FFFFFF;
    border-radius: 8px;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)

# --- Initialize Supabase Client ---
SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Optional: Email alert configuration from environment or secrets ---
EMAIL_USER = os.getenv("EMAIL_USER") or st.secrets.get("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS") or st.secrets.get("EMAIL_PASS")
ALERT_EMAIL = os.getenv("ALERT_EMAIL") or st.secrets.get("ALERT_EMAIL")

# --- Define Scraper Functions for Zillow and Craigslist ---
def scrape_zillow():
    """Scrape Zillow for new leads (returns list of lead dicts)."""
    leads = []
    # Example Zillow search URL for Dallas-Fort Worth area (could be adjusted as needed)
    search_url = "https://www.zillow.com/homes/Dallas-Fort-Worth_rb/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(search_url, headers=headers, timeout=15)
    except Exception as e:
        print("Error connecting to Zillow:", e)
        return leads
    if res.status_code != 200:
        print("Failed to fetch Zillow page, status code:", res.status_code)
        return leads
    # Parse Zillow page content for listings (Zillow embeds JSON in the page)
    text = res.text
    # Find the JSON that contains search results
    idx = text.find('"searchResults":')
    if idx != -1:
        try:
            start_idx = text.index('{', idx)
            end_idx = text.index(',"usersSearchTerm"', start_idx)  # end of searchResults JSON
            search_json_str = text[start_idx:end_idx]
            # Load the JSON data
            data = None
            data = eval(search_json_str)  # using eval to parse the JSON snippet (Zillow's JSON uses Python-like syntax for booleans and None)
        except Exception as e:
            try:
                # Fallback: attempt json.loads with some replacements if eval failed
                import json
                json_str = search_json_str.replace("null", "null").replace("true", "true").replace("false", "false")
                data = json.loads(json_str)
            except Exception as e2:
                print("Error parsing Zillow JSON:", e, e2)
                data = None
        if data and isinstance(data, dict):
            # Zillow JSON structure: data["searchResults"]["listResults"] contains list of properties
            results = []
            if "searchResults" in data:
                if "listResults" in data["searchResults"]:
                    results = data["searchResults"]["listResults"]
            elif "cat1" in data:  # alternate JSON path (Zillow often changes structure)
                results = data.get("cat1", {}).get("searchResults", {}).get("listResults", [])
            for item in results:
                address = item.get('address') or item.get('statusText') or "Unknown Address"
                price = None
                if item.get('unformattedPrice') is not None:
                    # Zillow provides unformattedPrice as a number if available
                    price = item['unformattedPrice']
                elif item.get('price'):
                    # price might be string like "$123,456"
                    price_str = item['price']
                    try:
                        price = int(price_str.replace("$", "").replace(",", "").strip())
                    except:
                        price = None
                # Coordinates
                lat = item.get('latLong', {}).get('latitude')
                lon = item.get('latLong', {}).get('longitude')
                url = item.get('detailUrl')
                source = "Zillow"
                created_at = datetime.utcnow().isoformat()
                # ARV estimation (use Zillow's zestimate if available as ARV)
                arv = None
                zestimate = item.get('zestimate') or item.get('variableData', {}).get('zestimate')
                if zestimate:
                    try:
                        arv = int(float(zestimate))
                    except:
                        arv = None
                # Profit Potential calculation (ARV - price if both available)
                profit = None
                if price is not None and arv is not None:
                    profit = arv - price
                lead = {
                    "address": address,
                    "price": price,
                    "lat": lat,
                    "lon": lon,
                    "url": url,
                    "source": source,
                    "created_at": created_at
                }
                if arv is not None:
                    lead["arv"] = arv
                if profit is not None:
                    lead["profit"] = profit
                leads.append(lead)
    return leads

def scrape_craigslist():
    """Scrape Craigslist for new leads (returns list of lead dicts)."""
    leads = []
    base_url = "https://dallas.craigslist.org"
    search_path = "/search/rea?query=fixer+upper&sort=date"  # looking for "fixer upper" in real estate section
    try:
        res = requests.get(base_url + search_path, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    except Exception as e:
        print("Error connecting to Craigslist:", e)
        return leads
    if res.status_code != 200:
        print("Failed to fetch Craigslist results, status code:", res.status_code)
        return leads
    soup = BeautifulSoup(res.text, 'html.parser')
    postings = soup.find_all('li', class_='result-row')
    for post in postings:
        a = post.find('a', class_='result-title')
        price_elem = post.find('span', class_='result-price')
        time_elem = post.find('time', class_='result-date')
        if not a:
            continue
        address = a.text.strip()
        url = a['href']
        price = None
        if price_elem:
            try:
                price = int(price_elem.text.strip().strip("$").replace(",", ""))
            except:
                price = None
        # Craigslist's result-date time datetime attribute
        posted_time = time_elem['datetime'] if time_elem else None
        created_at = datetime.utcnow().isoformat()
        lead = {
            "address": address,
            "price": price,
            "url": url,
            "source": "Craigslist",
            "created_at": created_at
        }
        # (No ARV/profit for Craigslist leads by default)
        leads.append(lead)
    return leads

def push_leads_to_supabase(leads):
    """Insert new leads into Supabase (avoid duplicates by unique URL)."""
    if not leads:
        return
    for lead in leads:
        try:
            # Use upsert on URL to avoid duplicating the same listing
            supabase.table("leads").upsert(lead, on_conflict="url").execute()
        except Exception as e:
            print(f"Supabase insert error for {lead.get('address')}: {e}")

def send_email_alert(lead):
    """Send an email alert for a hot lead."""
    if not (EMAIL_USER and EMAIL_PASS and ALERT_EMAIL):
        return  # Email credentials not configured
    try:
        address = lead.get('address', 'N/A')
        price = lead.get('price')
        arv = lead.get('arv')
        profit = lead.get('profit')
        # Compose email content
        subject = f"🔥 New Real Estate Lead: {address}"
        lines = [f"Address: {address}"]
        if price is not None:
            lines.append(f"Price: ${price:,.0f}")
        if arv is not None:
            lines.append(f"ARV: ${arv:,.0f}")
        if profit is not None:
            lines.append(f"Profit Potential: ${profit:,.0f}")
        lines.append(f"Source: {lead.get('source')}")
        if lead.get('url'):
            lines.append(f"Listing: {lead['url']}")
        body = "\n".join(lines)
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = EMAIL_USER
        msg['To'] = ALERT_EMAIL
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, [ALERT_EMAIL], msg.as_string())
        server.quit()
        print(f"Alert email sent for lead: {address}")
    except Exception as e:
        print("Failed to send email alert:", e)

def run_all_scrapers():
    """Run both Zillow and Craigslist scrapers, push new leads, and send alerts."""
    new_leads = []
    try:
        zillow_leads = scrape_zillow()
        craigslist_leads = scrape_craigslist()
        # Combine leads from both sources
        for lead in (zillow_leads or []):
            new_leads.append(lead)
        for lead in (craigslist_leads or []):
            new_leads.append(lead)
    except Exception as e:
        print("Error during scraping:", e)
    if not new_leads:
        return
    # Push to Supabase and send alerts for qualifying leads
    push_leads_to_supabase(new_leads)
    for lead in new_leads:
        # Determine if this lead should trigger an email (e.g., has profit and it's high, or very low price)
        prof = lead.get('profit')
        if prof is not None and prof > 50000:
            send_email_alert(lead)
        elif prof is None:
            # If no profit info, maybe alert if price is below a threshold
            price = lead.get('price') or 0
            if price > 0 and price < 100000:
                send_email_alert(lead)

# --- Background Scheduling of Scrapers (runs periodically) ---
if 'scheduler_thread' not in st.session_state:
    st.session_state.scheduler_thread = True
    # Schedule scrapers to run every 4 hours (for example)
    schedule.every(4).hours.do(run_all_scrapers)
    def scheduler_runner():
        while True:
            schedule.run_pending()
            time.sleep(60)  # check every minute
    threading.Thread(target=scheduler_runner, daemon=True).start()

# If an environment flag is set to run scrapers (for CI/cron usage), run once and exit
if os.getenv("RUN_SCRAPERS") or os.getenv("SCRAPE_ONLY"):
    run_all_scrapers()
    st.stop()

# --- Streamlit App UI ---
st.title("🏠 DFW Real Estate Leads Dashboard")
st.write("Real-time leads, hot deals, and ARV estimates across Dallas-Fort Worth.")

# Expandable section for the live leads table
with st.expander("📊 Live Leads Dashboard", expanded=True):
    # Query the latest 100 leads from Supabase, sorted by newest first
    try:
        res = supabase.table("leads").select("*").order("created_at", ascending=False).limit(100).execute()
        leads_data = res.data  # list of records
    except Exception as e:
        st.error(f"Error fetching leads from database: {e}")
        leads_data = None
    if not leads_data or len(leads_data) == 0:
        st.write("No leads available to display at this time.")
    else:
        df = pd.DataFrame(leads_data)
        # Ensure numeric columns are numeric types
        for col in ["price", "arv", "profit"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        # Compute profit on the fly if not present in data but price and arv are available
        if "profit" not in df.columns and "price" in df.columns and "arv" in df.columns:
            df["profit"] = df["arv"] - df["price"]
        # Define the order of columns to display
        desired_columns = ["created_at", "address", "price", "arv", "profit", "source"]
        display_columns = [c for c in desired_columns if c in df.columns]
        df_display = df[display_columns].copy()
        # Convert created_at to datetime and then format for display
        if "created_at" in df_display.columns:
            df_display["created_at"] = pd.to_datetime(df_display["created_at"])
            # Sort by created_at descending (newest first)
            df_display.sort_values("created_at", ascending=False, inplace=True)
            df_display["created_at"] = df_display["created_at"].dt.strftime("%Y-%m-%d %H:%M:%S")
        # Format numeric columns as currency strings for display
        if "price" in df_display.columns:
            df_display["price"] = df_display["price"].apply(lambda x: f"${x:,.0f}" if pd.notnull(x) else "")
        if "arv" in df_display.columns:
            df_display["arv"] = df_display["arv"].apply(lambda x: f"${x:,.0f}" if pd.notnull(x) else "")
        if "profit" in df_display.columns:
            df_display["profit"] = df_display["profit"].apply(lambda x: f"${x:,.0f}" if pd.notnull(x) else "")
        # Rename columns for a nicer display heading
        df_display.rename(columns={
            "created_at": "Date Added",
            "address": "Address",
            "price": "Price",
            "arv": "ARV",
            "profit": "Profit Potential",
            "source": "Source"
        }, inplace=True)
        # Reset index so it doesn't show the dataframe index
        df_display.reset_index(drop=True, inplace=True)
        # Display the table in the app
        st.dataframe(df_display, use_container_width=True)
