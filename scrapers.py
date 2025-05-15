import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from supabase import create_client, Client
from twilio.rest import Client as TwilioClient
from pyairtable import Table
from dotenv import load_dotenv

load_dotenv()

# ─── ENVIRONMENT VARIABLES ─────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_FROM")
ALERT_PHONE_TO = os.getenv("ALERT_PHONE_TO")
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT"))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")

# ─── SETUP ──────────────────────────────────────────────────────────────
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
twilio_client = TwilioClient(TWILIO_SID, TWILIO_TOKEN)
airtable = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)

HOT_WORDS = ["off market", "fsbo", "flip", "owner finance", "cash only", "needs work", "assignment"]
MAX_HOT_PRICE = 300000

# ─── FUNCTIONS ───────────────────────────────────────────────────────────
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

def scrape_redfin(city="Dallas TX"):
    query = city.replace(" ", "%20")
    url = f"https://www.redfin.com/stingray/do/location-autocomplete?location={query}&v=2"
    res = requests.get(url)
    if res.status_code != 200:
        return []
    try:
        data = res.json()["payload"]["sections"][0]["rows"]
        properties = []
        for item in data:
            name = item.get("name")
            url = f"https://www.redfin.com{item.get('url')}"
            arv = estimate_redfin_arv(url)
            properties.append({"title": name, "url": url, "price": arv})
        return properties
    except Exception as e:
        print(f"Redfin scrape error: {e}")
        return []

def estimate_redfin_arv(listing_url):
    try:
        res = requests.get(listing_url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        price_tag = soup.find("div", class_="statsValue")
        if price_tag:
            price = int(re.sub(r'[^\d]', '', price_tag.text))
            return price
    except Exception as e:
        print(f"ARV estimation error: {e}")
    return None

def push_to_supabase(lead):
    existing = supabase.table("leads").select("title").eq("title", lead["title"]).execute()
    if not existing.data:
        supabase.table("leads").insert(lead).execute()
        return True
    return False

def send_sms_alert(body):
    twilio_client.messages.create(body=body[:120], from_=TWILIO_FROM, to=ALERT_PHONE_TO)

def send_email_alert(body):
    import smtplib
    from email.mime.text import MIMEText
    msg = MIMEText(body)
    msg["Subject"] = "🚨 Hot Lead Alert!"
    msg["From"] = EMAIL_USER
    msg["To"] = ALERT_EMAIL_TO
    with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

def push_to_airtable(lead):
    try:
        airtable.create(lead)
    except Exception as e:
        print(f"⚠️ Airtable push failed for {lead['title']}: {e}")

# ─── MAIN ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    all_sources = scrape_craigslist() + scrape_redfin("Dallas TX")
    hot_alerts = []
    pushed = 0
    for lead in all_sources:
        if push_to_supabase(lead):
            push_to_airtable(lead)
            pushed += 1
            print(f"✅ Pushed: {lead['title']}")
            if lead['price'] and lead['price'] <= MAX_HOT_PRICE or any(word in lead['title'].lower() for word in HOT_WORDS):
                hot_alerts.append(f"{lead['title']} - ${lead['price'] or 'N/A'}")
    if hot_alerts:
        body = "\n".join(hot_alerts)
        send_sms_alert(body)
        send_email_alert(body)
    print(f"🔁 Done: {pushed} new leads pushed. {len(hot_alerts)} hot leads notified.")
