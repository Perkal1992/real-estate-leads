import requests
import pandas as pd
from io import StringIO
import urllib3

# Disable the HTTPS warnings since we're using HTTP
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_csv(url):
    # Now hitting HTTP, so cert warnings go away
    resp = requests.get(url, verify=False)
    resp.raise_for_status()
    return pd.read_csv(StringIO(resp.text))

# 1) Lis Pendens (Notice of Default)
url1 = (
    "http://gis.dallascounty.org/arcgis/rest/services/"
    "Real_Property_Records/MapServer/1/query?"
    "where=DocType%3D'Notice%20of%20Default'&"
    "outFields=RecordingAddress,RecordingCity,RecordingState,"
    "RecordingPostalCode,LienAmt,Est_Value&f=csv"
)

# 2) Absentee Owners (Non-Owner Occupied)
zip_list = ["75208", "75217", "75228"]
where2 = "SiteZip IN ({}) AND OwnerOccupied%3D'No'".format(
    ",".join(f"'{z}'" for z in zip_list)
)
url2 = (
    "http://gis.dallascounty.org/arcgis/rest/services/"
    "Tax_Assessor/MapServer/0/query?"
    f"where={where2}&"
    "outFields=SitusAddress,SitusCity,SitusState,"
    "SitusZip,MortgageBalance,MarketValue&f=csv"
)

# 3) Struck‐Off / Tax‐Deed Auctions
url3 = (
    "http://gis.dallascounty.org/arcgis/rest/services/"
    "Real_Property_Records/MapServer/2/query?"
    "where=Status%3D'Struck%20Off'&"
    "outFields=RecordingAddress,RecordingCity,RecordingState,"
    "RecordingPostalCode,LienAmt,Est_Value&f=csv"
)

# Fetch each
df1 = fetch_csv(url1).rename(columns={
    "RecordingAddress":"Property Address",
    "RecordingCity":"City",
    "RecordingState":"State",
    "RecordingPostalCode":"Zip Code",
    "LienAmt":"Amount Owed",
    "Est_Value":"Estimated Value"
})
df2 = fetch_csv(url2).rename(columns={
    "SitusAddress":"Property Address",
    "SitusCity":"City",
    "SitusState":"State",
    "SitusZip":"Zip Code",
    "MortgageBalance":"Amount Owed",
    "MarketValue":"Estimated Value"
})
df3 = fetch_csv(url3).rename(columns={
    "RecordingAddress":"Property Address",
    "RecordingCity":"City",
    "RecordingState":"State",
    "RecordingPostalCode":"Zip Code",
    "LienAmt":"Amount Owed",
    "Est_Value":"Estimated Value"
})

# Combine and flag hot leads
master = pd.concat([df1, df2, df3], ignore_index=True)
master["Amount Owed"]      = pd.to_numeric(master["Amount Owed"], errors="coerce")
master["Estimated Value"]  = pd.to_numeric(master["Estimated Value"], errors="coerce")
master["Equity"]           = master["Estimated Value"] - master["Amount Owed"]
master["hot_lead"]         = master["Equity"] / master["Estimated Value"] >= 0.25

# Save to CSV
master.to_csv("master_leads.csv", index=False)
print(f"Built master_leads.csv with {len(master)} rows, {int(master.hot_lead.sum())} hot leads.")
