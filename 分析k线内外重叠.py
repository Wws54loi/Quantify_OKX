"""
分析交易重叠情况按K线数量分类
1. 十条K线内的重叠
2. 十条K线外的重叠
"""

import pandas as pd
from datetime import datetime

# 读取交易日志
df = pd.read_csv('trade_log.csv')

# 转换时间格式
df['入场时间'] = pd.to_datetime(df['入场时间'])
df['出场时间'] = pd.to_datetime(df['出场时间'])

# 存储所有的重叠情况
overlaps_within_10 = []  # 十条K线内的重叠
overlaps_beyond_10 = []  # 十条K线外的重叠

# 遍历每一笔交易
for i in range(len(df)):
    trade_i = df.iloc[i]
    entry_i = trade_i['入场时间']
    exit_i = trade_i['出场时间']
    direction_i = trade_i['方向']
    holding_klines_i = trade_i['持仓K线数']
    
    # 检查后续交易是否与当前交易重叠
    for j in range(i + 1, len(df)):
        trade_j = df.iloc[j]
        entry_j = trade_j['入场时间']
        exit_j = trade_j['出场时间']
        direction_j = trade_j['方向']
        holding_klines_j = trade_j['持仓K线数']
        
        # 如果trade_j在trade_i结束后才开始，后续交易也不会重叠
        if entry_j >= exit_i:
            break
        
        # 检查是否有时间重叠
        if entry_j < exit_i:
            # 计算重叠时长
            overlap_start = entry_j
            overlap_end = min(exit_i, exit_j)
            overlap_duration = (overlap_end - overlap_start).total_seconds() / 60  # 分钟
            
            # 计算重叠K线数（按15分钟一根计算）
            overlap_klines = overlap_duration / 15
            
            # 确定重叠类型
            if direction_i == direction_j:
                if direction_i == '做多':
                    overlap_type = '双倍做多'
                else:
                    overlap_type = '双倍做空'
            else:
                overlap_type = '方向冲突'
            
            # 计算收益
            trade_i_profit_pct = float(trade_i['价格变动%'].rstrip('%'))
            trade_j_profit_pct = float(trade_j['价格变动%'].rstrip('%'))
            combined_profit_pct = trade_i_profit_pct + trade_j_profit_pct
            
            # 计算第一笔交易在重叠发生时已经持仓了多少根K线
            klines_before_overlap = (entry_j - entry_i).total_seconds() / 60 / 15
            
            # 构建重叠信息
            overlap_info = {
                '第一笔交易号': trade_i['交易编号'],
                '第一笔方向': direction_i,
                '第一笔入场': entry_i,
                '第一笔出场': exit_i,
                '第一笔持仓K线数': holding_klines_i,
                '第一笔收益%': trade_i_profit_pct,
                '第一笔结果': trade_i['结果'],
                '第二笔交易号': trade_j['交易编号'],
                '第二笔方向': direction_j,
                '第二笔入场': entry_j,
                '第二笔出场': exit_j,
                '第二笔持仓K线数': holding_klines_j,
                '第二笔收益%': trade_j_profit_pct,
                '第二笔结果': trade_j['结果'],
                '重叠类型': overlap_type,
                '重叠开始': overlap_start,
                '重叠结束': overlap_end,
                '重叠时长(分钟)': overlap_duration,
                '重叠K线数': overlap_klines,
                '第一笔重叠前已持仓K线数': klines_before_overlap,
                '综合收益%': combined_profit_pct,
                '第一笔合约收益%': float(trade_i['合约收益%'].rstrip('%')),
                '第二笔合约收益%': float(trade_j['合约收益%'].rstrip('%'))
            }
            
            # 按照第一笔交易持仓K线数分类
            if klines_before_overlap <= 10:
                overlaps_within_10.append(overlap_info)
            else:
                overlaps_beyond_10.append(overlap_info)

# 转换为DataFrame
df_within_10 = pd.DataFrame(overlaps_within_10)
df_beyond_10 = pd.DataFrame(overlaps_beyond_10)

total_overlaps = len(overlaps_within_10) + len(overlaps_beyond_10)

print("=" * 100)
print("K线内外重叠分析报告")
print("=" * 100)

print(f"\n总重叠次数: {total_overlaps}")
print(f"十条K线内重叠: {len(overlaps_within_10)} 次 ({len(overlaps_within_10)/total_overlaps*100:.2f}%)")
print(f"十条K线外重叠: {len(overlaps_beyond_10)} 次 ({len(overlaps_beyond_10)/total_overlaps*100:.2f}%)")

# 十条K线内的详细分析
if len(df_within_10) > 0:
    print("\n" + "=" * 100)
    print("【十条K线内的重叠】详细分析")
    print("=" * 100)
    
    df_within_10.to_csv('十条K线内重叠详情.csv', index=False, encoding='utf-8-sig')
    
    print(f"\n总次数: {len(df_within_10)}")
    print(f"平均第一笔持仓K线数: {df_within_10['第一笔重叠前已持仓K线数'].mean():.2f}")
    print(f"平均重叠K线数: {df_within_10['重叠K线数'].mean():.2f}")
    print(f"平均重叠时长: {df_within_10['重叠时长(分钟)'].mean():.2f} 分钟")
    
    # 按重叠类型统计
    print("\n按重叠类型统计:")
    for overlap_type in ['双倍做多', '双倍做空', '方向冲突']:
        type_df = df_within_10[df_within_10['重叠类型'] == overlap_type]
        if len(type_df) > 0:
            print(f"\n  {overlap_type}:")
            print(f"    次数: {len(type_df)} ({len(type_df)/len(df_within_10)*100:.2f}%)")
            print(f"    平均综合收益: {type_df['综合收益%'].mean():.3f}%")
            profit_count = len(type_df[type_df['综合收益%'] > 0])
            print(f"    盈利次数: {profit_count} ({profit_count/len(type_df)*100:.2f}%)")
    
    # 按第一笔持仓K线数分组统计
    print("\n按第一笔已持仓K线数分组:")
    for i in range(0, 11, 2):
        range_df = df_within_10[(df_within_10['第一笔重叠前已持仓K线数'] >= i) & 
                                 (df_within_10['第一笔重叠前已持仓K线数'] < i+2)]
        if len(range_df) > 0:
            print(f"  {i}-{i+1}根K线: {len(range_df)}次, 平均综合收益: {range_df['综合收益%'].mean():.3f}%")

