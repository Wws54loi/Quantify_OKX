# -*- coding: utf-8 -*-
"""
搜索开盘价为3299.93的K线
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

target_open = 3299.93

klines = load_klines()

print(f"搜索开盘价为 {target_open} 的K线:")
print()

found = False
for i, kline in enumerate(klines):
    if abs(kline['open'] - target_open) < 0.01:
        found = True
        time_str = ts_ms_to_str(kline['close_time'])
        print(f"找到匹配的K线 (索引 {i}):")
        print(f"  时间: {time_str}")
        print(f"  开: {kline['open']:.2f}, 高: {kline['high']:.2f}, 低: {kline['low']:.2f}, 收: {kline['close']:.2f}")
        
        # 检查附近的K线
        if i > 0:
            prev_kline = klines[i-1]
            prev_time = ts_ms_to_str(prev_kline['close_time'])
            print(f"  前一根K线 (索引 {i-1}):")
            print(f"    时间: {prev_time}")
            print(f"    开: {prev_kline['open']:.2f}, 高: {prev_kline['high']:.2f}, 低: {prev_kline['low']:.2f}, 收: {prev_kline['close']:.2f}")
        
        if i < len(klines) - 1:
            next_kline = klines[i+1]
            next_time = ts_ms_to_str(next_kline['close_time'])
            print(f"  后一根K线 (索引 {i+1}):")
            print(f"    时间: {next_time}")
            print(f"    开: {next_kline['open']:.2f}, 高: {next_kline['high']:.2f}, 低: {next_kline['low']:.2f}, 收: {next_kline['close']:.2f}")
        print("-" * 50)

if not found:
    print(f"没有找到开盘价为 {target_open} 的K线")
    
# 搜索接近的价格
print(f"\n搜索开盘价接近 {target_open} 的K线 (±5):")
for i, kline in enumerate(klines):
    if abs(kline['open'] - target_open) < 5.0:
        time_str = ts_ms_to_str(kline['close_time'])
        diff = kline['open'] - target_open
        print(f"索引 {i}: 时间:{time_str}, 开:{kline['open']:.2f} (差异:{diff:+.2f})")