import requests, json
ak = "cXlJYE1r6rIZsEEo83J5tRnL5btEyoJ5"
o = "34.7602,113.7730"
d = "34.4988,113.0281"

# Try ALL strategy combinations
for trans in [None, 0, 1, 2]:
    for tactics in [0, 1, 2]:
        params = {"origin":o,"destination":d,"ak":ak,"page_size":10}
        if trans is not None:
            params["trans_type_intercity"] = trans
        params["tactics_intercity"] = tactics
        
        r = requests.get("https://api.map.baidu.com/direction/v2/transit",
            params=params, timeout=10)
        data = r.json()
        if data.get("status") == 0:
            routes = data["result"]["routes"]
            types_set = set()
            for rt in routes:
                for s in rt.get("steps",[]):
                    for seg in (s if isinstance(s,list) else [s]):
                        vi = seg.get("vehicle_info",{})
                        t = vi.get("type","?")
                        types_set.add(t)
            trans_str = "default" if trans is None else ["train","flight","bus"][trans]
            print(f"trans={trans_str} tactics={tactics}: {routes[0]['duration']//60}min types={types_set}")
        else:
            print(f"trans={trans} tactics={tactics}: status={data.get('status')}")
