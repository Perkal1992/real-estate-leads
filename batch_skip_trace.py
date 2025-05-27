# batch_skip_trace.py

import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

INPUT_FILE  = "Skip_Trace_Top_500.xlsx"
OUTPUT_FILE = "Skip_Trace_Results.xlsx"

# 1) load your addresses
df = pd.read_excel(INPUT_FILE)

# 2) set up headless Chrome
options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
service = Service(ChromeDriverManager().install())
driver  = webdriver.Chrome(service=service, options=options)

results = []
for idx, row in df.iterrows():
    addr = f"{row['address']}, {row['city']}, {row['state']} {row['zip']}"
    print(f"[{idx+1}/{len(df)}] Searching: {addr}")
    driver.get("https://thatsthem.com")
    time.sleep(2)

    box = driver.find_element(By.NAME, "searchText")
    box.clear()
    box.send_keys(addr)
    box.submit()
    time.sleep(4)

    owner = phone = email = ""
    try:
        card = driver.find_element(By.CSS_SELECTOR, "div.ct-search-result")
        owner = card.find_element(By.CSS_SELECTOR, "div.name").text
        phone = card.find_element(By.CSS_SELECTOR, "div.phone").text
        email = card.find_element(By.CSS_SELECTOR, "div.email").text
    except:
        pass

    results.append({
        "address": addr,
        "owner_name": owner,
        "phone":       phone,
        "email":       email
    })

driver.quit()

# 5) save to Excel
out_df = pd.DataFrame(results)
out_df.to_excel(OUTPUT_FILE, index=False)
print(f"\n✅ Done—results in ./{OUTPUT_FILE}")
