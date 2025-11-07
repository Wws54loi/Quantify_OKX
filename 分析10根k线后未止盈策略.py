"""
分析10根K线后未止盈的最佳处理办法
研究部分止盈交易的特征，寻找最优的回流平仓策略
"""

import csv
import json
import os
from datetime import datetime
from typing import List, Dict
import statistics


def analyze_partial_profit_trades():
    """分析部分止盈交易的特征"""
    
    print("="*80)
    print("10根K线后未止盈交易分析")
    print("="*80)
    
    # 读取交易日志
    csv_file = "trade_log.csv"
    if not os.path.exists(csv_file):
        print(f"错误: 找不到文件 {csv_file}")
        return
    
    all_trades = []
    take_profit_trades = []
    partial_profit_trades = []
    stop_loss_trades = []
    
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trade = {
                'id': int(row['交易编号']),
                'type': row['策略类型'],
                'direction': row['方向'],
                'entry_time': row['入场时间'],
                'exit_time': row['出场时间'],
                'holding_bars': int(row['持仓K线数']),
                'price_change': float(row['价格变动%'].replace('%', '')),
                'contract_return': float(row['合约收益%'].replace('%', '')),
                'pnl': float(row['盈亏USDT']),
                'result': row['结果'],
                'k1_high': float(row['K1最高']),
                'k1_low': float(row['K1最低']),
            }
            all_trades.append(trade)
            
            if trade['result'] == '完全止盈':
                take_profit_trades.append(trade)
            elif trade['result'] == '部分止盈':
                partial_profit_trades.append(trade)
            elif trade['result'] == '止损':
                stop_loss_trades.append(trade)
    
    print(f"\n数据统计:")
    print(f"  总交易数: {len(all_trades)}")
    print(f"  完全止盈: {len(take_profit_trades)} ({len(take_profit_trades)/len(all_trades)*100:.1f}%)")
    print(f"  部分止盈: {len(partial_profit_trades)} ({len(partial_profit_trades)/len(all_trades)*100:.1f}%)")
    print(f"  止损: {len(stop_loss_trades)} ({len(stop_loss_trades)/len(all_trades)*100:.1f}%)")
    
    # 分析部分止盈交易
    if partial_profit_trades:
        print(f"\n{'='*80}")
        print("部分止盈交易详细分析")
        print(f"{'='*80}")
        
        holding_bars = [t['holding_bars'] for t in partial_profit_trades]
        returns = [t['contract_return'] for t in partial_profit_trades]
        
        print(f"\n持仓时长分析:")
        print(f"  平均持仓: {statistics.mean(holding_bars):.1f}根K线")
        print(f"  中位数: {statistics.median(holding_bars):.1f}根K线")
        print(f"  最短: {min(holding_bars)}根K线")
        print(f"  最长: {max(holding_bars)}根K线")
        
        # 按持仓时长分布
        holding_distribution = {}
        for bars in holding_bars:
            if bars <= 10:
                key = f"<=10根"
            elif bars <= 20:
                key = "11-20根"
            elif bars <= 30:
                key = "21-30根"
            elif bars <= 50:
                key = "31-50根"
            else:
                key = ">50根"
            holding_distribution[key] = holding_distribution.get(key, 0) + 1
        
        print(f"\n持仓时长分布:")
        for key in ["<=10根", "11-20根", "21-30根", "31-50根", ">50根"]:
            count = holding_distribution.get(key, 0)
            pct = count / len(partial_profit_trades) * 100
            print(f"  {key}: {count} ({pct:.1f}%)")
        
        print(f"\n收益率分析:")
        print(f"  平均收益: {statistics.mean(returns):.2f}%")
        print(f"  中位数: {statistics.median(returns):.2f}%")
        print(f"  最小: {min(returns):.2f}%")
        print(f"  最大: {max(returns):.2f}%")
        
        # 收益分布
        return_distribution = {
            "0-10%": 0,
            "10-20%": 0,
            "20-30%": 0,
            "30-40%": 0,
        }
        for r in returns:
            if r < 10:
                return_distribution["0-10%"] += 1
            elif r < 20:
                return_distribution["10-20%"] += 1
            elif r < 30:
                return_distribution["20-30%"] += 1
            else:
                return_distribution["30-40%"] += 1
        
        print(f"\n收益分布:")
        for key, count in return_distribution.items():
            pct = count / len(partial_profit_trades) * 100
            print(f"  {key}: {count} ({pct:.1f}%)")
        
        # 分析不同延迟参数的效果
        print(f"\n{'='*80}")
        print("模拟不同延迟参数的效果")
        print(f"{'='*80}")
        
        for delay in [5, 10, 15, 20, 30]:
            improved_count = 0
            worse_count = 0
            total_gain = 0
            
            for trade in partial_profit_trades:
                # 如果这笔交易在delay根K线内就会被平仓
                if trade['holding_bars'] <= delay:
                    # 收益会降低（没有等到更好的价格）
                    worse_count += 1
                else:
                    # 可能会避免后续的收益下降
                    improved_count += 1
                    total_gain += trade['contract_return']
            
            print(f"\n延迟{delay}根K线:")
            print(f"  提前平仓: {worse_count} ({worse_count/len(partial_profit_trades)*100:.1f}%)")
            print(f"  继续持有: {improved_count} ({improved_count/len(partial_profit_trades)*100:.1f}%)")
            if improved_count > 0:
                print(f"  继续持有平均收益: {total_gain/improved_count:.2f}%")
    
    # 比较完全止盈和部分止盈
    print(f"\n{'='*80}")
    print("完全止盈 vs 部分止盈对比")
    print(f"{'='*80}")
    
    if take_profit_trades:
        tp_holding = [t['holding_bars'] for t in take_profit_trades]
        tp_returns = [t['contract_return'] for t in take_profit_trades]
        
        print(f"\n完全止盈:")
        print(f"  数量: {len(take_profit_trades)}")
        print(f"  平均持仓: {statistics.mean(tp_holding):.1f}根K线")
        print(f"  平均收益: {statistics.mean(tp_returns):.2f}%")
    
    if partial_profit_trades:
        pp_holding = [t['holding_bars'] for t in partial_profit_trades]
        pp_returns = [t['contract_return'] for t in partial_profit_trades]
        
        print(f"\n部分止盈:")
        print(f"  数量: {len(partial_profit_trades)}")
        print(f"  平均持仓: {statistics.mean(pp_holding):.1f}根K线")
        print(f"  平均收益: {statistics.mean(pp_returns):.2f}%")
    
    # 分析K1振幅与结果的关系
    print(f"\n{'='*80}")
    print("K1振幅与交易结果的关系")
    print(f"{'='*80}")
    
    for result_type, trades_list in [
        ("完全止盈", take_profit_trades),
        ("部分止盈", partial_profit_trades),
        ("止损", stop_loss_trades)
    ]:
        if trades_list:
            k1_ranges = [(t['k1_high'] - t['k1_low']) / t['k1_low'] * 100 for t in trades_list]
            print(f"\n{result_type}:")
            print(f"  平均K1振幅: {statistics.mean(k1_ranges):.3f}%")
            print(f"  中位数: {statistics.median(k1_ranges):.3f}%")
            print(f"  最小: {min(k1_ranges):.3f}%")
            print(f"  最大: {max(k1_ranges):.3f}%")


