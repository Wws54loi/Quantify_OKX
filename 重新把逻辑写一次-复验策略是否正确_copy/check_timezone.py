# -*- coding: utf-8 -*-
"""
检查时区转换问题
"""
import json
from datetime import datetime, timezone, timedelta

def ts_ms_to_str_utc(ts_ms: int) -> str:
    """UTC时区"""
    return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")

def ts_ms_to_str_utc8(ts_ms: int) -> str:
    """UTC+8时区"""
    utc8 = timezone(timedelta(hours=8))
    return datetime.fromtimestamp(ts_ms / 1000.0, tz=utc8).strftime("%Y-%m-%d %H:%M")

# 加载K线数据
with open('ethusdt_15m_klines.json', 'r', encoding='utf-8') as f:
    raw_data = json.load(f)

print("=== 检查交易#1415相关的时间戳转换 ===")

# 交易#1415的入场时间应该是2025-11-05 19:59
# 让我找找开盘价为3299.93和3455.58的K线

target_opens = [3299.93, 3455.58]
entry_time_target = "2025-11-05 19:59"

print(f"目标入场时间: {entry_time_target}")
print(f"寻找开盘价: {target_opens}")
print()

for i, kline in enumerate(raw_data[-1000:], len(raw_data)-1000):  # 查看最后1000根
    open_price = float(kline[1])
    
    if open_price in target_opens:
        ts = int(kline[0])
        utc_time = ts_ms_to_str_utc(ts)
        utc8_time = ts_ms_to_str_utc8(ts)
        
        print(f"索引 {i}: 开盘价 {open_price}")
        print(f"  时间戳: {ts}")
        print(f"  UTC时间: {utc_time}")
        print(f"  UTC+8时间: {utc8_time}")
        print()

print("=== 检查29956-29957附近的K线 ===")
for i in range(29954, 29960):
    if i < len(raw_data):
        kline = raw_data[i]
        ts = int(kline[0])
        open_price = float(kline[1])
        utc_time = ts_ms_to_str_utc(ts)
        utc8_time = ts_ms_to_str_utc8(ts)
        
        print(f"索引 {i}: 开盘价 {open_price:.2f}")
        print(f"  UTC: {utc_time}, UTC+8: {utc8_time}")