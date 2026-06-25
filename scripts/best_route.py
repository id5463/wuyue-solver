import requests, json, time
ak = "cXlJYE1r6rIZsEEo83J5tRnL5btEyoJ5"

# 五岳登山口坐标
GATES = {
    "songshan": "34.4988,113.0281",
    "huashan": "34.5333,110.0833",
    "hengshan_n": "39.6667,113.7333",
    "taishan": "36.2150,117.1250",
    "hengshan_s": "27.2667,112.7333",
    "home": "33.738,113.295",
}

# 查询 A->B 最优路线
def query(a_name, b_name):
    key = f"{a_name}_{b_name}"
    cache_file = f"scripts/data/route_{key}.json"
    
    # try cache
    import os
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            data = json.load(f)
            if data.get("status") == 0:
                return data
    
    o, d = GATES[a_name], GATES[b_name]
    r = requests.get("https://api.map.baidu.com/direction/v2/transit", params={
        "origin": o, "destination": d, "ak": ak,
        "departure_date": "2026-06-28",
        "departure_time": "06:00-22:00",
        "page_size": 5
    }, timeout=10)
    data = r.json()
    time.sleep(0.5)
    
    # save cache
    with open(cache_file, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    return data

# 解析路线
def show_best(data, label):
    if data.get("status") != 0:
        print(f"{label}: no route")
        return
    for i, rt in enumerate(data["result"]["routes"][:2]):
        dur = rt["duration"] // 60
        price = rt.get("price", 0)
        steps_desc = []
        for s in rt.get("steps", []):
            for seg in (s if isinstance(s, list) else [s]):
                vi = seg.get("vehicle_info", {})
                t = vi.get("type")
                if t in [1, 6]:
                    dt = vi.get("detail", {})
                    steps_desc.append(f"{dt.get('name','')}({dt.get('departure_station','')}->{dt.get('arrive_station','')} {dt.get('departure_time','')})")
                elif t == 3:
                    steps_desc.append(f"bus:{vi.get('name','')}")
        print(f"  [{i}] {dur}min {price}yuan: {' | '.join(steps_desc[:3])}")

# 查询关键段
print("=== 嵩山->华山 ===")
show_best(query("songshan", "huashan"), "songshan->huashan")

print("\n=== 华山->恒山 ===")
show_best(query("huashan", "hengshan_n"), "huashan->hengshan_n")

print("\n=== 恒山->泰山 ===")
show_best(query("hengshan_n", "taishan"), "hengshan_n->taishan")

print("\n=== 泰山->衡山 ===")
show_best(query("taishan", "hengshan_s"), "taishan->hengshan_s")

print("\n=== 衡山->回家 ===")
show_best(query("hengshan_s", "home"), "hengshan_s->home")
