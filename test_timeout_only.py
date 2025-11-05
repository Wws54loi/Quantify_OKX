"""
三K线策略 - 纯超时平仓测试 (不设止盈止损)
测试1-30根K线内强制平仓的效果对比
"""

import urllib.request
import json
import time
import os
from datetime import datetime
from typing import List, Dict


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


class ThreeKlineStrategyTimeoutOnly:
    """三K线策略 - 仅超时平仓版本"""
    
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
                    min_k1_range: float = 0.005,
                    max_holding_bars: int = 10) -> List[Dict]:
        """
        查找所有交易信号并在指定K线数后强制平仓
        不设止盈止损,仅按超时平仓
        """
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
            # 检查法则1
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
            
            # 持仓到指定K线数后强制平仓
            if signal and entry_index:
                entry_price = signal['entry_price']
                direction = signal['direction']
                
                # 找到第N根K线或最后一根K线
                exit_index = min(entry_index + max_holding_bars - 1, len(klines) - 1)
                
                if exit_index < len(klines):
                    exit_kline = klines[exit_index]
                    
                    # 使用收盘价平仓
                    if direction == 'long':
                        actual_return = (exit_kline.close - entry_price) / entry_price
                    else:  # short
                        actual_return = (entry_price - exit_kline.close) / entry_price
                    
                    signal['exit_type'] = 'timeout_close'
                    signal['exit_price'] = exit_kline.close
                    signal['exit_time'] = exit_kline.timestamp
                    signal['exit_index'] = exit_index
                    signal['holding_bars'] = exit_index - entry_index + 1
                    signal['return'] = actual_return
                    signals.append(signal)
                
                in_position = False
                    
            i += 1
        
        self.signals = signals
        return signals
    
    def calculate_stats(self, signals: List[Dict], leverage: int = 50, initial_capital: float = 1.0) -> Dict:
        """计算统计数据"""
        if not signals:
            return {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0.0,
                'avg_profit': 0.0,
                'avg_loss': 0.0,
                'total_pnl': 0.0,
                'profit_factor': 0.0,
                'avg_holding_bars': 0.0
            }
        
        wins = 0
        losses = 0
        profits = []
        losses_list = []
        total_pnl = 0.0
        holding_bars_list = []
        
        for signal in signals:
            return_pct = signal['return']
            holding_bars = signal['holding_bars']
            holding_bars_list.append(holding_bars)
            
            pnl = initial_capital * return_pct * leverage
            total_pnl += pnl
            
            if return_pct > 0:
                wins += 1
                profits.append(return_pct)
            else:
                losses += 1
                losses_list.append(return_pct)
        
        total_trades = wins + losses
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        avg_profit = sum(profits) / len(profits) if profits else 0
        avg_loss = sum(losses_list) / len(losses_list) if losses_list else 0
        avg_holding_bars = sum(holding_bars_list) / len(holding_bars_list) if holding_bars_list else 0
        
        profit_factor = abs(sum(profits) / sum(losses_list)) if losses_list and sum(losses_list) != 0 else float('inf')
        
        return {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'avg_profit': avg_profit * 100,
            'avg_loss': avg_loss * 100,
            'total_pnl': total_pnl,
            'total_return_pct': (total_pnl / (total_trades * initial_capital) * 100) if total_trades > 0 else 0,
            'profit_factor': profit_factor,
            'avg_holding_bars': avg_holding_bars
        }


