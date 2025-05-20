import os
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime
from supabase import create_client
from redfin_comps import estimate_arv_from_redfin

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("🚀 Scraper started at", datetime.utcnow().isoformat())

HOT_WORDS = ["cash", "as-is", "must sell", "motivated", "investor", "cheap", "urgent", "fast"]

def normalize_price(val):
    try:
        return int("".join(filter(str.isdigit, str(val)))) if val else None
    except:
        return None

def extract_address_from_post(url):
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        address_tag = soup.select_one("div.mapaddress")
        if address_tag:
            return address_tag.text.strip()
    except Exception as e:
        print("❌ Failed to extract address:", e)
    return None

def insert_lead(data: dict):
    try:
        supabase.table("craigslist_leads").upsert(data).execute()
        print(f"✅ Inserted: {data.get('title')}")
    except Exception as e:
        print("❌ Insert failed:", e)

try:
    print("📡 Scraping Craigslist…")
    url = "https://dallas.craigslist.org/search/rea?hasPic=1"
    res = requests.get(url, timeout=10)
    soup = BeautifulSoup(res.text, "html.parser")
    rows = soup.select(".result-row")

    existing_titles = supabase.table("craigslist_leads").select("title").limit(1000).execute().data
    seen = {item["title"] for item in existing_titles}

    for row in rows:
        title_tag = row.select_one(".result-title")
        if not title_tag:
            continue
        title = title_tag.text.strip()
        if title in seen:
            continue

        link = title_tag["href"]
        price_tag = row.select_one(".result-price")
        price = normalize_price(price_tag.text) if price_tag else None
        is_hot = any(word in title.lower() for word in HOT_WORDS)

        post = {
            "title": title,
            "date_posted": datetime.utcnow().isoformat(),
            "source": "craigslist",
            "price": price,
            "link": link,
            "latitude": None,
            "longitude": None,
            "arv": None,
            "equity": None,
            "hot_lead": is_hot,
            "street_view_url": None
        }

        # 🔍 Try to extract full address
        address = extract_address_from_post(link)
        if address:
            print(f"📍 Found address: {address}")
            try:
                comps = estimate_arv_from_redfin(address)
                arv = comps.get("estimated_arv")
                post["arv"] = arv
                post["equity"] = (arv or 0) - (price or 0)
                post["hot_lead"] = (post["equity"] / arv >= 0.25) if arv and post["equity"] else is_hot
                print(f"💰 ARV: {arv} | Equity: {post['equity']} | Hot: {post['hot_lead']}")
            except Exception as e:
                print("❌ ARV fetch failed:", e)

        insert_lead(post)

except Exception as e:
    print("❌ Craigslist scraping failed:", e)

print("✅ Scraper complete.")
