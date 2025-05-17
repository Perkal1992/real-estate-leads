import requests
import re
from datetime import datetime
from bs4 import BeautifulSoup
from supabase import create_client, Client

# ─────────── CREDENTIALS ───────────
SUPABASE_URL = "https://pwkbszsljlpxhlfcvder.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9…"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HOT_WORDS = ["motivated", "cash", "as-is", "urgent", "must sell", "investor", "fast", "cheap"]

def is_hot(text: str) -> bool:
    txt = (text or "").lower()
    return any(word in txt for word in HOT_WORDS)

def normalize_price(val) -> int | None:
    if not val:
        return None
    digits = re.sub(r"[^\d]", "", str(val))
    return int(digits) if digits else None

def get_existing_titles() -> set[str]:
    try:
        res = supabase.table("leads").select("title").limit(5000).execute()
        return {r["title"] for r in res.data}
    except Exception:
        return set()

def push_to_supabase(leads: list[dict]):
    existing = get_existing_titles()
    pushed = 0
    for lead in leads:
        if lead["title"] in existing:
            continue
        try:
            supabase.table("leads").insert(lead).execute()
            pushed += 1
        except Exception as e:
            print(f"❌ Failed to push {lead['title']}: {e}")
    print(f"🔁 Done: pushed {pushed} new leads.")

# ─────────── SCRAPERS ───────────

def scrape_zillow(pages=3):
    print("🔍 Zillow: not currently supported, skipping.")
    return []

def scrape_facebook():
    print("🔍 Facebook: not currently supported, skipping.")
    return []

def scrape_craigslist(region="dallas", pages=1):
    print(f"🔍 Scraping Craigslist ({region})…")
    base = f"https://{region}.craigslist.org/search/rea?hasPic=1"
    leads = []
    try:
        r = requests.get(base, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select("li.result-row")  # fallback to standard selector

        print(f" → Found {len(items)} listings")
        for it in items:
            # date
            dt = it.select_one("time.result-date")["datetime"]

            # title & link
            a = it.select_one("a.result-title")
            title = a.text.strip()
            link  = a["href"]

            # price
            pe = it.select_one(".result-price")
            price = normalize_price(pe.text if pe else None)

            leads.append({
                "title":       title,
                "description": f"Craigslist listing for {title}",
                "link":        link,
                "price":       price,
                "city":        region,
                "source":      "Craigslist",
                "hot_lead":    is_hot(title),
                "created_at":  dt,
            })
    except Exception as e:
        print(f"❌ Craigslist error: {e}")
    return leads

# ─────────── MAIN ───────────

def main():
    z = scrape_zillow()
    f = scrape_facebook()
    c = scrape_craigslist("dallas")
    all_leads = z + f + c
    print(f"\n📦 Total scraped: {len(all_leads)} leads")
    push_to_supabase(all_leads)

if __name__ == "__main__":
    main()
