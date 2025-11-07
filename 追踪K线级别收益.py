"""
详细追踪每笔交易的K线级别收益
找出10根K线后未止盈交易的最佳平仓时机
"""

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


class ThreeKlineStrategy:
    """三K线策略 - 简化版用于分析"""
    
    def __init__(self):
        self.signals = []
        
    def is_contained(self, k1: KLine, k2: KLine) -> bool:
        return k2.high <= k1.high and k2.low >= k1.low
    
    def check_rule1(self, k1: KLine, k2: KLine, 
                   min_range_percent: float = 0.005, 
                   max_range_percent: float = 0.005) -> tuple:
        k1_range = abs(k1.close - k1.open) / k1.open
        if k1_range < min_range_percent or k1_range > max_range_percent:
            return (False, None)
        
        body_in_range = (k2.body_high <= k1.high and k2.body_low >= k1.low)
        if not body_in_range:
            return (False, None)
        
        if k2.low < k1.low:
            return (True, 'long')
        elif k2.high > k1.high:
            return (True, 'short')
        
        return (False, None)
    
    def analyze_signals_detailed(self, klines: List[KLine], 
                                 profit_target: float = 0.008,
                                 min_k1_range: float = 0.002,
                                 max_k1_range: float = 0.0051,
                                 leverage: int = 50) -> List[Dict]:
        """分析信号，记录每根K线的收益情况"""
        
        signals = []
        i = 0
        in_position = False
        
        while i < len(klines) - 2:
            if in_position:
                i += 1
                continue

            k1 = klines[i]
            k2 = klines[i + 1]
            signal = None
            entry_index = None

            if i < len(klines) - 2 and self.is_contained(k1, k2):
                k3 = klines[i + 2]
                is_valid, direction = self.check_rule1(k1, k3, min_k1_range, max_k1_range)
                if is_valid:
                    signal = {
                        'type': 'rule2',
                        'direction': direction,
                        'k1': k1,
                        'entry_price': k3.close,
                        'entry_time': k3.timestamp,
                        'entry_index': i + 2
                    }
                    entry_index = i + 3
                    in_position = True
                    i += 2
            else:
                is_valid, direction = self.check_rule1(k1, k2, min_k1_range, max_k1_range)
                if is_valid:
                    signal = {
                        'type': 'rule1',
                        'direction': direction,
                        'k1': k1,
                        'entry_price': k2.close,
                        'entry_time': k2.timestamp,
                        'entry_index': i + 1
                    }
                    entry_index = i + 2
                    in_position = True
                    i += 1

            if signal and entry_index:
                entry_price = signal['entry_price']
                direction = signal['direction']
                k1 = signal['k1']
                
                # 记录每根K线的收益情况
                bar_returns = []
                max_return_ever = -999
                max_return_bar = 0
                reached_40 = False
                reached_40_bar = 0
                
                # 分析最多50根K线
                for j in range(entry_index, min(entry_index + 50, len(klines))):
                    current_kline = klines[j]
                    holding_bars = j - entry_index + 1
                    
                    if direction == 'long':
                        high_return = (current_kline.high - entry_price) / entry_price
                        low_return = (current_kline.low - entry_price) / entry_price
                        close_return = (current_kline.close - entry_price) / entry_price
                    else:
                        high_return = (entry_price - current_kline.low) / entry_price
                        low_return = (entry_price - current_kline.high) / entry_price
                        close_return = (entry_price - current_kline.close) / entry_price
                    
                    # 记录本根K线的表现
                    bar_info = {
                        'bar': holding_bars,
                        'high_return': high_return * leverage * 100,  # 转换为合约收益%
                        'low_return': low_return * leverage * 100,
                        'close_return': close_return * leverage * 100,
                        'timestamp': current_kline.timestamp
                    }
                    bar_returns.append(bar_info)
                    
                    # 更新最高收益
                    if high_return * leverage * 100 > max_return_ever:
                        max_return_ever = high_return * leverage * 100
                        max_return_bar = holding_bars
                    
                    # 检查是否达到40%止盈
                    if not reached_40 and high_return >= profit_target:
                        reached_40 = True
                        reached_40_bar = holding_bars
                    
                    # 检查止损
                    liquidation_threshold = -1.0 / leverage
                    if low_return <= liquidation_threshold:
                        signal['exit_type'] = 'stop_loss'
                        signal['exit_bar'] = holding_bars
                        break
                
                signal['bar_returns'] = bar_returns
                signal['max_return'] = max_return_ever
                signal['max_return_bar'] = max_return_bar
                signal['reached_40'] = reached_40
                signal['reached_40_bar'] = reached_40_bar if reached_40 else None
                
                signals.append(signal)
                in_position = False

            i += 1

        return signals


