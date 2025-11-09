"""
三K线策略参数优化 - 遍历多维参数
遍历参数:
- leverage: 40-100
- profit_target_percent: 40-100
- min_k1_range_percent: 0.21-0.5
- stop_loss_percent: 固定100%

仅统计前10根K线内触发止盈/止损的交易
过滤包含关系的数据
"""

import urllib.request
import json
import time
import csv
import os
from datetime import datetime
from typing import List, Dict, Optional
import itertools


class BinanceAPI:
    """币安API接口封装"""
    BASE_URL = "https://api.binance.com"
    
    @staticmethod
    def get_klines(symbol: str = "BTCUSDT", interval: str = "15m", limit: int = 1000) -> List[List]:
        """获取K线数据（支持获取超过1000根）"""
        all_klines = []
        remaining = limit
        end_time = None
        
        while remaining > 0:
            batch_limit = min(remaining, 1000)
            url = f"{BinanceAPI.BASE_URL}/api/v3/klines?symbol={symbol}&interval={interval}&limit={batch_limit}"
            if end_time:
                url += f"&endTime={end_time}"
            
            try:
                with urllib.request.urlopen(url, timeout=10) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    if not data:
                        break
                    all_klines = data + all_klines
                    end_time = data[0][0] - 1
                    remaining -= len(data)
                    if len(data) < batch_limit:
                        break
                    time.sleep(0.2)
            except Exception as e:
                print(f"\n获取K线数据失败: {e}")
                break
        
        return all_klines


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
                    stop_loss: float = 0.004,
                    min_k1_range: float = 0.005,
                    allow_stop_loss_retry: bool = True) -> List[Dict]:
        """查找所有交易信号（仅前10根K线）"""
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
            
            # 跳过包含关系
            if i < len(klines) - 2 and self.is_contained(k1, k2):
                i += 1
                continue
            
            # 检查法则1
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
            
            # 监测止盈止损（仅前10根K线）
            if signal and entry_index:
                entry_price = signal['entry_price']
                direction = signal['direction']
                stop_loss_hit_count = 0
                
                max_check_bars = min(entry_index + 10, len(klines))
                for j in range(entry_index, max_check_bars):
                    current_kline = klines[j]
                    holding_bars = j - entry_index + 1
                    
                    if direction == 'long':
                        high_return = (current_kline.high - entry_price) / entry_price
                        low_return = (current_kline.low - entry_price) / entry_price
                    else:
                        high_return = (entry_price - current_kline.low) / entry_price
                        low_return = (entry_price - current_kline.high) / entry_price
                    
                    # 检查止盈
                    if high_return >= profit_target:
                        signal['exit_type'] = 'take_profit'
                        signal['exit_price'] = entry_price * (1 + profit_target) if direction == 'long' else entry_price * (1 - profit_target)
                        signal['exit_time'] = current_kline.timestamp
                        signal['exit_index'] = j
                        signal['holding_bars'] = holding_bars
                        signal['return'] = profit_target
                        signal['stop_loss_hit_count'] = stop_loss_hit_count
                        signals.append(signal)
                        in_position = False
                        break
                    # 检查止损
                    elif low_return <= -stop_loss:
                        stop_loss_hit_count += 1
                        if allow_stop_loss_retry and stop_loss_hit_count == 1:
                            continue
                        signal['exit_type'] = 'stop_loss'
                        signal['exit_price'] = entry_price * (1 - stop_loss) if direction == 'long' else entry_price * (1 + stop_loss)
                        signal['exit_time'] = current_kline.timestamp
                        signal['exit_index'] = j
                        signal['holding_bars'] = holding_bars
                        signal['return'] = -stop_loss
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
                'win_rate': 0.0,
                'avg_profit': 0.0,
                'avg_loss': 0.0,
                'avg_holding_bars': 0.0,
                'total_pnl': 0.0,
                'profit_factor': 0.0
            }
        
        wins = 0
        losses = 0
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
            'total_signals': len(signals),
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'avg_profit': avg_profit * 100,
            'avg_loss': avg_loss * 100,
            'avg_holding_bars': avg_holding_bars,
            'total_pnl': total_capital,
            'profit_factor': profit_factor
        }


