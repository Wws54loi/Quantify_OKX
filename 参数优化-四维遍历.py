"""
四维参数优化遍历
测试参数:
- profit_target_percent: 20%-60%, 步进5%
- min_k1_range_percent: 0.2%-0.46%, 步进0.01%
- max_k1_range_percent: 0.46%-2%, 步进0.01%
- stop_loss_delay_bars: 5-15, 步进1

重点指标: 胜率、完全止盈率
"""

import json
import os
from datetime import datetime
from typing import List, Dict
import csv


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
    
    def check_rule1(self, k1: KLine, k2: KLine, min_range_percent: float = 0.005, max_range_percent: float = 0.005) -> tuple:
        """检查法则1"""
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
    
    def find_signals(self, klines: List[KLine], 
                    profit_target: float = 0.008, 
                    stop_loss: float = 1.0,
                    min_k1_range: float = 0.005,
                    max_k1_range: float = 0.005,
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
                is_valid, direction = self.check_rule1(k1, k3, min_k1_range, max_k1_range)
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
                is_valid, direction = self.check_rule1(k1, k2, min_k1_range, max_k1_range)
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


def test_parameters(klines: List[KLine], 
                   profit_target_percent: float,
                   min_k1_range_percent: float,
                   max_k1_range_percent: float,
                   stop_loss_delay_bars: int,
                   leverage: int = 50) -> Dict:
    """测试特定参数组合"""
    strategy = ThreeKlineStrategy()
    
    # 计算价格变动百分比
    stop_loss_percent = 100
    price_profit_target = profit_target_percent / leverage / 100
    price_stop_loss = stop_loss_percent / leverage / 100
    min_k1_range = min_k1_range_percent / 100
    max_k1_range = max_k1_range_percent / 100
    
    # 查找信号
    signals = strategy.find_signals(
        klines, 
        profit_target=price_profit_target,
        stop_loss=price_stop_loss,
        min_k1_range=min_k1_range,
        max_k1_range=max_k1_range,
        stop_loss_delay_bars=stop_loss_delay_bars,
        leverage=leverage
    )
    
    # 计算统计数据
    stats = strategy.calculate_win_rate(signals, leverage=leverage, initial_capital=1.0)
    
    # 计算完全止盈率
    take_profit_rate = (stats['take_profit_count'] / stats['total_trades'] * 100) if stats['total_trades'] > 0 else 0
    
    return {
        'profit_target_percent': profit_target_percent,
        'min_k1_range_percent': min_k1_range_percent,
        'max_k1_range_percent': max_k1_range_percent,
        'stop_loss_delay_bars': stop_loss_delay_bars,
        'total_trades': stats['total_trades'],
        'wins': stats['wins'],
        'losses': stats['losses'],
        'take_profit_count': stats.get('take_profit_count', 0),
        'partial_profit_count': stats.get('partial_profit_count', 0),
        'win_rate': stats['win_rate'],
        'take_profit_rate': take_profit_rate,
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
    print("四维参数优化遍历")
    print("="*80)
    print("参数范围:")
    print("  profit_target_percent: 20%-60%, 步进5%")
    print("  min_k1_range_percent: 0.2%-0.46%, 步进0.01%")
    print("  max_k1_range_percent: 0.46%-1.0%, 步进0.01%")
    print("  stop_loss_delay_bars: 5-15, 步进1")
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
    
    # 生成参数组合
    profit_target_list = list(range(20, 65, 5))  # 20, 25, 30, ..., 60
    min_k1_range_list = [round(x * 0.01, 2) for x in range(20, 47)]  # 0.20, 0.21, ..., 0.46
    max_k1_range_list = [round(x * 0.01, 2) for x in range(46, 101)]  # 0.46, 0.47, ..., 1.00
    stop_loss_delay_list = list(range(5, 16))  # 5, 6, ..., 15
    
    total_combinations = (len(profit_target_list) * len(min_k1_range_list) * 
                         len(max_k1_range_list) * len(stop_loss_delay_list))
    
    print(f"\n参数组合统计:")
    print(f"  profit_target: {len(profit_target_list)} 个值")
    print(f"  min_k1_range: {len(min_k1_range_list)} 个值")
    print(f"  max_k1_range: {len(max_k1_range_list)} 个值")
    print(f"  stop_loss_delay: {len(stop_loss_delay_list)} 个值")
    print(f"  总组合数: {total_combinations:,}")
    
    # 确认是否继续
    print(f"\n⚠️  警告: 将测试 {total_combinations:,} 个参数组合，预计耗时较长")
    print("提示: 建议先缩小参数范围进行测试")
    
    # 执行测试
    results = []
    print("\n开始测试...")
    print("-"*80)
    
    count = 0
    start_time = datetime.now()
    
    for profit_target in profit_target_list:
        for min_k1 in min_k1_range_list:
            for max_k1 in max_k1_range_list:
                # 跳过无效组合：最小值必须小于等于最大值
                if min_k1 > max_k1:
                    continue
                    
                for delay_bars in stop_loss_delay_list:
                    count += 1
                    
                    if count % 1000 == 0:
                        elapsed = (datetime.now() - start_time).total_seconds()
                        speed = count / elapsed if elapsed > 0 else 0
                        remaining = (total_combinations - count) / speed if speed > 0 else 0
                        print(f"进度: {count}/{total_combinations} ({count/total_combinations*100:.1f}%) | "
                              f"速度: {speed:.1f} 组/秒 | 预计剩余: {remaining/60:.1f} 分钟")
                    
                    result = test_parameters(
                        klines, 
                        profit_target, 
                        min_k1, 
                        max_k1, 
                        delay_bars
                    )
                    results.append(result)
    
    elapsed_time = (datetime.now() - start_time).total_seconds()
    print(f"\n✓ 测试完成！总耗时: {elapsed_time/60:.1f} 分钟")
    print(f"  有效组合数: {len(results):,}")
    
    # 分析结果
    print("\n" + "="*80)
    print("测试结果分析")
    print("="*80)
    
    # 过滤掉交易数过少的结果
    min_trades = 100
    valid_results = [r for r in results if r['total_trades'] >= min_trades]
    print(f"\n过滤条件: 至少 {min_trades} 笔交易")
    print(f"符合条件的组合: {len(valid_results):,}")
    
    if not valid_results:
        print("没有符合条件的结果！")
        return
    
    # 按胜率排序
    by_win_rate = sorted(valid_results, key=lambda x: x['win_rate'], reverse=True)
    
    # 按完全止盈率排序
    by_take_profit_rate = sorted(valid_results, key=lambda x: x['take_profit_rate'], reverse=True)
    
    # 按总收益率排序
    by_total_return = sorted(valid_results, key=lambda x: x['total_return_pct'], reverse=True)
    
    # 综合评分（胜率50% + 完全止盈率50%）
    for r in valid_results:
        r['综合评分'] = r['win_rate'] * 0.5 + r['take_profit_rate'] * 0.5
    by_综合 = sorted(valid_results, key=lambda x: x['综合评分'], reverse=True)
    
    # 打印结果
    print("\n📊 按胜率排名 (前10):")
    print("-"*100)
    print(f"{'排名':<6} {'止盈%':<8} {'K1最小':<8} {'K1最大':<8} {'延迟':<6} {'总交易':<8} {'胜率':<10} {'完全止盈率':<12} {'收益率':<10}")
    print("-"*100)
    for i, r in enumerate(by_win_rate[:10], 1):
        print(f"{i:<6} {r['profit_target_percent']:<8} {r['min_k1_range_percent']:<8.2f} {r['max_k1_range_percent']:<8.2f} "
              f"{r['stop_loss_delay_bars']:<6} {r['total_trades']:<8} {r['win_rate']:<10.2f} "
              f"{r['take_profit_rate']:<12.2f} {r['total_return_pct']:<+10.2f}")
    
    print("\n🎯 按完全止盈率排名 (前10):")
    print("-"*100)
    print(f"{'排名':<6} {'止盈%':<8} {'K1最小':<8} {'K1最大':<8} {'延迟':<6} {'总交易':<8} {'完全止盈率':<12} {'胜率':<10} {'收益率':<10}")
    print("-"*100)
    for i, r in enumerate(by_take_profit_rate[:10], 1):
        print(f"{i:<6} {r['profit_target_percent']:<8} {r['min_k1_range_percent']:<8.2f} {r['max_k1_range_percent']:<8.2f} "
              f"{r['stop_loss_delay_bars']:<6} {r['total_trades']:<8} {r['take_profit_rate']:<12.2f} "
              f"{r['win_rate']:<10.2f} {r['total_return_pct']:<+10.2f}")
    
    print("\n💰 按总收益率排名 (前10):")
    print("-"*100)
    print(f"{'排名':<6} {'止盈%':<8} {'K1最小':<8} {'K1最大':<8} {'延迟':<6} {'总交易':<8} {'收益率':<10} {'胜率':<10} {'完全止盈率':<12}")
    print("-"*100)
    for i, r in enumerate(by_total_return[:10], 1):
        print(f"{i:<6} {r['profit_target_percent']:<8} {r['min_k1_range_percent']:<8.2f} {r['max_k1_range_percent']:<8.2f} "
              f"{r['stop_loss_delay_bars']:<6} {r['total_trades']:<8} {r['total_return_pct']:<+10.2f} "
              f"{r['win_rate']:<10.2f} {r['take_profit_rate']:<12.2f}")
    
    print("\n🏆 综合排名 (胜率50% + 完全止盈率50%) (前10):")
    print("-"*100)
    print(f"{'排名':<6} {'综合分':<8} {'止盈%':<8} {'K1最小':<8} {'K1最大':<8} {'延迟':<6} {'胜率':<10} {'完全止盈率':<12} {'收益率':<10}")
    print("-"*100)
    for i, r in enumerate(by_综合[:10], 1):
        print(f"{i:<6} {r['综合评分']:<8.2f} {r['profit_target_percent']:<8} {r['min_k1_range_percent']:<8.2f} "
              f"{r['max_k1_range_percent']:<8.2f} {r['stop_loss_delay_bars']:<6} {r['win_rate']:<10.2f} "
              f"{r['take_profit_rate']:<12.2f} {r['total_return_pct']:<+10.2f}")
    
    # 最佳参数推荐
    best = by_综合[0]
    print("\n" + "="*80)
    print("🌟 最佳参数推荐（综合评分最高）")
    print("="*80)
    print(f"止盈目标: {best['profit_target_percent']}%")
    print(f"K1涨跌幅区间: {best['min_k1_range_percent']:.2f}% - {best['max_k1_range_percent']:.2f}%")
    print(f"止损延迟: {best['stop_loss_delay_bars']} 根K线")
    print(f"\n性能指标:")
    print(f"  综合评分: {best['综合评分']:.2f}")
    print(f"  总交易数: {best['total_trades']}")
    print(f"  胜率: {best['win_rate']:.2f}%")
    print(f"  完全止盈: {best['take_profit_count']} 笔 ({best['take_profit_rate']:.2f}%)")
    print(f"  部分止盈: {best['partial_profit_count']} 笔")
    print(f"  止损: {best['losses']} 笔")
    print(f"  盈亏比: {best['profit_factor']:.2f}")
    print(f"  总收益率: {best['total_return_pct']:+.2f}%")
    
    # 保存详细结果到CSV
    print("\n" + "="*80)
    print("保存结果到文件...")
    
    output_file = "策略分析/四维参数优化结果.csv"
    os.makedirs("策略分析", exist_ok=True)
    
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        fieldnames = ['综合评分', '止盈目标%', 'K1最小%', 'K1最大%', '止损延迟', 
                     '总交易数', '胜率%', '完全止盈', '完全止盈率%', '部分止盈', '止损',
                     '盈亏比', '总收益率%', '平均持仓K线数']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for r in by_综合:
            writer.writerow({
                '综合评分': f"{r['综合评分']:.2f}",
                '止盈目标%': r['profit_target_percent'],
                'K1最小%': f"{r['min_k1_range_percent']:.2f}",
                'K1最大%': f"{r['max_k1_range_percent']:.2f}",
                '止损延迟': r['stop_loss_delay_bars'],
                '总交易数': r['total_trades'],
                '胜率%': f"{r['win_rate']:.2f}",
                '完全止盈': r['take_profit_count'],
                '完全止盈率%': f"{r['take_profit_rate']:.2f}",
                '部分止盈': r['partial_profit_count'],
                '止损': r['losses'],
                '盈亏比': f"{r['profit_factor']:.2f}",
                '总收益率%': f"{r['total_return_pct']:.2f}",
                '平均持仓K线数': f"{r['avg_holding_bars']:.1f}",
            })
    
    print(f"✓ 结果已保存到: {output_file}")
    print("="*80)


if __name__ == '__main__':
    main()
