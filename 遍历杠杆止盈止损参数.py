"""
三K线策略参数优化 - 遍历杠杆、止盈、止损参数
作者: 
日期: 2025-11-08

遍历参数:
- leverage: 100-150 (步进10)
- profit_target_percent: 100-200 (步进10)
- stop_loss_percent: 300-500 (步进10)

固定参数:
- min_k1_range_percent: 0.21%
- initial_capital: 1.0 USDT
"""

import urllib.request
import json
import time
import csv
import os
from datetime import datetime
from typing import List, Dict, Optional


class BinanceAPI:
    """币安API接口封装"""
    BASE_URL = "https://api.binance.com"
    
    @staticmethod
    def get_klines(symbol: str = "BTCUSDT", interval: str = "15m", limit: int = 1000) -> List[List]:
        """
        获取K线数据（支持获取超过1000根）
        
        参数:
            symbol: 交易对，默认BTCUSDT
            interval: K线周期，默认15m
            limit: 获取数量，如果超过1000会分批获取
        
        返回:
            K线数据列表
        """
        all_klines = []
        remaining = limit
        end_time = None
        
        while remaining > 0:
            # 每次最多获取1000根
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
        
    def __repr__(self):
        dt = datetime.fromtimestamp(self.timestamp / 1000)
        return f"KLine({dt.strftime('%Y-%m-%d %H:%M')}, O:{self.open:.2f}, H:{self.high:.2f}, L:{self.low:.2f}, C:{self.close:.2f})"


