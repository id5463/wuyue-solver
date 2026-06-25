# -*- coding: utf-8 -*-
"""
plan_all.py - 把所有路线翻译成人话旅游计划, 包含每段公交/打车细节
输出: all_plans.md
"""
import json, sys, io, itertools
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open("data/mountains.json", "r", encoding="utf-8") as f: md = json.load(f)
with open("data/transit.json", "r", encoding="utf-8") as f: td = json.load(f)

M = md["mountains"]; TR = td["transit"]; EX = md["additional_transfer_h"]
H2M = td["hub_mountains"]; M2H = {v:k for k,v in H2M.items()}
SPEED = float(sys.argv[1]) if len(sys.argv) > 1 else md.get("speed_factor", 1.0)
BUF = md["min_transfer_buffer_h"]
MKEYS = ["taishan","huashan","hengshan_south","hengshan_north","songshan"]

STATION_CN = {"TA":"泰安站","ZZ":"郑州东站","HS":"华山北站","DT":"大同南站","HX":"衡山西站","PDF":"平顶山西站"}

# 每座山的详细本地交通说明
LOCAL_TRANSIT = {
    "TA": {
        "to_gate": "泰安站出站乘K3路/K37路公交(¥2)到红门登山口,约30分钟",
        "to_stn": "红门乘K3路回泰安站,约30分钟",
        "cost": 2, "time_h": 0.5,
    },
    "HS": {
        "to_gate": "华山北站出站打车(¥15)到玉泉院登山口,约20分钟",
        "to_stn": "玉泉院打车回华山北站(¥15),约20分钟",
        "cost": 15, "time_h": 0.5,
    },
    "HX": {
        "to_gate": "衡山西站乘南岳1路公交(¥6)到胜利坊登山口,约20分钟",
        "to_stn": "胜利坊乘南岳1路回衡山西站,约20分钟",
        "cost": 6, "time_h": 0.5,
    },
    "DT": {
        "to_gate": "大同南站乘901路公交(¥20)到浑源县城(1.5h),换景区摆渡车(¥20)到岳门湾,合计约2h",
        "to_stn": "岳门湾摆渡车→浑源→901路回大同南站,约2h",
        "cost": 20, "time_h": 1.5, "bus_cutoff": 17,
        "taxi": "⚠公交已停!打车到恒山约¥150,1h",
        "taxi_cost": 150, "taxi_time_h": 1.0,
    },
    "ZZ": {
        "to_gate": "郑州东站旁客运东站乘大巴(¥25)到登封(1.5h),再乘2路公交到嵩阳书院登山口(30min),合计约2h",
        "to_stn": "嵩阳书院→2路公交→登封客运站→大巴回郑州东站,约2h",
        "cost": 25, "time_h": 2.0, "bus_cutoff": 18,
        "taxi": "⚠大巴已停!打车到登封约¥200,1.5h",
        "taxi_cost": 200, "taxi_time_h": 1.5,
    },
    "PDF": {
        "to_gate": "平顶山市区乘公交到平顶山西站,约30分钟",
        "to_stn": "平顶山西站乘公交回市区,约30分钟",
        "cost": 30, "time_h": 2.0,
    },
}

def hm(t): return int(t.split(":")[0])*60 + int(t.split(":")[1])
def parse(t, base=0):
    t = t.strip()
    if t.startswith("+"): return base + 1440 + hm(t[1:])
    return base + hm(t)
def fmt(m):
    d, h, mi = m//1440, (m%1440)//60, m%60
    return f"第{d}天 {h:02d}:{mi:02d}" if d > 0 else f"{h:02d}:{mi:02d}"

