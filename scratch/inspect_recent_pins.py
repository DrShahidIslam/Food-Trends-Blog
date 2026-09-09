import os
import requests
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

root_dir = Path(__file__).resolve().parent.parent
token_file = root_dir / "pinterest_auth.json"
token = os.getenv("PINTEREST_ACCESS_TOKEN")

if token_file.exists():
    try:
        with open(token_file, "r") as f:
            data = json.load(f)
            token = data.get("access_token", token)
    except Exception as e:
        print(f"Error reading token file: {e}")

if not token:
    print("No token found.")
    exit(1)

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Fetch recent pins
res = requests.get("https://api.pinterest.com/v5/pins?page_size=20", headers=headers)
if res.status_code != 200:
    print(f"Failed to fetch pins: {res.status_code} - {res.text}")
    exit(1)

pins_data = res.json()
items = pins_data.get("items", [])
print(f"Fetched {len(items)} recent pins:\n")

for i, pin in enumerate(items[:6], 1):
    pin_id = pin.get("id")
    title = pin.get("title")
    desc = pin.get("description", "")
    link = pin.get("link")
    created_at = pin.get("created_at")
    media = pin.get("media", {})
    images = media.get("images", {})
    img_url = images.get("originals", {}).get("url") or images.get("600x", {}).get("url")
    
    print(f"[{i}] ID: {pin_id}")
    print(f"    Created: {created_at}")
    print(f"    Title: {title}")
    print(f"    Link: {link}")
    print(f"    Desc: {desc[:100]}..." if len(desc) > 100 else f"    Desc: {desc}")
    print(f"    Image: {img_url}")
    print("-" * 60)
