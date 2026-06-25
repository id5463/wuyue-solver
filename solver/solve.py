# -*- coding: utf-8 -*-
"""
五岳特种兵路线优化器 v2
目标: 最小化 总花费 = 实际花费(交通+门票+索道) + 时间成本(50元/小时)
约束: 换乘至少1h缓冲, 恒山/嵩山/衡山禁止夜爬
每个山尝试 索道下山 和 徒步下山 两种策略
"""
import json, itertools, sys, io
from datetime import datetime, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ─── 加载 ───────────────────────────────────────────
with open("data/mountains.json", "r", encoding="utf-8") as f:
    md = json.load(f)
with open("data/transit.json", "r", encoding="utf-8") as f:
    td = json.load(f)

M = md["mountains"]
TR = td["transit"]
HUBS = td["hubs"]

# 加载公交数据（真实班次时刻、路线、频率）
try:
    with open("data/bus_info.json", "r", encoding="utf-8") as f:
        BI = json.load(f)
except:
    BI = {}
H2M = td["hub_mountains"]
EX = md["additional_transfer_h"]
TC = md["time_cost_per_hour_yuan"]
BUF = md["min_transfer_buffer_h"]
SPEED = md.get("speed_factor", 1.0)
M2H = {v: k for k, v in H2M.items()}
MKEYS = ["taishan", "huashan", "hengshan_south", "hengshan_north", "songshan"]

# 命令行可以覆盖速度系数: python solve.py 0.35
if len(sys.argv) > 1:
    SPEED = float(sys.argv[1])

# ─── 时间工具 ───────────────────────────────────────────
def hm(m): return int(m.split(":")[0])*60 + int(m.split(":")[1])

def parse(t: str, base: int = 0) -> int:
    t = t.strip()
    if t.startswith("+"): return base + 1440 + hm(t[1:])
    return base + hm(t)

def fmt(m: int) -> str:
    d, h, mi = m//1440, (m%1440)//60, m%60
    return f"D{d} {h:02d}:{mi:02d}" if d > 0 else f"{h:02d}:{mi:02d}"

