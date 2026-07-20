import os
import sys
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

print("Inspecting existing 'users' table columns...")
try:
    # We can fetch one row and inspect the keys
    res = client.table("users").select("*").limit(1).execute()
    if res.data:
        print("Columns found in 'users' table:")
        for key in res.data[0].keys():
            print(f"- {key}: {type(res.data[0][key]).__name__} (value: {res.data[0][key]})")
    else:
        print("Table 'users' is empty, cannot inspect columns this way.")
        
    # Let's inspect active schemas via GraphQL if possible, or try a dummy insert to see columns
except Exception as e:
    print(f"Error: {e}")
