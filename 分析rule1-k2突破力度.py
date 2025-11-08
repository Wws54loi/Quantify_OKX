#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析非包含关系下K2的突破线力度相对K1柱体的关联关系

突破力度定义:
- 做多信号: K2突破K1高点的力度 = (K2最高 - K1最高) / K1柱体
- 做空信号: K2突破K1低点的力度 = (K1最低 - K2最低) / K1柱体

K1柱体 = |K1收盘 - K1开盘|
"""

import pandas as pd
import os

def analyze_breakthrough_strength():
    """分析K2突破力度与K1柱体的关系"""
    
    # 读取交易记录
    csv_file = "trade_log.csv"
    if not os.path.exists(csv_file):
        print(f"错误: 找不到文件 {csv_file}")
        return
    
    df = pd.read_csv(csv_file)
    
    # 只保留非包含关系的交易(rule1)
    df_rule1 = df[df['策略类型'] == 'rule1'].copy()
    
    print(f"总交易数: {len(df)}")
    print(f"非包含关系交易数(rule1): {len(df_rule1)}")
    print("="*80)
    
    # 计算K1柱体大小
    df_rule1['K1柱体'] = abs(df_rule1['K1收盘'] - df_rule1['K1开盘'])
    
    # 计算K2突破力度
    def calc_breakthrough(row):
        k1_body = row['K1柱体']
        if k1_body == 0:
            return 0
        
        if row['方向'] == '做多':
            # 做多: K2突破K1高点的力度
            breakthrough = row['K2最高'] - row['K1最高']
        else:  # 做空
            # 做空: K2突破K1低点的力度
            breakthrough = row['K1最低'] - row['K2最低']
        
        # 相对K1柱体的比例
        return breakthrough / k1_body
    
    df_rule1['突破力度比'] = df_rule1.apply(calc_breakthrough, axis=1)
    
    # 分析突破力度的分布
    print("\n【突破力度分布统计】")
    print("突破力度比 = K2突破距离 / K1柱体")
    print("-"*80)
    
    # 按区间统计 (包含负值区间,因为很多K2并未突破K1边界)
    bins = [float('-inf'), -2.0, -1.5, -1.0, -0.9, -0.8, -0.7, -0.6, -0.5, -0.4, -0.3, -0.2, -0.1, 
            0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.5, 2.0, float('inf')]
    labels = ['<-2.00', '-2.00至-1.50', '-1.50至-1.00', '-1.00至-0.90', '-0.90至-0.80', 
              '-0.80至-0.70', '-0.70至-0.60', '-0.60至-0.50', '-0.50至-0.40', '-0.40至-0.30',
              '-0.30至-0.20', '-0.20至-0.10', '-0.10至0.00',
              '0.00-0.10', '0.10-0.20', '0.20-0.30', '0.30-0.40', '0.40-0.50', 
              '0.50-0.60', '0.60-0.70', '0.70-0.80', '0.80-0.90', '0.90-1.00',
              '1.00-1.50', '1.50-2.00', '2.00+']
    
    df_rule1['突破力度区间'] = pd.cut(df_rule1['突破力度比'], bins=bins, labels=labels, right=False)
    
    # 统计每个区间
    stats_list = []
    for interval in labels:
        interval_df = df_rule1[df_rule1['突破力度区间'] == interval]
        if len(interval_df) == 0:
            continue
        
        total = len(interval_df)
        wins = len(interval_df[interval_df['结果'] == '止盈'])
        losses = len(interval_df[interval_df['结果'] == '止损'])
        win_rate = wins / total * 100 if total > 0 else 0
        
        stats_list.append({
            '突破力度区间': interval,
            '交易数': total,
            '止盈': wins,
            '止损': losses,
            '胜率%': round(win_rate, 2)
        })
    
    stats_df = pd.DataFrame(stats_list)
    print(stats_df.to_string(index=False))
    
    # 找出高胜率和低胜率区间
    print("\n【关键发现】")
    print("-"*80)
    
    # 正突破(真正突破了K1边界)
    positive_breakthrough = df_rule1[df_rule1['突破力度比'] >= 0]
    negative_breakthrough = df_rule1[df_rule1['突破力度比'] < 0]
    
    print(f"\n真正突破K1边界的交易: {len(positive_breakthrough)}笔")
    print(f"  止盈: {len(positive_breakthrough[positive_breakthrough['结果']=='止盈'])}笔")
    print(f"  止损: {len(positive_breakthrough[positive_breakthrough['结果']=='止损'])}笔")
    print(f"  胜率: {len(positive_breakthrough[positive_breakthrough['结果']=='止盈'])/len(positive_breakthrough)*100:.2f}%")
    
    print(f"\nK2未突破K1边界的交易: {len(negative_breakthrough)}笔")
    print(f"  止盈: {len(negative_breakthrough[negative_breakthrough['结果']=='止盈'])}笔")
    print(f"  止损: {len(negative_breakthrough[negative_breakthrough['结果']=='止损'])}笔")
    print(f"  胜率: {len(negative_breakthrough[negative_breakthrough['结果']=='止盈'])/len(negative_breakthrough)*100:.2f}%")
    
    # 高胜率区间 (>70% 且交易数>=10)
    high_win = stats_df[(stats_df['胜率%'] > 70) & (stats_df['交易数'] >= 10)]
    if len(high_win) > 0:
        print("\n✓ 高胜率区间 (胜率>70%, 交易数≥10):")
        for _, row in high_win.iterrows():
            print(f"  {row['突破力度区间']}: 胜率{row['胜率%']}%, 交易数{row['交易数']} (止盈{row['止盈']}/止损{row['止损']})")
    
    # 低胜率区间 (<50% 且交易数>=10)
    low_win = stats_df[(stats_df['胜率%'] < 50) & (stats_df['交易数'] >= 10)]
    if len(low_win) > 0:
        print("\n✗ 低胜率区间 (胜率<50%, 交易数≥10):")
        for _, row in low_win.iterrows():
            print(f"  {row['突破力度区间']}: 胜率{row['胜率%']}%, 交易数{row['交易数']} (止盈{row['止盈']}/止损{row['止损']})")
    
    # 交易数最多的区间
    print("\n📊 交易数最多的前5个区间:")
    top5 = stats_df.nlargest(5, '交易数')
    for _, row in top5.iterrows():
        print(f"  {row['突破力度区间']}: {row['交易数']}笔, 胜率{row['胜率%']}%")
    
    # 按方向分析
    print("\n"+"="*80)
    print("【按方向分析突破力度】")
    print("-"*80)
    
    for direction in ['做多', '做空']:
        df_dir = df_rule1[df_rule1['方向'] == direction]
        print(f"\n{direction} (共{len(df_dir)}笔)")
        print(f"  平均突破力度: {df_dir['突破力度比'].mean():.3f}")
        print(f"  中位突破力度: {df_dir['突破力度比'].median():.3f}")
        print(f"  最小突破力度: {df_dir['突破力度比'].min():.3f}")
        print(f"  最大突破力度: {df_dir['突破力度比'].max():.3f}")
        
        # 止盈vs止损的突破力度对比
        wins_dir = df_dir[df_dir['结果'] == '止盈']
        losses_dir = df_dir[df_dir['结果'] == '止损']
        
        print(f"\n  止盈交易平均突破力度: {wins_dir['突破力度比'].mean():.3f}")
        print(f"  止损交易平均突破力度: {losses_dir['突破力度比'].mean():.3f}")
    
    # 相关性分析
    print("\n"+"="*80)
    print("【突破力度与交易结果的相关性】")
    print("-"*80)
    
    # 将结果转为数值 (止盈=1, 止损=0)
    df_rule1['结果数值'] = df_rule1['结果'].apply(lambda x: 1 if x == '止盈' else 0)
    correlation = df_rule1['突破力度比'].corr(df_rule1['结果数值'])
    print(f"突破力度与胜率的相关系数: {correlation:.4f}")
    
    if correlation > 0:
        print("结论: 突破力度越大,胜率越高 (正相关)")
    else:
        print("结论: 突破力度越大,胜率越低 (负相关)")
    
    # 导出详细数据
    output_file = "突破力度分析.csv"
    export_df = df_rule1[['交易编号', '方向', '结果', 'K1柱体', '突破力度比', 
                          'K1开盘', 'K1最高', 'K1最低', 'K1收盘',
                          'K2开盘', 'K2最高', 'K2最低', 'K2收盘']].copy()
    export_df = export_df.sort_values('突破力度比', ascending=False)
    export_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n详细数据已导出到: {output_file}")
    
    # 导出区间统计
    stats_output = "突破力度区间统计.csv"
    stats_df.to_csv(stats_output, index=False, encoding='utf-8-sig')
    print(f"区间统计已导出到: {stats_output}")
    
    print("\n"+"="*80)
    print("分析完成!")
    print("="*80)


if __name__ == "__main__":
    analyze_breakthrough_strength()
