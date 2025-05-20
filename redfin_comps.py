import requests
from bs4 import BeautifulSoup
import re

def estimate_arv_from_redfin(address, city, zip_code, default_sqft=1500):
    try:
        search_query = f"{address}, {city}, {zip_code}".replace(" ", "-")
        search_url = f"https://www.redfin.com/stingray/do/location-autocomplete?location={search_query}&v=2&market=dallas"

        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        res = requests.get(search_url, headers=headers).json()
        suggestions = res.get("payload", {}).get("sections", [])[0].get("rows", [])
        if not suggestions:
            return None

        redfin_url = f"https://www.redfin.com{suggestions[0]['url']}"
        sold_url = redfin_url + "/filter/include=sold-6mo"
        page = requests.get(sold_url, headers=headers)
        soup = BeautifulSoup(page.text, "html.parser")

        script_tag = soup.find("script", text=re.compile("window.__REDUX_STORE__"))
        if not script_tag:
            return None

        script_text = script_tag.string
        matches = re.findall(r'"price":(\\d+),"sqFt":(\\d+)', script_text)

        comps = [(int(price), int(sqft)) for price, sqft in matches if int(sqft) > 0]
        if not comps:
            return None

        avg_ppsqft = sum(price / sqft for price, sqft in comps) / len(comps)
        estimated_arv = round(avg_ppsqft * default_sqft)

        return {
            "estimated_arv": estimated_arv,
            "avg_price_per_sqft": round(avg_ppsqft, 2),
            "comp_count": len(comps),
            "source": sold_url
        }

    except Exception as e:
        return {"error": str(e)}