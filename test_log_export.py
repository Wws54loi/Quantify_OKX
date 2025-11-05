"""
快速测试参数优化LOG生成功能（小范围测试）
"""

import json
import os
from datetime import datetime
from three_kline_strategy_close_exit import KLine, ThreeKlineStrategy
import itertools
import csv

# 固定参数
leverage = 50
initial_capital = 1.0

# 小范围测试参数
profit_target_range = [30, 40, 50]  # 仅测试3个止盈值
stop_loss_range = [20, 30]          # 仅测试2个止损值
min_k1_range_range = [0.2, 0.5]     # 仅测试2个K1涨跌幅

print("="*80)
print("参数优化测试 - 生成TOP 10日志")
print("="*80)
print(f"快速测试: 仅测试 {len(profit_target_range)} x {len(stop_loss_range)} x {len(min_k1_range_range)} = {len(profit_target_range)*len(stop_loss_range)*len(min_k1_range_range)} 种组合")

# 加载K线数据
cache_file = "btcusdt_15m_klines.json"
print(f"\n正在读取K线数据...")
with open(cache_file, 'r', encoding='utf-8') as f:
    raw_klines = json.load(f)

klines = [KLine(k) for k in raw_klines]
print(f"✓ 成功读取 {len(klines)} 根K线数据")

# 存储所有结果
results = []

print(f"\n开始参数优化...")
count = 0
total = len(profit_target_range) * len(stop_loss_range) * len(min_k1_range_range)

for profit_pct, stop_pct, k1_pct in itertools.product(profit_target_range, stop_loss_range, min_k1_range_range):
    count += 1
    
    price_profit_target = profit_pct / leverage / 100
    price_stop_loss = stop_pct / leverage / 100
    min_k1_range = k1_pct / 100
    
    strategy = ThreeKlineStrategy()
    signals = strategy.find_signals(klines, min_k1_range=min_k1_range)
    
    stats = strategy.calculate_win_rate(
        signals,
        profit_target=price_profit_target,
        stop_loss=price_stop_loss,
        leverage=leverage,
        initial_capital=initial_capital
    )
    
    if stats['total_trades'] > 0:
        result = {
            'profit_target_percent': profit_pct,
            'stop_loss_percent': stop_pct,
            'min_k1_range_percent': k1_pct,
            'total_trades': stats['total_trades'],
            'win_rate': stats['win_rate'],
            'total_pnl': stats['total_pnl'],
            'final_capital': stats['final_capital'],
            'profit_factor': stats['profit_factor'],
            'return_rate': (stats['total_pnl'] / (stats['total_trades'] * initial_capital) * 100)
        }
        results.append(result)
    
    print(f"进度: {count}/{total}", end='\r')

print(f"\n✓ 优化完成! 共测试了 {len(results)} 个有效参数组合\n")

# 按总盈亏排序
results.sort(key=lambda x: x['total_pnl'], reverse=True)

# 显示TOP 5
print("="*80)
print("TOP 5 最佳参数组合")
print("="*80)
for i, result in enumerate(results[:5], 1):
    print(f"\n第 {i} 名:")
    print(f"  参数: 止盈={result['profit_target_percent']}% | 止损={result['stop_loss_percent']}% | K1涨跌幅={result['min_k1_range_percent']}%")
    print(f"  胜率: {result['win_rate']:.2f}% | 总盈亏: {result['total_pnl']:+.4f} USDT | 收益率: {result['return_rate']:+.2f}%")

# 导出LOG文件
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
logfilename = f"test_optimization_top10_{timestamp}.log"

print(f"\n{'='*80}")
print("导出LOG文件")
print("="*80)

with open(logfilename, 'w', encoding='utf-8') as f:
    f.write("="*80 + "\n")
    f.write("参数优化结果 - TOP 10 盈利策略 (测试版本)\n")
    f.write("="*80 + "\n")
    f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"固定参数: 杠杆={leverage}x, 每次投入={initial_capital} USDT\n")
    f.write(f"平仓规则: 下一根K线止盈/止损/收盘价强制平仓\n")
    f.write(f"测试组合数: {total} 种\n")
    f.write(f"有效组合数: {len(results)} 种\n")
    f.write("="*80 + "\n\n")
    
    for i, result in enumerate(results[:min(10, len(results))], 1):
        f.write(f"{'='*80}\n")
        f.write(f"第 {i} 名 - 最优参数组合\n")
        f.write(f"{'='*80}\n\n")
        
        f.write(f"【参数设置】\n")
        f.write(f"  杠杆倍数: {leverage}x\n")
        f.write(f"  止盈设置: {result['profit_target_percent']}% (合约收益)\n")
        f.write(f"  止损设置: {result['stop_loss_percent']}% (合约亏损)\n")
        f.write(f"  K1涨跌幅要求: {result['min_k1_range_percent']}%\n")
        f.write(f"  每次投入: {initial_capital} USDT\n")
        
        price_profit = result['profit_target_percent'] / leverage
        price_stop = result['stop_loss_percent'] / leverage
        f.write(f"  (对应现货价格变动: 止盈={price_profit:.2f}%, 止损={price_stop:.2f}%)\n\n")
        
        f.write(f"【交易统计】\n")
        f.write(f"  总交易数: {result['total_trades']} 笔\n")
        f.write(f"  胜率: {result['win_rate']:.2f}%\n")
        f.write(f"  盈亏比: {result['profit_factor']:.2f}\n\n")
        
        f.write(f"【资金收益】\n")
        f.write(f"  总投入: {result['total_trades'] * initial_capital:.2f} USDT\n")
        f.write(f"  总盈亏: {result['total_pnl']:+.4f} USDT\n")
        f.write(f"  最终资金: {result['final_capital']:.4f} USDT\n")
        f.write(f"  收益率: {result['return_rate']:+.2f}%\n\n")
        
        f.write(f"【复制参数代码】\n")
        f.write(f"leverage = {leverage}\n")
        f.write(f"profit_target_percent = {result['profit_target_percent']}\n")
        f.write(f"stop_loss_percent = {result['stop_loss_percent']}\n")
        f.write(f"initial_capital = {initial_capital}\n")
        f.write(f"min_k1_range_percent = {result['min_k1_range_percent']}\n\n")
    
    f.write("="*80 + "\n")
    f.write("说明:\n")
    f.write("- 以上策略按总盈亏从高到低排序\n")
    f.write("- 这是快速测试版本，仅测试了部分参数组合\n")
    f.write("- 实际交易需考虑手续费、滑点、资金费率等因素\n")
    f.write("- 历史回测结果不代表未来收益\n")
    f.write("="*80 + "\n")

print(f"✓ TOP 10策略已导出到: {logfilename}")
print(f"\n请查看文件了解详细的策略参数和统计数据！")
