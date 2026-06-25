# -*- coding: utf-8 -*-
import json

with open("top20_dated.json", "r", encoding="utf-8") as f:
    data = json.load(f)

p0 = data[0]
es = p0["enhanced_steps"]

print("=== 第1条, 第1步 (火车) ===")
print(json.dumps(es[0], ensure_ascii=False, indent=2))
print()
print("=== 第1条, 第2步 (嵩山爬山) ===")
print(json.dumps(es[1], ensure_ascii=False, indent=2))
print()
print(f"共 {len(data)} 条, 每条 {len(es)} 步")
print(f"起点: {p0['start_date_label']} → 终点: {p0['end_date_label']}")

# 显示所有20条的日期范围
print("\n=== 20条路线日期概览 ===")
for p in data:
    r = " → ".join(p["route"])
    print(f"  #{p['rank']:2d}  {p['start_date_label']}~{p['end_date_label']}  {p['total_yuan']:.0f}元  {r}")
