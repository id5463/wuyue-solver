# -*- coding: utf-8 -*-
"""检查 bus_schedules.json 里有啥，缺啥"""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open("data/bus_schedules.json", "r", encoding="utf-8") as f:
    data = json.load(f)

KEYS = {
    "TA_transit": ("泰安站", "泰山红门"),
    "HS_transit": ("华山北站", "华山玉泉院"),
    "HX_transit": ("衡山西站", "衡山胜利坊"),
    "DT_transit": ("大同南站", "恒山岳门湾"),
    "ZZ_transit": ("郑州东站", "嵩山嵩阳书院"),
}

for k, (frm, to) in KEYS.items():
    routes = data.get(k, {}).get("result", {}).get("routes", [])
    best = routes[0] if routes else None
    if not best:
        print(f"\n【{frm}→{to}】❌ 无数据")
        continue
    
    price = best.get("price", 0)
    dur = best.get("duration", 0)
    steps = best.get("steps", [])
    
    print(f"\n【{frm}→{to}】¥{price} {dur//60}分钟")
    
    for si, step_list in enumerate(steps):
        if not step_list or not isinstance(step_list, list):
            continue
        item = step_list[0]
        instr = item.get("instruction", "")
        veh = item.get("vehicle", {})
        bus_name = veh.get("name", "")
        step_type = veh.get("type", 0)
        
        if step_type == 0 and not bus_name:
            print(f"  🚶 {instr}")
        else:
            start_time = veh.get("start_time", "")
            end_time = veh.get("end_time", "")
            stop_num = veh.get("stop_num", 0)
            print(f"  🚌 {instr}")
            print(f"    首班{start_time} 末班{end_time} {stop_num}站")

print("\n\n====== 总结 ======")
print("""
✅ 已有：从火车站到登山口的公交路线数据（每个站都有）
❌ 缺的：
  1. 登山口回火车站的公交路线（反向数据）
  2. 具体班次时刻表（现在只有首末班时间）
  3. 这些数据还没整合到 solve.py 里

目前 solve.py 用的是 mountains.json 里的硬编码值：
  station_to_mountain: 0.5~2小时
  local_bus_cost: ¥2~25
  bus_cutoff_h: 17~22点
这些是凭感觉填的，不是真实公交数据。
""")
