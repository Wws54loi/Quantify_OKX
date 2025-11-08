"""
参数优化脚本 - 全面遍历
自动遍历所有参数组合，找出最优策略配置

参数范围：
- 杠杆倍数: 20-90倍，步进5
- 止盈百分比: 30-70%，步进5
- 止损百分比: 20-50%，步进5
- K1涨跌幅要求: 0.21-0.6%，步进0.01
- 约束条件: 盈利必须是亏损的1.5倍以上
"""

import urllib.request
import json
import time
import csv
import os
from datetime import datetime
from typing import List, Dict, Optional
import itertools


class KLine:
    """K线数据类"""
    
    def __init__(self, kline_data: List):
        self.timestamp = int(kline_data[0])
        self.open = float(kline_data[1])
        self.high = float(kline_data[2])
        self.low = float(kline_data[3])
        self.close = float(kline_data[4])
        self.volume = float(kline_data[5])
        
        # 计算实体部分
        self.body_high = max(self.open, self.close)
        self.body_low = min(self.open, self.close)
        
    def __repr__(self):
        dt = datetime.fromtimestamp(self.timestamp / 1000)
        return f"KLine({dt.strftime('%Y-%m-%d %H:%M')}, O:{self.open:.2f}, H:{self.high:.2f}, L:{self.low:.2f}, C:{self.close:.2f})"


class ThreeKlineStrategy:
    """三K线策略"""
    
    def __init__(self):
        self.signals = []
        
    def is_contained(self, k1: KLine, k2: KLine) -> bool:
        """判断k2是否被k1完全包含"""
        return k2.high <= k1.high and k2.low >= k1.low
    
    def check_rule1(self, k1: KLine, k2: KLine, min_range_percent: float = 0.005,
                    filter_body_ratio: bool = True) -> tuple:
        """
        检查法则1
        过滤K2实体与K1实体比值在1.6-1.7或0.9-1.10范围内的情况
        """
        k1_range = abs(k1.close - k1.open) / k1.open
        if k1_range < min_range_percent:
            return (False, None)
        
        body_in_range = (k2.body_high <= k1.high and k2.body_low >= k1.low)
        if not body_in_range:
            return (False, None)
        
        # 过滤K2实体与K1实体的比值
        if filter_body_ratio:
            k1_body_size = abs(k1.close - k1.open)
            k2_body_size = abs(k2.close - k2.open)
            
            if k1_body_size > 0:
                body_ratio = k2_body_size / k1_body_size
                # 过滤比值在1.6-1.7或0.9-1.10范围内的情况
                if (1.6 <= body_ratio <= 1.7) or (0.9 <= body_ratio <= 1.10):
                    return (False, None)
        
        if k2.low < k1.low:
            return (True, 'long')
        elif k2.high > k1.high:
            return (True, 'short')
        
        return (False, None)
    
    def find_signals(self, klines: List[KLine], 
                    profit_target: float = 0.008, 
                    stop_loss: float = 0.004,
                    min_k1_range: float = 0.005) -> List[Dict]:
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
            
            # 检查法则2: k2被k1包含
            if i < len(klines) - 2 and self.is_contained(k1, k2):
                k3 = klines[i + 2]
                is_valid, direction = self.check_rule1(k1, k3, min_k1_range)
                if is_valid:
                    signal = {
                        'type': 'rule2',
                        'direction': direction,
                        'entry_price': k3.close,
                        'entry_time': k3.timestamp,
                        'entry_index': i + 2
                    }
                    entry_index = i + 3
                    in_position = True
                    i += 2
            # 检查法则1: k2相对于k1
            else:
                is_valid, direction = self.check_rule1(k1, k2, min_k1_range)
                if is_valid:
                    signal = {
                        'type': 'rule1',
                        'direction': direction,
                        'entry_price': k2.close,
                        'entry_time': k2.timestamp,
                        'entry_index': i + 1
                    }
                    entry_index = i + 2
                    in_position = True
                    i += 1
            
            # 如果有信号,持续监测直到触发止盈/止损
            if signal and entry_index:
                entry_price = signal['entry_price']
                direction = signal['direction']
                
                for j in range(entry_index, len(klines)):
                    current_kline = klines[j]
                    holding_bars = j - entry_index + 1
                    
                    if direction == 'long':
                        high_return = (current_kline.high - entry_price) / entry_price
                        low_return = (current_kline.low - entry_price) / entry_price
                    else:
                        high_return = (entry_price - current_kline.low) / entry_price
                        low_return = (entry_price - current_kline.high) / entry_price
                    
                    if high_return >= profit_target:
                        signal['exit_type'] = 'take_profit'
                        signal['return'] = profit_target
                        signals.append(signal)
                        in_position = False
                        break
                    elif low_return <= -stop_loss:
                        signal['exit_type'] = 'stop_loss'
                        signal['return'] = -stop_loss
                        signals.append(signal)
                        in_position = False
                        break
                
                if in_position:
                    in_position = False
                    
            i += 1
        
        return signals
    
    def calculate_win_rate(self, signals: List[Dict], leverage: int = 50) -> Dict:
        """计算胜率"""
        if not signals:
            return {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_profit': 0.0,
                'avg_loss': 0.0,
            }
        
        wins = 0
        losses = 0
        profits = []
        losses_list = []
        
        for signal in signals:
            return_pct = signal['return']
            
            if signal['exit_type'] == 'take_profit':
                wins += 1
                profits.append(return_pct)
            else:
                losses += 1
                losses_list.append(return_pct)
        
        total_trades = wins + losses
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        avg_profit = sum(profits) / len(profits) if profits else 0
        avg_loss = sum(losses_list) / len(losses_list) if losses_list else 0
        total_pnl = sum(profits) + sum(losses_list)
        
        return {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'total_pnl': total_pnl * leverage,
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
        }