def traverse_parameters(klines: List[KLine]):
    """遍历参数组合"""
    
    # 参数范围
    leverage_range = range(40, 101, 5)  # 40, 45, 50, ..., 100
    profit_target_range = range(40, 101, 5)  # 40, 45, 50, ..., 100
    min_k1_range_range = [round(x * 0.01, 3) for x in range(21, 51, 2)]  # 0.21, 0.23, ..., 0.49
    stop_loss_percent = 100  # 固定值
    initial_capital = 1.0  # 固定值
    
    results = []
    total_combinations = len(list(leverage_range)) * len(list(profit_target_range)) * len(min_k1_range_range)
    current = 0
    
    print(f"开始遍历参数...")
    print(f"总共需要测试 {total_combinations} 种参数组合")
    print(f"参数范围:")
    print(f"  - leverage: {min(leverage_range)} - {max(leverage_range)} (步长5)")
    print(f"  - profit_target_percent: {min(profit_target_range)} - {max(profit_target_range)} (步长5)")
    print(f"  - min_k1_range_percent: {min(min_k1_range_range)} - {max(min_k1_range_range)} (步长0.02)")
    print(f"  - stop_loss_percent: {stop_loss_percent} (固定)")
    print("="*80)
    
    start_time = time.time()
    
    for leverage in leverage_range:
        for profit_target_percent in profit_target_range:
            for min_k1_range_percent in min_k1_range_range:
                current += 1
                
                # 计算价格变动百分比
                price_profit_target = profit_target_percent / leverage / 100
                price_stop_loss = stop_loss_percent / leverage / 100
                min_k1_range = min_k1_range_percent / 100
                
                # 创建策略并运行
                strategy = ThreeKlineStrategy()
                signals = strategy.find_signals(
                    klines,
                    profit_target=price_profit_target,
                    stop_loss=price_stop_loss,
                    min_k1_range=min_k1_range
                )
                
                # 计算统计
                stats = strategy.calculate_win_rate(signals, leverage=leverage, initial_capital=initial_capital)
                
                # 保存结果
                result = {
                    'leverage': leverage,
                    'profit_target_percent': profit_target_percent,
                    'stop_loss_percent': stop_loss_percent,
                    'min_k1_range_percent': min_k1_range_percent,
                    'total_trades': stats['total_trades'],
                    'wins': stats['wins'],
                    'losses': stats['losses'],
                    'win_rate': stats['win_rate'],
                    'avg_profit_percent': stats['avg_profit'] * leverage,
                    'avg_loss_percent': stats['avg_loss'] * leverage,
                    'avg_holding_bars': stats['avg_holding_bars'],
                    'total_pnl': stats['total_pnl'],
                    'profit_factor': stats['profit_factor'],
                    'price_profit_target': price_profit_target * 100,
                    'price_stop_loss': price_stop_loss * 100
                }
                results.append(result)
                
                # 显示进度
                if current % 100 == 0 or current == total_combinations:
                    elapsed = time.time() - start_time
                    progress = current / total_combinations * 100
                    eta = (elapsed / current) * (total_combinations - current) if current > 0 else 0
                    print(f"进度: {current}/{total_combinations} ({progress:.1f}%) | "
                          f"已用时: {elapsed:.0f}秒 | 预计剩余: {eta:.0f}秒")
    
    print(f"\n遍历完成! 总耗时: {time.time() - start_time:.1f}秒")
    return results


def export_results(results: List[Dict], filename: str = "参数优化结果-前10根k线.csv"):
    """导出结果到CSV"""
    if not results:
        print("没有结果可导出")
        return
    
    fieldnames = [
        '杠杆', '止盈%', '止损%', 'K1涨跌幅%', 
        '总交易数', '盈利次数', '亏损次数', '胜率%',
        '平均盈利%', '平均亏损%', '平均持仓K线数',
        '总盈亏USDT', '盈亏比',
        '价格止盈%', '价格止损%'
    ]
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for r in results:
                writer.writerow({
                    '杠杆': r['leverage'],
                    '止盈%': r['profit_target_percent'],
                    '止损%': r['stop_loss_percent'],
                    'K1涨跌幅%': f"{r['min_k1_range_percent']:.2f}",
                    '总交易数': r['total_trades'],
                    '盈利次数': r['wins'],
                    '亏损次数': r['losses'],
                    '胜率%': f"{r['win_rate']:.2f}",
                    '平均盈利%': f"{r['avg_profit_percent']:.2f}",
                    '平均亏损%': f"{r['avg_loss_percent']:.2f}",
                    '平均持仓K线数': f"{r['avg_holding_bars']:.2f}",
                    '总盈亏USDT': f"{r['total_pnl']:.4f}",
                    '盈亏比': f"{r['profit_factor']:.2f}",
                    '价格止盈%': f"{r['price_profit_target']:.4f}",
                    '价格止损%': f"{r['price_stop_loss']:.4f}"
                })
        
        print(f"\n✓ 结果已导出到: {filename}")
        return filename
    except Exception as e:
        print(f"\n✗ 导出失败: {e}")
        return None


