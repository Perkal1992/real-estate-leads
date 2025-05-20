import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0",
}

def estimate_arv_from_redfin(city, state, zip_code, sqft=1200):
    try:
        base_url = f"https://www.redfin.com/city/{city.replace(' ', '-')}/{state}/homes"
        sold_url = f"https://www.redfin.com/stingray/do/location-autocomplete?location={zip_code}&v=2&market=dallas"
        loc_res = requests.get(sold_url, headers=HEADERS, timeout=10)
        loc_data = loc_res.json()
        if not loc_data or not loc_data.get("payload"):
            return None

        location = loc_data["payload"]["sections"][0]["rows"][0]["url"]
        full_url = f"https://www.redfin.com{location}/filter/include=sold-3mo"
        page = requests.get(full_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(page.text, "html.parser")

        script_tag = soup.find("script", text=re.compile("window.__REDFIN_INITIAL_STATE__"))
        if not script_tag:
            return None

        script_text = script_tag.string
        prices = re.findall(r'"price":(\d+)', script_text)
        sqfts = re.findall(r'"sqFt":(\d+)', script_text)

        comps = [(int(p), int(s)) for p, s in zip(prices, sqfts) if int(s) > 0]
        if not comps:
            return None

        avg_ppsqft = sum(price / sqft for price, sqft in comps) / len(comps)
        estimated_arv = round(avg_ppsqft * sqft)

        return {
            "estimated_arv": estimated_arv,
            "avg_price_per_sqft": round(avg_ppsqft),
            "comps_used": len(comps)
        }

    except Exception as e:
        return {
            "error": str(e)
        }
