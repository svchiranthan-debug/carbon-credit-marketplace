import requests
import json

queries = [
    "Bengaluru",
    "Basavanagudi Bengaluru",
    "Basavanagudi 1st Cross Bengaluru",
    "Shivamogga",
    "Basavanagudi 1st Cross Shivamogga",
    "Mandya",
    "Mysuru",
    "577201"
]

headers = {
    "User-Agent": "CarbonGeospatialVerification/1.0",
    "Accept-Language": "en"
}

print("🌍 Testing Address-Level Geocoding for High-Precision Map Navigation...\n")

for q in queries:
    url = f"https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=5&q={requests.utils.quote(q)}"
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data:
                top = data[0]
                display = top.get("display_name", "")
                lat = top.get("lat")
                lon = top.get("lon")
                place_type = top.get("type", "")
                cls = top.get("class", "")
                print(f"📍 Query: '{q}' -> Found {len(data)} results")
                print(f"   Top Result: {display[:80]}...")
                print(f"   Coords: ({lat}, {lon}) | Type: {place_type} ({cls})\n")
            else:
                print(f"⚠️ Query: '{q}' -> 0 results found.\n")
        else:
            print(f"❌ Query: '{q}' -> HTTP {res.status_code}\n")
    except Exception as e:
        print(f"⚠️ Query: '{q}' -> Error: {e}\n")
