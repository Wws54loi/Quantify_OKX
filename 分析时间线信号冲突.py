"""
分析交易日志中的时间线信号重叠情况
包括:
1. 做多遇到做多（双倍做多）
2. 做空遇到做空（双倍做空）
3. 做多遇到做空（方向冲突）
4. 做空遇到做多（方向冲突）
"""

import pandas as pd
from datetime import datetime

# 读取交易日志
df = pd.read_csv('trade_log.csv')

# 转换时间格式
df['入场时间'] = pd.to_datetime(df['入场时间'])
df['出场时间'] = pd.to_datetime(df['出场时间'])

# 存储所有的重叠情况
overlaps = []

# 遍历每一笔交易
for i in range(len(df)):
    trade_i = df.iloc[i]
    entry_i = trade_i['入场时间']
    exit_i = trade_i['出场时间']
    direction_i = trade_i['方向']
    
    # 检查后续交易是否与当前交易重叠
    for j in range(i + 1, len(df)):
        trade_j = df.iloc[j]
        entry_j = trade_j['入场时间']
        exit_j = trade_j['出场时间']
        direction_j = trade_j['方向']
        
        # 如果trade_j在trade_i结束后才开始，后续交易也不会重叠
        if entry_j >= exit_i:
            break
        
        # 检查是否有时间重叠
        if entry_j < exit_i:
            # 计算重叠时长
            overlap_start = entry_j
            overlap_end = min(exit_i, exit_j)
            overlap_duration = (overlap_end - overlap_start).total_seconds() / 60  # 分钟
            
            # 确定重叠类型
            if direction_i == direction_j:
                if direction_i == '做多':
                    overlap_type = '双倍做多'
                else:
                    overlap_type = '双倍做空'
            else:
                overlap_type = '方向冲突'
            
            # 计算第一笔交易在重叠期间的收益
            trade_i_entry_price = trade_i['入场价格']
            trade_i_exit_price = trade_i['出场价格']
            trade_i_profit_pct = float(trade_i['价格变动%'].rstrip('%'))
            
            # 计算第二笔交易的收益
            trade_j_entry_price = trade_j['入场价格']
            trade_j_exit_price = trade_j['出场价格']
            trade_j_profit_pct = float(trade_j['价格变动%'].rstrip('%'))
            
            # 计算重叠期间的综合收益
            if overlap_type == '双倍做多' or overlap_type == '双倍做空':
                # 同向交易，收益叠加
                combined_profit_pct = trade_i_profit_pct + trade_j_profit_pct
            else:
                # 反向交易，收益对冲
                combined_profit_pct = trade_i_profit_pct + trade_j_profit_pct
            
            # 记录重叠信息
            overlaps.append({
                '第一笔交易号': trade_i['交易编号'],
                '第一笔方向': direction_i,
                '第一笔入场': entry_i,
                '第一笔出场': exit_i,
                '第一笔收益%': trade_i_profit_pct,
                '第一笔结果': trade_i['结果'],
                '第二笔交易号': trade_j['交易编号'],
                '第二笔方向': direction_j,
                '第二笔入场': entry_j,
                '第二笔出场': exit_j,
                '第二笔收益%': trade_j_profit_pct,
                '第二笔结果': trade_j['结果'],
                '重叠类型': overlap_type,
                '重叠开始': overlap_start,
                '重叠结束': overlap_end,
                '重叠时长(分钟)': overlap_duration,
                '第一笔合约收益%': float(trade_i['合约收益%'].rstrip('%')),
                '第二笔合约收益%': float(trade_j['合约收益%'].rstrip('%')),
                '综合收益%': combined_profit_pct
            })

# 转换为DataFrame
overlap_df = pd.DataFrame(overlaps)

