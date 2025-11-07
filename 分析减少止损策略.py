"""
分析如何减少100%止损的发生
因为每次止损都会亏损100%，所以减少止损比提高止盈更重要
目标: 找到既能减少止损，又能保持足够交易量(>=200)的参数组合
"""

import csv
import json
import os
from datetime import datetime
from typing import List, Dict
import statistics


class KLine:
    """K线数据类"""
    
    def __init__(self, kline_data: List):
        self.timestamp = int(kline_data[0])
        self.open = float(kline_data[1])
        self.high = float(kline_data[2])
        self.low = float(kline_data[3])
        self.close = float(kline_data[4])
        self.volume = float(kline_data[5])
        self.body_high = max(self.open, self.close)
        self.body_low = min(self.open, self.close)


def analyze_stop_loss_patterns():
    """分析止损交易的特征"""
    
    print("="*80)
    print("止损交易特征分析")
    print("="*80)
    
    csv_file = "trade_log.csv"
    if not os.path.exists(csv_file):
        print(f"错误: 找不到文件 {csv_file}")
        return
    
    all_trades = []
    profit_trades = []
    loss_trades = []
    
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trade = {
                'id': int(row['交易编号']),
                'type': row['策略类型'],
                'direction': row['方向'],
                'holding_bars': int(row['持仓K线数']),
                'contract_return': float(row['合约收益%'].replace('%', '')),
                'result': row['结果'],
                'k1_high': float(row['K1最高']),
                'k1_low': float(row['K1最低']),
                'k2_high': float(row['K2最高']),
                'k2_low': float(row['K2最低']),
            }
            all_trades.append(trade)
            
            if trade['result'] == '止盈':
                profit_trades.append(trade)
            else:
                loss_trades.append(trade)
    
    total = len(all_trades)
    profit_count = len(profit_trades)
    loss_count = len(loss_trades)
    
    print(f"\n总体统计:")
    print(f"  总交易数: {total}")
    print(f"  止盈交易: {profit_count} ({profit_count/total*100:.1f}%)")
    print(f"  止损交易: {loss_count} ({loss_count/total*100:.1f}%)")
    print(f"  止损率: {loss_count/total*100:.1f}%")
    
    # 关键发现：止损的影响
    print(f"\n💡 关键发现:")
    print(f"  每次止盈收益: +40% (0.4 USDT)")
    print(f"  每次止损亏损: -100% (1.0 USDT)")
    print(f"  盈亏比: 1次止损 = 2.5次止盈的损失")
    print(f"  ")
    print(f"  当前策略:")
    print(f"    {profit_count}次止盈 = +{profit_count * 0.4:.1f} USDT")
    print(f"    {loss_count}次止损 = -{loss_count * 1.0:.1f} USDT")
    print(f"    净收益 = {profit_count * 0.4 - loss_count * 1.0:.1f} USDT")
    print(f"  ")
    print(f"  如果减少10%的止损(47次):")
    print(f"    可以增加净收益: +{47 * 1.0:.1f} USDT")
    print(f"    相当于增加: {47 * 1.0 / 0.4:.0f}次止盈")
    
    # 分析止损交易的K1特征
    print(f"\n{'='*80}")
    print("止损交易的K1振幅分析")
    print(f"{'='*80}")
    
    if loss_trades:
        loss_k1_ranges = [(t['k1_high'] - t['k1_low']) / t['k1_low'] * 100 for t in loss_trades]
        profit_k1_ranges = [(t['k1_high'] - t['k1_low']) / t['k1_low'] * 100 for t in profit_trades]
        
        print(f"\n止损交易K1振幅:")
        print(f"  平均: {statistics.mean(loss_k1_ranges):.3f}%")
        print(f"  中位数: {statistics.median(loss_k1_ranges):.3f}%")
        print(f"  最小: {min(loss_k1_ranges):.3f}%")
        print(f"  最大: {max(loss_k1_ranges):.3f}%")
        
        print(f"\n止盈交易K1振幅:")
        print(f"  平均: {statistics.mean(profit_k1_ranges):.3f}%")
        print(f"  中位数: {statistics.median(profit_k1_ranges):.3f}%")
        print(f"  最小: {min(profit_k1_ranges):.3f}%")
        print(f"  最大: {max(profit_k1_ranges):.3f}%")
        
        print(f"\n结论: 止损交易的K1振幅({statistics.mean(loss_k1_ranges):.3f}%) "
              f"比止盈交易({statistics.mean(profit_k1_ranges):.3f}%)更大")
    
    # 分析K2突破幅度
    print(f"\n{'='*80}")
    print("K2突破幅度分析")
    print(f"{'='*80}")
    
    loss_k2_breakouts = []
    profit_k2_breakouts = []
    
    for t in loss_trades:
        if t['direction'] == '做多':
            breakout = (t['k1_low'] - t['k2_low']) / t['k1_low'] * 100
        else:
            breakout = (t['k2_high'] - t['k1_high']) / t['k1_high'] * 100
        loss_k2_breakouts.append(breakout)
    
    for t in profit_trades:
        if t['direction'] == '做多':
            breakout = (t['k1_low'] - t['k2_low']) / t['k1_low'] * 100
        else:
            breakout = (t['k2_high'] - t['k1_high']) / t['k1_high'] * 100
        profit_k2_breakouts.append(breakout)
    
    print(f"\n止损交易K2突破幅度:")
    print(f"  平均: {statistics.mean(loss_k2_breakouts):.3f}%")
    print(f"  中位数: {statistics.median(loss_k2_breakouts):.3f}%")
    
    print(f"\n止盈交易K2突破幅度:")
    print(f"  平均: {statistics.mean(profit_k2_breakouts):.3f}%")
    print(f"  中位数: {statistics.median(profit_k2_breakouts):.3f}%")
    
    # 分析方向分布
    print(f"\n{'='*80}")
    print("止损交易方向分析")
    print(f"{'='*80}")
    
    loss_long = len([t for t in loss_trades if t['direction'] == '做多'])
    loss_short = len([t for t in loss_trades if t['direction'] == '做空'])
    profit_long = len([t for t in profit_trades if t['direction'] == '做多'])
    profit_short = len([t for t in profit_trades if t['direction'] == '做空'])
    
    print(f"\n止损交易:")
    print(f"  做多止损: {loss_long} ({loss_long/loss_count*100:.1f}%)")
    print(f"  做空止损: {loss_short} ({loss_short/loss_count*100:.1f}%)")
    
    print(f"\n止盈交易:")
    print(f"  做多止盈: {profit_long} ({profit_long/profit_count*100:.1f}%)")
    print(f"  做空止盈: {profit_short} ({profit_short/profit_count*100:.1f}%)")
    
    # 计算各方向的胜率
    total_long = loss_long + profit_long
    total_short = loss_short + profit_short
    
    print(f"\n方向胜率:")
    print(f"  做多胜率: {profit_long/total_long*100:.1f}% ({profit_long}/{total_long})")
    print(f"  做空胜率: {profit_short/total_short*100:.1f}% ({profit_short}/{total_short})")
    
    # 分析持仓时长
    print(f"\n{'='*80}")
    print("持仓时长分析")
    print(f"{'='*80}")
    
    loss_holding = [t['holding_bars'] for t in loss_trades]
    profit_holding = [t['holding_bars'] for t in profit_trades]
    
    print(f"\n止损交易持仓:")
    print(f"  平均: {statistics.mean(loss_holding):.1f}根K线")
    print(f"  中位数: {statistics.median(loss_holding):.1f}根K线")
    
    print(f"\n止盈交易持仓:")
    print(f"  平均: {statistics.mean(profit_holding):.1f}根K线")
    print(f"  中位数: {statistics.median(profit_holding):.1f}根K线")
    
    # 早期止损分析
    early_loss = len([t for t in loss_trades if t['holding_bars'] <= 10])
    print(f"\n早期止损(≤10根K线): {early_loss} ({early_loss/loss_count*100:.1f}%)")
    
    return {
        'total': total,
        'profit_count': profit_count,
        'loss_count': loss_count,
        'loss_k1_avg': statistics.mean(loss_k1_ranges),
        'profit_k1_avg': statistics.mean(profit_k1_ranges),
        'loss_k2_breakout_avg': statistics.mean(loss_k2_breakouts),
        'profit_k2_breakout_avg': statistics.mean(profit_k2_breakouts),
    }


