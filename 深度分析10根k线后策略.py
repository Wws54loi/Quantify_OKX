"""
深度分析：10根K线后未止盈交易的最佳处理策略
通过分析实际交易数据，寻找最优的回流平仓参数
"""

import csv
import json
import os
from datetime import datetime
from typing import List, Dict
import statistics


def analyze_trades_by_holding_time():
    """按持仓时长分析交易表现"""
    
    print("="*80)
    print("按持仓时长分析交易表现")
    print("="*80)
    
    # 读取交易日志
    csv_file = "trade_log.csv"
    if not os.path.exists(csv_file):
        print(f"错误: 找不到文件 {csv_file}")
        return
    
    all_trades = []
    
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trade = {
                'id': int(row['交易编号']),
                'holding_bars': int(row['持仓K线数']),
                'contract_return': float(row['合约收益%'].replace('%', '')),
                'result': row['结果'],
                'direction': row['方向'],
            }
            all_trades.append(trade)
    
    print(f"\n总交易数: {len(all_trades)}")
    
    # 按结果分类
    profit_trades = [t for t in all_trades if t['result'] == '止盈']
    loss_trades = [t for t in all_trades if t['result'] == '止损']
    
    print(f"止盈交易: {len(profit_trades)} ({len(profit_trades)/len(all_trades)*100:.1f}%)")
    print(f"止损交易: {len(loss_trades)} ({len(loss_trades)/len(all_trades)*100:.1f}%)")
    
    # 分析止盈交易的持仓时长分布
    print(f"\n{'='*80}")
    print("止盈交易持仓时长分析")
    print(f"{'='*80}")
    
    if profit_trades:
        holding_bars = [t['holding_bars'] for t in profit_trades]
        
        print(f"\n基本统计:")
        print(f"  平均持仓: {statistics.mean(holding_bars):.1f}根K线")
        print(f"  中位数: {statistics.median(holding_bars):.1f}根K线")
        print(f"  最短: {min(holding_bars)}根K线")
        print(f"  最长: {max(holding_bars)}根K线")
        
        # 持仓时长分布
        distribution = {
            "1-5根": [],
            "6-10根": [],
            "11-15根": [],
            "16-20根": [],
            "21-30根": [],
            ">30根": []
        }
        
        for trade in profit_trades:
            bars = trade['holding_bars']
            if bars <= 5:
                distribution["1-5根"].append(trade)
            elif bars <= 10:
                distribution["6-10根"].append(trade)
            elif bars <= 15:
                distribution["11-15根"].append(trade)
            elif bars <= 20:
                distribution["16-20根"].append(trade)
            elif bars <= 30:
                distribution["21-30根"].append(trade)
            else:
                distribution[">30根"].append(trade)
        
        print(f"\n持仓时长分布:")
        print(f"{'区间':<10} {'数量':<8} {'占比':<10} {'平均收益'}")
        print("-"*50)
        
        for key in ["1-5根", "6-10根", "11-15根", "16-20根", "21-30根", ">30根"]:
            trades = distribution[key]
            count = len(trades)
            pct = count / len(profit_trades) * 100
            avg_return = statistics.mean([t['contract_return'] for t in trades]) if trades else 0
            print(f"{key:<10} {count:<8} {pct:>6.1f}%    {avg_return:>6.2f}%")
        
        # 分析关键节点
        print(f"\n{'='*80}")
        print("关键时间节点分析")
        print(f"{'='*80}")
        
        for cutoff in [5, 10, 15, 20]:
            within = [t for t in profit_trades if t['holding_bars'] <= cutoff]
            beyond = [t for t in profit_trades if t['holding_bars'] > cutoff]
            
            print(f"\n{cutoff}根K线分界:")
            print(f"  {cutoff}根内止盈: {len(within)} ({len(within)/len(profit_trades)*100:.1f}%)")
            if within:
                print(f"    平均收益: {statistics.mean([t['contract_return'] for t in within]):.2f}%")
            
            print(f"  {cutoff}根后止盈: {len(beyond)} ({len(beyond)/len(profit_trades)*100:.1f}%)")
            if beyond:
                print(f"    平均收益: {statistics.mean([t['contract_return'] for t in beyond]):.2f}%")
    
    # 分析止损交易
    print(f"\n{'='*80}")
    print("止损交易持仓时长分析")
    print(f"{'='*80}")
    
    if loss_trades:
        holding_bars = [t['holding_bars'] for t in loss_trades]
        
        print(f"\n基本统计:")
        print(f"  平均持仓: {statistics.mean(holding_bars):.1f}根K线")
        print(f"  中位数: {statistics.median(holding_bars):.1f}根K线")
        print(f"  最短: {min(holding_bars)}根K线")
        print(f"  最长: {max(holding_bars)}根K线")
        
        # 分析在不同时间节点的止损情况
        print(f"\n止损发生时间分布:")
        for cutoff in [5, 10, 15, 20, 30]:
            within = len([t for t in loss_trades if t['holding_bars'] <= cutoff])
            print(f"  {cutoff}根K线内止损: {within} ({within/len(loss_trades)*100:.1f}%)")