class ThreeKlineStrategy:
    """三K线策略"""
    
    def __init__(self):
        self.signals = []  # 存储所有信号
        
    def is_contained(self, k1: KLine, k2: KLine) -> bool:
        """
        判断k2是否被k1完全包含
        
        参数:
            k1: 第一根K线
            k2: 第二根K线
        
        返回:
            True if k2被k1包含
        """
        return k2.high <= k1.high and k2.low >= k1.low
    
    def check_rule1(self, k1: KLine, k2: KLine, min_range_percent: float = 0.005) -> tuple:
        """
        检查法则1: 
        - 第一根K线的开盘价和收盘价必须有起码0.5%的涨跌幅
        - 第二根K线的最低价或最高价突破第一根K线
        - 但第二根K线的实体部分仍在第一根K线范围内
        - K2实体柱与K1实体柱的比值必须在0.5-1.6之间
        
        参数:
            k1: 第一根K线
            k2: 第二根K线
            min_range_percent: K1最小涨跌幅要求，默认0.5%
        
        返回:
            (是否满足, 方向) - 方向为 'long' 做多 或 'short' 做空，不满足则返回 (False, None)
        """
        # 检查K1的涨跌幅是否满足最小要求(使用开盘价和收盘价)
        k1_range = abs(k1.close - k1.open) / k1.open
        if k1_range < min_range_percent:
            return (False, None)
        
        # 检查实体是否在第一根K线范围内
        body_in_range = (k2.body_high <= k1.high and k2.body_low >= k1.low)
        
        if not body_in_range:
            return (False, None)
        
        # 检查K2实体柱与K1实体柱的比值
        k1_body_size = abs(k1.close - k1.open)
        k2_body_size = abs(k2.close - k2.open)
        
        # 避免除零错误
        if k1_body_size == 0:
            return (False, None)
        
        body_ratio = k2_body_size / k1_body_size
        
        # K2实体柱与K1实体柱的比值必须在0.5-1.6之间
        if body_ratio < 0.5 or body_ratio > 1.6:
            return (False, None)
        
        # 向下突破 -> 做多信号（预期反弹）
        if k2.low < k1.low:
            return (True, 'long')
        
        # 向上突破 -> 做空信号（预期回落）
        elif k2.high > k1.high:
            return (True, 'short')
        
        return (False, None)
    
    def find_signals(self, klines: List[KLine], 
                    profit_target: float = 0.008, 
                    stop_loss: float = 0.004,
                    min_k1_range: float = 0.005,
                    max_holding_bars_tp: int = None,
                    max_holding_bars_sl: int = None,
                    allow_stop_loss_retry: bool = True) -> List[Dict]:
        """
        查找所有交易信号并模拟持仓直到触发止盈/止损
        
        参数:
            klines: K线列表
            profit_target: 止盈百分比 (现货价格变动)
            stop_loss: 止损百分比 (现货价格变动)
            min_k1_range: K1最小涨跌幅要求 (小数形式，如0.005表示0.5%)
            max_holding_bars_tp: 止盈超时阈值(根K线数)，超过此时间未止盈则平仓
            max_holding_bars_sl: 止损超时阈值(根K线数)，超过此时间未止损则平仓
            allow_stop_loss_retry: 是否允许第一次触及止损点时不平仓，第二次才止损
        
        返回:
            信号列表(仅包含已触发止盈/止损的交易)
        """
        signals = []
        i = 0
        in_position = False  # 是否持仓中
        
        while i < len(klines) - 2:
            # 如果已经持仓,跳过新信号检测
            if in_position:
                i += 1
                continue
                
            k1 = klines[i]
            k2 = klines[i + 1]
            
            signal = None
            entry_index = None
            
            # 检查法则2: k2被k1包含 - 跳过包含关系的情况
            if i < len(klines) - 2 and self.is_contained(k1, k2):
                # 跳过包含关系，不生成信号
                i += 1
                continue
            # 检查法则1: k2相对于k1
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
                    entry_index = i + 2  # 从下一根K线开始监测
                    in_position = True
                    i += 1  # 跳到入场K线位置
            
            # 如果有信号,持续监测直到触发止盈/止损
            if signal and entry_index:
                entry_price = signal['entry_price']
                direction = signal['direction']
                stop_loss_hit_count = 0  # 止损触发次数计数器
                
                # 从入场后的第一根K线开始监测（只监测前100根K线）
                max_check_bars = min(entry_index + 100, len(klines))
                for j in range(entry_index, max_check_bars):
                    current_kline = klines[j]
                    holding_bars = j - entry_index + 1
                    
                    # 计算收益率
                    if direction == 'long':
                        high_return = (current_kline.high - entry_price) / entry_price
                        low_return = (current_kline.low - entry_price) / entry_price
                        current_return = (current_kline.close - entry_price) / entry_price
                    else:  # short
                        high_return = (entry_price - current_kline.low) / entry_price
                        low_return = (entry_price - current_kline.high) / entry_price
                        current_return = (entry_price - current_kline.close) / entry_price
                    
                    # 检查是否触发止盈
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
                    # 检查是否触发止损
                    elif low_return <= -stop_loss:
                        stop_loss_hit_count += 1
                        # 如果允许重试且是第一次触及止损，继续持仓
                        if allow_stop_loss_retry and stop_loss_hit_count == 1:
                            continue
                        # 第二次触及止损或不允许重试，则平仓
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
                    # 检查止盈超时（如果设置了）
                    elif max_holding_bars_tp is not None and holding_bars > max_holding_bars_tp and current_return > 0:
                        signal['exit_type'] = 'timeout_profit'
                        signal['exit_price'] = current_kline.close
                        signal['exit_time'] = current_kline.timestamp
                        signal['exit_index'] = j
                        signal['holding_bars'] = holding_bars
                        signal['return'] = current_return
                        signal['stop_loss_hit_count'] = stop_loss_hit_count
                        signals.append(signal)
                        in_position = False
                        break
                    # 检查止损超时（如果设置了）
                    elif max_holding_bars_sl is not None and holding_bars > max_holding_bars_sl and current_return <= 0:
                        signal['exit_type'] = 'timeout_loss'
                        signal['exit_price'] = current_kline.close
                        signal['exit_time'] = current_kline.timestamp
                        signal['exit_index'] = j
                        signal['holding_bars'] = holding_bars
                        signal['return'] = current_return
                        signal['stop_loss_hit_count'] = stop_loss_hit_count
                        signals.append(signal)
                        in_position = False
                        break
                
                # 如果循环结束还没触发,说明前100根K线内未触发止盈/止损,不纳入统计
                if in_position:
                    in_position = False
                    
            i += 1
        
        self.signals = signals
        return signals
    
    def calculate_win_rate(self, signals: List[Dict], 
                          leverage: int = 50,
                          initial_capital: float = 1.0) -> Dict:
        """
        计算胜率(信号已经包含止盈/止损信息)
        
        参数:
            signals: 信号列表(已触发止盈/止损)
            leverage: 杠杆倍数
            initial_capital: 每次交易投入的本金(USDT)
        
        返回:
            统计结果字典
        """
        if not signals:
            return {
                'total_signals': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0.0,
                'avg_profit': 0.0,
                'avg_loss': 0.0,
                'avg_holding_bars': 0.0,
                'total_capital': 0.0,
                'total_pnl': 0.0
            }
        
        wins = 0
        losses = 0
        profits = []
        losses_list = []
        holding_bars_list = []
        
        total_capital = 0.0  # 累计资金
        
        for signal in signals:
            return_pct = signal['return']
            holding_bars = signal['holding_bars']
            exit_type = signal['exit_type']
            
            holding_bars_list.append(holding_bars)
            
            # 计算本次交易盈亏(USDT)
            pnl = initial_capital * return_pct * leverage
            total_capital += pnl
            
            # 判断盈亏
            if exit_type in ('take_profit', 'timeout_profit'):
                wins += 1
                profits.append(return_pct)
            else:  # stop_loss or timeout_loss
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
            'win_rate': win_rate,
            'avg_profit': avg_profit * 100,
            'avg_loss': avg_loss * 100,
            'avg_holding_bars': avg_holding_bars,
            'initial_capital_per_trade': initial_capital,
            'total_capital': total_capital,
            'total_pnl': total_capital,
            'final_capital': total_trades * initial_capital + total_capital,
            'profit_factor': abs(sum(profits) / sum(losses_list)) if losses_list and sum(losses_list) != 0 else float('inf')
        }


