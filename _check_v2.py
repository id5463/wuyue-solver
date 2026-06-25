# -*- coding: utf-8 -*-
import json
with open("data/bus_info.json", "r", encoding="utf-8") as f:
    d = json.load(f)
for k in ["TA","HS","HX","DT","ZZ"]:
    v = d[k]
    s = v["station_to_gate"]
    print(f"{k}: dur={s['total_duration_min']}min cost=Y{s['total_price']}")
    for st in s["steps"]:
        if st["mode"] == "bus":
            freq = v.get("schedules",{}).get("bus_freq",{}).get(st["bus_name"],{})
            iv = freq.get("interval_min","?")
            fix = freq.get("fixed",[])
            if fix:
                print(f"  {st['bus_name']}: {st['first_bus']}-{st['last_bus']} FIXED {fix}")
            else:
                print(f"  {st['bus_name']}: {st['first_bus']}-{st['last_bus']} every {iv}min")
        else:
            print(f"  walk {st['duration_min']}min")
    tx = v.get("schedules",{}).get("taxi",{})
    print(f"  taxi: Y{tx.get('cost','?')} {tx.get('time_min','?')}min")