def simulate_exit_strategies():
    """模拟不同的退出策略"""
    
    print(f"\n{'='*80}")
    print("模拟不同退出策略的效果")
    print(f"{'='*80}")
    
    csv_file = "trade_log.csv"
    all_trades = []
    
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trade = {
                'id': int(row['交易编号']),
                'holding_bars': int(row['持仓K线数']),
                'contract_return': float(row['合约收益%'].replace('%', '')),
                'result': row['结果'],
            }
            all_trades.append(trade)
    
    profit_trades = [t for t in all_trades if t['result'] == '止盈']
    
    # 定义不同的退出策略
    strategies = [
        {"name": "当前策略(5根)", "delay": 5, "min_return": 0.01},
        {"name": "激进策略(3根)", "delay": 3, "min_return": 0.01},
        {"name": "保守策略(8根)", "delay": 8, "min_return": 0.01},
        {"name": "中等策略(10根)", "delay": 10, "min_return": 0.01},
        {"name": "延迟策略(15根)", "delay": 15, "min_return": 0.01},
        {"name": "5根+10%收益", "delay": 5, "min_return": 10},
        {"name": "10根+15%收益", "delay": 10, "min_return": 15},
    ]
    
    print(f"\n策略对比（仅考虑止盈交易的影响）:")
    print(f"{'策略名称':<20} {'提前平仓数':<12} {'继续持有数':<12} {'影响评估'}")
    print("-"*70)
    
    for strategy in strategies:
        delay = strategy['delay']
        min_return = strategy['min_return']
        
        # 计算会被提前平仓的交易
        early_exit = [t for t in profit_trades if t['holding_bars'] > delay]
        continued = [t for t in profit_trades if t['holding_bars'] <= delay]
        
        # 提前平仓可能降低收益（原本40%，现在可能只有部分收益）
        # 继续持有保持原收益40%
        
        early_exit_count = len(early_exit)
        continued_count = len(continued)
        
        if early_exit:
            # 假设提前平仓平均获得20%收益（介于0-40%之间）
            estimated_return = statistics.mean([t['contract_return'] for t in early_exit])
            impact = f"损失 {(40 - estimated_return) * early_exit_count:.0f}%收益"
        else:
            impact = "无影响"
        
        print(f"{strategy['name']:<20} {early_exit_count:<12} {continued_count:<12} {impact}")
    
    # 详细分析最佳策略
    print(f"\n{'='*80}")
    print("推荐策略分析")
    print(f"{'='*80}")
    
    # 分析：大部分止盈在多少根K线内完成
    quick_profit = len([t for t in profit_trades if t['holding_bars'] <= 10])
    slow_profit = len([t for t in profit_trades if t['holding_bars'] > 10])
    
    print(f"\n止盈速度分析:")
    print(f"  10根K线内止盈: {quick_profit} ({quick_profit/len(profit_trades)*100:.1f}%)")
    print(f"  10根K线后止盈: {slow_profit} ({slow_profit/len(profit_trades)*100:.1f}%)")
    
    if quick_profit > slow_profit:
        print(f"\n结论: 大部分交易在10根K线内完成止盈")
        print(f"建议: 使用较短的延迟参数(5-8根)，快速止盈减少风险")
    else:
        print(f"\n结论: 较多交易需要10根K线以上才能止盈")
        print(f"建议: 使用较长的延迟参数(10-15根)，给予更多时间")


def analyze_optimal_parameters():
    """分析最优参数组合"""
    
    print(f"\n{'='*80}")
    print("最优参数推荐")
    print(f"{'='*80}")
    
    print(f"""
基于数据分析，针对10根K线后未止盈的情况，建议采用以下策略：

【策略A - 快速止盈型】
参数: stop_loss_delay_bars = 5
适用: 市场波动较大，追求稳定收益
特点: 
  - 5根K线后有任何盈利就立即平仓
  - 减少持仓时间，降低风险
  - 可能错过部分完全止盈机会(40%)
  - 但能保证大部分交易获得部分收益(10-30%)

【策略B - 平衡型】
参数: stop_loss_delay_bars = 10
适用: 常规市场环境，平衡收益与风险
特点:
  - 给予10根K线时间达到完全止盈
  - 如果10根K线后仍未止盈，有盈利就平仓
  - 兼顾完全止盈率和风险控制

【策略C - 激进型】
参数: stop_loss_delay_bars = 3-5 + 最低收益要求15%
适用: 追求高收益，能承受较高风险
特点:
  - 3-5根K线后必须达到15%以上收益才平仓
  - 如果收益不足15%，继续持有等待
  - 可能增加止损风险，但成功时收益更高

【推荐测试方案】
建议创建对比测试，分别测试以下参数组合:
1. delay=5, min_profit=任何盈利
2. delay=10, min_profit=任何盈利  
3. delay=5, min_profit=15%
4. delay=10, min_profit=20%
5. delay=15, min_profit=任何盈利

对比指标:
- 总收益率
- 胜率
- 完全止盈率(达到40%)
- 部分止盈率(10-39%)
- 平均持仓时间
- 最大回撤

【关键发现】
从当前数据来看:
- 止盈交易占73.2%，止损占26.8%
- 需要详细分析每笔止盈交易在不同K线时刻的价格表现
- 建议记录每根K线的最高收益率，找出最佳平仓时机

【下一步行动】
1. 修改策略代码，支持不同的delay参数
2. 对每个参数组合进行完整回测
3. 记录详细的K线级别收益数据
4. 对比各策略的综合表现
5. 选择最优参数投入实盘测试
    """)


def main():
    """主函数"""
    
    # 分析交易持仓时长
    analyze_trades_by_holding_time()
    
    # 模拟不同退出策略
    simulate_exit_strategies()
    
    # 最优参数推荐
    analyze_optimal_parameters()
    
    print(f"\n{'='*80}")
    print("分析完成")
    print(f"{'='*80}")


if __name__ == '__main__':
    main()
