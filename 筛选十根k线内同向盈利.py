"""
筛选十根K线内、方向相同且都盈利的重叠交易
"""

import pandas as pd

# 读取十条K线内重叠详情
df = pd.read_csv('十条K线内重叠详情.csv')

# 筛选条件：
# 1. 重叠类型是双倍做多或双倍做空（方向相同）
# 2. 第一笔收益% > 0
# 3. 第二笔收益% > 0
filtered_df = df[
    ((df['重叠类型'] == '双倍做多') | (df['重叠类型'] == '双倍做空')) &
    (df['第一笔收益%'] > 0) &
    (df['第二笔收益%'] > 0)
]

print(f"筛选结果：找到 {len(filtered_df)} 条符合条件的记录")
print(f"双倍做多且都盈利：{len(filtered_df[filtered_df['重叠类型'] == '双倍做多'])} 条")
print(f"双倍做空且都盈利：{len(filtered_df[filtered_df['重叠类型'] == '双倍做空'])} 条")

# 保存为CSV
filtered_df.to_csv('十根k线内同向且都盈利.csv', index=False, encoding='utf-8-sig')

# 保存为格式化的TXT
with open('十根k线内同向且都盈利.txt', 'w', encoding='utf-8') as f:
    f.write("=" * 100 + "\n")
    f.write("十根K线内、方向相同且都盈利的重叠交易详情\n")
    f.write("=" * 100 + "\n\n")
    f.write(f"总计：{len(filtered_df)} 笔重叠交易\n")
    f.write(f"  - 双倍做多且都盈利：{len(filtered_df[filtered_df['重叠类型'] == '双倍做多'])} 笔\n")
    f.write(f"  - 双倍做空且都盈利：{len(filtered_df[filtered_df['重叠类型'] == '双倍做空'])} 笔\n\n")
    
    # 统计数据
    f.write("=" * 100 + "\n")
    f.write("统计摘要\n")
    f.write("=" * 100 + "\n\n")
    f.write(f"平均第一笔收益：{filtered_df['第一笔收益%'].mean():.3f}%\n")
    f.write(f"平均第二笔收益：{filtered_df['第二笔收益%'].mean():.3f}%\n")
    f.write(f"平均综合收益：{filtered_df['综合收益%'].mean():.3f}%\n")
    f.write(f"平均重叠K线数：{filtered_df['重叠K线数'].mean():.2f} 根\n")
    f.write(f"平均第一笔已持仓K线数：{filtered_df['第一笔重叠前已持仓K线数'].mean():.2f} 根\n")
    f.write(f"平均重叠时长：{filtered_df['重叠时长(分钟)'].mean():.2f} 分钟\n\n")
    
    # 按重叠类型分组统计
    f.write("=" * 100 + "\n")
    f.write("分类统计\n")
    f.write("=" * 100 + "\n\n")
    
    for overlap_type in ['双倍做多', '双倍做空']:
        type_df = filtered_df[filtered_df['重叠类型'] == overlap_type]
        if len(type_df) > 0:
            f.write(f"【{overlap_type}】\n")
            f.write(f"  次数：{len(type_df)}\n")
            f.write(f"  平均综合收益：{type_df['综合收益%'].mean():.3f}%\n")
            f.write(f"  最大综合收益：{type_df['综合收益%'].max():.3f}%\n")
            f.write(f"  最小综合收益：{type_df['综合收益%'].min():.3f}%\n")
            f.write(f"  平均重叠K线数：{type_df['重叠K线数'].mean():.2f} 根\n\n")
    
    # 详细记录
    f.write("=" * 100 + "\n")
    f.write("详细记录\n")
    f.write("=" * 100 + "\n\n")
    
    for idx, row in filtered_df.iterrows():
        f.write(f"记录 #{idx + 1}: {row['重叠类型']}\n")
        f.write("-" * 100 + "\n")
        f.write(f"第一笔交易:\n")
        f.write(f"  交易编号: #{row['第一笔交易号']}\n")
        f.write(f"  方向: {row['第一笔方向']}\n")
        f.write(f"  入场时间: {row['第一笔入场']}\n")
        f.write(f"  出场时间: {row['第一笔出场']}\n")
        f.write(f"  持仓K线数: {row['第一笔持仓K线数']} 根\n")
        f.write(f"  价格变动: {row['第一笔收益%']:.3f}%\n")
        f.write(f"  合约收益: {row['第一笔合约收益%']:.2f}%\n")
        f.write(f"  结果: {row['第一笔结果']}\n\n")
        
        f.write(f"第二笔交易:\n")
        f.write(f"  交易编号: #{row['第二笔交易号']}\n")
        f.write(f"  方向: {row['第二笔方向']}\n")
        f.write(f"  入场时间: {row['第二笔入场']}\n")
        f.write(f"  出场时间: {row['第二笔出场']}\n")
        f.write(f"  持仓K线数: {row['第二笔持仓K线数']} 根\n")
        f.write(f"  价格变动: {row['第二笔收益%']:.3f}%\n")
        f.write(f"  合约收益: {row['第二笔合约收益%']:.2f}%\n")
        f.write(f"  结果: {row['第二笔结果']}\n\n")
        
        f.write(f"重叠信息:\n")
        f.write(f"  重叠开始: {row['重叠开始']}\n")
        f.write(f"  重叠结束: {row['重叠结束']}\n")
        f.write(f"  重叠时长: {row['重叠时长(分钟)']:.0f} 分钟\n")
        f.write(f"  重叠K线数: {row['重叠K线数']:.2f} 根\n")
        f.write(f"  第一笔在第 {row['第一笔重叠前已持仓K线数']:.0f} 根K线时遇到重叠\n")
        f.write(f"  综合收益: {row['综合收益%']:.3f}%\n")
        f.write("\n" + "=" * 100 + "\n\n")

print(f"\n已保存到:")
print(f"  - 十根k线内同向且都盈利.csv")
print(f"  - 十根k线内同向且都盈利.txt")
