"""
三K线策略胜率统计 - 币安BTC 15分钟K线
作者: 
日期: 2025-11-04

交易模式: 合约交易 (50倍杠杆)
止盈: 40% (价格变动0.8%)
止损: 20% (价格变动0.4%)

策略规则:
法则1: 三K线策略
  - 第一根K线的开盘价和收盘价必须有起码0.5%的涨跌幅
  - 第二根K线的最低价或最高价突破第一根K线
  - 但第二根K线的实体部分仍在第一根K线范围内
  - 向下突破做多（预期反弹），向上突破做空（预期回落）
  - 在第二根K线收盘价入场

法则2: 包含关系处理
  - 如果第二根K线的最高点和最低点都被包含在第一根K线里
  - 则第三根K线执行法则1中第二根K线的规则
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
                print(f"  正在获取K线数据... (已获取 {len(all_klines)}/{limit})", end='\r')
                with urllib.request.urlopen(url, timeout=10) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    
                    if not data:
                        break
                    
                    # 添加到结果中（倒序添加以保持时间顺序）
                    all_klines = data + all_klines
                    
                    # 更新end_time为最早K线的时间戳
                    end_time = data[0][0] - 1
                    
                    remaining -= len(data)
                    
                    # 如果返回的数据少于请求的数量，说明没有更多历史数据了
                    if len(data) < batch_limit:
                        break
                    
                    # 避免请求过快
                    time.sleep(0.2)
                    
            except Exception as e:
                print(f"\n获取K线数据失败: {e}")
                break
        
        print(f"  成功获取 {len(all_klines)} 根K线数据" + " " * 20)
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
            
            # 检查法则2: k2被k1包含
            if i < len(klines) - 2 and self.is_contained(k1, k2):
                k3 = klines[i + 2]
                # k3执行法则1的规则(相对于k1)
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
                    entry_index = i + 3  # 从下一根K线开始监测
                    in_position = True
                    i += 2  # 跳到入场K线位置
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
                
                # 从入场后的第一根K线开始监测
                for j in range(entry_index, len(klines)):
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
                
                # 如果循环结束还没触发,说明到最新时间都没平仓,不纳入统计
                if in_position:
                    in_position = False
                    
            i += 1
        
        self.signals = signals
        return signals
    
    def calculate_win_rate(self, signals: List[Dict], 
                          leverage: int = 50,
                          initial_capital: float = 1.0) -> Dict:  # 杠杆倍数和每次投入资金
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
                'total_pnl': 0.0,
                'trade_details': []
            }
        
        wins = 0
        losses = 0
        profits = []
        losses_list = []
        holding_bars_list = []
        trade_details = []  # 存储每笔交易详情
        
        total_capital = 0.0  # 累计资金
        
        for idx, signal in enumerate(signals, 1):
            entry_price = signal['entry_price']
            exit_price = signal['exit_price']
            direction = signal['direction']
            exit_type = signal['exit_type']
            return_pct = signal['return']
            holding_bars = signal['holding_bars']
            
            holding_bars_list.append(holding_bars)
            
            # 计算本次交易盈亏(USDT)
            pnl = initial_capital * return_pct * leverage
            total_capital += pnl
            
            # 判断盈亏
            if exit_type == 'take_profit':
                wins += 1
                profits.append(return_pct)
                result = '止盈'
            elif exit_type == 'timeout_profit':
                wins += 1
                profits.append(return_pct)
                result = '超时止盈'
            elif exit_type == 'stop_loss':
                losses += 1
                losses_list.append(return_pct)
                result = '止损'
            else:  # timeout_loss
                losses += 1
                losses_list.append(return_pct)
                result = '超时止损'
            
            # 计算百分比
            price_change_percent = return_pct * 100
            contract_return = return_pct * leverage * 100
            
            # 记录交易详情
            trade_detail = {
                'trade_id': idx,
                'signal_type': signal['type'],
                'direction': '做多' if direction == 'long' else '做空',
                'entry_time': datetime.fromtimestamp(signal['entry_time']/1000).strftime('%Y-%m-%d %H:%M'),
                'entry_price': entry_price,
                'exit_time': datetime.fromtimestamp(signal['exit_time']/1000).strftime('%Y-%m-%d %H:%M'),
                'exit_price': exit_price,
                'holding_bars': holding_bars,
                'holding_time': f"{holding_bars * 15}分钟",
                'price_change_percent': price_change_percent,
                'contract_return': contract_return,
                'pnl': pnl,
                'cumulative_capital': total_capital,
                'result': result,
                'k1_high': signal['k1'].high,
                'k1_low': signal['k1'].low,
                'k2_high': signal['k2'].high,
                'k2_low': signal['k2'].low,
            }
            trade_details.append(trade_detail)
        
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
            'avg_profit': avg_profit * 100,  # 转换为百分比
            'avg_loss': avg_loss * 100,  # 转换为百分比
            'avg_holding_bars': avg_holding_bars,
            'avg_holding_time': f"{avg_holding_bars * 15:.1f}分钟",
            'initial_capital_per_trade': initial_capital,
            'total_capital': total_capital,
            'total_pnl': total_capital,
            'final_capital': total_trades * initial_capital + total_capital,
            'profit_factor': abs(sum(profits) / sum(losses_list)) if losses_list and sum(losses_list) != 0 else float('inf'),
            'trade_details': trade_details
        }


def export_to_csv(trade_details: List[Dict], filename: str = "trade_log.csv"):
    """导出交易详情到CSV文件"""
    if not trade_details:
        print("没有交易数据可导出")
        return
    
    fieldnames = [
        '交易编号', '策略类型', '方向', '入场时间', '入场价格', 
        '出场时间', '出场价格', '持仓K线数', '持仓时长', '价格变动%', '合约收益%', 
        '盈亏USDT', '累计资金USDT', '结果', 'K1最高', 'K1最低', 'K2最高', 'K2最低'
    ]
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for trade in trade_details:
                writer.writerow({
                    '交易编号': trade['trade_id'],
                    '策略类型': trade['signal_type'],
                    '方向': trade['direction'],
                    '入场时间': trade['entry_time'],
                    '入场价格': f"{trade['entry_price']:.2f}",
                    '出场时间': trade['exit_time'],
                    '出场价格': f"{trade['exit_price']:.2f}",
                    '持仓K线数': trade['holding_bars'],
                    '持仓时长': trade['holding_time'],
                    '价格变动%': f"{trade['price_change_percent']:.3f}%",
                    '合约收益%': f"{trade['contract_return']:.2f}%",
                    '盈亏USDT': f"{trade['pnl']:.4f}",
                    '累计资金USDT': f"{trade['cumulative_capital']:.4f}",
                    '结果': trade['result'],
                    'K1最高': f"{trade['k1_high']:.2f}",
                    'K1最低': f"{trade['k1_low']:.2f}",
                    'K2最高': f"{trade['k2_high']:.2f}",
                    'K2最低': f"{trade['k2_low']:.2f}",
                })
        
        print(f"\n✓ 交易日志已导出到: {filename}")
        return filename
    except Exception as e:
        print(f"\n✗ 导出CSV失败: {e}")
        return None


def export_to_txt(trade_details: List[Dict], stats: Dict, filename: str = "trade_log.txt"):
    """导出详细交易日志到TXT文件"""
    if not trade_details:
        print("没有交易数据可导出")
        return
    
    try:
        # 从stats中获取动态参数
        leverage = stats.get('leverage', 30)
        profit_target_percent = stats.get('profit_target_percent', 40)
        stop_loss_percent = stats.get('stop_loss_percent', 20)
        min_k1_range_percent = stats.get('min_k1_range_percent', 0.5)
        price_profit_target = profit_target_percent / leverage
        price_stop_loss = stop_loss_percent / leverage
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("三K线策略交易日志\n")
            f.write("="*80 + "\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"交易对: BTCUSDT\n")
            f.write(f"K线周期: 15分钟\n")
            f.write(f"交易模式: 合约 ({leverage}倍杠杆)\n")
            f.write(f"止盈设置: {profit_target_percent}% (价格变动 {price_profit_target:.2f}%)\n")
            f.write(f"止损设置: {stop_loss_percent}% (价格变动 {price_stop_loss:.2f}%)\n")
            f.write(f"K1涨跌幅要求: {min_k1_range_percent}%\n")
            f.write("="*80 + "\n\n")
            
            f.write("策略统计摘要:\n")
            f.write("-"*80 + "\n")
            f.write(f"总信号数: {stats['total_signals']}\n")
            f.write(f"总交易数: {stats['total_trades']}\n")
            f.write(f"盈利次数: {stats['wins']}\n")
            f.write(f"亏损次数: {stats['losses']}\n")
            f.write(f"胜率: {stats['win_rate']:.2f}%\n")
            f.write(f"平均盈利: {stats['avg_profit']*leverage:.2f}% (合约收益)\n")
            f.write(f"平均亏损: {stats['avg_loss']*leverage:.2f}% (合约亏损)\n")
            f.write(f"平均持仓: {stats['avg_holding_bars']:.1f}根K线 ({stats['avg_holding_time']})\n")
            f.write(f"盈亏比: {stats['profit_factor']:.2f}\n")
            f.write("-"*80 + "\n")
            f.write(f"每次投入: {stats['initial_capital_per_trade']:.2f} USDT\n")
            f.write(f"总投入: {stats['total_trades'] * stats['initial_capital_per_trade']:.2f} USDT\n")
            f.write(f"总盈亏: {stats['total_pnl']:.4f} USDT\n")
            f.write(f"最终资金: {stats['final_capital']:.4f} USDT\n")
            f.write(f"总收益率: {(stats['total_pnl'] / (stats['total_trades'] * stats['initial_capital_per_trade']) * 100):.2f}%\n")
            f.write("="*80 + "\n\n")
            
            f.write("详细交易记录:\n")
            f.write("="*80 + "\n\n")
            
            for trade in trade_details:
                f.write(f"交易 #{trade['trade_id']} - {trade['result']} ({trade['direction']})\n")
                f.write(f"  策略类型: {trade['signal_type']}\n")
                f.write(f"  交易方向: {trade['direction']}\n")
                f.write(f"  入场时间: {trade['entry_time']}\n")
                f.write(f"  入场价格: {trade['entry_price']:.2f} USDT\n")
                f.write(f"  出场时间: {trade['exit_time']}\n")
                f.write(f"  出场价格: {trade['exit_price']:.2f} USDT\n")
                f.write(f"  持仓时长: {trade['holding_bars']}根K线 ({trade['holding_time']})\n")
                f.write(f"  价格变动: {trade['price_change_percent']:.3f}%\n")
                f.write(f"  合约收益: {trade['contract_return']:.2f}%\n")
                f.write(f"  本次盈亏: {trade['pnl']:+.4f} USDT\n")
                f.write(f"  累计盈亏: {trade['cumulative_capital']:+.4f} USDT\n")
                f.write(f"  K1区间: [{trade['k1_low']:.2f} - {trade['k1_high']:.2f}]\n")
                f.write(f"  K2区间: [{trade['k2_low']:.2f} - {trade['k2_high']:.2f}]\n")
                f.write("-"*80 + "\n")
        
        print(f"✓ 详细日志已导出到: {filename}")
        return filename
    except Exception as e:
        print(f"✗ 导出TXT失败: {e}")
        return None


def print_signal_details(signals: List[Dict], limit: int = 10):
    """打印信号详情"""
    print(f"\n{'='*80}")
    print(f"交易信号详情 (显示前{min(limit, len(signals))}个)")
    print(f"{'='*80}")
    
    for i, signal in enumerate(signals[:limit]):
        print(f"\n信号 #{i+1} - 类型: {signal['type']} - {signal['exit_type']}")
        print(f"  入场时间: {datetime.fromtimestamp(signal['entry_time']/1000).strftime('%Y-%m-%d %H:%M')}")
        print(f"  出场时间: {datetime.fromtimestamp(signal['exit_time']/1000).strftime('%Y-%m-%d %H:%M')}")
        print(f"  持仓: {signal['holding_bars']}根K线 ({signal['holding_bars'] * 15}分钟)")
        print(f"  入场价格: {signal['entry_price']:.2f}")
        print(f"  出场价格: {signal['exit_price']:.2f}")
        print(f"  收益率: {signal['return']*100:.3f}%")


def main():
    """主函数"""
    # ====== 关键参数集中设置 ======
    leverage = 50               # 杠杆倍数
    profit_target_percent = 40  # 止盈百分比（合约收益%）
    stop_loss_percent = 99      # 止损百分比（合约亏损%）
    initial_capital = 1.0       # 每次投入资金（USDT）
    min_k1_range_percent = 0.44  # 第一根K线开收涨跌幅要求（%）
    # ==============================
    
    # 计算现货价格需要变动的百分比
    price_profit_target = profit_target_percent / leverage / 100
    price_stop_loss = stop_loss_percent / leverage / 100
    min_k1_range = min_k1_range_percent / 100
    
    print("="*80)
    print("三K线策略胜率统计系统")
    print("="*80)
    print(f"交易对: BTCUSDT")
    print(f"K线周期: 15分钟")
    print(f"交易模式: 合约 ({leverage}倍杠杆)")
    print(f"数据来源: 币安API")
    print("="*80)
    
    # K线数据缓存文件
    cache_file = "btcusdt_15m_klines.json"
    
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
            print(f"  (如需重新获取最新数据,请删除此文件)")
        except Exception as e:
            print(f"✗ 保存缓存失败: {e}")
    
    # 转换为KLine对象
    klines = [KLine(k) for k in raw_klines]
    print(f"\n数据统计:")
    print(f"  K线数量: {len(klines)} 根")
    print(f"  时间范围: {datetime.fromtimestamp(klines[0].timestamp/1000).strftime('%Y-%m-%d %H:%M')} 至 {datetime.fromtimestamp(klines[-1].timestamp/1000).strftime('%Y-%m-%d %H:%M')}")
    print(f"  时间跨度: {(klines[-1].timestamp - klines[0].timestamp) / 1000 / 86400:.1f} 天")
    
    # 创建策略实例
    strategy = ThreeKlineStrategy()
    
    # 查找信号
    print("\n正在分析K线形态并模拟交易...")
    
    signals = strategy.find_signals(klines, 
                                    profit_target=price_profit_target,
                                    stop_loss=price_stop_loss,
                                    min_k1_range=min_k1_range)
    print(f"找到 {len(signals)} 个已平仓交易 (触发止盈/止损)")
    
    # 打印信号详情
    print_signal_details(signals, limit=5)
    
    # 计算胜率
    print("\n正在计算统计数据...")
    stats = strategy.calculate_win_rate(signals, leverage=leverage, initial_capital=initial_capital)
    
    # 附加关键参数到stats，便于导出txt时动态展示
    stats['leverage'] = leverage
    stats['profit_target_percent'] = profit_target_percent
    stats['stop_loss_percent'] = stop_loss_percent
    stats['min_k1_range_percent'] = min_k1_range_percent
    
    # 打印统计结果
    print(f"\n{'='*80}")
    print("策略统计结果")
    print(f"{'='*80}")
    print(f"交易模式: 合约交易 ({leverage}倍杠杆)")
    print(f"止盈设置: {profit_target_percent}% (价格变动 {price_profit_target*100:.2f}%)")
    print(f"止损设置: {stop_loss_percent}% (价格变动 {price_stop_loss*100:.2f}%)")
    print(f"K1涨跌幅要求: {min_k1_range_percent}%")
    print(f"每次投入: {initial_capital} USDT")
    print(f"{'-'*80}")
    print(f"总交易数: {stats['total_trades']} (仅统计已触发止盈/止损的交易)")
    print(f"盈利次数: {stats['wins']} (止盈)")
    print(f"亏损次数: {stats['losses']} (止损)")
    print(f"胜率: {stats['win_rate']:.2f}%")
    print(f"平均盈利: {stats['avg_profit']*leverage:.2f}% (合约收益)")
    print(f"平均亏损: {stats['avg_loss']*leverage:.2f}% (合约亏损)")
    print(f"平均持仓: {stats['avg_holding_bars']:.1f}根K线 ({stats['avg_holding_time']})")
    print(f"盈亏比: {stats['profit_factor']:.2f}")
    print(f"{'-'*80}")
    print(f"资金管理 (每次投入 {initial_capital:.2f} USDT):")
    print(f"  总投入: {stats['total_trades'] * initial_capital:.2f} USDT")
    print(f"  总盈亏: {stats['total_pnl']:+.4f} USDT")
    print(f"  最终资金: {stats['final_capital']:.4f} USDT")
    print(f"  总收益率: {(stats['total_pnl'] / (stats['total_trades'] * initial_capital) * 100):+.2f}%")
    print(f"{'='*80}")
    
    # 策略评估
    print("\n策略评估:")
    if stats['win_rate'] >= 60:
        print("✓ 胜率优秀 (>=60%)")
    elif stats['win_rate'] >= 50:
        print("○ 胜率中等 (50%-60%)")
    else:
        print("✗ 胜率较低 (<50%)")
    
    if stats['profit_factor'] >= 2:
        print("✓ 盈亏比优秀 (>=2)")
    elif stats['profit_factor'] >= 1.5:
        print("○ 盈亏比中等 (1.5-2)")
    else:
        print("✗ 盈亏比较低 (<1.5)")
    
    print("\n注意事项:")
    print("- 本统计仅供参考，实际交易需考虑手续费、滑点、资金费率等因素")
    print(f"- 合约交易风险极高，{leverage}倍杠杆下价格波动{price_stop_loss*100:.2f}%即触发止损")
    print("- 建议严格执行止损，控制仓位，避免爆仓风险")
    
    # 导出日志
    print(f"\n{'='*80}")
    print("导出交易日志")
    print(f"{'='*80}")
    
    # 导出CSV格式（适合Excel分析）
    csv_file = export_to_csv(stats['trade_details'])
    
    # 导出TXT格式（适合阅读）
    txt_file = export_to_txt(stats['trade_details'], stats)
    
    print(f"\n日志文件已保存在当前目录下")


if __name__ == '__main__':
    main()
