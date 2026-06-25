# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open("top20.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"共 {len(data)} 条路线，起点 2026-07-01\n")

for p in data[:5]:
    route_str = " → ".join(p["route"])
    print(f"┌─ #{p['rank']}  ¥{p['total_yuan']:.0f}  {p['total_h']}h  {route_str}")
    for st in p["steps"]:
        if st["type"] == "train":
            print(f"│  🚂 {st['from']}→{st['to']}  {st['train']}  {st['dep_datetime']}({st['dep_weekday']}) → {st['arr_datetime']}({st['arr_weekday']})")
        else:
            print(f"│  ⛰️ {st['mountain']}  {st['gate_datetime']}({st['gate_weekday']})进山 → {st['summit_datetime']}登顶 → {st['depart_station_datetime']}离站")
    print("└─")