# ─── 中转 ───────────────────────────────────────────
def transits(frm: str, to: str, earliest: int) -> list:
    """查找最早出发>=earliest+60分钟的列车, 过滤阴间时间(06:00前/22:00后不发车)"""
    key = f"{frm}->{to}"
    if key not in TR: return []
    earliest = earliest + int(BUF * 60)
    opts = []
    bd = (earliest // 1440) * 1440
    for t in TR[key]:
        d = parse(t["dep"], bd)
        while d < earliest: d += 1440
        # 过滤阴间时间: 只允许06:00-22:00出发
        hour_of_day = (d % 1440) // 60
        if hour_of_day < 6 or hour_of_day >= 22:
            continue
        a = parse(t["arr"], (d//1440)*1440)
        if a <= d: a += 1440
        opts.append({"dep": d, "arr": a, "cost": t["cost"],
                     "type": t.get("type","?"), "train": t.get("train",""),
                     "frm": frm, "to": to})
    opts.sort(key=lambda x: (x["arr"], x["cost"]))
    return opts

# ─── 公交时间计算（基于真实班次频率/时刻） ────────────────
def _calc_bus_step(arrival_min, step, freq_db):
    """
    给定到达时间（分钟），计算这个公交步骤的完成时间和费用。
    返回 (completed_min, cost) 或 None（没车了）
    """
    if step["mode"] == "walk":
        return (arrival_min + step["duration_min"], 0)
    
    bus_name = step["bus_name"]
    fb = step["first_min"]   # 首班分钟数
    lb = step["last_min"]    # 末班分钟数
    tod = arrival_min % 1440 # 当天时间（分钟）
    
    # 检查是否在运营时间内
    if tod < fb or tod > lb:
        return None
    
    freq = freq_db.get(bus_name, {})
    interval = freq.get("interval_min", 15)
    fixed = freq.get("fixed", [])
    
    if fixed:
        # 固定班次（如机场巴士登封线有具体发车时间）
        today_midnight = (arrival_min // 1440) * 1440
        next_dep = None
        for t_str in fixed:
            h, m = t_str.split(":")
            t_min = int(h)*60 + int(m)
            dep_time = today_midnight + t_min
            if dep_time >= arrival_min:
                next_dep = dep_time
                break
        if next_dep is None:
            return None  # 今日已无班次
        depart = next_dep
    else:
        # 按首班+频率计算下一班
        today_first = (arrival_min // 1440) * 1440 + fb
        if arrival_min <= today_first:
            depart = today_first
        elif interval > 0:
            wait = ((arrival_min - today_first + interval - 1) // interval) * interval
            depart = today_first + wait
        else:
            depart = arrival_min
    
    cost = freq.get("price", step.get("price", 0))
    return (depart + step["duration_min"], cost)


def _calc_route_time(arrival_min, route_steps, freq_db):
    """
    计算整条公交路线从站到门的总时间和费用。
    返回 (gate_arrival_min, total_cost) 或 (None, None)
    """
    cur = arrival_min
    total_cost = 0
    for step in route_steps:
        res = _calc_bus_step(cur, step, freq_db)
        if res is None:
            return (None, None)
        cur, cost = res
        total_cost += cost
    return (cur, total_cost)


# ─── 爬山 (返回两种策略) ─────────────────────────────────
def climb(mkey: str, arrive_hub: int):
    """
    返回 [(策略名, depart_hub, money, details), ...]
    使用 bus_info.json 的真实公交数据（5条路线全部尝试）
    """
    mt = M[mkey]; hub = M2H[mkey]; ex = EX[hub]
    bus_hub = BI.get(hub, {})
    routes = bus_hub.get("routes", [])
    freq_db = bus_hub.get("freq", {})
    taxi = bus_hub.get("taxi", {})
    
    # 旧硬编码值（当无公交数据时fallback用）
    old_to_gate = int(ex["station_to_mountain"]*60)
    old_to_stn = int(ex["mountain_to_station"]*60)
    old_local_bus = ex.get("local_bus_cost", 0)
    old_cutoff = ex.get("bus_cutoff_h", 24)
    old_taxi_cost = ex.get("taxi_cost", 0)
    old_taxi_min = int(ex.get("taxi_time_h", ex["station_to_mountain"]) * 60)
    
    # ── 计算去程时间 + 费用（尝试所有公交路线，选最佳） ──
    best_gate = None   # (gate_arrival, bus_cost, used_route_index)
    if routes and freq_db:
        for ri, route in enumerate(routes):
            res = _calc_route_time(arrive_hub, route["steps"], freq_db)
            if res[0] is not None:
                gate_t, bus_c = res
                gate_dur = gate_t - arrive_hub
                if best_gate is None or gate_dur < best_gate[0]:
                    best_gate = (gate_dur, bus_c, ri)
    
    if best_gate is None:
        # 没公交了→打车或fallback
        arrive_h = (arrive_hub % 1440) / 60
        if taxi:
            to_gate = int(taxi["time_min"])
            local_bus = int(taxi["cost"])
        elif arrive_h >= old_cutoff:
            to_gate = int(old_taxi_min)
            local_bus = int(old_taxi_cost)
        else:
            to_gate = int(old_to_gate)
            local_bus = int(old_local_bus)
    else:
        to_gate = int(best_gate[0])
        local_bus = int(best_gate[1])
    
    up = int(mt["hike_up_h"]*60 * SPEED)
    dn_hike = int(mt["hike_down_h"]*60 * SPEED)
    dn_cable = 30
    ticket = mt["ticket_yuan"]
    cable_cost = mt.get("cable_car_down_yuan", 0)
    night = mt["night_climb"]
    open_m = int(mt["open_hour"]*60)
    close_m = int(mt["close_hour"]*60)
    
    results = []
    strategies = [("索道", dn_cable, cable_cost)] if cable_cost > 0 else []
    strategies.append(("徒步", dn_hike, 0))
    
    for sname, dn_time, dn_cost in strategies:
        gate = arrive_hub + to_gate
        ds = (gate // 1440) * 1440
        
        if not night:
            if gate < ds + open_m:
                gate = ds + open_m
            while gate >= ds + close_m:
                ds += 1440
                gate = ds + open_m
            if gate + up > ds + close_m:
                ds += 1440
                gate = ds + open_m
                if gate + up > ds + close_m:
                    continue
        
        summit = gate + up + 30
        finish = summit + dn_time
        
        # ── 回程（同样尝试公交路线，方向反转） ──
        return_time = int(old_to_stn)  # fallback
        return_cost = 0
        if routes and freq_db:
            best_back = None
            for route in routes:
                rev_steps = list(reversed(route["steps"]))
                res = _calc_route_time(finish, rev_steps, freq_db)
                if res[0] is not None:
                    back_dur = int(res[0] - finish)
                    if best_back is None or back_dur < best_back[0]:
                        best_back = (back_dur, int(res[1]))
            if best_back:
                return_time = best_back[0]
                return_cost = best_back[1]
            elif taxi:
                return_time = int(taxi["time_min"])
                return_cost = int(taxi["cost"])
        elif taxi:
            return_time = int(taxi["time_min"])
            return_cost = int(taxi["cost"])
        
        dep_hub = finish + int(return_time)
        money = ticket + dn_cost + int(local_bus) + int(return_cost)
        
        results.append({
            "strategy": sname,
            "depart_hub": int(dep_hub),
            "money": int(money),
            "gate": int(gate),
            "summit": int(summit),
            "total_min": int(dep_hub - arrive_hub),
        })
    
    if TC > 0:
        results.sort(key=lambda r: r["depart_hub"] + r["money"]/TC*60)
    else:
        results.sort(key=lambda r: (r["money"], r["depart_hub"]))
    return results

# ─── 评估一条路线 (动规: 每个山试所有策略) ──────────────────
def evaluate(perm: list, start_hub: str, start_t: int):
    """
    对给定顺序, 用BFS/DP找最优中转+爬山组合.
    返回最优的完整路线, 或None.
    """
    # state: (time, hub, money, history)
    states = [(start_t, start_hub, 0, [])]
    
    for mkey in perm:
        target_hub = M2H[mkey]
        next_states = []
        
        for cur_t, cur_hub, cur_money, hist in states:
            # 找所有可行中转
            if cur_hub == target_hub:
                # 同站: 已经在目标城市, 直接去爬山, 不用坐火车
                t_opts = [{"dep": cur_t, "arr": cur_t, "cost": 0, "type": "same",
                            "train": "", "frm": cur_hub, "to": target_hub}]
            else:
                t_opts = transits(cur_hub, target_hub, cur_t)
                if not t_opts:
                    continue
            
            for tr_opt in t_opts[:8]:  # 取前8个最优中转
                arr = tr_opt["arr"]
                money = cur_money + tr_opt["cost"]
                history = hist + [{"kind": "transit", "dep": tr_opt["dep"], 
                    "arr": tr_opt["arr"], "cost": tr_opt["cost"],
                    "train": tr_opt["train"], "ttype": tr_opt.get("type","?"),
                    "frm": tr_opt["frm"], "to": tr_opt["to"],
                    "sleeper": tr_opt.get("sleeper", False)}]
                
                # 爬山策略
                climb_opts = climb(mkey, arr)
                for co in climb_opts[:3]:  # 每个山最多试3种策略
                    new_t = co["depart_hub"]
                    new_money = money + co["money"]
                    new_hist = history + [{"kind": "climb", **co,
                                           "mountain": M[mkey]["name_cn"],
                                           "mkey": mkey,
                                           "gate_str": fmt(co["gate"]),
                                           "summit_str": fmt(co["summit"]),
                                           "dep_hub_str": fmt(co["depart_hub"])}]
                    next_states.append((new_t, target_hub, new_money, new_hist))
        
        if not next_states:
            return None
        # 去重: 相同hub+time, 保留money最小的
        next_states.sort(key=lambda x: (x[1], x[0], x[2]))
        dedup = []
        for ns in next_states:
            if dedup and dedup[-1][1] == ns[1] and abs(dedup[-1][0] - ns[0]) < 30:
                if ns[2] < dedup[-1][2]:
                    dedup[-1] = ns
            else:
                dedup.append(ns)
        states = dedup[:50]  # 每层最多保留50个状态
    
    # ─── 回家! 从最后一座山的hub回到平顶山(PDF) ───
    home_states = []
    for cur_t, cur_hub, cur_money, hist in states:
        if cur_hub == "PDF":
            home_states.append((cur_t, "PDF", cur_money, hist))
        else:
            t_opts = transits(cur_hub, "PDF", cur_t)
            if not t_opts:
                continue
            for tr_opt in t_opts[:5]:
                home_states.append((
                    tr_opt["arr"],
                    "PDF",
                    cur_money + tr_opt["cost"],
                    hist + [{"kind": "transit", "dep": tr_opt["dep"],
                             "arr": tr_opt["arr"], "cost": tr_opt["cost"],
                             "train": tr_opt["train"], "ttype": tr_opt.get("type","?"),
                             "frm": tr_opt["frm"], "to": tr_opt["to"],
                             "sleeper": tr_opt.get("sleeper", False)}]
                ))
    
    if not home_states:
        return None
    states = home_states
    
    if not states:
        return None
    
    # 找最优
    best = min(states, key=lambda s: s[2] + (s[0]-start_t)/60*TC)
    total_min = best[0] - start_t
    total_nights = total_min // 1440
    
    # 统计夜火车覆盖的夜晚: sleeper标记的火车=省一晚
    train_nights = sum(1 for s in best[3] 
                       if s.get("kind","") != "climb" and s.get("sleeper", False))
    
    hotel_nights = max(0, total_nights - train_nights)
    accom = hotel_nights * md.get("accommodation_per_night_yuan", 50)
    food = (total_min / 1440) * md.get("food_per_day_yuan", 30)  # 按天数算吃饭
    return {
        "permutation": perm,
        "total_yuan": round(best[2] + total_min/60*TC + accom + food, 0),
        "total_h": round(total_min/60, 1),
        "actual_yuan": best[2],
        "accom_yuan": accom,
        "food_yuan": round(food, 0),
        "time_cost_yuan": round(total_min/60*TC, 0),
        "itinerary": best[3],
        "start": fmt(start_t),
        "start_t": start_t,
        "nights": total_nights,
        "hotel_nights": hotel_nights,
        "train_nights": train_nights,
    }

# ─── 带日期的 JSON 输出 ─────────────────────────────────
START_DATE = "20260701"
TRANSIT_LOOKUP = None  # lazy load

def build_transit_lookup():
    """建立 (frm, to, train) -> dep/arr 的快速查找表"""
    global TRANSIT_LOOKUP
    if TRANSIT_LOOKUP is not None:
        return TRANSIT_LOOKUP
    TRANSIT_LOOKUP = {}
    for key, trains in TR.items():
        frm, to = key.split("->")
        for t in trains:
            tn = t.get("train", "")
            if tn:
                TRANSIT_LOOKUP[(frm, to, tn)] = (t["dep"], t["arr"])
    return TRANSIT_LOOKUP

def min_to_date_str(minutes: int) -> str:
    """将绝对分钟值转换为 YYYYMMDD 日期字符串"""
    start = datetime.strptime(START_DATE, "%Y%m%d")
    d = start + timedelta(days=minutes // 1440)
    return d.strftime("%Y%m%d")

def min_to_time_str(minutes: int) -> str:
    """将绝对分钟值转换为 HH:MM 时间字符串"""
    h = (minutes % 1440) // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"

def min_to_datetime_str(minutes: int) -> str:
    """将绝对分钟值转换为 YYYYMMDD HH:MM 字符串"""
    start = datetime.strptime(START_DATE, "%Y%m%d")
    d = start + timedelta(days=minutes // 1440)
    h = (minutes % 1440) // 60
    m = minutes % 60
    return f"{d.strftime('%Y%m%d')} {h:02d}:{m:02d}"

def get_calendar_weekday(minutes: int) -> str:
    """返回中文星期几"""
    start = datetime.strptime(START_DATE, "%Y%m%d")
    d = start + timedelta(days=minutes // 1440)
    weekdays = ["周一","周二","周三","周四","周五","周六","周日"]
    return weekdays[d.weekday()]

def save_top20_json(all_r, top_n=20):
    """保存前 top_n 条路线为带日期的 JSON"""
    build_transit_lookup()
    top20 = []
    
    for rank, r in enumerate(all_r[:top_n], 1):
        start_t = r.get("start_t", 0)
        
        steps = []
        for s in r["itinerary"]:
            if s.get("kind") == "transit":
                frm = s["frm"]; to = s["to"]
                if frm == to:
                    continue
                dep_min = s.get("dep", 0)
                arr_min = s.get("arr", 0)
                train = s.get("train", "")
                
                # 从原始数据中查实际发车/到达时间
                actual_dep = s.get("dep_str", "")
                actual_arr = s.get("arr_str", "")
                # 如果 dep_str/arr_str 未存, 则从分钟值推算
                if not actual_dep or actual_dep == "?":
                    # 尝试从 transit 查找表获取原始时间
                    lookup_key = (frm, to, train)
                    if lookup_key in TRANSIT_LOOKUP:
                        actual_dep, actual_arr = TRANSIT_LOOKUP[lookup_key]
                    else:
                        actual_dep = min_to_time_str(dep_min)
                        actual_arr = min_to_time_str(arr_min)
                
                steps.append({
                    "type": "train",
                    "from": frm,
                    "to": to,
                    "train": train,
                    "dep": actual_dep,
                    "arr": actual_arr,
                    "dep_date": min_to_date_str(dep_min),
                    "arr_date": min_to_date_str(arr_min),
                    "dep_datetime": min_to_datetime_str(dep_min),
                    "arr_datetime": min_to_datetime_str(arr_min),
                    "dep_day": dep_min // 1440,
                    "arr_day": arr_min // 1440,
                    "dep_weekday": get_calendar_weekday(dep_min),
                    "arr_weekday": get_calendar_weekday(arr_min),
                    "cost": s.get("cost", 0),
                    "sleeper": s.get("sleeper", False),
                    "ttype": s.get("ttype", "?"),
                })
                
            elif s.get("kind") == "climb":
                gate_min = s.get("gate", 0)
                summit_min = s.get("summit", 0)
                dep_hub_min = s.get("depart_hub", 0)
                
                steps.append({
                    "type": "climb",
                    "mountain": s.get("mountain", ""),
                    "strategy": s.get("strategy", "徒步"),
                    "gate_time": min_to_time_str(gate_min),
                    "gate_date": min_to_date_str(gate_min),
                    "gate_datetime": min_to_datetime_str(gate_min),
                    "gate_weekday": get_calendar_weekday(gate_min),
                    "summit_time": min_to_time_str(summit_min),
                    "summit_date": min_to_date_str(summit_min),
                    "summit_datetime": min_to_datetime_str(summit_min),
                    "summit_weekday": get_calendar_weekday(summit_min),
                    "depart_station_time": min_to_time_str(dep_hub_min),
                    "depart_station_date": min_to_date_str(dep_hub_min),
                    "depart_station_datetime": min_to_datetime_str(dep_hub_min),
                    "depart_station_weekday": get_calendar_weekday(dep_hub_min),
                    "cost": s.get("money", 0),
                    "ticket": s.get("ticket", 0),
                    "cable": s.get("cable", 0),
                    "bus": s.get("bus", 0),
                })
        
        # 路线的起止日期
        first_step = steps[0] if steps else {}
        last_step = steps[-1] if steps else {}
        
        top20.append({
            "rank": rank,
            "total_yuan": r["total_yuan"],
            "total_h": r["total_h"],
            "actual_yuan": r["actual_yuan"],
            "accom_yuan": r.get("accom_yuan", 0),
            "food_yuan": r.get("food_yuan", 0),
            "start_date": START_DATE,
            "start_time": r["start"],
            "route": [M[m]["name_cn"] for m in r["permutation"]],
            "steps": steps,
        })
    
    with open("top20.json", "w", encoding="utf-8") as f:
        json.dump(top20, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ top20.json 已生成 ({len(top20)} 条路线, 起点 {START_DATE})")
    print(f"   展示前3条摘要:")
    for pi, p in enumerate(top20[:3]):
        route_str = " → ".join(p["route"])
        print(f"   #{p['rank']}: {route_str} ¥{p['total_yuan']:.0f} {p['total_h']}h")
        for st in p["steps"][:3]:
            if st["type"] == "train":
                print(f"     🚂 {st['from']}→{st['to']} {st['train']} {st['dep_datetime']}→{st['arr_datetime']}")
            else:
                print(f"     ⛰️ {st['mountain']} {st['gate_datetime']} 进山 → {st['summit_datetime']} 登顶")

# ─── 主函数 ───────────────────────────────────────────
def main():
    all_r = []
    for start_hub in ["PDF"]:
        for sh in range(6, 20, 2):
            st = sh * 60
            for perm in itertools.permutations(MKEYS):
                r = evaluate(list(perm), start_hub, st)
                if r: all_r.append(r)
    
    all_r.sort(key=lambda x: x["total_yuan"])
    
    # 生成 markdown 文件 + 控制台输出
    md_lines = []
    def out(s):
        print(s)
        md_lines.append(s)
    
    out("=" * 80)
    out(f"五岳特种兵 最优路线 (时间成本={TC}元/h, 速度系数={SPEED})")
    out("=" * 80)
    
    max_show = min(200, len(all_r))
    shown = 0
    max_h = 168  # 最多7天
    for rank, r in enumerate(all_r[:max_show], 1):
        if r['total_h'] > max_h:
            continue
        shown += 1
        out(f"\n{'─'*70}")
        out(f"[{shown}] 总: {r['total_yuan']:.0f}元 | {r['total_h']:.1f}h | "
              f"票{r['actual_yuan']}元+住{r.get('accom_yuan',0)}+吃{r.get('food_yuan',0)}"
              f"(夜车{r.get('train_nights',0)}晚) | {r['start']}出发")
        out(f"    路线: {' -> '.join(M[m]['name_cn'] for m in r['permutation'])}")
        for s in r["itinerary"]:
            if s.get("kind") == "climb":
                mtn = s.get('mountain', s.get('mkey','?'))
                stg = s.get('strategy','?'); summit = s.get('summit_str','?')
                dep = s.get('dep_hub_str','?'); money = s.get('money',0)
                out(f"    [山] {mtn}({stg}下山) 登顶{summit} 出站{dep} +{money}元")
            else:
                frm = s.get('frm','?'); to = s.get('to','?')
                train = s.get('train','?'); dep_s = s.get('dep_str','?')
                arr = s.get('arr_str','?'); cost = s.get('cost',0)
                dtype = s.get('ttype','?'); sleeper = s.get('sleeper', False)
                if frm == to: continue
                slp = " 💤卧铺" if sleeper else ""
                out(f"    [车] {frm}->{to} {dtype}{train} ({dep_s}->{arr}) ¥{cost}{slp}")
    
    out(f"\n{'='*80}")
    out(f"共 {len(all_r)} 条可行路线")
    
    d3 = [r for r in all_r if r['total_h'] <= 72]
    d5 = [r for r in all_r if r['total_h'] <= 120]
    out(f"\n3天内: {'无!' if not d3 else f'{len(d3)}条, 最优 {d3[0]['total_yuan']:.0f}元 {d3[0]['total_h']:.1f}h'}")
    out(f"5天内: {'无!' if not d5 else f'{len(d5)}条, 最优 {d5[0]['total_yuan']:.0f}元 {d5[0]['total_h']:.1f}h'}")
    
    # 写文件
    fname = f"result_speed{SPEED}.md"
    with open(fname, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    out(f"\n✅ 完整结果已保存到 {fname}")
    
    # 保存 top 200 带日期的 JSON
    save_top20_json(all_r, top_n=200)

if __name__ == "__main__":
    main()