if len(overlap_df) > 0:
    # 保存详细记录
    overlap_df.to_csv('时间线信号重叠详情.csv', index=False, encoding='utf-8-sig')
    
    print("=" * 100)
    print("时间线信号重叠分析报告")
    print("=" * 100)
    
    # 总体统计
    print(f"\n总交易笔数: {len(df)}")
    print(f"发现重叠情况: {len(overlap_df)} 次")
    print(f"重叠比例: {len(overlap_df)/len(df)*100:.2f}%")
    
    # 按重叠类型分类统计
    print("\n" + "=" * 100)
    print("按重叠类型统计:")
    print("=" * 100)
    
    for overlap_type in ['双倍做多', '双倍做空', '方向冲突']:
        type_df = overlap_df[overlap_df['重叠类型'] == overlap_type]
        if len(type_df) > 0:
            print(f"\n【{overlap_type}】")
            print(f"  发生次数: {len(type_df)}")
            print(f"  平均重叠时长: {type_df['重叠时长(分钟)'].mean():.2f} 分钟")
            print(f"  最长重叠时长: {type_df['重叠时长(分钟)'].max():.2f} 分钟")
            print(f"  最短重叠时长: {type_df['重叠时长(分钟)'].min():.2f} 分钟")
            
            # 收益统计
            print(f"\n  收益统计:")
            print(f"    第一笔平均收益: {type_df['第一笔收益%'].mean():.3f}%")
            print(f"    第二笔平均收益: {type_df['第二笔收益%'].mean():.3f}%")
            print(f"    综合平均收益: {type_df['综合收益%'].mean():.3f}%")
            
            # 统计双方盈亏情况
            both_profit = len(type_df[(type_df['第一笔收益%'] > 0) & (type_df['第二笔收益%'] > 0)])
            both_loss = len(type_df[(type_df['第一笔收益%'] < 0) & (type_df['第二笔收益%'] < 0)])
            one_profit = len(type_df) - both_profit - both_loss
            
            print(f"\n  盈亏分布:")
            print(f"    双方都盈利: {both_profit} 次 ({both_profit/len(type_df)*100:.2f}%)")
            print(f"    双方都亏损: {both_loss} 次 ({both_loss/len(type_df)*100:.2f}%)")
            print(f"    一盈一亏: {one_profit} 次 ({one_profit/len(type_df)*100:.2f}%)")
    
    # 详细案例展示
    print("\n" + "=" * 100)
    print("典型案例展示 (前10个):")
    print("=" * 100)
    
    for i, row in overlap_df.head(10).iterrows():
        print(f"\n案例 {i+1}: {row['重叠类型']}")
        print(f"  第一笔: 交易#{row['第一笔交易号']} {row['第一笔方向']}")
        print(f"    时间: {row['第一笔入场']} -> {row['第一笔出场']}")
        print(f"    收益: {row['第一笔收益%']:.3f}% (合约收益: {row['第一笔合约收益%']:.2f}%)")
        print(f"    结果: {row['第一笔结果']}")
        print(f"  第二笔: 交易#{row['第二笔交易号']} {row['第二笔方向']}")
        print(f"    时间: {row['第二笔入场']} -> {row['第二笔出场']}")
        print(f"    收益: {row['第二笔收益%']:.3f}% (合约收益: {row['第二笔合约收益%']:.2f}%)")
        print(f"    结果: {row['第二笔结果']}")
        print(f"  重叠时段: {row['重叠开始']} -> {row['重叠结束']}")
        print(f"  重叠时长: {row['重叠时长(分钟)']:.0f} 分钟")
        print(f"  综合收益: {row['综合收益%']:.3f}%")
    
    # 计算如果按重叠情况合并后的收益
    print("\n" + "=" * 100)
    print("重叠期间收益影响分析:")
    print("=" * 100)
    
    # 双倍做多情况
    double_long = overlap_df[overlap_df['重叠类型'] == '双倍做多']
    if len(double_long) > 0:
        print(f"\n【双倍做多】")
        profit_count = len(double_long[double_long['综合收益%'] > 0])
        loss_count = len(double_long[double_long['综合收益%'] < 0])
        print(f"  总次数: {len(double_long)}")
        print(f"  盈利次数: {profit_count} ({profit_count/len(double_long)*100:.2f}%)")
        print(f"  亏损次数: {loss_count} ({loss_count/len(double_long)*100:.2f}%)")
        print(f"  平均综合收益: {double_long['综合收益%'].mean():.3f}%")
        print(f"  最大综合收益: {double_long['综合收益%'].max():.3f}%")
        print(f"  最大综合亏损: {double_long['综合收益%'].min():.3f}%")
    
    # 双倍做空情况
    double_short = overlap_df[overlap_df['重叠类型'] == '双倍做空']
    if len(double_short) > 0:
        print(f"\n【双倍做空】")
        profit_count = len(double_short[double_short['综合收益%'] > 0])
        loss_count = len(double_short[double_short['综合收益%'] < 0])
        print(f"  总次数: {len(double_short)}")
        print(f"  盈利次数: {profit_count} ({profit_count/len(double_short)*100:.2f}%)")
        print(f"  亏损次数: {loss_count} ({loss_count/len(double_short)*100:.2f}%)")
        print(f"  平均综合收益: {double_short['综合收益%'].mean():.3f}%")
        print(f"  最大综合收益: {double_short['综合收益%'].max():.3f}%")
        print(f"  最大综合亏损: {double_short['综合收益%'].min():.3f}%")
    
    # 方向冲突情况
    conflict = overlap_df[overlap_df['重叠类型'] == '方向冲突']
    if len(conflict) > 0:
        print(f"\n【方向冲突】")
        profit_count = len(conflict[conflict['综合收益%'] > 0])
        loss_count = len(conflict[conflict['综合收益%'] < 0])
        neutral_count = len(conflict[conflict['综合收益%'] == 0])
        print(f"  总次数: {len(conflict)}")
        print(f"  净盈利次数: {profit_count} ({profit_count/len(conflict)*100:.2f}%)")
        print(f"  净亏损次数: {loss_count} ({loss_count/len(conflict)*100:.2f}%)")
        print(f"  持平次数: {neutral_count} ({neutral_count/len(conflict)*100:.2f}%)")
        print(f"  平均综合收益: {conflict['综合收益%'].mean():.3f}%")
        print(f"  最大综合收益: {conflict['综合收益%'].max():.3f}%")
        print(f"  最大综合亏损: {conflict['综合收益%'].min():.3f}%")
        
        # 分析对冲效果
        print(f"\n  对冲效果分析:")
        total_without_hedge = abs(conflict['第一笔收益%']).mean() + abs(conflict['第二笔收益%']).mean()
        total_with_hedge = abs(conflict['综合收益%']).mean()
        hedge_ratio = (total_without_hedge - total_with_hedge) / total_without_hedge * 100
        print(f"    无对冲平均波动: {total_without_hedge:.3f}%")
        print(f"    有对冲平均波动: {total_with_hedge:.3f}%")
        print(f"    风险降低比例: {hedge_ratio:.2f}%")
    
    print("\n" + "=" * 100)
    print(f"详细数据已保存至: 时间线信号重叠详情.csv")
    print("=" * 100)
    
else:
    print("未发现时间线重叠的交易信号")