def recommend_strategies(analysis_result):
    """基于分析结果推荐减少止损的策略"""
    
    print(f"\n{'='*80}")
    print("减少止损的策略推荐")
    print(f"{'='*80}")
    
    loss_count = analysis_result['loss_count']
    profit_count = analysis_result['profit_count']
    total = analysis_result['total']
    
    print(f"""
【核心问题】
- 当前止损率: {loss_count/total*100:.1f}% ({loss_count}次)
- 每次止损损失: 100% (1 USDT)
- 每次止盈收益: 40% (0.4 USDT)
- 盈亏比: 1次止损 = 2.5次止盈

【减少止损的策略】

策略1: 提高K1振幅要求 ⭐⭐⭐⭐⭐
原理: 止损交易的K1振幅({analysis_result['loss_k1_avg']:.3f}%) > 止盈交易({analysis_result['profit_k1_avg']:.3f}%)
建议: 
  - 当前K1范围: 0.2%-0.51%
  - 优化方向: 缩小上限至0.46%或更低
  - 预期效果: 过滤掉振幅过大的信号，减少30-40%的止损
  - 风险: 交易量会减少，但整体净收益会提高

策略2: 限制K2突破幅度 ⭐⭐⭐⭐
原理: 突破幅度过大的信号往往是假突破
建议:
  - 设置max_k2_breakout参数
  - 限制K2突破K1的最大幅度(如0.3%-0.5%)
  - 预期效果: 减少20-30%的止损
  - 需要: 修改代码增加此参数

策略3: 增加K2实体和影线要求 ⭐⭐⭐⭐
原理: 通过K2形态筛选高质量信号
建议:
  - min_k2_shadow_percent: 30-50% (要求影线足够长)
  - max_k2_body_percent: 50-70% (要求实体不能太大)
  - 预期效果: 减少15-25%的止损
  - 优势: 当前正在遍历优化中

策略4: 区分做多做空策略 ⭐⭐⭐
原理: 不同方向可能有不同的最优参数
建议:
  - 分别优化做多和做空的参数
  - 或者只做胜率更高的方向
  - 预期效果: 提高5-10%胜率

策略5: 早期止损保护 ⭐⭐
原理: {loss_count}次止损中，早期(≤10根K线)占比较高
建议:
  - 前5根K线：更严格的止损(如-50%)
  - 5-10根K线：渐进放松至-100%
  - 预期效果: 减少10-15%的大额止损
  - 风险: 可能增加小额止损次数

【参数优化建议】

优先级1: K1振幅参数 (立即可测试)
- min_k1_range: 0.2% (保持)
- max_k1_range: 0.46% → 0.40% (收紧)
- 目标: 减少止损30%，保持交易量>300

优先级2: K2参数优化 (正在遍历中)
- 等待三维遍历结果
- 重点关注止损率低的参数组合
- 次要关注总收益

优先级3: 组合策略
- K1范围: 0.2%-0.40%
- K2 body: 10%-60%
- K2 shadow: 30%-50%
- 预期: 止损率<20%，交易量>200

【评估标准】

✓ 交易量 >= 200次
✓ 止损率 <= 20% (当前{loss_count/total*100:.1f}%)
✓ 净收益 = 止盈次数×0.4 - 止损次数×1.0 > 当前({profit_count*0.4 - loss_count*1.0:.1f} USDT)

【下一步行动】

1. 测试K1上限从0.51%降至0.46%、0.40%、0.35%的效果
2. 查看K2三维遍历结果，筛选止损率<20%的组合
3. 创建综合评分: 净收益优先，而非胜率优先
   新评分 = (止盈次数×0.4 - 止损次数×1.0) / 总次数
4. 对最优参数进行完整回测验证
    """)