def main():
    """主函数"""
    # 参数设置
    leverage = 50
    initial_capital = 1.0
    min_k1_range_percent = 0.21
    min_k1_range = min_k1_range_percent / 100
    
    print("="*80)
    print("三K线策略 - 纯超时平仓测试 (不设止盈止损)")
    print("="*80)
    print(f"交易对: BTCUSDT")
    print(f"K线周期: 15分钟")
    print(f"杠杆: {leverage}x")
    print(f"测试范围: 1-30根K线强制平仓")
    print(f"K1涨跌幅要求: {min_k1_range_percent}%")
    print("="*80)
    
    # 读取K线数据
    cache_file = "btcusdt_15m_klines.json"
    if not os.path.exists(cache_file):
        print("\n错误: 找不到缓存文件,请先运行 three_kline_strategy.py")
        return
    
    print(f"\n正在读取K线数据...")
    with open(cache_file, 'r', encoding='utf-8') as f:
        raw_klines = json.load(f)
    
    klines = [KLine(k) for k in raw_klines]
    print(f"✓ 成功读取 {len(klines)} 根K线数据")
    print(f"  时间范围: {datetime.fromtimestamp(klines[0].timestamp/1000).strftime('%Y-%m-%d %H:%M')} 至 {datetime.fromtimestamp(klines[-1].timestamp/1000).strftime('%Y-%m-%d %H:%M')}")
    
    # 创建策略实例
    strategy = ThreeKlineStrategyTimeoutOnly()
    
    # 存储所有测试结果
    all_results = []
    
    print("\n" + "="*80)
    print("开始测试不同K线数的强制平仓效果...")
    print("="*80)
    
    # 测试1-30根K线
    for max_holding_bars in range(1, 31):
        print(f"\r[{max_holding_bars}/30] 测试第 {max_holding_bars} 根K线平仓...", end='', flush=True)
        
        signals = strategy.find_signals(klines, 
                                        min_k1_range=min_k1_range,
                                        max_holding_bars=max_holding_bars)
        
        stats = strategy.calculate_stats(signals, leverage=leverage, initial_capital=initial_capital)
        
        result = {
            'kline_num': max_holding_bars,
            'total_trades': stats['total_trades'],
            'wins': stats['wins'],
            'losses': stats['losses'],
            'win_rate': stats['win_rate'],
            'avg_profit': stats['avg_profit'],
            'avg_loss': stats['avg_loss'],
            'profit_factor': stats['profit_factor'],
            'total_pnl': stats['total_pnl'],
            'total_return_pct': stats['total_return_pct'],
            'avg_holding_bars': stats['avg_holding_bars']
        }
        all_results.append(result)
    
    print("\n✓ 测试完成!")
    
    # 生成日志文件
    log_filename = f"timeout_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    print(f"\n正在生成日志文件: {log_filename}")
    
    with open(log_filename, 'w', encoding='utf-8') as f:
        f.write("="*100 + "\n")
        f.write("三K线策略 - 纯超时平仓测试报告 (不设止盈止损)\n")
        f.write("="*100 + "\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"交易对: BTCUSDT\n")
        f.write(f"K线周期: 15分钟\n")
        f.write(f"杠杆倍数: {leverage}x\n")
        f.write(f"每次投入: {initial_capital} USDT\n")
        f.write(f"K1涨跌幅要求: {min_k1_range_percent}%\n")
        f.write(f"测试范围: 1-30根K线强制平仓\n")
        f.write(f"数据量: {len(klines)} 根K线\n")
        f.write(f"数据时间: {datetime.fromtimestamp(klines[0].timestamp/1000).strftime('%Y-%m-%d %H:%M')} 至 {datetime.fromtimestamp(klines[-1].timestamp/1000).strftime('%Y-%m-%d %H:%M')}\n")
        f.write("="*100 + "\n\n")
        
        # 详细结果表格
        f.write("测试结果明细:\n")
        f.write("-"*100 + "\n")
        f.write(f"{'K线数':<8} {'交易数':<8} {'盈利':<8} {'亏损':<8} {'胜率%':<10} "
                f"{'平均盈利%':<12} {'平均亏损%':<12} {'盈亏比':<10} {'总收益%':<12}\n")
        f.write("-"*100 + "\n")
        
        for result in all_results:
            f.write(f"{result['kline_num']:<8} {result['total_trades']:<8} "
                   f"{result['wins']:<8} {result['losses']:<8} "
                   f"{result['win_rate']:<10.2f} "
                   f"{result['avg_profit']:<12.3f} {result['avg_loss']:<12.3f} "
                   f"{result['profit_factor']:<10.2f} "
                   f"{result['total_return_pct']:<12.2f}\n")
        
        f.write("-"*100 + "\n\n")
        
        # 最佳配置分析
        f.write("="*100 + "\n")
        f.write("最佳配置分析\n")
        f.write("="*100 + "\n\n")
        
        # 按胜率排序
        best_by_winrate = max(all_results, key=lambda x: x['win_rate'])
        f.write(f"【最高胜率】第 {best_by_winrate['kline_num']} 根K线平仓\n")
        f.write(f"  胜率: {best_by_winrate['win_rate']:.2f}%\n")
        f.write(f"  交易数: {best_by_winrate['total_trades']}\n")
        f.write(f"  盈亏比: {best_by_winrate['profit_factor']:.2f}\n")
        f.write(f"  总收益: {best_by_winrate['total_return_pct']:+.2f}%\n")
        f.write(f"  平均持仓: {best_by_winrate['avg_holding_bars']:.1f}根K线\n\n")
        
        # 按总收益排序
        best_by_return = max(all_results, key=lambda x: x['total_return_pct'])
        f.write(f"【最高收益】第 {best_by_return['kline_num']} 根K线平仓\n")
        f.write(f"  总收益: {best_by_return['total_return_pct']:+.2f}%\n")
        f.write(f"  胜率: {best_by_return['win_rate']:.2f}%\n")
        f.write(f"  交易数: {best_by_return['total_trades']}\n")
        f.write(f"  盈亏比: {best_by_return['profit_factor']:.2f}\n")
        f.write(f"  平均持仓: {best_by_return['avg_holding_bars']:.1f}根K线\n\n")
        
        # 按盈亏比排序
        best_by_pf = max(all_results, key=lambda x: x['profit_factor'] if x['profit_factor'] != float('inf') else 0)
        f.write(f"【最高盈亏比】第 {best_by_pf['kline_num']} 根K线平仓\n")
        f.write(f"  盈亏比: {best_by_pf['profit_factor']:.2f}\n")
        f.write(f"  胜率: {best_by_pf['win_rate']:.2f}%\n")
        f.write(f"  交易数: {best_by_pf['total_trades']}\n")
        f.write(f"  总收益: {best_by_pf['total_return_pct']:+.2f}%\n")
        f.write(f"  平均持仓: {best_by_pf['avg_holding_bars']:.1f}根K线\n\n")
        
        # 综合推荐
        valid_results = [r for r in all_results if r['win_rate'] >= 50 and r['total_trades'] >= 10]
        if valid_results:
            best_overall = max(valid_results, key=lambda x: x['total_return_pct'])
            f.write(f"【综合推荐】第 {best_overall['kline_num']} 根K线平仓 (胜率≥50%, 交易数≥10)\n")
            f.write(f"  胜率: {best_overall['win_rate']:.2f}%\n")
            f.write(f"  总收益: {best_overall['total_return_pct']:+.2f}%\n")
            f.write(f"  交易数: {best_overall['total_trades']}\n")
            f.write(f"  盈亏比: {best_overall['profit_factor']:.2f}\n")
            f.write(f"  平均持仓: {best_overall['avg_holding_bars']:.1f}根K线\n\n")
        else:
            f.write(f"【综合推荐】无符合条件的配置 (胜率≥50%, 交易数≥10)\n\n")
        
        # 数据趋势分析
        f.write("="*100 + "\n")
        f.write("数据趋势分析\n")
        f.write("="*100 + "\n\n")
        
        # 胜率趋势
        f.write("胜率趋势 (前15根K线):\n")
        for i in range(0, min(15, len(all_results))):
            result = all_results[i]
            bar_length = int(result['win_rate'] / 2)
            bar = "█" * bar_length
            f.write(f"  {result['kline_num']:2}根: {bar} {result['win_rate']:.2f}%\n")
        f.write("\n")
        
        # 收益趋势
        f.write("总收益趋势 (前15根K线):\n")
        max_abs_return = max(abs(r['total_return_pct']) for r in all_results[:15]) if all_results else 1
        for i in range(0, min(15, len(all_results))):
            result = all_results[i]
            bar_length = int(abs(result['total_return_pct']) / max_abs_return * 40)
            bar = "█" * bar_length
            sign = "+" if result['total_return_pct'] >= 0 else "-"
            f.write(f"  {result['kline_num']:2}根: {bar} {sign}{abs(result['total_return_pct']):.2f}%\n")
        f.write("\n")
        
        # 统计摘要
        f.write("="*100 + "\n")
        f.write("统计摘要\n")
        f.write("="*100 + "\n")
        f.write(f"平均胜率: {sum(r['win_rate'] for r in all_results) / len(all_results):.2f}%\n")
        f.write(f"平均收益: {sum(r['total_return_pct'] for r in all_results) / len(all_results):.2f}%\n")
        f.write(f"最高胜率: {max(r['win_rate'] for r in all_results):.2f}% (第{best_by_winrate['kline_num']}根)\n")
        f.write(f"最低胜率: {min(r['win_rate'] for r in all_results):.2f}%\n")
        f.write(f"最高收益: {max(r['total_return_pct'] for r in all_results):+.2f}% (第{best_by_return['kline_num']}根)\n")
        f.write(f"最低收益: {min(r['total_return_pct'] for r in all_results):+.2f}%\n")
        f.write("\n")
        
        f.write("="*100 + "\n")
        f.write("报告结束\n")
        f.write("="*100 + "\n")
    
    print(f"✓ 日志文件已保存: {log_filename}")
    
    # 打印控制台摘要
    print("\n" + "="*80)
    print("测试结果摘要")
    print("="*80)
    print(f"\n【最高胜率】第 {best_by_winrate['kline_num']} 根K线: {best_by_winrate['win_rate']:.2f}%, 收益 {best_by_winrate['total_return_pct']:+.2f}%")
    print(f"【最高收益】第 {best_by_return['kline_num']} 根K线: {best_by_return['total_return_pct']:+.2f}%, 胜率 {best_by_return['win_rate']:.2f}%")
    print(f"【最高盈亏比】第 {best_by_pf['kline_num']} 根K线: {best_by_pf['profit_factor']:.2f}, 胜率 {best_by_pf['win_rate']:.2f}%")
    
    if valid_results:
        print(f"【综合推荐】第 {best_overall['kline_num']} 根K线: 胜率 {best_overall['win_rate']:.2f}%, 收益 {best_overall['total_return_pct']:+.2f}%")
    
    print("\n详细报告已保存到:", log_filename)
    print("="*80)


if __name__ == '__main__':
    main()
