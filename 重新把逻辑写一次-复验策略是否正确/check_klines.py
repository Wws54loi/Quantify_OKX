# -*- coding: utf-8 -*-
"""
检查原始K线数据，找出交易#1415对应的真实K1和K2
"""
import json
import os
from datetime import datetime, timezone

def ts_ms_to_str(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")

def load_klines():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, 'ethusdt_15m_klines.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    
    # 取最后30000根
    data = raw[-30000:] if len(raw) > 30000 else raw
    
    klines = []
    for row in data:
        klines.append({
            'open_time': int(row[0]),
            'open': float(row[1]),
            'high': float(row[2]),
            'low': float(row[3]),
            'close': float(row[4]),
            'close_time': int(row[6]) if len(row) > 6 else (int(row[0]) + 15*60*1000)
        })
    return klines

# 交易#1415的入场时间是 2025-11-05 19:59，入场价格是3455.12
target_time = "2025-11-05 19:59"
target_price = 3455.12

klines = load_klines()

print(f"总K线数量: {len(klines)}")
print(f"寻找入场时间: {target_time}")
print(f"寻找入场价格: {target_price}")
print()

# 寻找匹配的K线
for i, kline in enumerate(klines):
    time_str = ts_ms_to_str(kline['close_time'])
    if abs(kline['close'] - target_price) < 0.01:  # 价格匹配
        print(f"找到匹配的K线 (索引 {i}):")
        print(f"  时间: {time_str}")
        print(f"  开: {kline['open']:.2f}, 高: {kline['high']:.2f}, 低: {kline['low']:.2f}, 收: {kline['close']:.2f}")
        
        if i > 0:
            k1 = klines[i-1]
            k1_time = ts_ms_to_str(k1['close_time'])
            print(f"  对应的K1 (索引 {i-1}):")
            print(f"    时间: {k1_time}")
            print(f"    开: {k1['open']:.2f}, 高: {k1['high']:.2f}, 低: {k1['low']:.2f}, 收: {k1['close']:.2f}")
        print()

# 也按时间搜索
print("=== 按时间搜索 ===")
target_timestamp = int(datetime.strptime("2025-11-05 19:59", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp() * 1000)

for i, kline in enumerate(klines):
    if abs(kline['close_time'] - target_timestamp) < 5*60*1000:  # 5分钟误差
        time_str = ts_ms_to_str(kline['close_time'])
        print(f"接近时间的K线 (索引 {i}):")
        print(f"  时间: {time_str}")
        print(f"  开: {kline['open']:.2f}, 高: {kline['high']:.2f}, 低: {kline['low']:.2f}, 收: {kline['close']:.2f}")
        
        if i > 0:
            k1 = klines[i-1]
            k1_time = ts_ms_to_str(k1['close_time'])
            print(f"  对应的K1 (索引 {i-1}):")
            print(f"    时间: {k1_time}")
            print(f"    开: {k1['open']:.2f}, 高: {k1['high']:.2f}, 低: {k1['low']:.2f}, 收: {k1['close']:.2f}")
        print()