def run_single_test(klines: List[KLine], 
                   leverage: int,
                   profit_target_percent: float,
                   stop_loss_percent: float,
                   min_k1_range_percent: float = 0.21,
                   initial_capital: float = 1.0) -> Dict:
    """
    运行单次参数测试
    
    参数:
        klines: K线数据
        leverage: 杠杆倍数
        profit_target_percent: 止盈百分比（合约收益%）
        stop_loss_percent: 止损百分比（合约亏损%）
        min_k1_range_percent: K1最小涨跌幅（%）
        initial_capital: 每次投入资金（USDT）
    
    返回:
        统计结果字典
    """
    # 计算现货价格需要变动的百分比
    price_profit_target = profit_target_percent / leverage / 100
    price_stop_loss = stop_loss_percent / leverage / 100
    min_k1_range = min_k1_range_percent / 100
    
    # 创建策略实例
    strategy = ThreeKlineStrategy()
    
    # 查找信号
    signals = strategy.find_signals(klines, 
                                    profit_target=price_profit_target,
                                    stop_loss=price_stop_loss,
                                    min_k1_range=min_k1_range)
    
    # 计算胜率
    stats = strategy.calculate_win_rate(signals, leverage=leverage, initial_capital=initial_capital)
    
    # 添加参数信息
    stats['leverage'] = leverage
    stats['profit_target_percent'] = profit_target_percent
    stats['stop_loss_percent'] = stop_loss_percent
    stats['min_k1_range_percent'] = min_k1_range_percent
    stats['price_profit_target'] = price_profit_target * 100
    stats['price_stop_loss'] = price_stop_loss * 100
    
    return stats


