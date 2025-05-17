import requests
from bs4 import BeautifulSoup
from datetime import datetime

def get_craigslist_leads(city: str, timeout: int = 10):
    """
    Fetch the latest real-estate listings from Craigslist for the given city subdomain.
    Returns a list of dicts with: date_posted (datetime), title, link, price (float).
    """
    url = f"https://{city}.craigslist.org/search/rea"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    leads = []
    for result in soup.select(".result-info"):
        title_el = result.select_one(".result-title")
        date_el = result.select_one(".result-date")
        price_el = result.select_one(".result-price")

        # parse price to float
        price = None
        if price_el:
            try:
                price = float(price_el.text.replace("$", "").replace(",", ""))
            except ValueError:
                price = None

        # parse date
        date_posted = None
        if date_el:
            try:
                date_posted = datetime.fromisoformat(date_el["datetime"])
            except Exception:
                date_posted = None

        leads.append({
            "date_posted": date_posted,
            "title": title_el.text if title_el else "",
            "link": title_el["href"] if title_el and title_el.has_attr("href") else "",
            "price": price,
            "fetched_at": datetime.utcnow()
        })

    return leads
