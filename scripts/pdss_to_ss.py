import requests, json
ak = "cXlJYE1r6rIZsEEo83J5tRnL5btEyoJ5"
# 平顶山->嵩阳书院
o = "33.738,113.295"
d = "34.4988,113.0281"

r = requests.get("https://api.map.baidu.com/direction/v2/transit", params={
    "origin": o, "destination": d, "ak": ak, "page_size": 5
}, timeout=10)
data = r.json()
print("Status:", data.get("status"))
if data.get("status") == 0:
    for i, rt in enumerate(data["result"]["routes"][:3]):
        dur = rt["duration"] // 60
        price = rt.get("price", 0)
        types = set()
        print(f"\nRoute {i}: {dur}min {price}yuan")
        for s in rt.get("steps", []):
            for seg in (s if isinstance(s, list) else [s]):
                vi = seg.get("vehicle_info", {})
                t = vi.get("type")
                if t: types.add(t)
                if t in [1, 6]:
                    dt = vi.get("detail", {})
                    print(f"  Type{t}: {dt.get('name')} {dt.get('departure_station')}->{dt.get('arrive_station')} {dt.get('price')}yuan")
                elif t == 3:
                    print(f"  Bus: {vi.get('name')} {vi.get('on_station')}->{vi.get('off_station')}")
        print(f"  All types: {types}")
