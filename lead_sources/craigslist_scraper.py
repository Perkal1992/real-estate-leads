import requests
from bs4 import BeautifulSoup

def fetch_craigslist_leads():
    url = "https://dallas.craigslist.org/search/rea?availabilityMode=0&sale_date=all+dates"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    leads = []

    for listing in soup.find_all('li', class_='result-row'):
        try:
            title = listing.find('a', class_='result-title')
            price_tag = listing.find('span', class_='result-price')
            lead = {
                'address': title.text.strip(),
                'price': int(price_tag.text.replace("$", "").replace(",", "").strip()) if price_tag else None,
                'url': title['href'],
                'source': 'Craigslist',
                'status': 'Active'
            }
            leads.append(lead)
        except Exception:
            continue

    return leads
