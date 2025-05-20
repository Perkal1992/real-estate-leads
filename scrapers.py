import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from supabase import create_client
from redfin_comps import estimate_arv_from_redfin

# ───── Supabase Setup ─────
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

def extract_address_from_craigslist_post(url):
    try:
        res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        map_tag = soup.find("div", class_="mapaddress")
        if map_tag:
            return map_tag.text.strip()

        text_body = soup.find("section", id="postingbody")
        if text_body:
            match = re.search(r"\d{2,5}\s+[^\n,]+", text_body.text)
            if match:
                return match.group(0).strip()
    except Exception as e:
        print(f"❌ Address extraction failed: {e}")
    return None

def insert_lead(data: dict):
    try:
        supabase.table("craigslist_leads").insert(data).execute()
        print(f"✅ Inserted: {data.get('title')}")
    except Exception as e:
        print("❌ Insert failed:", e)

# ───── Craigslist Scraper ─────
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
        link = title_tag["href"] if title_tag.has_attr("href") else None
        price_tag = row.select_one(".result-price")
        price = normalize_price(price_tag.text) if price_tag else None
        is_hot = any(word in title.lower() for word in HOT_WORDS)

        post = {
            "title": title,
            "date_posted": datetime.utcnow().isoformat(),
            "source": "craigslist",
            "price": price,
            "link": link,
            "is_hot": is_hot,
            "latitude": None,
            "longitude": None,
            "arv": None,
            "equity": None,
            "street_view_url": None
        }

        # 🏠 Extract Address + Estimate ARV
        if link:
            extracted_address = extract_address_from_craigslist_post(link)
            if extracted_address:
                print("📍 Address found:", extracted_address)
                try:
                    comps_data = estimate_arv_from_redfin(extracted_address)
                    post["arv"] = comps_data.get("estimated_arv")
                    post["equity"] = (post["arv"] or 0) - (post["price"] or 0)
                    post["hot_lead"] = (post["equity"] / post["arv"] >= 0.25) if post["arv"] and post["equity"] else False
                    print(f"💰 ARV: {post['arv']}, Equity: {post['equity']}, Hot: {post['hot_lead']}")
                except Exception as e:
                    print("❌ ARV fetch failed:", e)
            else:
                print("⚠️ No address found.")
        
        insert_lead(post)

except Exception as e:
    print("❌ Craigslist scraping failed:", e)

print("✅ Scraper complete.")
