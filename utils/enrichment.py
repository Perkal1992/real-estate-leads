import requests

def enrich_lead(lead, google_maps_api_key):
    # Enrich lead with Google Maps data
    address = lead.get("address")
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={google_maps_api_key}"
    response = requests.get(url)
    data = response.json()
    lead["latitude"] = data["results"][0]["geometry"]["location"]["lat"]
    lead["longitude"] = data["results"][0]["geometry"]["location"]["lng"]
    return lead