def optimize_parameters(klines: List[KLine]):
    """参数优化主函数"""
    
    print("="*80)
    print("参数优化 - 全面遍历")
    print("="*80)
    
    # 定义参数范围
    leverage_range = range(20, 91, 5)  # 20-90，步进5
    profit_target_range = range(30, 71, 5)  # 30-70，步进5
    stop_loss_range = range(20, 51, 5)  # 20-50，步进5
    min_k1_range_values = [round(x * 0.01, 2) for x in range(21, 61)]  # 0.21-0.60，步进0.01
    
    total_combinations = (len(list(leverage_range)) * 
                         len(list(profit_target_range)) * 
                         len(list(stop_loss_range)) * 
                         len(min_k1_range_values))
    
    print(f"参数组合总数: {total_combinations}")
    print(f"杠杆范围: {min(leverage_range)}-{max(leverage_range)}倍，步进5")
    print(f"止盈范围: {min(profit_target_range)}-{max(profit_target_range)}%，步进5")
    print(f"止损范围: {min(stop_loss_range)}-{max(stop_loss_range)}%，步进5")
    print(f"K1涨跌幅范围: {min(min_k1_range_values):.2f}-{max(min_k1_range_values):.2f}%，步进0.01")
    print(f"约束条件: 止盈 >= 止损 * 1.5")
    print("="*80)
    
    results = []
    tested_count = 0
    valid_count = 0
    start_time = time.time()
    
    strategy = ThreeKlineStrategy()
    
    # 遍历所有参数组合
    for leverage in leverage_range:
        for profit_target_percent in profit_target_range:
            for stop_loss_percent in stop_loss_range:
                # 检查盈亏比约束
                if profit_target_percent < stop_loss_percent * 1.5:
                    continue
                
                for min_k1_range_percent in min_k1_range_values:
                    tested_count += 1
                    
                    # 计算现货价格需要变动的百分比
                    price_profit_target = profit_target_percent / leverage / 100
                    price_stop_loss = stop_loss_percent / leverage / 100
                    min_k1_range = min_k1_range_percent / 100
                    
                    # 查找信号
                    signals = strategy.find_signals(
                        klines,
                        profit_target=price_profit_target,
                        stop_loss=price_stop_loss,
                        min_k1_range=min_k1_range
                    )
                    
                    # 计算统计数据
                    stats = strategy.calculate_win_rate(signals, leverage=leverage)
                    
                    # 只保留有足够样本的结果
                    if stats['total_trades'] >= 30:
                        valid_count += 1
                        # 计算总收益率
                        total_return_percent = (stats['total_pnl'] / stats['total_trades']) * 100
                        
                        results.append({
                            'leverage': leverage,
                            'profit_target_percent': profit_target_percent,
                            'stop_loss_percent': stop_loss_percent,
                            'min_k1_range_percent': min_k1_range_percent,
                            'total_trades': stats['total_trades'],
                            'wins': stats['wins'],
                            'losses': stats['losses'],
                            'win_rate': stats['win_rate'],
                            'total_pnl': stats['total_pnl'],
                            'total_return_percent': total_return_percent,
                            'avg_profit': stats['avg_profit'] * 100,
                            'avg_loss': stats['avg_loss'] * 100,
                            'profit_factor': abs(stats['avg_profit'] / stats['avg_loss']) if stats['avg_loss'] != 0 else 0,
                        })
                    
                    # 每100次显示进度
                    if tested_count % 100 == 0:
                        elapsed = time.time() - start_time
                        rate = tested_count / elapsed if elapsed > 0 else 0
                        remaining = (total_combinations - tested_count) / rate if rate > 0 else 0
                        print(f"进度: {tested_count}/{total_combinations} ({tested_count/total_combinations*100:.1f}%) | "
                              f"有效: {valid_count} | "
                              f"速度: {rate:.1f}次/秒 | "
                              f"剩余: {remaining/60:.1f}分钟", end='\r')
    
    elapsed = time.time() - start_time
    print(f"\n完成! 总耗时: {elapsed/60:.1f}分钟 | 测试: {tested_count} | 有效结果: {valid_count}")
    
    return results


