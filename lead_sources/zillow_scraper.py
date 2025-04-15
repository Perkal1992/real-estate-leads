import requests
from bs4 import BeautifulSoup

def fetch_zillow_fsbo():
    url = "https://www.zillow.com/dfw-tx/fsbo/"  # DFW-specific FSBO URL
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
    }

    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    leads = []

    for listing in soup.find_all('article'):
        try:
            lead = {
                "address": listing.find("address").text.strip(),
                "price": int(listing.find("div", {"class": "list-card-price"}).text.replace("$", "").replace(",", "").strip().split()[0]),
                "url": listing.find("a", {"class": "list-card-link"})["href"],
                "source": "Zillow FSBO",
                "status": "Active"
            }
            leads.append(lead)
        except Exception:
            continue

    return leads