def transits(frm, to, earliest):
    key = f"{frm}->{to}"
    if key not in TR: return []
    earliest = earliest + int(BUF * 60)
    opts, bd = [], (earliest//1440)*1440
    for t in TR[key]:
        d = parse(t["dep"], bd)
        while d < earliest: d += 1440
        if (d%1440)//60 < 6 or (d%1440)//60 >= 22: continue
        a = parse(t["arr"], (d//1440)*1440)
        if a <= d: a += 1440
        opts.append({"dep":d,"arr":a,"cost":t["cost"],"ttype":t.get("type","?"),"train":t.get("train",""),"frm":frm,"to":to})
    opts.sort(key=lambda x:(x["arr"],x["cost"]))
    return opts

def climb(mkey, arrive_hub):
    mt = M[mkey]; hub = M2H[mkey]; lt = LOCAL_TRANSIT[hub]
    to_gate_m = int(lt["time_h"]*60); to_stn_m = to_gate_m
    local_cost = lt["cost"]; bus_note = lt["to_gate"]
    cutoff = lt.get("bus_cutoff", 24)
    arrive_h = (arrive_hub % 1440) / 60
    if arrive_h >= cutoff and "taxi" in lt:
        to_gate_m = int(lt["taxi_time_h"]*60)
        local_cost = lt["taxi_cost"]
        bus_note = lt["taxi"]
    up = int(mt["hike_up_h"]*60*SPEED)
    dn_hike = int(mt["hike_down_h"]*60*SPEED)
    ticket = mt["ticket_yuan"]; cable_cost = mt.get("cable_car_down_yuan",0)
    night = mt["night_climb"]
    open_m, close_m = int(mt["open_hour"]*60), int(mt["close_hour"]*60)
    strategies = [("索道",30,cable_cost)] if cable_cost>0 else []
    strategies.append(("徒步",dn_hike,0))
    results = []
    for sname, dn_time, dn_cost in strategies:
        gate = arrive_hub + to_gate_m; ds = (gate//1440)*1440
        if not night:
            if gate < ds+open_m: gate = ds+open_m
            while gate >= ds+close_m: ds+=1440; gate=ds+open_m
            if gate+up > ds+close_m: ds+=1440; gate=ds+open_m
            if gate+up > ds+close_m: continue
        summit = gate+up+30; finish = summit+dn_time
        dep_hub = finish+to_stn_m
        money = ticket+dn_cost+local_cost
        results.append({"strategy":sname,"depart_hub":dep_hub,"money":money,
            "gate":gate,"summit":summit,"mtn_name":mt["name_cn"],
            "ticket":ticket,"cable":dn_cost,"bus":local_cost,"bus_note":bus_note,
            "lt":lt, "hub":hub})
    results.sort(key=lambda r:r["depart_hub"]+(r["money"]/50*60 if md["time_cost_per_hour_yuan"]>0 else 0))
    return results

def evaluate(perm, start_hub, start_t):
    states = [(start_t, start_hub, 0, [])]
    for mkey in perm:
        target_hub = M2H[mkey]; next_states = []
        for cur_t, cur_hub, cur_money, hist in states:
            if cur_hub == target_hub:
                t_opts = [{"dep":cur_t,"arr":cur_t,"cost":0,"ttype":"same","train":"","frm":cur_hub,"to":target_hub}]
            else:
                t_opts = transits(cur_hub, target_hub, cur_t)
                if not t_opts: continue
            for tr in t_opts[:5]:
                arr=tr["arr"]; money=cur_money+tr["cost"]
                h = hist+[{"kind":"transit","dep":tr["dep"],"arr":tr["arr"],"cost":tr["cost"],"train":tr["train"],"ttype":tr["ttype"],"frm":tr["frm"],"to":tr["to"]}]
                for co in climb(mkey, arr)[:2]:
                    next_states.append((co["depart_hub"],target_hub,money+co["money"],h+[{"kind":"climb","depart_hub":co["depart_hub"],"money":co["money"],"gate":co["gate"],"summit":co["summit"],"strategy":co["strategy"],"mtn_name":co["mtn_name"],"ticket":co["ticket"],"cable":co["cable"],"bus":co["bus"],"bus_note":co["bus_note"],"hub":co["hub"],"lt":co["lt"]}]))
        if not next_states: return None
        next_states.sort(key=lambda x:(x[1],x[0],x[2]))
        dedup=[]
        for ns in next_states:
            if dedup and dedup[-1][1]==ns[1] and abs(dedup[-1][0]-ns[0])<30:
                if ns[2]<dedup[-1][2]: dedup[-1]=ns
            else: dedup.append(ns)
        states=dedup[:30]
    home_states=[]
    for cur_t,cur_hub,cur_money,hist in states:
        if cur_hub=="PDF": home_states.append((cur_t,"PDF",cur_money,hist))
        else:
            for tr in transits(cur_hub,"PDF",cur_t)[:3]:
                home_states.append((tr["arr"],"PDF",cur_money+tr["cost"],hist+[{"kind":"transit","dep":tr["dep"],"arr":tr["arr"],"cost":tr["cost"],"train":tr["train"],"ttype":tr["ttype"],"frm":tr["frm"],"to":tr["to"]}]))
    if not home_states: return None
    best = min(home_states, key=lambda s:s[2])
    total_min=best[0]-start_t
    tn=total_min//1440
    train_n=sum(1 for s in best[3] if s["kind"]=="transit" and (s["dep"]%1440)//60>=18 and (s["arr"]-s["dep"])>240)
    hn=max(0,tn-train_n)
    return {"permutation":perm,"total_h":round(total_min/60,1),"actual_yuan":best[2],"accom_yuan":hn*50,"food_yuan":round(total_min/1440*30,0),"total_yuan":round(best[2]+hn*50+total_min/1440*30,0),"itinerary":best[3],"start_t":start_t,"hotel_nights":hn,"train_nights":train_n}

# ─── 生成计划 ───
DAY_NAMES = ["周六","周日","周一","周二","周三","周四","周五","周六","周日","周一","周二","周三","周四","周五"]

def gen_plan(route, rank):
    L=[]; p=lambda s:L.append(s)
    p(f"\n{'='*70}")
    p(f"  #{rank}  ¥{route['total_yuan']:.0f} | {route['total_h']}h | 住宿{route['hotel_nights']}晚(夜车{route['train_nights']}晚)")
    order = " → ".join(M[m]["name_cn"] for m in route["permutation"])
    p(f"  路线: {order}")
    p(f"{'='*70}")
    
    sn=0; train_sum=0; ticket_sum=0
    for item in route["itinerary"]:
        if item["kind"]=="transit":
            if item.get("frm","")==item.get("to",""): continue
            sn+=1; dep=item["dep"]; arr=item["arr"]
            dd,ad=dep//1440,arr//1440
            frm=STATION_CN.get(item["frm"],item["frm"]); to=STATION_CN.get(item["to"],item["to"])
            train=item["train"]; cost=item["cost"]; tt=item.get("ttype","?")
            dur=round((arr-dep)/60,1)
            if tt=="G": tname="高铁"
            elif tt=="D": tname="动车"
            elif tt in ("Z","K"): tname="普速"
            else: tname=tt
            ovn = " 💤夜车免住宿!" if (dep%1440)//60>=18 and dur>4 else ""
            ds=f"{DAY_NAMES[dd]} {fmt(dep)[-5:]}"; ars=f"{DAY_NAMES[ad]} {fmt(arr)[-5:]}"
            p(f"")
            p(f"  🚂 {sn}. {frm} → {to}")
            p(f"     {tname} {train}")
            p(f"     {ds} 出发 → {ars} 到达 ({dur}h){ovn}")
            p(f"     票价 ¥{cost}")
            train_sum+=cost
        elif item["kind"]=="climb":
            sn+=1; co=item
            gate=co["gate"]; summit=co["summit"]; dep_h=co["depart_hub"]
            gd,sd=gate//1440,summit//1440
            mtn=co["mtn_name"]; stg=co["strategy"]; money=co["money"]
            hub=co["hub"]; lt=co["lt"]
            
            p(f"")
            p(f"  ⛰️  {sn}. 登{mtn}")
            # 到站→公交→登山口
            p(f"     📍 到{STATION_CN.get(hub,hub)}后: {co['bus_note']}")
            p(f"     🥾 {DAY_NAMES[gd]} {fmt(gate)[-5:]} 到达登山口,开始爬山")
            p(f"     📸 {DAY_NAMES[sd]} {fmt(summit)[-5:]} 登顶!")
            p(f"     🔽 {stg}下山 → {DAY_NAMES[gd]} {fmt(dep_h)[-5:]} 回到火车站")
            # 下山后的本地交通
            p(f"     🚌 下山后: {lt['to_stn']}")
            p(f"     💰 门票¥{co['ticket']} + {stg}¥{co['cable']} + 公交¥{co['bus']} = ¥{money}")
            ticket_sum+=money
    
    p(f"")
    p(f"  {'─'*50}")
    p(f"  火车票合计: ¥{train_sum:.0f}")
    p(f"  门票+下山+公交: ¥{ticket_sum:.0f}")
    p(f"  住宿{route['hotel_nights']}晚: ¥{route['accom_yuan']:.0f}")
    p(f"  吃饭: ¥{route['food_yuan']:.0f}")
    p(f"  ★ 总计: ¥{route['total_yuan']:.0f}")
    return "\n".join(L)

# ─── main ───
if __name__ == "__main__":
    print("计算中...")
    all_r = []
    for sh in range(6, 20, 2):
        for perm in itertools.permutations(MKEYS):
            r = evaluate(list(perm), "PDF", sh*60)
            if r: all_r.append(r)
    all_r.sort(key=lambda x: x["total_yuan"])
    
    out_lines = ["# 五岳穷游全计划\n", f"共 {len(all_r)} 条路线, 按总花费从低到高排列\n"]
    for i, r in enumerate(all_r, 1):
        out_lines.append(gen_plan(r, i))
    
    with open("all_plans.md", "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
    
    print(f"✅ 已生成 {len(all_r)} 条计划 → all_plans.md")
    # 也打印第一条到控制台
    print(gen_plan(all_r[0], 1))