def save_results(results: List[Dict], filename: str = "参数优化结果-全面遍历.csv"):
    """保存优化结果"""
    if not results:
        print("没有结果可保存")
        return
    
    # 按总收益率排序
    results_sorted = sorted(results, key=lambda x: x['total_return_percent'], reverse=True)
    
    fieldnames = [
        '排名', '杠杆倍数', '止盈%', '止损%', 'K1涨跌幅%', 
        '总交易数', '盈利次数', '亏损次数', '胜率%', 
        '总盈亏', '总收益率%', '平均盈利%', '平均亏损%', '盈亏比'
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for rank, result in enumerate(results_sorted, 1):
            writer.writerow({
                '排名': rank,
                '杠杆倍数': result['leverage'],
                '止盈%': result['profit_target_percent'],
                '止损%': result['stop_loss_percent'],
                'K1涨跌幅%': result['min_k1_range_percent'],
                '总交易数': result['total_trades'],
                '盈利次数': result['wins'],
                '亏损次数': result['losses'],
                '胜率%': f"{result['win_rate']:.2f}",
                '总盈亏': f"{result['total_pnl']:.4f}",
                '总收益率%': f"{result['total_return_percent']:.2f}",
                '平均盈利%': f"{result['avg_profit']:.3f}",
                '平均亏损%': f"{result['avg_loss']:.3f}",
                '盈亏比': f"{result['profit_factor']:.2f}",
            })
    
    print(f"\n✓ 结果已保存到: {filename}")


def print_top_results(results: List[Dict], top_n: int = 20):
    """打印最优结果"""
    if not results:
        print("没有结果可显示")
        return
    
    # 按总收益率排序
    results_sorted = sorted(results, key=lambda x: x['total_return_percent'], reverse=True)
    
    print("\n" + "="*130)
    print(f"Top {top_n} 最优参数组合（按总收益率排序）")
    print("="*130)
    print(f"{'排名':<5} {'杠杆':<6} {'止盈%':<7} {'止损%':<7} {'K1涨跌%':<9} "
          f"{'交易数':<8} {'胜率%':<8} {'总收益率%':<12} {'总盈亏':<12} {'盈亏比':<8}")
    print("-"*130)
    
    for rank, result in enumerate(results_sorted[:top_n], 1):
        print(f"{rank:<5} {result['leverage']:<6} {result['profit_target_percent']:<7} "
              f"{result['stop_loss_percent']:<7} {result['min_k1_range_percent']:<9.2f} "
              f"{result['total_trades']:<8} {result['win_rate']:<8.2f} "
              f"{result['total_return_percent']:<12.2f} {result['total_pnl']:<12.4f} {result['profit_factor']:<8.2f}")
    
    # 显示最优配置详情
    print("\n" + "="*130)
    print("最优配置详情（收益率最高）")
    print("="*130)
    best = results_sorted[0]
    print(f"杠杆倍数: {best['leverage']}倍")
    print(f"止盈设置: {best['profit_target_percent']}% (价格变动 {best['profit_target_percent']/best['leverage']:.2f}%)")
    print(f"止损设置: {best['stop_loss_percent']}% (价格变动 {best['stop_loss_percent']/best['leverage']:.2f}%)")
    print(f"K1涨跌幅要求: {best['min_k1_range_percent']}%")
    print(f"-"*130)
    print(f"总交易数: {best['total_trades']}")
    print(f"盈利次数: {best['wins']}")
    print(f"亏损次数: {best['losses']}")
    print(f"胜率: {best['win_rate']:.2f}%")
    print(f"总收益率: {best['total_return_percent']:.2f}% (每次投入1 USDT)")
    print(f"总盈亏: {best['total_pnl']:.4f} USDT")
    print(f"平均盈利: {best['avg_profit']:.3f}% (现货价格变动)")
    print(f"平均亏损: {best['avg_loss']:.3f}% (现货价格变动)")
    print(f"盈亏比: {best['profit_factor']:.2f}")
    print("="*130)
    
    # 按胜率排序的Top 10
    print("\n" + "="*130)
    print("Top 10 最高胜率参数组合")
    print("="*130)
    results_by_winrate = sorted(results, key=lambda x: x['win_rate'], reverse=True)
    print(f"{'排名':<5} {'杠杆':<6} {'止盈%':<7} {'止损%':<7} {'K1涨跌%':<9} "
          f"{'交易数':<8} {'胜率%':<8} {'总收益率%':<12} {'总盈亏':<12} {'盈亏比':<8}")
    print("-"*130)
    
    for rank, result in enumerate(results_by_winrate[:10], 1):
        print(f"{rank:<5} {result['leverage']:<6} {result['profit_target_percent']:<7} "
              f"{result['stop_loss_percent']:<7} {result['min_k1_range_percent']:<9.2f} "
              f"{result['total_trades']:<8} {result['win_rate']:<8.2f} "
              f"{result['total_return_percent']:<12.2f} {result['total_pnl']:<12.4f} {result['profit_factor']:<8.2f}")
    
    # 按盈亏比排序的Top 10
    print("\n" + "="*130)
    print("Top 10 最高盈亏比参数组合")
    print("="*130)
    results_by_pf = sorted(results, key=lambda x: x['profit_factor'], reverse=True)
    print(f"{'排名':<5} {'杠杆':<6} {'止盈%':<7} {'止损%':<7} {'K1涨跌%':<9} "
          f"{'交易数':<8} {'胜率%':<8} {'总收益率%':<12} {'总盈亏':<12} {'盈亏比':<8}")
    print("-"*130)
    
    for rank, result in enumerate(results_by_pf[:10], 1):
        print(f"{rank:<5} {result['leverage']:<6} {result['profit_target_percent']:<7} "
              f"{result['stop_loss_percent']:<7} {result['min_k1_range_percent']:<9.2f} "
              f"{result['total_trades']:<8} {result['win_rate']:<8.2f} "
              f"{result['total_return_percent']:<12.2f} {result['total_pnl']:<12.4f} {result['profit_factor']:<8.2f}")
    
    print("="*130)


def main():
    """主函数"""
    print("="*80)
    print("参数优化脚本 - 全面遍历")
    print("="*80)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 读取K线数据
    cache_file = "ethusdt_15m_klines.json"
    
    if not os.path.exists(cache_file):
        print(f"错误: 未找到K线数据文件 {cache_file}")
        return
    
    print("正在读取K线数据...")
    with open(cache_file, 'r', encoding='utf-8') as f:
        raw_klines = json.load(f)
    
    klines = [KLine(k) for k in raw_klines]
    print(f"✓ 成功读取 {len(klines)} 根K线数据")
    print(f"时间范围: {datetime.fromtimestamp(klines[0].timestamp/1000).strftime('%Y-%m-%d')} 至 "
          f"{datetime.fromtimestamp(klines[-1].timestamp/1000).strftime('%Y-%m-%d')}\n")
    
    # 执行参数优化
    results = optimize_parameters(klines)
    
    # 保存结果
    save_results(results)
    
    # 打印最优结果
    print_top_results(results, top_n=20)
    
    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)


if __name__ == '__main__':
    main()
