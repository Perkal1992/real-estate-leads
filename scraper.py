import os
import time
import traceback
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv
from lead_sources.zillow_scraper import scrape_zillow
from lead_sources.craigslist_scraper import scrape_craigslist

# Load .env credentials
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing Supabase credentials in environment.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Insert leads safely into Supabase
def insert_leads_to_supabase(leads: list, source: str):
    success, failed = 0, 0
    for lead in leads:
        try:
            formatted_lead = {
                "address": lead.get("address"),
                "google_maps": lead.get("google_maps"),
                "street_view": lead.get("street_view"),
                "latitude": lead.get("latitude"),
                "longitude": lead.get("longitude"),
                "source": source,
                "status": "new",
                "arv": None,
                "discount_to_arv": None,
                "is_hot": False,
                "enriched": False
            }
            supabase.table("leads").insert(formatted_lead).execute()
            success += 1
        except Exception as e:
            print(f"❌ Failed to insert lead: {lead.get('address')}. Error: {e}")
            failed += 1
    print(f"✅ {success} leads inserted from {source}. ❌ {failed} failed.")

# Main scrape-and-push loop
def run_scrapers():
    try:
        print("🔍 Scraping Zillow...")
        zillow_leads = scrape_zillow()
        insert_leads_to_supabase(zillow_leads, source="zillow")

        print("🔍 Scraping Craigslist...")
        craigslist_leads = scrape_craigslist()
        insert_leads_to_supabase(craigslist_leads, source="craigslist")

        print("✅ All scrapers finished successfully.")

    except Exception as e:
        print("🔥 An error occurred during scraping:")
        traceback.print_exc()

if __name__ == "__main__":
    run_scrapers()

