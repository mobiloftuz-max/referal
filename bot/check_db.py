import os
import sys
from dotenv import load_dotenv

# Load env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

try:
    from supabase import create_client, Client
except ImportError:
    print("Error: supabase-py is not installed. Please make sure the venv is ready.")
    sys.exit(1)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_KEY not found in env.")
    sys.exit(1)

print(f"Connecting to Supabase at: {SUPABASE_URL}")
client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

tables_to_check = ["users", "channels", "withdrawals", "settings"]

for table in tables_to_check:
    try:
        # Attempt a basic select
        res = client.table(table).select("*").limit(1).execute()
        print(f"✅ Table '{table}' exists and is accessible. Rows found: {len(res.data) if res.data else 0}")
    except Exception as e:
        error_msg = str(e)
        if "relation" in error_msg and "does not exist" in error_msg:
            print(f"❌ Table '{table}' does NOT exist in the database.")
        else:
            print(f"⚠️ Error checking table '{table}': {error_msg}")
