import requests

def fetch_craigslist_leads():
    url = "https://api.craigslist.org/leads"  # Example, adjust to actual API
    response = requests.get(url)
    data = response.json()
    return data["leads"]
