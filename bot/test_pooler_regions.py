import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase_url = os.environ.get("SUPABASE_URL", "")
project_ref = supabase_url.replace("https://", "").split(".")[0]

# List of regions to test
regions = [
    "ap-southeast-1",  # Singapore
    "eu-central-1",    # Frankfurt
    "us-east-1",       # N. Virginia
    "us-east-2",       # Ohio
    "us-west-1",       # N. California
    "us-west-2",       # Oregon
    "ap-northeast-1",  # Tokyo
    "ap-northeast-2",  # Seoul
    "eu-west-1",       # Ireland
    "eu-west-2",       # London
    "eu-west-3",       # Paris
    "sa-east-1",       # São Paulo
    "ca-central-1"     # Canada
]

username = f"postgres.{project_ref}"
password = SUPABASE_SERVICE_KEY
database = "postgres"
port = 6543  # Pooler transaction port

print(f"Project Reference: {project_ref}")
print(f"Username: {username}")

success = False
for r in regions:
    host = f"aws-0-{r}.pooler.supabase.com"
    print(f"Trying region '{r}' at {host}...")
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=username,
            password=password,
            database=database,
            connect_timeout=3
        )
        print(f"🎉 SUCCESS! Connected to region '{r}'")
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        print(f"Postgres Version: {cursor.fetchone()[0]}")
        conn.close()
        success = True
        # Write the working host to .env or a local config
        print(f"Saving host: {host}")
        with open("bot/pooler_config.txt", "w") as f:
            f.write(f"POOLER_HOST={host}\n")
            f.write(f"POOLER_USER={username}\n")
            f.write(f"POOLER_PASS={password}\n")
        break
    except Exception as e:
        print(f"❌ Failed for region '{r}': {e}")

if not success:
    print("\n❌ Could not connect to any regional pooler. Double-check your SUPABASE_SERVICE_KEY or network.")
