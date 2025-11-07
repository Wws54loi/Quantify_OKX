"""
遍历K1开收涨跌幅要求，寻找最优策略
区间: 0.21% - 0.5%
步进: 0.01%
"""

import json
import os
from datetime import datetime
from typing import List, Dict


class KLine:
    """K线数据类"""
    
    def __init__(self, kline_data: List):
        """初始化K线对象"""
        self.timestamp = int(kline_data[0])
        self.open = float(kline_data[1])
        self.high = float(kline_data[2])
        self.low = float(kline_data[3])
        self.close = float(kline_data[4])
        self.volume = float(kline_data[5])
        
        # 计算实体部分
        self.body_high = max(self.open, self.close)
        self.body_low = min(self.open, self.close)


class ThreeKlineStrategy:
    """三K线策略"""
    
    def __init__(self):
        self.signals = []
        
    def is_contained(self, k1: KLine, k2: KLine) -> bool:
        """判断k2是否被k1完全包含"""
        return k2.high <= k1.high and k2.low >= k1.low
    
    def check_rule1(self, k1: KLine, k2: KLine, min_range_percent: float = 0.005) -> tuple:
        """检查法则1"""
        k1_range = abs(k1.close - k1.open) / k1.open
        if k1_range < min_range_percent:
            return (False, None)
        
        body_in_range = (k2.body_high <= k1.high and k2.body_low >= k1.low)
        
        if not body_in_range:
            return (False, None)
        
        if k2.low < k1.low:
            return (True, 'long')
        elif k2.high > k1.high:
            return (True, 'short')
        
        return (False, None)
    
    def find_signals(self, klines: List[KLine], 
                    profit_target: float = 0.008, 
                    stop_loss: float = 1.0,
                    min_k1_range: float = 0.005,
                    max_holding_bars_tp: int = None,
                    max_holding_bars_sl: int = None,
                    allow_stop_loss_retry: bool = True,
                    stop_loss_delay_bars: int = 10,
                    leverage: int = 50) -> List[Dict]:
        """查找所有交易信号"""
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
                is_valid, direction = self.check_rule1(k1, k3, min_k1_range)
                if is_valid:
                    signal = {
                        'type': 'rule2',
                        'direction': direction,
                        'k1': k1,
                        'k2': k2,
                        'k3': k3,
                        'entry_price': k3.close,
                        'entry_time': k3.timestamp,
                        'entry_index': i + 2
                    }
                    entry_index = i + 3
                    in_position = True
                    i += 2
            else:
                is_valid, direction = self.check_rule1(k1, k2, min_k1_range)
                if is_valid:
                    signal = {
                        'type': 'rule1',
                        'direction': direction,
                        'k1': k1,
                        'k2': k2,
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
                stop_loss_hit_count = 0
                k1 = signal['k1']
                if direction == 'long':
                    target_price = k1.high
                    profit_target_dynamic = (target_price - entry_price) / entry_price
                else:
                    target_price = k1.low
                    profit_target_dynamic = (entry_price - target_price) / entry_price
                if profit_target_dynamic < profit_target:
                    profit_target_dynamic = profit_target

                for j in range(entry_index, len(klines)):
                    current_kline = klines[j]
                    holding_bars = j - entry_index + 1
                    if direction == 'long':
                        high_return = (current_kline.high - entry_price) / entry_price
                        low_return = (current_kline.low - entry_price) / entry_price
                        current_return = (current_kline.close - entry_price) / entry_price
                    else:
                        high_return = (entry_price - current_kline.low) / entry_price
                        low_return = (entry_price - current_kline.high) / entry_price
                        current_return = (entry_price - current_kline.close) / entry_price

                    liquidation_threshold = -1.0 / leverage
                    
                    if low_return <= liquidation_threshold:
                        signal['exit_type'] = 'stop_loss'
                        signal['exit_price'] = entry_price * (1 + liquidation_threshold) if direction == 'long' else entry_price * (1 - liquidation_threshold)
                        signal['exit_time'] = current_kline.timestamp
                        signal['exit_index'] = j
                        signal['holding_bars'] = holding_bars
                        signal['return'] = liquidation_threshold
                        signal['stop_loss_hit_count'] = stop_loss_hit_count
                        signals.append(signal)
                        in_position = False
                        break
                    elif high_return >= profit_target_dynamic:
                        signal['exit_type'] = 'take_profit'
                        signal['exit_price'] = target_price
                        signal['exit_time'] = current_kline.timestamp
                        signal['exit_index'] = j
                        signal['holding_bars'] = holding_bars
                        signal['return'] = profit_target_dynamic
                        signal['stop_loss_hit_count'] = stop_loss_hit_count
                        signals.append(signal)
                        in_position = False
                        break
                    elif holding_bars > stop_loss_delay_bars and high_return > 0:
                        if direction == 'long':
                            exit_price = max(entry_price * 1.0001, current_kline.close)
                        else:
                            exit_price = min(entry_price * 0.9999, current_kline.close)
                        if direction == 'long':
                            actual_return = (exit_price - entry_price) / entry_price
                        else:
                            actual_return = (entry_price - exit_price) / entry_price
                        
                        signal['exit_type'] = 'partial_profit'
                        signal['exit_price'] = exit_price
                        signal['exit_time'] = current_kline.timestamp
                        signal['exit_index'] = j
                        signal['holding_bars'] = holding_bars
                        signal['return'] = actual_return
                        signal['stop_loss_hit_count'] = stop_loss_hit_count
                        signals.append(signal)
                        in_position = False
                        break

                if in_position:
                    in_position = False

            i += 1

        self.signals = signals
        return signals
    
    def calculate_win_rate(self, signals: List[Dict], 
                          leverage: int = 50,
                          initial_capital: float = 1.0) -> Dict:
        """计算胜率"""
        if not signals:
            return {
                'total_signals': 0,
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'take_profit_count': 0,
                'partial_profit_count': 0,
                'win_rate': 0.0,
                'avg_profit': 0.0,
                'avg_loss': 0.0,
                'avg_holding_bars': 0.0,
                'total_pnl': 0.0,
                'profit_factor': 0.0,
            }
        
        wins = 0
        losses = 0
        take_profit_count = 0
        partial_profit_count = 0
        profits = []
        losses_list = []
        holding_bars_list = []
        total_capital = 0.0
        
        for signal in signals:
            return_pct = signal['return']
            holding_bars = signal['holding_bars']
            exit_type = signal['exit_type']
            
            holding_bars_list.append(holding_bars)
            pnl = initial_capital * return_pct * leverage
            total_capital += pnl
            
            if exit_type == 'take_profit':
                wins += 1
                take_profit_count += 1
                profits.append(return_pct)
            elif exit_type == 'partial_profit':
                wins += 1
                partial_profit_count += 1
                profits.append(return_pct)
            elif exit_type == 'stop_loss':
                losses += 1
                losses_list.append(return_pct)
        
        total_trades = wins + losses
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        avg_profit = sum(profits) / len(profits) if profits else 0
        avg_loss = sum(losses_list) / len(losses_list) if losses_list else 0
        avg_holding_bars = sum(holding_bars_list) / len(holding_bars_list) if holding_bars_list else 0
        
        return {
            'total_signals': len(signals),
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'take_profit_count': take_profit_count,
            'partial_profit_count': partial_profit_count,
            'win_rate': win_rate,
            'avg_profit': avg_profit * 100,
            'avg_loss': avg_loss * 100,
            'avg_holding_bars': avg_holding_bars,
            'total_pnl': total_capital,
            'profit_factor': abs(sum(profits) / sum(losses_list)) if losses_list and sum(losses_list) != 0 else float('inf'),
        }


def test_k1_range(klines: List[KLine], k1_range_percent: float, 
                  leverage: int = 50, stop_loss_delay_bars: int = 10) -> Dict:
    """
    测试特定K1开收涨跌幅要求下的策略表现
    
    参数:
        klines: K线列表
        k1_range_percent: K1开收涨跌幅要求（百分比形式）
        leverage: 杠杆倍数
        stop_loss_delay_bars: 止损延迟K线数
    
    返回:
        策略统计结果
    """
    strategy = ThreeKlineStrategy()
    
    # 计算价格变动百分比
    profit_target_percent = 40
    stop_loss_percent = 100
    price_profit_target = profit_target_percent / leverage / 100
    price_stop_loss = stop_loss_percent / leverage / 100
    min_k1_range = k1_range_percent / 100
    
    # 查找信号
    signals = strategy.find_signals(
        klines, 
        profit_target=price_profit_target,
        stop_loss=price_stop_loss,
        min_k1_range=min_k1_range,
        stop_loss_delay_bars=stop_loss_delay_bars,
        leverage=leverage
    )
    
    # 计算统计数据
    stats = strategy.calculate_win_rate(signals, leverage=leverage, initial_capital=1.0)
    
    return {
        'k1_range_percent': k1_range_percent,
        'total_trades': stats['total_trades'],
        'wins': stats['wins'],
        'losses': stats['losses'],
        'take_profit_count': stats.get('take_profit_count', 0),
        'partial_profit_count': stats.get('partial_profit_count', 0),
        'win_rate': stats['win_rate'],
        'avg_profit': stats['avg_profit'],
        'avg_loss': stats['avg_loss'],
        'profit_factor': stats['profit_factor'],
        'total_pnl': stats['total_pnl'],
        'total_return_pct': (stats['total_pnl'] / (stats['total_trades'] * 1.0) * 100) if stats['total_trades'] > 0 else 0,
        'avg_holding_bars': stats['avg_holding_bars'],
    }


def main():
    """主函数"""
    print("="*80)
    print("K1开收涨跌幅要求优化测试")
    print("="*80)
    print("测试区间: 0.21% - 0.5%")
    print("步进: 0.01%")
    print("="*80)
    
    # 读取K线数据
    cache_file = "btcusdt_15m_klines.json"
    if not os.path.exists(cache_file):
        print("错误: 未找到K线数据缓存文件")
        return
    
    print("\n正在读取K线数据...")
    with open(cache_file, 'r', encoding='utf-8') as f:
        raw_klines = json.load(f)
    
    klines = [KLine(k) for k in raw_klines]
    print(f"✓ 成功读取 {len(klines)} 根K线数据")
    
    # 测试参数范围
    start_percent = 0.21
    end_percent = 0.50
    step_percent = 0.01
    
    # 生成测试点
    test_points = []
    current = start_percent
    while current <= end_percent + 0.001:  # 加一点误差避免浮点数问题
        test_points.append(round(current, 2))
        current += step_percent
    
    print(f"\n将测试 {len(test_points)} 个参数值:")
    print(f"参数列表: {test_points}")
    
    # 执行测试
    results = []
    print("\n开始测试...")
    print("-"*80)
    
    for i, k1_range in enumerate(test_points, 1):
        print(f"\n[{i}/{len(test_points)}] 测试 K1开收涨跌幅 = {k1_range:.2f}%")
        
        result = test_k1_range(klines, k1_range)
        results.append(result)
        
        print(f"  总交易: {result['total_trades']}笔")
        print(f"  胜率: {result['win_rate']:.2f}%")
        print(f"  完全止盈: {result['take_profit_count']}笔 ({result['take_profit_count']/result['total_trades']*100:.1f}%)" if result['total_trades'] > 0 else "  完全止盈: 0笔")
        print(f"  部分止盈: {result['partial_profit_count']}笔 ({result['partial_profit_count']/result['total_trades']*100:.1f}%)" if result['total_trades'] > 0 else "  部分止盈: 0笔")
        print(f"  盈亏比: {result['profit_factor']:.2f}")
        print(f"  总收益率: {result['total_return_pct']:+.2f}%")
    
    # 分析结果
    print("\n" + "="*80)
    print("测试结果汇总")
    print("="*80)
    
    # 按不同指标排序
    by_total_return = sorted(results, key=lambda x: x['total_return_pct'], reverse=True)
    by_win_rate = sorted(results, key=lambda x: x['win_rate'], reverse=True)
    by_profit_factor = sorted(results, key=lambda x: x['profit_factor'], reverse=True)
    by_take_profit_ratio = sorted(results, key=lambda x: x['take_profit_count']/max(x['total_trades'], 1), reverse=True)
    
    print("\n📊 按总收益率排名 (前5):")
    print("-"*80)
    print(f"{'排名':<6} {'K1涨跌幅':<12} {'总交易':<10} {'胜率':<10} {'完全止盈':<12} {'收益率':<12}")
    print("-"*80)
    for i, r in enumerate(by_total_return[:5], 1):
        tp_ratio = f"{r['take_profit_count']}/{r['total_trades']}" if r['total_trades'] > 0 else "0/0"
        print(f"{i:<6} {r['k1_range_percent']:.2f}%{'':<7} {r['total_trades']:<10} {r['win_rate']:.2f}%{'':<4} {tp_ratio:<12} {r['total_return_pct']:+.2f}%")
    
    print("\n📈 按胜率排名 (前5):")
    print("-"*80)
    print(f"{'排名':<6} {'K1涨跌幅':<12} {'总交易':<10} {'胜率':<10} {'完全止盈':<12} {'收益率':<12}")
    print("-"*80)
    for i, r in enumerate(by_win_rate[:5], 1):
        tp_ratio = f"{r['take_profit_count']}/{r['total_trades']}" if r['total_trades'] > 0 else "0/0"
        print(f"{i:<6} {r['k1_range_percent']:.2f}%{'':<7} {r['total_trades']:<10} {r['win_rate']:.2f}%{'':<4} {tp_ratio:<12} {r['total_return_pct']:+.2f}%")
    
    print("\n💰 按盈亏比排名 (前5):")
    print("-"*80)
    print(f"{'排名':<6} {'K1涨跌幅':<12} {'总交易':<10} {'盈亏比':<10} {'完全止盈':<12} {'收益率':<12}")
    print("-"*80)
    for i, r in enumerate(by_profit_factor[:5], 1):
        tp_ratio = f"{r['take_profit_count']}/{r['total_trades']}" if r['total_trades'] > 0 else "0/0"
        print(f"{i:<6} {r['k1_range_percent']:.2f}%{'':<7} {r['total_trades']:<10} {r['profit_factor']:.2f}{'':<6} {tp_ratio:<12} {r['total_return_pct']:+.2f}%")
    
    print("\n🎯 按完全止盈比例排名 (前5):")
    print("-"*80)
    print(f"{'排名':<6} {'K1涨跌幅':<12} {'总交易':<10} {'完全止盈率':<14} {'胜率':<10} {'收益率':<12}")
    print("-"*80)
    for i, r in enumerate(by_take_profit_ratio[:5], 1):
        tp_rate = r['take_profit_count']/r['total_trades']*100 if r['total_trades'] > 0 else 0
        print(f"{i:<6} {r['k1_range_percent']:.2f}%{'':<7} {r['total_trades']:<10} {tp_rate:.1f}%{'':<9} {r['win_rate']:.2f}%{'':<4} {r['total_return_pct']:+.2f}%")
    
    # 推荐参数
    print("\n" + "="*80)
    print("💡 推荐参数")
    print("="*80)
    
    best_return = by_total_return[0]
    print(f"\n最佳总收益率: K1开收涨跌幅 = {best_return['k1_range_percent']:.2f}%")
    print(f"  总交易: {best_return['total_trades']}笔")
    print(f"  胜率: {best_return['win_rate']:.2f}%")
    print(f"  完全止盈: {best_return['take_profit_count']}笔 ({best_return['take_profit_count']/best_return['total_trades']*100:.1f}%)")
    print(f"  部分止盈: {best_return['partial_profit_count']}笔 ({best_return['partial_profit_count']/best_return['total_trades']*100:.1f}%)")
    print(f"  亏损: {best_return['losses']}笔 ({best_return['losses']/best_return['total_trades']*100:.1f}%)")
    print(f"  盈亏比: {best_return['profit_factor']:.2f}")
    print(f"  总收益率: {best_return['total_return_pct']:+.2f}%")
    
    # 综合评分（加权）
    print("\n综合评分 (收益率40% + 胜率20% + 盈亏比20% + 完全止盈率20%):")
    print("-"*80)
    
    for r in results:
        if r['total_trades'] > 0:
            # 归一化各项指标（0-100分）
            return_score = max(0, min(100, (r['total_return_pct'] + 10) * 5))  # -10%~10% 映射到 0~100
            win_rate_score = r['win_rate']  # 已经是0-100
            pf_score = min(100, r['profit_factor'] * 33.33)  # 0-3 映射到 0-100
            tp_rate = r['take_profit_count']/r['total_trades']*100
            tp_score = tp_rate  # 已经是0-100
            
            # 加权总分
            r['综合评分'] = (return_score * 0.4 + win_rate_score * 0.2 + 
                          pf_score * 0.2 + tp_score * 0.2)
        else:
            r['综合评分'] = 0
    
    by_综合 = sorted(results, key=lambda x: x['综合评分'], reverse=True)
    
    print(f"{'排名':<6} {'K1涨跌幅':<12} {'综合评分':<12} {'收益率':<12} {'胜率':<10} {'盈亏比':<10}")
    print("-"*80)
    for i, r in enumerate(by_综合[:10], 1):
        print(f"{i:<6} {r['k1_range_percent']:.2f}%{'':<7} {r['综合评分']:.1f}{'':<7} {r['total_return_pct']:+.2f}%{'':<6} {r['win_rate']:.2f}%{'':<4} {r['profit_factor']:.2f}")
    
    best_综合 = by_综合[0]
    print(f"\n🏆 综合最优参数: K1开收涨跌幅 = {best_综合['k1_range_percent']:.2f}%")
    print(f"   综合评分: {best_综合['综合评分']:.1f}分")
    print(f"   总收益率: {best_综合['total_return_pct']:+.2f}%")
    print(f"   胜率: {best_综合['win_rate']:.2f}%")
    print(f"   盈亏比: {best_综合['profit_factor']:.2f}")
    print(f"   完全止盈率: {best_综合['take_profit_count']/best_综合['total_trades']*100:.1f}%")
    
    # 保存详细结果到CSV
    print("\n" + "="*80)
    print("保存结果到文件...")
    
    output_file = "策略分析/k1涨跌幅优化结果.csv"
    os.makedirs("策略分析", exist_ok=True)
    
    import csv
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        fieldnames = ['K1涨跌幅%', '总交易数', '胜率%', '完全止盈', '部分止盈', '止损', 
                     '完全止盈率%', '盈亏比', '总收益率%', '综合评分']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for r in by_综合:
            tp_rate = r['take_profit_count']/r['total_trades']*100 if r['total_trades'] > 0 else 0
            writer.writerow({
                'K1涨跌幅%': f"{r['k1_range_percent']:.2f}",
                '总交易数': r['total_trades'],
                '胜率%': f"{r['win_rate']:.2f}",
                '完全止盈': r['take_profit_count'],
                '部分止盈': r['partial_profit_count'],
                '止损': r['losses'],
                '完全止盈率%': f"{tp_rate:.1f}",
                '盈亏比': f"{r['profit_factor']:.2f}",
                '总收益率%': f"{r['total_return_pct']:.2f}",
                '综合评分': f"{r['综合评分']:.1f}",
            })
    
    print(f"✓ 结果已保存到: {output_file}")
    print("="*80)


if __name__ == '__main__':
    main()
