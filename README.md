# 穷游路线优化器 (Budget Travel Route Optimizer)

基于真实交通数据（12306火车票 + 百度地图公交），穷举所有可行路线，找到最优方案。

## 做什么

输入：起点城市、目的地列表、预算约束、时间约束  
输出：总花费最低的完整行程，精确到每段火车车次、公交线路、登山时间

## 目录

```
solver/   核心代码
  solve.py       穷举优化引擎
  build_transit.py  12306→transit.json 数据构建
  plan_all.py    人话行程计划生成
data/
  mountains.json 五岳数据（开放可改）
  transit.json   城际交通（12306实时→缓存）
```

## 快速开始

```bash
pip install -r requirements.txt
python solver/solve.py           # 默认: 时间成本0, 普通人速度
python solver/solve.py 0.7       # 经常锻炼
python solver/build_transit.py    # 重新抓12306数据
python solver/plan_all.py         # 生成全部人话计划
```

## 自定义

改 `data/mountains.json` 换山/改约束/调速度。`transit.json` 由 12306 MCP 自动构建。

## 限制

只支持中国五岳。扩展到其他目的地需添加 `mountains.json` 条目 + 对应交通数据。

## License

MIT — 自由使用，修改请建立副本 (fork)。
