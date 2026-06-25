import requests, json
ak = "cXlJYE1r6rIZsEEo83J5tRnL5btEyoJ5"
r = requests.get("https://api.map.baidu.com/direction/v2/transit", params={
    "origin": "30.573,104.067", "destination": "29.563,106.551",
    "ak": ak, "trans_type_intercity": 2, "page_size": 5
}, timeout=10)
data = r.json()

for i, rt in enumerate(data["result"]["routes"][:3]):
    print(f"\n=== Route {i} ===")
    for si, step in enumerate(rt.get("steps", [])):
        for seg in (step if isinstance(step, list) else [step]):
            vi = seg.get("vehicle_info", {})
            if vi.get("type") == 6:
                detail = vi.get("detail", {})
                print(json.dumps(detail, ensure_ascii=False, indent=2))
                break
