import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from supabase import create_client

# ───── Supabase Setup ─────
SUPABASE_URL   = os.getenv("SUPABASE_URL")
SUPABASE_KEY   = os.getenv("SUPABASE_KEY")
RAPIDAPI_KEY   = os.getenv("RAPIDAPI_KEY")
supabase       = create_client(SUPABASE_URL, SUPABASE_KEY)

print("🚀 Scraper started at", datetime.utcnow().isoformat())

def insert_lead(title, source, is_hot=False):
    post = {
        "title":      title,
        "date_posted": datetime.utcnow().isoformat(),
        "source":     source,
        "is_hot":     is_hot
    }
    try:
        supabase.table("craigslist_leads").insert(post).execute()
        print(f"✅ {source} lead: {title}")
    except Exception as e:
        print(f"❌ Failed to insert {source} lead:", e)

# ───── Craigslist ─────
try:
    print("📡 Scraping Craigslist…")
    url = "https://dallas.craigslist.org/search/rea?hasPic=1"
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    hot_words = ["cash","as-is","must sell","motivated","investor"]
    existing = supabase.table("craigslist_leads").select("title").limit(1000).execute().data
    seen = {r["title"] for r in existing}
    for row in soup.select(".result-row .result-title"):
        t = row.text.strip()
        if t in seen: continue
        insert_lead(t, "craigslist", any(w in t.lower() for w in hot_words))
except Exception as e:
    print("❌ Craigslist failed:", e)

# ───── Zillow FSBO ─────
try:
    print("📡 Scraping Zillow FSBO…")
    z_url = "https://zillow-com1.p.rapidapi.com/propertyExtendedSearch"
    z_hdr = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host":"zillow-com1.p.rapidapi.com"
    }
    z_prm = {"location":"Dallas, TX","status_type":"ForSaleByOwner"}
    z_res = requests.get(z_url, headers=z_hdr, params=z_prm).json()
    for p in z_res.get("props", []):
        insert_lead(p.get("address","Unknown"), "zillow_fsbo")
except Exception as e:
    print("❌ Zillow FSBO failed:", e)

# ───── Facebook Marketplace ─────
try:
    print("📡 Scraping Facebook Marketplace…")
    f_url = "https://facebook-marketplace1.p.rapidapi.com/search"
    f_hdr = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host":"facebook-marketplace1.p.rapidapi.com"
    }
    f_prm = {"city":"Dallas","daysSinceListed":1,"sort":"newest"}
    f_res = requests.get(f_url, headers=f_hdr, params=f_prm).json()
    for l in f_res.get("listings", []):
        insert_lead(l.get("marketplace_listing_title","No title"), "facebook")
except Exception as e:
    print("❌ Facebook failed:", e)

print("✅ Scraper run complete.")

def is_hot_lead(title: str) -> bool:
    title_lower = title.lower()
    return any(word in title_lower for word in HOT_WORDS)

def fetch_existing_titles() -> set:
    try:
        result = supabase.table("craigslist_leads").select("title").limit(1000).execute()
        return {item["title"] for item in result.data}
    except Exception as e:
        print("Error fetching existing titles:", e)
        return set()

def scrape():
    print(f"Scraping {TARGET_URL} ...")
    res = requests.get(TARGET_URL)
    soup = BeautifulSoup(res.text, "html.parser")
    listings = soup.select(".result-row")
    
    print(f"Found {len(listings)} listings.")
    existing_titles = fetch_existing_titles()

    for item in listings:
        title_elem = item.select_one(".result-title")
        if not title_elem:
            continue
        title = normalize_title(title_elem.text)
        if title in existing_titles:
            continue  # skip duplicates

        post = {
            "title": title,
            "date_posted": datetime.utcnow().isoformat(),
            "source": SOURCE,
            "is_hot": is_hot_lead(title)
        }

        try:
            supabase.table("craigslist_leads").insert(post).execute()
            print("✅ Inserted:", title)
        except Exception as err:
            print("❌ Insert error:", err)

if __name__ == "__main__":
    try:
        scrape()
        print("✅ Scraper finished successfully.")
    except Exception as e:
        print("❌ Critical error in scraper:", e)
