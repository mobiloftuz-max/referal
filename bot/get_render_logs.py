import httpx
import json

RENDER_API_KEY = "rnd_qVwIMc3D7fcpyHUafa9zOYEnxqdC"
SERVICE_ID = "srv-d9f19b741pts73fr3q0g"
OWNER_ID = "tea-d9f16rf7f7vs73bmaqpg"

url = f"https://api.render.com/v1/logs"
headers = {
    "Authorization": f"Bearer {RENDER_API_KEY}",
    "Accept": "application/json"
}
params = {
    "ownerId": OWNER_ID,
    "resource": SERVICE_ID,
    "limit": 100
}

print("Fetching Render service logs...")
try:
    resp = httpx.get(url, headers=headers, params=params, timeout=20)
    if resp.status_code == 200:
        logs_data = resp.json()
        print("\nLogs retrieved successfully:")
        logs_list = logs_data.get("logs", [])
        
        # Sort logs by timestamp ascending
        logs_list.reverse()
        
        for log in logs_list:
            msg = log.get("message", "")
            ts = log.get("timestamp", "")
            # Filter app logs (exclude noise like pip install cache messages if possible, or just print everything)
            # Check labels to see if type is app
            print(f"[{ts}] {msg}")
    else:
        print(f"❌ Failed to fetch logs: Status code {resp.status_code}")
        print(resp.text)
except Exception as e:
    print(f"❌ Error occurred: {e}")