def main():
    """主函数"""
    print("="*80)
    print("三K线策略参数优化 - 遍历杠杆、止盈、止损")
    print("="*80)
    print(f"交易对: BTCUSDT")
    print(f"K线周期: 15分钟")
    print(f"数据来源: 币安API")
    print("="*80)
    
    # 参数范围设置
    leverage_range = range(100, 151, 10)  # 100-150, 步进10
    profit_range = range(100, 201, 10)    # 100-200, 步进10
    stop_loss_range = range(300, 501, 10) # 300-500, 步进10
    
    # 固定参数
    min_k1_range_percent = 0.21
    initial_capital = 1.0
    
    print(f"\n遍历参数设置:")
    print(f"  杠杆倍数: {leverage_range.start}-{leverage_range.stop-1} (步进{leverage_range.step})")
    print(f"  止盈百分比: {profit_range.start}-{profit_range.stop-1}% (步进{profit_range.step})")
    print(f"  止损百分比: {stop_loss_range.start}-{stop_loss_range.stop-1}% (步进{stop_loss_range.step})")
    print(f"\n固定参数:")
    print(f"  K1涨跌幅要求: {min_k1_range_percent}%")
    print(f"  每次投入: {initial_capital} USDT")
    
    # 计算总测试次数
    total_tests = len(leverage_range) * len(profit_range) * len(stop_loss_range)
    print(f"\n总测试次数: {total_tests}")
    print("="*80)
    
    # K线数据缓存文件
    cache_file = "ethusdt_15m_klines.json"
    
    # 获取K线数据
    if os.path.exists(cache_file):
        print(f"\n发现本地缓存文件: {cache_file}")
        print("正在读取本地数据...")
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                raw_klines = json.load(f)
            print(f"✓ 成功从缓存读取 {len(raw_klines)} 根K线数据")
        except Exception as e:
            print(f"✗ 读取缓存失败: {e}")
            print("将重新从币安获取数据...")
            raw_klines = None
    else:
        raw_klines = None
    
    # 如果没有缓存或读取失败,则从API获取
    if raw_klines is None:
        print("\n正在从币安API获取K线数据...")
        api = BinanceAPI()
        raw_klines = api.get_klines(symbol="BTCUSDT", interval="15m", limit=10000)
        
        if not raw_klines:
            print("获取K线数据失败！")
            return
        
        # 保存到本地缓存
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(raw_klines, f)
            print(f"✓ K线数据已缓存到: {cache_file}")
        except Exception as e:
            print(f"✗ 保存缓存失败: {e}")
    
    # 转换为KLine对象
    klines = [KLine(k) for k in raw_klines]
    print(f"\n数据统计:")
    print(f"  K线数量: {len(klines)} 根")
    print(f"  时间范围: {datetime.fromtimestamp(klines[0].timestamp/1000).strftime('%Y-%m-%d %H:%M')} 至 {datetime.fromtimestamp(klines[-1].timestamp/1000).strftime('%Y-%m-%d %H:%M')}")
    print(f"  时间跨度: {(klines[-1].timestamp - klines[0].timestamp) / 1000 / 86400:.1f} 天")
    
    # 开始遍历测试
    print(f"\n{'='*80}")
    print("开始参数优化测试...")
    print(f"{'='*80}\n")
    
    results = []
    test_count = 0
    start_time = time.time()
    
    for leverage in leverage_range:
        for profit_target in profit_range:
            for stop_loss in stop_loss_range:
                test_count += 1
                
                # 显示进度
                progress = test_count / total_tests * 100
                elapsed = time.time() - start_time
                eta = (elapsed / test_count) * (total_tests - test_count)
                
                print(f"[{test_count}/{total_tests}] ({progress:.1f}%) "
                      f"杠杆:{leverage}x 止盈:{profit_target}% 止损:{stop_loss}% "
                      f"已用时:{elapsed:.1f}s 预计剩余:{eta:.1f}s", end='\r')
                
                # 运行测试
                stats = run_single_test(klines, leverage, profit_target, stop_loss, 
                                       min_k1_range_percent, initial_capital)
                
                # 保存结果
                results.append({
                    '杠杆倍数': leverage,
                    '止盈百分比': profit_target,
                    '止损百分比': stop_loss,
                    '价格止盈%': f"{stats['price_profit_target']:.3f}",
                    '价格止损%': f"{stats['price_stop_loss']:.3f}",
                    '总交易数': stats['total_trades'],
                    '胜率%': f"{stats['win_rate']:.2f}",
                    '盈利次数': stats['wins'],
                    '亏损次数': stats['losses'],
                    '平均盈利%': f"{stats['avg_profit']:.3f}",
                    '平均亏损%': f"{stats['avg_loss']:.3f}",
                    '盈亏比': f"{stats['profit_factor']:.2f}",
                    '平均持仓K线数': f"{stats['avg_holding_bars']:.1f}",
                    '总盈亏USDT': f"{stats['total_pnl']:.4f}",
                    '最终资金USDT': f"{stats['final_capital']:.4f}",
                    '总收益率%': f"{(stats['total_pnl'] / (stats['total_trades'] * initial_capital) * 100):.2f}" if stats['total_trades'] > 0 else "0.00"
                })
    
    print(f"\n\n{'='*80}")
    print(f"参数优化完成！总用时: {time.time() - start_time:.1f}秒")
    print(f"{'='*80}")
    
    # 导出结果到CSV
    output_file = f"参数优化结果_杠杆止盈止损_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    try:
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = results[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        print(f"\n✓ 优化结果已导出到: {output_file}")
    except Exception as e:
        print(f"\n✗ 导出CSV失败: {e}")
    
    # 显示最佳结果
    print(f"\n{'='*80}")
    print("最佳参数组合 (按总收益率排序):")
    print(f"{'='*80}")
    
    # 按总收益率排序（转换为float进行排序）
    results_sorted = sorted(results, key=lambda x: float(x['总收益率%']), reverse=True)
    
    print("\n前10名最佳参数组合:")
    print("-"*120)
    print(f"{'排名':<6} {'杠杆':<8} {'止盈%':<8} {'止损%':<8} {'交易数':<8} {'胜率%':<10} {'盈亏比':<10} {'总收益率%':<12} {'总盈亏USDT':<12}")
    print("-"*120)
    
    for idx, result in enumerate(results_sorted[:10], 1):
        print(f"{idx:<6} {result['杠杆倍数']:<8} {result['止盈百分比']:<8} {result['止损百分比']:<8} "
              f"{result['总交易数']:<8} {result['胜率%']:<10} {result['盈亏比']:<10} "
              f"{result['总收益率%']:<12} {result['总盈亏USDT']:<12}")
    
    print("-"*120)
    
    # 按胜率排序
    print("\n\n按胜率排序前10名:")
    print("-"*120)
    results_by_winrate = sorted(results, key=lambda x: float(x['胜率%']), reverse=True)
    
    print(f"{'排名':<6} {'杠杆':<8} {'止盈%':<8} {'止损%':<8} {'交易数':<8} {'胜率%':<10} {'盈亏比':<10} {'总收益率%':<12} {'总盈亏USDT':<12}")
    print("-"*120)
    
    for idx, result in enumerate(results_by_winrate[:10], 1):
        print(f"{idx:<6} {result['杠杆倍数']:<8} {result['止盈百分比']:<8} {result['止损百分比']:<8} "
              f"{result['总交易数']:<8} {result['胜率%']:<10} {result['盈亏比']:<10} "
              f"{result['总收益率%']:<12} {result['总盈亏USDT']:<12}")
    
    print("-"*120)
    
    print(f"\n完整结果已保存到: {output_file}")
    print("您可以使用Excel打开该文件进行进一步分析")


if __name__ == '__main__':
    main()