def test_k1_upper_limit():
    """测试不同K1上限对止损率的影响"""
    
    print(f"\n{'='*80}")
    print("测试不同K1上限参数")
    print(f"{'='*80}")
    
    cache_file = "btcusdt_15m_klines.json"
    if not os.path.exists(cache_file):
        print(f"提示: 需要K线数据文件进行测试")
        return
    
    print(f"\n建议测试以下K1上限参数:")
    
    test_params = [
        {"max_k1": 0.51, "name": "当前参数"},
        {"max_k1": 0.46, "name": "收紧5bp"},
        {"max_k1": 0.40, "name": "收紧11bp"},
        {"max_k1": 0.35, "name": "收紧16bp"},
        {"max_k1": 0.30, "name": "收紧21bp"},
    ]
    
    print(f"\n{'参数名称':<15} {'K1上限':<10} {'预期效果'}")
    print("-"*60)
    for p in test_params:
        if p['max_k1'] == 0.51:
            effect = f"基准 (止损率{26.8:.1f}%)"
        else:
            reduction = (0.51 - p['max_k1']) / 0.51 * 30  # 估算
            effect = f"预计减少{reduction:.0f}%止损"
        print(f"{p['name']:<15} {p['max_k1']:<10.2f} {effect}")
    
    print(f"\n建议: 先测试0.46和0.40这两个参数")


def main():
    """主函数"""
    
    # 分析止损交易特征
    result = analyze_stop_loss_patterns()
    
    # 推荐策略
    recommend_strategies(result)
    
    # 测试参数建议
    test_k1_upper_limit()
    
    print(f"\n{'='*80}")
    print("分析完成")
    print(f"{'='*80}")


if __name__ == '__main__':
    main()
