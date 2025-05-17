import os
import re
import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def scrape_craigslist():
    url = "https://dallas.craigslist.org/search/rea?hasPic=1"
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    posts = soup.select(".result-row")
    leads = []
    for post in posts:
        title = post.select_one(".result-title").text.strip()
        link = post.select_one(".result-title")['href']
        price_match = re.search(r'\$(\d+[\,\d]*)', post.text)
        price = int(price_match.group(1).replace(',', '')) if price_match else None
        leads.append({"title": title, "url": link, "price": price})
    return leads

def push_to_supabase(lead):
    existing = supabase.table("leads").select("title").eq("title", lead["title"]).execute()
    if not existing.data:
        supabase.table("leads").insert(lead).execute()
        return True
    return False

if __name__ == "__main__":
    all_leads = scrape_craigslist()
    pushed = 0
    for lead in all_leads:
        if push_to_supabase(lead):
            pushed += 1
            print(f"✅ Pushed: {lead['title']}")
    print(f"🔁 Done: {pushed} new leads pushed.")
