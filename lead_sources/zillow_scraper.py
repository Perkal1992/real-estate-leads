import requests

def fetch_zillow_fsbo():
    url = "https://api.zillow.com/fsbo"  # Example, adjust to actual API
    response = requests.get(url)
    data = response.json()
    return data["leads"]
