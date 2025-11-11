# -*- coding: utf-8 -*-
"""
查找特定K线的交易
"""
import json
from datetime import datetime, timezone, timedelta

def ts_ms_to_str(ts_ms: int) -> str:
    utc8 = timezone(timedelta(hours=8))
    return datetime.fromtimestamp(ts_ms / 1000.0, tz=utc8).strftime("%Y-%m-%d %H:%M")

# 加载K线数据
with open('ethusdt_15m_klines.json', 'r', encoding='utf-8') as f:
    raw_data = json.load(f)

# 检查索引29924和29925
print("=== 检查K线索引29924-29925 ===")
for i in [29924, 29925]:
    if i < len(raw_data):
        kline = raw_data[i]
        ts = int(kline[0])
        open_p = float(kline[1])
        close_p = float(kline[4])
        time_str = ts_ms_to_str(ts)
        print(f"索引 {i}: {time_str}, 开:{open_p:.2f}, 收:{close_p:.2f}")

# 搜索CSV文件中对应的交易
import csv
print("\n=== 搜索CSV中的对应交易 ===")
with open('rule1_results_eth_140x.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        k1_open = float(row['k1_open'])
        k2_open = float(row['k2_open'])
        if abs(k1_open - 3299.93) < 0.01 or abs(k2_open - 3299.93) < 0.01:  # K1或K2开盘价匹配
            print(f"找到交易 #{row['trade_id']}")
            print(f"  入场时间: {row['entry_time']}")
            print(f"  入场价格: {row['entry_price']}")
            print(f"  K1: 开:{row['k1_open']}, 高:{row['k1_high']}, 低:{row['k1_low']}, 收:{row['k1_close']}")
            print(f"  K2: 开:{row['k2_open']}, 高:{row['k2_high']}, 低:{row['k2_low']}, 收:{row['k2_close']}")
            print()
            break