# 十条K线外的详细分析
if len(df_beyond_10) > 0:
    print("\n" + "=" * 100)
    print("【十条K线外的重叠】详细分析")
    print("=" * 100)
    
    df_beyond_10.to_csv('十条K线外重叠详情.csv', index=False, encoding='utf-8-sig')
    
    print(f"\n总次数: {len(df_beyond_10)}")
    print(f"平均第一笔持仓K线数: {df_beyond_10['第一笔重叠前已持仓K线数'].mean():.2f}")
    print(f"平均重叠K线数: {df_beyond_10['重叠K线数'].mean():.2f}")
    print(f"平均重叠时长: {df_beyond_10['重叠时长(分钟)'].mean():.2f} 分钟")
    
    # 按重叠类型统计
    print("\n按重叠类型统计:")
    for overlap_type in ['双倍做多', '双倍做空', '方向冲突']:
        type_df = df_beyond_10[df_beyond_10['重叠类型'] == overlap_type]
        if len(type_df) > 0:
            print(f"\n  {overlap_type}:")
            print(f"    次数: {len(type_df)} ({len(type_df)/len(df_beyond_10)*100:.2f}%)")
            print(f"    平均综合收益: {type_df['综合收益%'].mean():.3f}%")
            profit_count = len(type_df[type_df['综合收益%'] > 0])
            print(f"    盈利次数: {profit_count} ({profit_count/len(type_df)*100:.2f}%)")
    
    # 按第一笔持仓K线数分组统计
    print("\n按第一笔已持仓K线数分组:")
    bins = [10, 20, 30, 40, 50, 100]
    for i in range(len(bins)-1):
        range_df = df_beyond_10[(df_beyond_10['第一笔重叠前已持仓K线数'] >= bins[i]) & 
                                 (df_beyond_10['第一笔重叠前已持仓K线数'] < bins[i+1])]
        if len(range_df) > 0:
            print(f"  {bins[i]}-{bins[i+1]}根K线: {len(range_df)}次, 平均综合收益: {range_df['综合收益%'].mean():.3f}%")
    
    # 超过100根的
    range_df = df_beyond_10[df_beyond_10['第一笔重叠前已持仓K线数'] >= 100]
    if len(range_df) > 0:
        print(f"  100根以上: {len(range_df)}次, 平均综合收益: {range_df['综合收益%'].mean():.3f}%")

# 对比分析
print("\n" + "=" * 100)
print("【对比分析】")
print("=" * 100)

if len(df_within_10) > 0 and len(df_beyond_10) > 0:
    print(f"\n十条K线内:")
    print(f"  平均综合收益: {df_within_10['综合收益%'].mean():.3f}%")
    within_profit = len(df_within_10[df_within_10['综合收益%'] > 0])
    print(f"  盈利比例: {within_profit/len(df_within_10)*100:.2f}%")
    
    print(f"\n十条K线外:")
    print(f"  平均综合收益: {df_beyond_10['综合收益%'].mean():.3f}%")
    beyond_profit = len(df_beyond_10[df_beyond_10['综合收益%'] > 0])
    print(f"  盈利比例: {beyond_profit/len(df_beyond_10)*100:.2f}%")
    
    # 结论
    print("\n结论:")
    if df_within_10['综合收益%'].mean() > df_beyond_10['综合收益%'].mean():
        diff = df_within_10['综合收益%'].mean() - df_beyond_10['综合收益%'].mean()
        print(f"  ✓ 十条K线内的重叠表现更好，收益高出 {diff:.3f}%")
    else:
        diff = df_beyond_10['综合收益%'].mean() - df_within_10['综合收益%'].mean()
        print(f"  ✓ 十条K线外的重叠表现更好，收益高出 {diff:.3f}%")

# 展示典型案例
print("\n" + "=" * 100)
print("【典型案例】")
print("=" * 100)

if len(df_within_10) > 0:
    print("\n十条K线内重叠案例（前5个）:")
    for idx, row in df_within_10.head(5).iterrows():
        print(f"\n  案例: {row['重叠类型']}")
        print(f"    第一笔在第 {row['第一笔重叠前已持仓K线数']:.0f} 根K线时遇到重叠")
        print(f"    重叠了 {row['重叠K线数']:.0f} 根K线")
        print(f"    综合收益: {row['综合收益%']:.3f}%")

if len(df_beyond_10) > 0:
    print("\n十条K线外重叠案例（前5个）:")
    for idx, row in df_beyond_10.head(5).iterrows():
        print(f"\n  案例: {row['重叠类型']}")
        print(f"    第一笔在第 {row['第一笔重叠前已持仓K线数']:.0f} 根K线时遇到重叠")
        print(f"    重叠了 {row['重叠K线数']:.0f} 根K线")
        print(f"    综合收益: {row['综合收益%']:.3f}%")

print("\n" + "=" * 100)
print("详细数据已保存")
print("=" * 100)
