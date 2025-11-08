"""
参数优化分析 - 寻找最优参数组合
目标:
1. 亏损笔数在个位数（<10）
2. 胜率在95%以上
3. 至少100笔交易

参数范围:
- leverage: 20-80 (步进1)
- profit_target_percent: 20-80 (步进1)
- stop_loss_percent: 100-400 (步进1)
- min_k1_range_percent: 0.21-0.5 (步进0.01)
"""

import json
import os
from datetime import datetime
from typing import List, Dict
import csv


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
        return k2.high <= k1.high and k2.low >= k1.low
    
    def check_rule1(self, k1: KLine, k2: KLine, min_range_percent: float) -> tuple:
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
                    profit_target: float,
                    stop_loss: float,
                    min_k1_range: float) -> List[Dict]:
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
                        stop_loss_hit_count += 1
                        if stop_loss_hit_count == 1:
                            continue
                        signal['exit_type'] = 'stop_loss'
                        signal['return'] = -stop_loss
                        signals.append(signal)
                        in_position = False
                        break
                
                if in_position:
                    in_position = False
                    
            i += 1
        
        return signals
    
    def calculate_stats(self, signals: List[Dict]) -> Dict:
        if not signals:
            return {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0.0
            }
        
        wins = sum(1 for s in signals if s['exit_type'] == 'take_profit')
        losses = len(signals) - wins
        
        return {
            'total_trades': len(signals),
            'wins': wins,
            'losses': losses,
            'win_rate': (wins / len(signals) * 100) if signals else 0
        }


def load_klines():
    """加载K线数据"""
    cache_file = "ethusdt_15m_klines.json"
    
    if not os.path.exists(cache_file):
        print(f"✗ 未找到缓存文件: {cache_file}")
        print("请先运行主策略脚本生成缓存文件")
        return None
    
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            raw_klines = json.load(f)
        print(f"✓ 成功加载 {len(raw_klines)} 根K线数据")
        return [KLine(k) for k in raw_klines]
    except Exception as e:
        print(f"✗ 加载K线数据失败: {e}")
        return None


def optimize_parameters(klines: List[KLine]):
    """参数优化"""
    print("\n" + "="*80)
    print("参数优化分析")
    print("="*80)
    print(f"数据量: {len(klines)} 根K线")
    print(f"时间范围: {datetime.fromtimestamp(klines[0].timestamp/1000).strftime('%Y-%m-%d')} 至 {datetime.fromtimestamp(klines[-1].timestamp/1000).strftime('%Y-%m-%d')}")
    
    # 参数范围
    leverage_range = range(20, 81, 5)  # 步进改为5
    profit_range = range(20, 81, 3)    # 步进改为3
    stop_loss_range = range(100, 401, 5)  # 步进改为5
    min_k1_range = [round(x * 0.01, 2) for x in range(21, 51, 2)]  # 步进改为0.02
    
    total_combinations = len(leverage_range) * len(profit_range) * len(stop_loss_range) * len(min_k1_range)
    print(f"\n总组合数: {total_combinations:,}")
    print(f"预计耗时: 约 {total_combinations * 0.5 / 60:.0f} 分钟")
    print("\n开始优化...")
    print("-"*80)
    
    strategy = ThreeKlineStrategy()
    
    # 存储结果
    perfect_solutions = []  # 符合目标的完美解
    good_solutions = []     # 接近目标的优质解
    
    count = 0
    last_print_time = datetime.now()
    
    for leverage in leverage_range:
        for profit_target_percent in profit_range:
            for stop_loss_percent in stop_loss_range:
                for min_k1_pct in min_k1_range:
                    count += 1
                    
                    # 每10秒打印一次进度
                    now = datetime.now()
                    if (now - last_print_time).seconds >= 10:
                        progress = count / total_combinations * 100
                        print(f"进度: {progress:.2f}% ({count:,}/{total_combinations:,}) | 找到: 完美解={len(perfect_solutions)}, 优质解={len(good_solutions)}", end='\r')
                        last_print_time = now
                    
                    # 计算现货价格变动百分比
                    price_profit_target = profit_target_percent / leverage / 100
                    price_stop_loss = stop_loss_percent / leverage / 100
                    min_k1_range_val = min_k1_pct / 100
                    
                    # 运行策略
                    signals = strategy.find_signals(
                        klines,
                        profit_target=price_profit_target,
                        stop_loss=price_stop_loss,
                        min_k1_range=min_k1_range_val
                    )
                    
                    stats = strategy.calculate_stats(signals)
                    
                    # 至少100笔交易
                    if stats['total_trades'] < 100:
                        continue
                    
                    result = {
                        'leverage': leverage,
                        'profit_target_percent': profit_target_percent,
                        'stop_loss_percent': stop_loss_percent,
                        'min_k1_range_percent': min_k1_pct,
                        'total_trades': stats['total_trades'],
                        'wins': stats['wins'],
                        'losses': stats['losses'],
                        'win_rate': stats['win_rate']
                    }
                    
                    # 目标解：亏损<10 或 胜率>=95% (OR关系)
                    if stats['losses'] < 10 or stats['win_rate'] >= 95.0:
                        perfect_solutions.append(result)
                    # 次优解：亏损<15 或 胜率>=90% (备选)
                    elif stats['losses'] < 15 or stats['win_rate'] >= 90.0:
                        good_solutions.append(result)
    
    print("\n" + "-"*80)
    print(f"✓ 优化完成！共测试 {count:,} 组参数")
    
    return perfect_solutions, good_solutions


