import requests

def fetch_facebook_leads():
    url = "https://api.facebook.com/marketplace/leads"  # Example, adjust to actual API
    response = requests.get(url)
    data = response.json()
    return data["leads"]