def main():
    """主函数"""
    
    print("="*80)
    print("详细追踪交易的K线级别收益表现")
    print("="*80)
    
    # 读取K线数据
    cache_file = "btcusdt_15m_klines.json"
    if not os.path.exists(cache_file):
        print(f"错误: 找不到K线数据文件")
        return
    
    print(f"\n正在加载K线数据...")
    with open(cache_file, 'r', encoding='utf-8') as f:
        raw_klines = json.load(f)
    klines = [KLine(k) for k in raw_klines]
    print(f"✓ 已加载 {len(klines)} 根K线数据")
    
    # 创建策略实例
    strategy = ThreeKlineStrategy()
    
    # 参数设置
    leverage = 50
    profit_target_percent = 40
    price_profit_target = profit_target_percent / leverage / 100
    min_k1_range = 0.002 / 100
    max_k1_range = 0.51 / 100
    
    print(f"\n正在分析交易信号...")
    signals = strategy.analyze_signals_detailed(
        klines,
        profit_target=price_profit_target,
        min_k1_range=min_k1_range,
        max_k1_range=max_k1_range,
        leverage=leverage
    )
    
    print(f"✓ 找到 {len(signals)} 个交易信号")
    
    # 分析达到40%止盈的交易
    reached_40 = [s for s in signals if s['reached_40']]
    not_reached_40 = [s for s in signals if not s['reached_40']]
    
    print(f"\n{'='*80}")
    print("交易分类统计")
    print(f"{'='*80}")
    print(f"达到40%止盈: {len(reached_40)} ({len(reached_40)/len(signals)*100:.1f}%)")
    print(f"未达到40%止盈: {len(not_reached_40)} ({len(not_reached_40)/len(signals)*100:.1f}%)")
    
    # 分析达到40%的交易
    if reached_40:
        bars_to_40 = [s['reached_40_bar'] for s in reached_40]
        print(f"\n达到40%止盈的交易:")
        print(f"  平均耗时: {statistics.mean(bars_to_40):.1f}根K线")
        print(f"  中位数: {statistics.median(bars_to_40):.1f}根K线")
        print(f"  最快: {min(bars_to_40)}根K线")
        print(f"  最慢: {max(bars_to_40)}根K线")
        
        # 统计分布
        within_5 = len([b for b in bars_to_40 if b <= 5])
        within_10 = len([b for b in bars_to_40 if b <= 10])
        within_15 = len([b for b in bars_to_40 if b <= 15])
        within_20 = len([b for b in bars_to_40 if b <= 20])
        
        print(f"\n达到40%止盈的时间分布:")
        print(f"  5根K线内: {within_5} ({within_5/len(reached_40)*100:.1f}%)")
        print(f"  10根K线内: {within_10} ({within_10/len(reached_40)*100:.1f}%)")
        print(f"  15根K线内: {within_15} ({within_15/len(reached_40)*100:.1f}%)")
        print(f"  20根K线内: {within_20} ({within_20/len(reached_40)*100:.1f}%)")
    
    # 重点分析：10根K线后仍未达到40%的交易
    print(f"\n{'='*80}")
    print("10根K线后未达到40%的交易分析")
    print(f"{'='*80}")
    
    delayed_signals = [s for s in signals if not s['reached_40'] or s['reached_40_bar'] > 10]
    
    print(f"\n10根K线后仍未止盈的交易: {len(delayed_signals)}")
    
    if delayed_signals:
        # 分析这些交易在第10根K线时的收益情况
        returns_at_bar_10 = []
        max_returns_after_10 = []
        
        for sig in delayed_signals:
            if len(sig['bar_returns']) >= 10:
                bar_10 = sig['bar_returns'][9]  # 第10根K线(索引9)
                returns_at_bar_10.append(bar_10['high_return'])
                
                # 找出第10根之后的最高收益
                max_after_10 = max([b['high_return'] for b in sig['bar_returns'][10:]] if len(sig['bar_returns']) > 10 else [bar_10['high_return']])
                max_returns_after_10.append(max_after_10)
        
        if returns_at_bar_10:
            print(f"\n第10根K线时的收益情况:")
            print(f"  平均最高收益: {statistics.mean(returns_at_bar_10):.2f}%")
            print(f"  中位数: {statistics.median(returns_at_bar_10):.2f}%")
            print(f"  最小: {min(returns_at_bar_10):.2f}%")
            print(f"  最大: {max(returns_at_bar_10):.2f}%")
            
            # 统计有盈利的比例
            profitable = len([r for r in returns_at_bar_10 if r > 0])
            print(f"\n第10根K线时有盈利的: {profitable} ({profitable/len(returns_at_bar_10)*100:.1f}%)")
            
            # 比较第10根vs之后的最高收益
            if max_returns_after_10:
                improvement = [max_returns_after_10[i] - returns_at_bar_10[i] for i in range(len(returns_at_bar_10))]
                avg_improvement = statistics.mean(improvement)
                
                print(f"\n继续持有的收益改善:")
                print(f"  平均改善: {avg_improvement:+.2f}%")
                
                improved_count = len([i for i in improvement if i > 0])
                worsened_count = len([i for i in improvement if i < 0])
                
                print(f"  收益提升的: {improved_count} ({improved_count/len(improvement)*100:.1f}%)")
                print(f"  收益下降的: {worsened_count} ({worsened_count/len(improvement)*100:.1f}%)")
    
    # 提供具体建议
    print(f"\n{'='*80}")
    print("最佳处理策略建议")
    print(f"{'='*80}")
    
    if returns_at_bar_10:
        avg_return_at_10 = statistics.mean(returns_at_bar_10)
        profitable_rate = profitable / len(returns_at_bar_10) * 100
        
        print(f"""
基于{len(delayed_signals)}笔10根K线后未止盈的交易分析:

【关键发现】
1. 第10根K线时平均最高收益: {avg_return_at_10:.2f}%
2. 第10根K线时有盈利的概率: {profitable_rate:.1f}%
3. 继续持有平均改善: {avg_improvement:+.2f}%
4. 收益提升概率: {improved_count/len(improvement)*100:.1f}%

【策略推荐】

方案1: 第10根K线立即平仓(如果有盈利)
- 适用场景: 保守型，追求稳定收益
- 预期效果: 平均收益约{avg_return_at_10:.2f}%
- 优点: 快速止盈，减少风险
- 缺点: 可能错过后续更高收益

方案2: 第10根K线设置保护性止损
- 适用场景: 平衡型，兼顾收益和风险
- 具体做法: 第10根K线后，如果收益回撤到10%以下就平仓
- 预期效果: 既保护已有盈利，又给予上涨空间
- 优点: 平衡收益与风险

方案3: 延长至15-20根K线再决定
- 适用场景: 激进型，追求最大收益
- 具体做法: 延长持仓时间，给予更多机会达到40%
- 预期效果: 可能获得更高收益，但风险也增加
- 缺点: 可能面临止损

【最终建议】
根据数据分析，推荐使用【方案2】:
- 前10根K线: 等待达到40%完全止盈
- 第10根K线: 如果收益>20%，设置保护性止损在15%
- 第10根K线: 如果收益10-20%，有盈利就平仓
- 第10根K线: 如果收益<10%，继续等待但设置止损
        """)


if __name__ == '__main__':
    main()