def simulate_different_strategies():
    """模拟不同的回流平仓策略"""
    
    print(f"\n{'='*80}")
    print("模拟不同回流平仓策略")
    print(f"{'='*80}")
    
    # 读取原始K线数据
    cache_file = "btcusdt_15m_klines.json"
    if not os.path.exists(cache_file):
        print(f"错误: 找不到K线数据文件")
        return
    
    print(f"\n正在加载K线数据...")
    with open(cache_file, 'r', encoding='utf-8') as f:
        raw_klines = json.load(f)
    print(f"✓ 已加载 {len(raw_klines)} 根K线数据")
    
    # 测试不同的策略组合
    strategies = [
        {"delay": 5, "min_profit": 0.0001, "name": "5根K线+任何盈利"},
        {"delay": 10, "min_profit": 0.0001, "name": "10根K线+任何盈利"},
        {"delay": 15, "min_profit": 0.0001, "name": "15根K线+任何盈利"},
        {"delay": 10, "min_profit": 0.003, "name": "10根K线+15%盈利"},
        {"delay": 10, "min_profit": 0.004, "name": "10根K线+20%盈利"},
        {"delay": 15, "min_profit": 0.003, "name": "15根K线+15%盈利"},
        {"delay": 20, "min_profit": 0.0001, "name": "20根K线+任何盈利"},
    ]
    
    print(f"\n将测试以下策略:")
    for i, s in enumerate(strategies, 1):
        print(f"  {i}. {s['name']}")
    
    print(f"\n提示: 需要重新运行回测才能得到准确结果")
    print(f"建议修改主策略文件中的参数进行测试")


def main():
    """主函数"""
    
    # 分析现有数据
    analyze_partial_profit_trades()
    
    # 提供策略建议
    simulate_different_strategies()
    
    print(f"\n{'='*80}")
    print("结论与建议")
    print(f"{'='*80}")
    
    print(f"""
基于当前数据分析，建议测试以下策略组合：

1. 【激进策略】5根K线 + 任何盈利
   - 优点: 快速止盈，减少回撤风险
   - 缺点: 可能错过更大收益
   - 适用: 市场波动较大时

2. 【平衡策略】10根K线 + 15%盈利（约0.3%价格变动）
   - 优点: 兼顾收益和风险
   - 缺点: 需要达到一定盈利才平仓
   - 适用: 常规市场环境

3. 【保守策略】15根K线 + 任何盈利
   - 优点: 给予更多时间达到完全止盈
   - 缺点: 可能持有时间过长，增加止损风险
   - 适用: 市场趋势明确时

建议操作步骤：
1. 分别测试这3种策略的完整回测
2. 对比胜率、完全止盈率、平均收益
3. 选择综合评分最高的策略
4. 考虑市场环境动态调整参数
    """)
    
    print(f"{'='*80}")


if __name__ == '__main__':
    main()