def export_results(perfect_solutions, good_solutions):
    """导出结果"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"参数优化结果_{timestamp}.csv"
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ['类型', '杠杆', '止盈%', '止损%', 'K1涨跌幅%', '总交易数', '盈利数', '亏损数', '胜率%']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for sol in perfect_solutions:
                writer.writerow({
                    '类型': '目标解',
                    '杠杆': sol['leverage'],
                    '止盈%': sol['profit_target_percent'],
                    '止损%': sol['stop_loss_percent'],
                    'K1涨跌幅%': sol['min_k1_range_percent'],
                    '总交易数': sol['total_trades'],
                    '盈利数': sol['wins'],
                    '亏损数': sol['losses'],
                    '胜率%': f"{sol['win_rate']:.2f}"
                })
            
            for sol in good_solutions:
                writer.writerow({
                    '类型': '次优解',
                    '杠杆': sol['leverage'],
                    '止盈%': sol['profit_target_percent'],
                    '止损%': sol['stop_loss_percent'],
                    'K1涨跌幅%': sol['min_k1_range_percent'],
                    '总交易数': sol['total_trades'],
                    '盈利数': sol['wins'],
                    '亏损数': sol['losses'],
                    '胜率%': f"{sol['win_rate']:.2f}"
                })
        
        print(f"\n✓ 结果已导出到: {filename}")
        return filename
    except Exception as e:
        print(f"\n✗ 导出失败: {e}")
        return None


def print_summary(perfect_solutions, good_solutions):
    """打印摘要"""
    print("\n" + "="*80)
    print("优化结果摘要")
    print("="*80)
    
    if perfect_solutions:
        print(f"\n✓ 找到 {len(perfect_solutions)} 个目标解（亏损<10 或 胜率≥95%）:")
        print("-"*80)
        print(f"{'杠杆':<6} {'止盈%':<6} {'止损%':<6} {'K1%':<6} {'交易数':<8} {'盈利':<6} {'亏损':<6} {'胜率%':<8}")
        print("-"*80)
        
        # 按胜率降序，然后按亏损升序
        sorted_perfect = sorted(perfect_solutions, key=lambda x: (-x['win_rate'], x['losses']))
        
        for i, sol in enumerate(sorted_perfect[:20], 1):  # 显示前20个
            print(f"{sol['leverage']:<6} {sol['profit_target_percent']:<6} {sol['stop_loss_percent']:<6} "
                  f"{sol['min_k1_range_percent']:<6.2f} {sol['total_trades']:<8} {sol['wins']:<6} "
                  f"{sol['losses']:<6} {sol['win_rate']:<8.2f}")
        
        if len(sorted_perfect) > 20:
            print(f"... 还有 {len(sorted_perfect) - 20} 个目标解（已导出到CSV）")
        
        print("\n推荐配置（最优目标解）:")
        best = sorted_perfect[0]
        print(f"  杠杆倍数: {best['leverage']}")
        print(f"  止盈百分比: {best['profit_target_percent']}% (合约)")
        print(f"  止损百分比: {best['stop_loss_percent']}% (合约)")
        print(f"  K1涨跌幅要求: {best['min_k1_range_percent']}%")
        print(f"  统计结果: {best['total_trades']}笔交易, {best['wins']}盈/{best['losses']}亏, 胜率{best['win_rate']:.2f}%")
        
    else:
        print("\n✗ 未找到目标解（亏损<10 或 胜率≥95%）")
        
        if good_solutions:
            print(f"\n○ 找到 {len(good_solutions)} 个次优解（亏损<15 或 胜率≥90%）:")
            print("-"*80)
            print(f"{'杠杆':<6} {'止盈%':<6} {'止损%':<6} {'K1%':<6} {'交易数':<8} {'盈利':<6} {'亏损':<6} {'胜率%':<8}")
            print("-"*80)
            
            # 按胜率降序，然后按亏损升序
            sorted_good = sorted(good_solutions, key=lambda x: (-x['win_rate'], x['losses']))
            
            for i, sol in enumerate(sorted_good[:20], 1):
                print(f"{sol['leverage']:<6} {sol['profit_target_percent']:<6} {sol['stop_loss_percent']:<6} "
                      f"{sol['min_k1_range_percent']:<6.2f} {sol['total_trades']:<8} {sol['wins']:<6} "
                      f"{sol['losses']:<6} {sol['win_rate']:<8.2f}")
            
            if len(sorted_good) > 20:
                print(f"... 还有 {len(sorted_good) - 20} 个次优解（已导出到CSV）")
            
            print("\n推荐配置（最优次优解）:")
            best = sorted_good[0]
            print(f"  杠杆倍数: {best['leverage']}")
            print(f"  止盈百分比: {best['profit_target_percent']}% (合约)")
            print(f"  止损百分比: {best['stop_loss_percent']}% (合约)")
            print(f"  K1涨跌幅要求: {best['min_k1_range_percent']}%")
            print(f"  统计结果: {best['total_trades']}笔交易, {best['wins']}盈/{best['losses']}亏, 胜率{best['win_rate']:.2f}%")
        else:
            print("\n✗ 也未找到次优解（亏损<15 或 胜率≥90%）")
            print("\n建议:")
            print("  1. 扩大参数搜索范围")
            print("  2. 降低目标要求（如胜率≥85%，亏损<20）")
            print("  3. 增加K线数据量以获得更多交易样本")
    
    print("="*80)


def main():
    """主函数"""
    print("="*80)
    print("三K线策略参数优化分析")
    print("="*80)
    print("目标:")
    print("  1. 至少100笔交易")
    print("  2. 亏损笔数 < 10  或  胜率 ≥ 95% (满足任一条件即可)")
    print("="*80)
    
    # 加载K线数据
    klines = load_klines()
    if not klines:
        return
    
    # 参数优化
    perfect_solutions, good_solutions = optimize_parameters(klines)
    
    # 打印摘要
    print_summary(perfect_solutions, good_solutions)
    
    # 导出结果
    if perfect_solutions or good_solutions:
        export_results(perfect_solutions, good_solutions)
    
    print("\n分析完成！")


if __name__ == '__main__':
    main()
