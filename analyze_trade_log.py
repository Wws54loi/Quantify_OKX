#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分析trade_log.txt中的同时持仓情况
"""
import re
from datetime import datetime
from collections import defaultdict

def parse_time(time_str):
    """解析时间字符串"""
    return datetime.strptime(time_str, '%Y-%m-%d %H:%M')

def parse_trade_log(log_file):
    """解析trade_log.txt文件"""
    trades = []
    
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 使用正则表达式提取每笔交易
    pattern = r'交易 #(\d+) - (.*?) \((.*?)\).*?交易方向: (.*?)\n.*?入场时间: (.*?)\n.*?入场价格: (.*?) USDT.*?出场时间: (.*?)\n.*?出场价格: (.*?) USDT.*?合约收益: (.*?)%.*?本次盈亏: (.*?) USDT'
    
    matches = re.finditer(pattern, content, re.DOTALL)
    
    for match in matches:
        trade_id = int(match.group(1))
        exit_reason = match.group(2)
        entry_direction = match.group(4).strip()
        entry_time = parse_time(match.group(5))
        entry_price = float(match.group(6))
        exit_time = parse_time(match.group(7))
        exit_price = float(match.group(8))
        contract_return = float(match.group(9))
        profit = float(match.group(10))
        
        trades.append({
            'id': trade_id,
            'exit_reason': exit_reason,
            'direction': entry_direction,
            'entry_time': entry_time,
            'exit_time': exit_time,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'contract_return': contract_return,
            'profit': profit
        })
    
    return trades

def analyze_concurrent_positions(trades):
    """分析同时持仓情况"""
    print(f"总交易数: {len(trades)}")
    print("=" * 80)
    
    # 获取所有时间点
    all_times = set()
    for trade in trades:
        all_times.add(trade['entry_time'])
        all_times.add(trade['exit_time'])
    
    all_times = sorted(all_times)
    
    # 统计每个时间点的持仓情况
    max_concurrent = 0
    four_position_moments = []
    
    for time in all_times:
        active_positions = []
        for trade in trades:
            if trade['entry_time'] <= time < trade['exit_time']:
                active_positions.append(trade)
        
        concurrent = len(active_positions)
        if concurrent > max_concurrent:
            max_concurrent = concurrent
        
        if concurrent == 4:
            # 统计方向
            directions = [p['direction'] for p in active_positions]
            long_count = directions.count('做多')
            short_count = directions.count('做空')
            
            four_position_moments.append({
                'time': time,
                'positions': active_positions,
                'long_count': long_count,
                'short_count': short_count
            })
    
    print(f"最大并发持仓数: {max_concurrent}")
    print(f"出现4个持仓的时刻数: {len(four_position_moments)}")
    print("=" * 80)
    
    # 统计4个持仓的方向分布
    direction_stats = defaultdict(int)
    four_position_trades = set()  # 收集所有在4个持仓时刻参与的交易
    
    for moment in four_position_moments:
        key = f"{moment['long_count']}多{moment['short_count']}空"
        direction_stats[key] += 1
        # 收集这些交易ID
        for pos in moment['positions']:
            four_position_trades.add(pos['id'])
    
    print("\n4个持仓时的方向分布:")
    print("-" * 80)
    for direction, count in sorted(direction_stats.items()):
        print(f"{direction}: {count}次")
    
    # 检查是否有全做多或全做空的情况
    all_long = direction_stats.get('4多0空', 0)
    all_short = direction_stats.get('0多4空', 0)
    
    print("=" * 80)
    print(f"\n全部做多(4多0空): {all_long}次")
    print(f"全部做空(0多4空): {all_short}次")
    
    # 统计在4个持仓时刻的交易的止盈止损情况
    print("\n" + "=" * 80)
    print("4个持仓时刻涉及的交易统计:")
    print("=" * 80)
    
    four_pos_trade_list = [t for t in trades if t['id'] in four_position_trades]
    
    # 出场原因统计
    exit_reason_stats = defaultdict(int)
    exit_reason_profit = defaultdict(list)
    exit_reason_returns = defaultdict(list)
    
    for trade in four_pos_trade_list:
        reason = trade['exit_reason']
        exit_reason_stats[reason] += 1
        exit_reason_profit[reason].append(trade['profit'])
        exit_reason_returns[reason].append(trade['contract_return'])
    
    print(f"\n涉及的交易数: {len(four_pos_trade_list)}")
    print(f"涉及交易占总交易的比例: {len(four_pos_trade_list)/len(trades)*100:.1f}%")
    
    for reason, count in sorted(exit_reason_stats.items(), key=lambda x: x[1], reverse=True):
        profits = exit_reason_profit[reason]
        returns = exit_reason_returns[reason]
        win_count = sum(1 for p in profits if p > 0)
        win_rate = win_count / count * 100 if count > 0 else 0
        avg_profit = sum(profits) / count if count > 0 else 0
        avg_return = sum(returns) / count if count > 0 else 0
        
        print(f"\n{reason}:")
        print(f"  次数: {count} ({count/len(four_pos_trade_list)*100:.1f}%)")
        print(f"  胜率: {win_rate:.2f}% ({win_count}/{count})")
        print(f"  平均合约收益: {avg_return:+.2f}%")
        print(f"  平均盈亏: {avg_profit:+.4f} USDT")
    
    # 统计合约收益分布
    print("\n" + "=" * 80)
    print("4个持仓时刻的合约收益分布:")
    print("=" * 80)
    
    contract_returns = [t['contract_return'] for t in four_pos_trade_list]
    tp_count = sum(1 for r in contract_returns if abs(r - 330.0) < 1)  # 止盈
    tp_count_297 = sum(1 for r in contract_returns if abs(r - 297.0) < 1)  # 40根后止盈
    sl_count = sum(1 for r in contract_returns if abs(r + 530.0) < 1)  # 止损
    sl_count_159 = sum(1 for r in contract_returns if abs(r + 159.0) < 1)  # 40根后止损
    
    print(f"止盈330%: {tp_count}笔 ({tp_count/len(four_pos_trade_list)*100:.1f}%)")
    print(f"止盈297%(40根后): {tp_count_297}笔 ({tp_count_297/len(four_pos_trade_list)*100:.1f}%)")
    print(f"止损-530%: {sl_count}笔 ({sl_count/len(four_pos_trade_list)*100:.1f}%)")
    print(f"止损-159%(40根后): {sl_count_159}笔 ({sl_count_159/len(four_pos_trade_list)*100:.1f}%)")
    print(f"跟踪止损: {exit_reason_stats.get('跟踪止损', 0)}笔 ({exit_reason_stats.get('跟踪止损', 0)/len(four_pos_trade_list)*100:.1f}%)")
    
    # 显示一些4个持仓的具体例子
    if four_position_moments:
        print("\n" + "=" * 80)
        print("4个持仓的具体例子（前5个）:")
        print("=" * 80)
        for i, moment in enumerate(four_position_moments[:5], 1):
            print(f"\n例子 #{i} - 时间: {moment['time']}")
            print(f"方向分布: {moment['long_count']}个做多, {moment['short_count']}个做空")
            for j, pos in enumerate(moment['positions'], 1):
                print(f"  持仓{j}: #{pos['id']:3d} {pos['direction']} "
                      f"入场:{pos['entry_time']} 价格:{pos['entry_price']:.2f}")

if __name__ == '__main__':
    log_file = 'trade_log.txt'
    print("正在解析trade_log.txt...")
    trades = parse_trade_log(log_file)
    print(f"解析完成，共{len(trades)}笔交易\n")
    analyze_concurrent_positions(trades)
