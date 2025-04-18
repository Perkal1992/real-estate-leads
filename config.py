# config.py

import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL       = os.getenv("SUPABASE_URL")
SUPABASE_KEY       = os.getenv("SUPABASE_KEY")
GOOGLE_MAPS_API_KEY= os.getenv("GOOGLE_MAPS_API_KEY")
RAPIDAPI_KEY       = os.getenv("RAPIDAPI_KEY")
