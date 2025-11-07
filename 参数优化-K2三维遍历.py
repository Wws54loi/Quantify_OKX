"""
K2参数三维遍历优化
遍历 min_k2_body_percent, max_k2_body_percent, min_k2_shadow_percent
"""

import json
import os
import csv
from datetime import datetime
from typing import List, Dict
import time

# 导入策略类
import sys
sys.path.append(os.path.dirname(__file__))

# 直接复制必要的类定义
class KLine:
    """K线数据类"""
    
    def __init__(self, kline_data: List):
        """
        初始化K线对象
        
        参数:
            kline_data: 币安K线数据 [时间, 开, 高, 低, 收, 成交量, ...]
        """
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
        return k2.high <= k1.high and k2.low >= k1.low
    
    def check_rule1(self, k1: KLine, k2: KLine, 
                   min_range_percent: float = 0.005, 
                   max_range_percent: float = 0.005,
                   min_k2_body_percent: float = 0.0,
                   max_k2_body_percent: float = 100.0,
                   min_k2_shadow_percent: float = 0.0) -> tuple:
        k1_range = abs(k1.close - k1.open) / k1.open
        if k1_range < min_range_percent or k1_range > max_range_percent:
            return (False, None)
        
        body_in_range = (k2.body_high <= k1.high and k2.body_low >= k1.low)
        if not body_in_range:
            return (False, None)
        
        k2_body_size = abs(k2.close - k2.open)
        k2_total_size = k2.high - k2.low
        
        if k2_total_size == 0:
            return (False, None)
        
        k2_body_ratio = (k2_body_size / k2_total_size) * 100
        
        if k2_body_ratio < min_k2_body_percent or k2_body_ratio > max_k2_body_percent:
            return (False, None)
        
        if k2.low < k1.low:
            lower_shadow = k2.body_low - k2.low
            shadow_ratio = (lower_shadow / k2_total_size) * 100
            
            if shadow_ratio < min_k2_shadow_percent:
                return (False, None)
            
            return (True, 'long')
        
        elif k2.high > k1.high:
            upper_shadow = k2.high - k2.body_high
            shadow_ratio = (upper_shadow / k2_total_size) * 100
            
            if shadow_ratio < min_k2_shadow_percent:
                return (False, None)
            
            return (True, 'short')
        
        return (False, None)
    
    def find_signals(self, klines: List[KLine], 
                    profit_target: float = 0.008, 
                    stop_loss: float = 1.0,
                    min_k1_range: float = 0.005,
                    max_k1_range: float = 0.005,
                    min_k2_body_percent: float = 0.0,
                    max_k2_body_percent: float = 100.0,
                    min_k2_shadow_percent: float = 0.0,
                    max_holding_bars_tp: int = None,
                    max_holding_bars_sl: int = None,
                    allow_stop_loss_retry: bool = True,
                    stop_loss_delay_bars: int = 10,
                    leverage: int = 50) -> List[Dict]:
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
                is_valid, direction = self.check_rule1(k1, k3, min_k1_range, max_k1_range, 
                                                       min_k2_body_percent, max_k2_body_percent, 
                                                       min_k2_shadow_percent)
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
                is_valid, direction = self.check_rule1(k1, k2, min_k1_range, max_k1_range,
                                                       min_k2_body_percent, max_k2_body_percent,
                                                       min_k2_shadow_percent)
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
        if not signals:
            return {
                'total_trades': 0,
                'wins': 0,
                'win_rate': 0.0,
                'take_profit_count': 0,
                'partial_profit_count': 0,
                'total_pnl': 0.0
            }
        
        wins = 0
        take_profit_count = 0
        partial_profit_count = 0
        total_pnl = 0.0
        
        for signal in signals:
            return_pct = signal['return']
            exit_type = signal['exit_type']
            
            pnl = initial_capital * return_pct * leverage
            total_pnl += pnl
            
            if exit_type == 'take_profit':
                wins += 1
                take_profit_count += 1
            elif exit_type == 'partial_profit':
                wins += 1
                partial_profit_count += 1
        
        total_trades = len(signals)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        return {
            'total_trades': total_trades,
            'wins': wins,
            'win_rate': win_rate,
            'take_profit_count': take_profit_count,
            'partial_profit_count': partial_profit_count,
            'total_pnl': total_pnl
        }


