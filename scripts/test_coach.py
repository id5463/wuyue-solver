import requests
ak = "cXlJYE1r6rIZsEEo83J5tRnL5btEyoJ5"

# Test 1: Beijing->Tianjin (should have train)
pairs = [
    ("Beijing->Tianjin", "39.915,116.404", "39.085,117.200"),
    ("Chengdu->Chongqing", "30.573,104.067", "29.563,106.551"),
    ("Nanjing->Shanghai", "32.061,118.792", "31.230,121.474"),
]

for name, o, d in pairs:
    r = requests.get("https://api.map.baidu.com/direction/v2/transit", params={
        "origin": o, "destination": d, "ak": ak,
        "trans_type_intercity": 2, "page_size": 5
    }, timeout=10)
    d2 = r.json()
    if d2.get("status") == 0:
        for i, rt in enumerate(d2["result"]["routes"][:1]):
            types = set()
            for s in rt.get("steps", []):
                for seg in (s if isinstance(s, list) else [s]):
                    t = seg.get("vehicle_info", {}).get("type")
                    if t: types.add(t)
            print(f"{name}: {rt['duration']//60}min types={types}")
    else:
        print(f"{name}: status={d2.get('status')}")
