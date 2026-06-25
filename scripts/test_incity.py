import requests
ak = "cXlJYE1r6rIZsEEo83J5tRnL5btEyoJ5"
o = "34.7602,113.7730"
d = "34.4988,113.0281"

for ti in [0, 1, 2, 3, 4, 5]:
    r = requests.get("https://api.map.baidu.com/direction/v2/transit", params={
        "origin": o, "destination": d, "ak": ak,
        "tactics_incity": ti,
        "trans_type_intercity": 2, "tactics_intercity": 0,
        "page_size": 10
    }, timeout=10)
    data = r.json()
    if data.get("status") == 0:
        rt = data["result"]["routes"][0]
        dur = rt["duration"] // 60
        types = set()
        for step in rt.get("steps", []):
            for seg in (step if isinstance(step, list) else [step]):
                t = seg.get("vehicle_info", {}).get("type")
                if t: types.add(t)
        print(f"incity={ti}: {dur}min types={types}")
    else:
        print(f"incity={ti}: {data.get('status')}")