def analyze_best_results(results: List[Dict], top_n: int = 10):
    """分析最佳结果"""
    # 过滤掉交易数太少的结果（至少50笔交易）
    valid_results = [r for r in results if r['total_trades'] >= 50]
    
    if not valid_results:
        print("\n没有足够的有效结果（需要至少50笔交易）")
        return
    
    print(f"\n{'='*80}")
    print(f"最佳参数分析 (过滤条件: 交易数 >= 50)")
    print(f"{'='*80}")
    
    # 按总盈亏排序
    by_pnl = sorted(valid_results, key=lambda x: x['total_pnl'], reverse=True)[:top_n]
    print(f"\n【按总盈亏排名 Top {top_n}】")
    print(f"{'排名':<4} {'杠杆':<6} {'止盈%':<7} {'K1%':<7} {'交易数':<8} {'胜率%':<8} {'总盈亏':<12} {'盈亏比':<8}")
    print("-"*80)
    for i, r in enumerate(by_pnl, 1):
        print(f"{i:<4} {r['leverage']:<6} {r['profit_target_percent']:<7} "
              f"{r['min_k1_range_percent']:<7.2f} {r['total_trades']:<8} "
              f"{r['win_rate']:<8.2f} {r['total_pnl']:<12.4f} {r['profit_factor']:<8.2f}")
    
    # 按胜率排序
    by_winrate = sorted(valid_results, key=lambda x: x['win_rate'], reverse=True)[:top_n]
    print(f"\n【按胜率排名 Top {top_n}】")
    print(f"{'排名':<4} {'杠杆':<6} {'止盈%':<7} {'K1%':<7} {'交易数':<8} {'胜率%':<8} {'总盈亏':<12} {'盈亏比':<8}")
    print("-"*80)
    for i, r in enumerate(by_winrate, 1):
        print(f"{i:<4} {r['leverage']:<6} {r['profit_target_percent']:<7} "
              f"{r['min_k1_range_percent']:<7.2f} {r['total_trades']:<8} "
              f"{r['win_rate']:<8.2f} {r['total_pnl']:<12.4f} {r['profit_factor']:<8.2f}")
    
    # 按盈亏比排序
    by_pf = sorted(valid_results, key=lambda x: x['profit_factor'], reverse=True)[:top_n]
    print(f"\n【按盈亏比排名 Top {top_n}】")
    print(f"{'排名':<4} {'杠杆':<6} {'止盈%':<7} {'K1%':<7} {'交易数':<8} {'胜率%':<8} {'总盈亏':<12} {'盈亏比':<8}")
    print("-"*80)
    for i, r in enumerate(by_pf, 1):
        print(f"{i:<4} {r['leverage']:<6} {r['profit_target_percent']:<7} "
              f"{r['min_k1_range_percent']:<7.2f} {r['total_trades']:<8} "
              f"{r['win_rate']:<8.2f} {r['total_pnl']:<12.4f} {r['profit_factor']:<8.2f}")
    
    # 综合评分（胜率 * 盈亏比 * 总盈亏的归一化）
    max_pnl = max([r['total_pnl'] for r in valid_results]) if valid_results else 1
    for r in valid_results:
        r['score'] = (r['win_rate'] / 100) * r['profit_factor'] * (r['total_pnl'] / max_pnl if max_pnl > 0 else 0)
    
    by_score = sorted(valid_results, key=lambda x: x['score'], reverse=True)[:top_n]
    print(f"\n【按综合评分排名 Top {top_n}】")
    print(f"{'排名':<4} {'杠杆':<6} {'止盈%':<7} {'K1%':<7} {'交易数':<8} {'胜率%':<8} {'总盈亏':<12} {'盈亏比':<8} {'评分':<8}")
    print("-"*80)
    for i, r in enumerate(by_score, 1):
        print(f"{i:<4} {r['leverage']:<6} {r['profit_target_percent']:<7} "
              f"{r['min_k1_range_percent']:<7.2f} {r['total_trades']:<8} "
              f"{r['win_rate']:<8.2f} {r['total_pnl']:<12.4f} {r['profit_factor']:<8.2f} {r['score']:<8.4f}")


def main():
    """主函数"""
    print("="*80)
    print("三K线策略参数优化系统")
    print("="*80)
    print("策略特点:")
    print("  - 仅统计前10根K线内触发止盈/止损的交易")
    print("  - 过滤包含关系的数据（仅rule1）")
    print("  - 止损固定为100%")
    print("="*80)
    
    # 加载K线数据
    cache_file = "ethusdt_15m_klines.json"
    
    if os.path.exists(cache_file):
        print(f"\n从缓存加载数据: {cache_file}")
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                raw_klines = json.load(f)
            print(f"✓ 成功读取 {len(raw_klines)} 根K线数据")
        except Exception as e:
            print(f"✗ 读取失败: {e}")
            return
    else:
        print(f"\n缓存文件不存在: {cache_file}")
        print("请先运行主策略脚本生成缓存文件")
        return
    
    # 转换为KLine对象
    klines = [KLine(k) for k in raw_klines]
    print(f"时间范围: {datetime.fromtimestamp(klines[0].timestamp/1000).strftime('%Y-%m-%d')} 至 "
          f"{datetime.fromtimestamp(klines[-1].timestamp/1000).strftime('%Y-%m-%d')}")
    
    # 遍历参数
    results = traverse_parameters(klines)
    
    # 导出结果
    export_results(results)
    
    # 分析最佳结果
    analyze_best_results(results, top_n=15)
    
    print(f"\n{'='*80}")
    print("参数优化完成！")
    print(f"{'='*80}")


if __name__ == '__main__':
    main()