def main():
    """主函数"""
    print("="*80)
    print("K2参数三维遍历优化")
    print("="*80)
    
    # 固定参数
    leverage = 50
    profit_target_percent = 40
    stop_loss_percent = 100
    initial_capital = 1.0
    min_k1_range_percent = 0.2
    max_k1_range_percent = 0.51
    stop_loss_delay_bars = 5
    
    price_profit_target = profit_target_percent / leverage / 100
    price_stop_loss = stop_loss_percent / leverage / 100
    min_k1_range = min_k1_range_percent / 100
    max_k1_range = max_k1_range_percent / 100
    
    print(f"固定参数:")
    print(f"  杠杆倍数: {leverage}")
    print(f"  止盈: {profit_target_percent}% (每笔+0.4 USDT)")
    print(f"  止损: {stop_loss_percent}% (每笔-1.0 USDT)")
    print(f"  K1范围: {min_k1_range_percent}%-{max_k1_range_percent}%")
    print(f"  部分止盈延迟: {stop_loss_delay_bars}根K线")
    print(f"  最小交易量要求: 200次")
    print()
    print(f"评分标准 (优先减少止损):")
    print(f"  净收益 = 止盈次数×0.4 - 止损次数×1.0")
    print(f"  综合评分 = 净收益占比×60% + 胜率×25% + 完全止盈率×15%")
    print()
    
    # 遍历参数范围
    min_k2_body_list = [i * 0.01 for i in range(0, 101)]  # 0-1, 步进0.01
    max_k2_body_list = [i * 0.01 for i in range(30, 201)]  # 0.3-2, 步进0.01
    min_k2_shadow_list = [i * 0.01 for i in range(0, 101)]  # 0-1, 步进0.01
    
    total_combinations = len(min_k2_body_list) * len(max_k2_body_list) * len(min_k2_shadow_list)
    
    print(f"遍历参数:")
    print(f"  min_k2_body_percent: 0%-100% (步进1%, {len(min_k2_body_list)}个值)")
    print(f"  max_k2_body_percent: 30%-200% (步进1%, {len(max_k2_body_list)}个值)")
    print(f"  min_k2_shadow_percent: 0%-100% (步进1%, {len(min_k2_shadow_list)}个值)")
    print(f"  总组合数: {total_combinations:,}")
    print("="*80)
    
    # 读取K线数据
    cache_file = "btcusdt_15m_klines.json"
    if not os.path.exists(cache_file):
        print(f"错误: 找不到K线数据文件 {cache_file}")
        return
    
    print(f"正在加载K线数据...")
    with open(cache_file, 'r', encoding='utf-8') as f:
        raw_klines = json.load(f)
    klines = [KLine(k) for k in raw_klines]
    print(f"✓ 已加载 {len(klines)} 根K线数据")
    print()
    
    # 准备结果存储
    results = []
    best_result = None
    best_score = -999999
    
    # 开始遍历
    start_time = time.time()
    count = 0
    
    print("开始遍历测试...")
    print("-"*80)
    
    for min_k2_body in min_k2_body_list:
        for max_k2_body in max_k2_body_list:
            # 跳过不合理的组合（最小值大于最大值）
            if min_k2_body > max_k2_body:
                count += len(min_k2_shadow_list)
                continue
                
            for min_k2_shadow in min_k2_shadow_list:
                count += 1
                
                # 创建策略实例
                strategy = ThreeKlineStrategy()
                
                # 执行策略
                signals = strategy.find_signals(
                    klines,
                    profit_target=price_profit_target,
                    stop_loss=price_stop_loss,
                    min_k1_range=min_k1_range,
                    max_k1_range=max_k1_range,
                    min_k2_body_percent=min_k2_body,
                    max_k2_body_percent=max_k2_body,
                    min_k2_shadow_percent=min_k2_shadow,
                    stop_loss_delay_bars=stop_loss_delay_bars,
                    leverage=leverage
                )
                
                # 计算统计
                stats = strategy.calculate_win_rate(signals, leverage=leverage, initial_capital=initial_capital)
                
                # 计算关键指标
                total_trades = stats['total_trades']
                win_rate = stats['win_rate']
                loss_count = total_trades - stats['wins']
                loss_rate = (loss_count / total_trades * 100) if total_trades > 0 else 100
                take_profit_rate = (stats['take_profit_count'] / total_trades * 100) if total_trades > 0 else 0
                
                # 计算净收益评分 (因为止损-100%，止盈+40%)
                # 净收益 = 止盈次数×0.4 - 止损次数×1.0
                net_profit = stats['wins'] * 0.4 - loss_count * 1.0
                net_profit_per_trade = net_profit / total_trades if total_trades > 0 else -999
                
                # 综合评分：优先考虑减少止损
                # 评分 = 净收益占比×60% + 胜率×25% + 完全止盈率×15%
                score = net_profit_per_trade * 60 + win_rate * 0.25 + take_profit_rate * 0.15
                
                # 保存结果
                result = {
                    'min_k2_body_percent': min_k2_body,
                    'max_k2_body_percent': max_k2_body,
                    'min_k2_shadow_percent': min_k2_shadow,
                    'total_trades': total_trades,
                    'win_rate': win_rate,
                    'loss_count': loss_count,
                    'loss_rate': loss_rate,
                    'take_profit_count': stats['take_profit_count'],
                    'partial_profit_count': stats['partial_profit_count'],
                    'take_profit_rate': take_profit_rate,
                    'total_pnl': stats['total_pnl'],
                    'net_profit': net_profit,
                    'net_profit_per_trade': net_profit_per_trade,
                    'score': score
                }
                results.append(result)
                
                # 更新最佳结果 (要求交易量>=200)
                if score > best_score and stats['total_trades'] >= 200:
                    best_score = score
                    best_result = result
                
                # 进度显示
                if count % 1000 == 0:
                    elapsed = time.time() - start_time
                    speed = count / elapsed
                    remaining = (total_combinations - count) / speed if speed > 0 else 0
                    progress = count / total_combinations * 100
                    print(f"进度: {count}/{total_combinations} ({progress:.1f}%) - "
                          f"速度: {speed:.1f}组/秒 - "
                          f"剩余: {remaining/60:.1f}分钟")
    
    elapsed = time.time() - start_time
    print("-"*80)
    print(f"✓ 遍历完成! 总耗时: {elapsed/60:.1f}分钟")
    print()
    
    # 显示最佳结果
    if best_result:
        print("="*80)
        print("最佳参数组合 (优先减少止损):")
        print("="*80)
        print(f"min_k2_body_percent: {best_result['min_k2_body_percent']:.2f}%")
        print(f"max_k2_body_percent: {best_result['max_k2_body_percent']:.2f}%")
        print(f"min_k2_shadow_percent: {best_result['min_k2_shadow_percent']:.2f}%")
        print(f"-"*80)
        print(f"总交易数: {best_result['total_trades']}")
        print(f"胜率: {best_result['win_rate']:.2f}%")
        print(f"止损次数: {best_result['loss_count']} (止损率: {best_result['loss_rate']:.2f}%)")
        print(f"完全止盈: {best_result['take_profit_count']} ({best_result['take_profit_rate']:.2f}%)")
        print(f"部分止盈: {best_result['partial_profit_count']}")
        print(f"净收益: {best_result['net_profit']:+.4f} USDT (每笔: {best_result['net_profit_per_trade']:+.4f})")
        print(f"综合评分: {best_result['score']:.2f}")
        print("="*80)
    else:
        print("未找到满足条件的最佳参数组合（至少需要200笔交易）")
    
    # 导出结果
    output_dir = "策略分析"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    output_file = os.path.join(output_dir, "K2三维参数优化结果.csv")
    
    print(f"\n正在导出结果到: {output_file}")
    
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        fieldnames = [
            'min_k2_body_percent', 'max_k2_body_percent', 'min_k2_shadow_percent',
            'total_trades', 'win_rate', 'loss_count', 'loss_rate',
            'take_profit_count', 'partial_profit_count', 'take_profit_rate', 
            'total_pnl', 'net_profit', 'net_profit_per_trade', 'score'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        # 按综合评分排序
        results.sort(key=lambda x: x['score'], reverse=True)
        
        for result in results:
            writer.writerow(result)
    
    print(f"✓ 结果已导出")
    print(f"\n前10名结果 (按净收益优先排序):")
    print("-"*100)
    print(f"{'排名':<4} {'min_body%':<10} {'max_body%':<10} {'min_shadow%':<12} "
          f"{'交易数':<8} {'胜率%':<8} {'止损率%':<10} {'净收益':<12} {'评分':<8}")
    print("-"*100)
    
    for i, result in enumerate(results[:10], 1):
        print(f"{i:<4} {result['min_k2_body_percent']:<10.2f} "
              f"{result['max_k2_body_percent']:<10.2f} "
              f"{result['min_k2_shadow_percent']:<12.2f} "
              f"{result['total_trades']:<8} "
              f"{result['win_rate']:<8.2f} "
              f"{result['loss_rate']:<10.2f} "
              f"{result['net_profit']:<12.2f} "
              f"{result['score']:<8.2f}")
    
    print("="*80)
    print("完成！")


if __name__ == '__main__':
    main()
