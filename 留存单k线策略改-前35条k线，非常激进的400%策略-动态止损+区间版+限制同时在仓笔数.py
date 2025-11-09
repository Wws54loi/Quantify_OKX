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
                    allow_stop_loss_retry: bool = True,
                    switch_bars: int = 35,
                    after_50_bars_tp_ratio: float = 0.9,
                    after_50_bars_sl_ratio: float = 0.3,
                    after_100_bars_tp_ratio: float = 1.0,
                    after_100_bars_sl_ratio: float = 1.0,
                    trailing_stop_percent: float = None,
                    max_concurrent_positions: int = 5) -> List[Dict]:
        """
                查找所有交易信号并模拟持仓直到触发止盈/止损。
                支持两级动态调整：
                    1) 超过 switch_bars 根K线后，用 after_50_bars_tp_ratio / after_50_bars_sl_ratio 调整
                    2) 超过 100 根K线后，再乘以 after_100_bars_tp_ratio / after_100_bars_sl_ratio 形成二次调整
        
        参数:
            klines: K线列表
            profit_target: 止盈百分比 (现货价格变动)
            stop_loss: 止损百分比 (现货价格变动)
            min_k1_range: K1最小涨跌幅要求 (小数形式，如0.005表示0.5%)
            max_holding_bars_tp: 止盈超时阈值(根K线数)，超过此时间未止盈则平仓
            max_holding_bars_sl: 止损超时阈值(根K线数)，超过此时间未止损则平仓
            allow_stop_loss_retry: 是否允许第一次触及止损点时不平仓，第二次才止损
            switch_bars: 多少根K线后切换止盈止损点，默认50根
            after_50_bars_tp_ratio: N根K线后的止盈比例，默认1.0不变，<1降低，>1提高
            after_50_bars_sl_ratio: N根K线后的止损比例，默认1.0不变，<1降低，>1提高
            trailing_stop_percent: 跟踪止损比例(小数形式，如0.03表示3%)，None表示不启用
            max_concurrent_positions: 最大同时持仓数量，默认5笔
        
        返回:
            信号列表(仅包含已触发止盈/止损的交易)
        """
        signals = []
        active_positions = []  # 活跃持仓列表: [{'entry_index': int, 'exit_index': int}, ...]
        i = 0
        in_position = False  # 是否持仓中
        
        while i < len(klines) - 2:
            # 清理已平仓的持仓(出场时间<=当前时间)
            current_time = klines[i].timestamp
            active_positions = [pos for pos in active_positions if pos['exit_index'] > i]
            
            # 检查是否达到最大持仓数限制
            if len(active_positions) >= max_concurrent_positions:
                i += 1
                continue
            
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
                    # 计算K1的实际涨跌幅(用于分阶段仓位)
                    k1_actual_range = abs(k1.close - k1.open) / k1.open * 100
                    
                    signal = {
                        'type': 'rule1',
                        'direction': direction,
                        'k1': k1,
                        'k2': k2,
                        'entry_price': k2.close,
                        'entry_time': k2.timestamp,
                        'entry_index': i + 1,
                        'k1_range_percent': k1_actual_range  # 记录K1涨跌幅(%)
                    }
                    entry_index = i + 2  # 从下一根K线开始监测
                    in_position = True
                    
                    # 添加临时持仓记录(出场index稍后更新)
                    temp_position = {'entry_index': i + 1, 'exit_index': len(klines)}
                    active_positions.append(temp_position)
                    
                    i += 1  # 跳到入场K线位置
            
            # 如果有信号,持续监测直到触发止盈/止损
            if signal and entry_index:
                entry_price = signal['entry_price']
                direction = signal['direction']
                stop_loss_hit_count = 0  # 止损触发次数计数器
                
                # 跟踪止损相关变量
                highest_price = entry_price  # 记录最高价（做多）
                lowest_price = entry_price   # 记录最低价（做空）
                trailing_stop_price = None   # 跟踪止损价
                min_profit_for_trailing = profit_target * 0.3  # 达到止盈目标30%后启用跟踪止损
                trailing_activated = False     # 跟踪止损是否已激活
                trailing_enable_after_bars = switch_bars  # 在N根K线后才允许启用跟踪止损
                
                # 从入场后的第一根K线开始监测（只监测前100根K线）
                max_check_bars = len(klines)

                # max_check_bars = min(entry_index +50, len(klines))
                for j in range(entry_index, max_check_bars):
                    current_kline = klines[j]
                    holding_bars = j - entry_index + 1
                    
                    # 动态调整止盈止损点：N根K线后使用新的比例
                    current_profit_target = profit_target
                    current_stop_loss = stop_loss
                    # 两级动态调整：先判断是否超过100根，再判断是否超过switch_bars
                    if holding_bars > 100:
                        current_profit_target = profit_target * after_50_bars_tp_ratio * after_100_bars_tp_ratio
                        current_stop_loss = stop_loss * after_50_bars_sl_ratio * after_100_bars_sl_ratio
                    elif holding_bars > switch_bars:
                        current_profit_target = profit_target * after_50_bars_tp_ratio
                        current_stop_loss = stop_loss * after_50_bars_sl_ratio
                    
                    # 计算收益率
                    if direction == 'long':
                        # 更新最高价
                        if current_kline.high > highest_price:
                            highest_price = current_kline.high
                        
                        high_return = (current_kline.high - entry_price) / entry_price
                        low_return = (current_kline.low - entry_price) / entry_price
                        current_return = (current_kline.close - entry_price) / entry_price
                        
                        # 跟踪止损逻辑（做多）- 只在持仓超过N根K线后才启用
                        if trailing_stop_percent is not None and holding_bars > trailing_enable_after_bars:
                            # 检查是否达到最低收益率要求
                            if not trailing_activated and high_return >= min_profit_for_trailing:
                                trailing_activated = True
                                trailing_stop_price = highest_price * (1 - trailing_stop_percent)
                                print(f"  [跟踪止损激活] 交易方向:做多, 入场价:{entry_price:.2f}, 最高价:{highest_price:.2f}, 初始止损价:{trailing_stop_price:.2f}, 持仓:{holding_bars}根K线")
                            
                            # 如果已激活，更新跟踪止损价
                            elif trailing_activated:
                                new_trailing_stop = highest_price * (1 - trailing_stop_percent)
                                if new_trailing_stop > trailing_stop_price:
                                    trailing_stop_price = new_trailing_stop
                        
                    else:  # short
                        # 更新最低价
                        if current_kline.low < lowest_price:
                            lowest_price = current_kline.low
                        
                        high_return = (entry_price - current_kline.low) / entry_price
                        low_return = (entry_price - current_kline.high) / entry_price
                        current_return = (entry_price - current_kline.close) / entry_price
                        
                        # 跟踪止损逻辑（做空）- 只在持仓超过N根K线后才启用
                        if trailing_stop_percent is not None and holding_bars > trailing_enable_after_bars:
                            # 检查是否达到最低收益率要求
                            if not trailing_activated and high_return >= min_profit_for_trailing:
                                trailing_activated = True
                                trailing_stop_price = lowest_price * (1 + trailing_stop_percent)
                                print(f"  [跟踪止损激活] 交易方向:做空, 入场价:{entry_price:.2f}, 最低价:{lowest_price:.2f}, 初始止损价:{trailing_stop_price:.2f}, 持仓:{holding_bars}根K线")
                            
                            # 如果已激活，更新跟踪止损价
                            elif trailing_activated:
                                new_trailing_stop = lowest_price * (1 + trailing_stop_percent)
                                if new_trailing_stop < trailing_stop_price:
                                    trailing_stop_price = new_trailing_stop
                    
                    # 检查是否触发止盈
                    if high_return >= current_profit_target:
                        signal['exit_type'] = 'take_profit'
                        signal['exit_price'] = entry_price * (1 + current_profit_target) if direction == 'long' else entry_price * (1 - current_profit_target)
                        signal['exit_time'] = current_kline.timestamp
                        signal['exit_index'] = j
                        signal['holding_bars'] = holding_bars
                        signal['return'] = current_profit_target
                        signal['stop_loss_hit_count'] = stop_loss_hit_count
                        signal['trailing_activated'] = trailing_activated
                        signal['highest_price'] = highest_price if direction == 'long' else None
                        signal['lowest_price'] = lowest_price if direction == 'short' else None
                        signals.append(signal)
                        temp_position['exit_index'] = j  # 更新平仓位置
                        in_position = False
                        break
                    
                    # 检查跟踪止损（优先级高于固定止损，但不能超过最大止损限制）
                    elif trailing_activated and trailing_stop_price is not None:
                        trailing_stop_triggered = False
                        
                        if direction == 'long':
                            # 做多：价格跌破跟踪止损价
                            if current_kline.low <= trailing_stop_price:
                                trailing_stop_triggered = True
                                actual_exit_price = trailing_stop_price
                        else:  # short
                            # 做空：价格突破跟踪止损价
                            if current_kline.high >= trailing_stop_price:
                                trailing_stop_triggered = True
                                actual_exit_price = trailing_stop_price
                        
                        if trailing_stop_triggered:
                            # 计算实际收益率
                            if direction == 'long':
                                actual_return = (actual_exit_price - entry_price) / entry_price
                            else:
                                actual_return = (entry_price - actual_exit_price) / entry_price
                            
                            # 关键修复：如果跟踪止损的亏损超过了固定止损点，强制使用固定止损点
                            # 注意：只有当亏损真的超过固定止损时才修正，否则保持跟踪止损的结果
                            if actual_return < -current_stop_loss:
                                # 亏损超限，强制使用固定止损价
                                actual_return = -current_stop_loss
                                actual_exit_price = entry_price * (1 - current_stop_loss) if direction == 'long' else entry_price * (1 + current_stop_loss)
                                signal['exit_type'] = 'stop_loss'
                            else:
                                # 跟踪止损正常工作（可能是盈利也可能是小额亏损，但未超过固定止损点）
                                signal['exit_type'] = 'trailing_stop'
                            
                            signal['exit_price'] = actual_exit_price
                            signal['exit_time'] = current_kline.timestamp
                            signal['exit_index'] = j
                            signal['holding_bars'] = holding_bars
                            signal['return'] = actual_return
                            signal['stop_loss_hit_count'] = stop_loss_hit_count
                            signal['trailing_activated'] = trailing_activated
                            signal['highest_price'] = highest_price if direction == 'long' else None
                            signal['lowest_price'] = lowest_price if direction == 'short' else None
                            signal['trailing_stop_price'] = trailing_stop_price
                            signals.append(signal)
                            temp_position['exit_index'] = j  # 更新平仓位置
                            in_position = False
                            print(f"  [跟踪止损触发] 出场价:{actual_exit_price:.2f}, 收益率:{actual_return*100:.2f}%, 类型:{signal['exit_type']}")
                            break
                    
                    # 检查是否触发固定止损（仅在跟踪止损未激活时检查）
                    if not trailing_activated and low_return <= -current_stop_loss:
                        stop_loss_hit_count += 1
                        # 如果允许重试且是第一次触及止损，继续持仓
                        if allow_stop_loss_retry and stop_loss_hit_count == 1:
                            continue
                        # 第二次触及止损或不允许重试，则平仓
                        signal['exit_type'] = 'stop_loss'
                        signal['exit_price'] = entry_price * (1 - current_stop_loss) if direction == 'long' else entry_price * (1 + current_stop_loss)
                        signal['exit_time'] = current_kline.timestamp
                        signal['exit_index'] = j
                        signal['holding_bars'] = holding_bars
                        signal['return'] = -current_stop_loss
                        signal['stop_loss_hit_count'] = stop_loss_hit_count
                        signal['trailing_activated'] = trailing_activated
                        signals.append(signal)
                        temp_position['exit_index'] = j  # 更新平仓位置
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
                        signal['trailing_activated'] = trailing_activated
                        signals.append(signal)
                        temp_position['exit_index'] = j  # 更新平仓位置
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
                        signal['trailing_activated'] = trailing_activated
                        signals.append(signal)
                        temp_position['exit_index'] = j  # 更新平仓位置
                        in_position = False
                        break
                
                # 如果循环结束还没触发,说明未触发止盈/止损,不纳入统计
                if in_position:
                    # 从active_positions中移除这个未成交的持仓
                    active_positions = [pos for pos in active_positions if pos != temp_position]
                    in_position = False
                    
            i += 1
        
        self.signals = signals
        return signals
    
    def calculate_win_rate(self, signals: List[Dict], 
                          leverage: int = 50,
                          initial_capital: float = 1.0,
                          position_tiers: List[Dict] = None) -> Dict:  # 新增分阶段仓位配置
        """
        计算胜率(信号已经包含止盈/止损信息)
        
        参数:
            signals: 信号列表(已触发止盈/止损)
            leverage: 杠杆倍数
            initial_capital: 基础投入本金(USDT),当position_tiers为None时使用
            position_tiers: 分阶段仓位配置列表,格式:
                [{'threshold': 0.30, 'capital': 1.5},  # K1涨跌幅>=0.30%时投入1.5U
                 {'threshold': 0.40, 'capital': 2.0},  # K1涨跌幅>=0.40%时投入2.0U
                 ...]
                如果为None则使用固定initial_capital
        
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
        rule2_trades = 0
        rule2_wins = 0
        rule2_losses = 0
        profits = []
        losses_list = []
        holding_bars_list = []
        trade_details = []  # 存储每笔交易详情
        
        total_capital = 0.0  # 累计资金
        total_investment = 0.0  # 总投入本金
        
        for idx, signal in enumerate(signals, 1):
            entry_price = signal['entry_price']
            exit_price = signal['exit_price']
            direction = signal['direction']
            exit_type = signal['exit_type']
            return_pct = signal['return']
            holding_bars = signal['holding_bars']
            
            holding_bars_list.append(holding_bars)
            
            # 根据K1涨跌幅动态确定本次投入本金
            k1_range = signal.get('k1_range_percent', 0)
            if position_tiers:
                # 使用分阶段仓位配置
                # 按阈值从高到低排序,找到第一个满足条件的档位
                sorted_tiers = sorted(position_tiers, key=lambda x: x['threshold'], reverse=True)
                trade_capital = initial_capital  # 默认使用基础本金
                for tier in sorted_tiers:
                    if k1_range >= tier['threshold']:
                        trade_capital = tier['capital']
                        break
            else:
                # 使用固定本金
                trade_capital = initial_capital
            
            total_investment += trade_capital
            
            # 计算本次交易盈亏(USDT)
            pnl = trade_capital * return_pct * leverage
            total_capital += pnl
            
            # 判断盈亏
            if exit_type == 'take_profit':
                wins += 1
                profits.append(return_pct)
                result = '止盈'
            elif exit_type == 'trailing_stop':
                wins += 1
                profits.append(return_pct)
                result = '跟踪止损'
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
            # 统计包含关系（rule2）
            if signal.get('type') == 'rule2':
                rule2_trades += 1
                if result in ('止盈', '跟踪止损', '超时止盈'):
                    rule2_wins += 1
                else:
                    rule2_losses += 1
            
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
                'k1_range_percent': k1_range,  # K1涨跌幅
                'trade_capital': trade_capital,  # 本次投入本金
                'price_change_percent': price_change_percent,
                'contract_return': contract_return,
                'pnl': pnl,
                'cumulative_capital': total_capital,
                'result': result,
                'trailing_activated': signal.get('trailing_activated', False),
                'highest_price': signal.get('highest_price'),
                'lowest_price': signal.get('lowest_price'),
                'trailing_stop_price': signal.get('trailing_stop_price'),
                # K1信息（完整）
                'k1_open': signal['k1'].open,
                'k1_high': signal['k1'].high,
                'k1_low': signal['k1'].low,
                'k1_close': signal['k1'].close,
                # K2信息（完整）
                'k2_open': signal['k2'].open,
                'k2_high': signal['k2'].high,
                'k2_low': signal['k2'].low,
                'k2_close': signal['k2'].close,
            }
            
            # 如果是包含关系（rule2），添加K3信息
            if signal.get('type') == 'rule2' and 'k3' in signal:
                trade_detail['k3_open'] = signal['k3'].open
                trade_detail['k3_high'] = signal['k3'].high
                trade_detail['k3_low'] = signal['k3'].low
                trade_detail['k3_close'] = signal['k3'].close
            
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
            'total_investment': total_investment,  # 实际总投入
            'total_capital': total_capital,
            'total_pnl': total_capital,
            'final_capital': total_investment + total_capital,
            'profit_factor': abs(sum(profits) / sum(losses_list)) if losses_list and sum(losses_list) != 0 else float('inf'),
            'trade_details': trade_details,
            'rule2_trades': rule2_trades,
            'rule2_wins': rule2_wins,
            'rule2_losses': rule2_losses,
            'rule1_trades': total_trades - rule2_trades,
            'rule1_wins': wins - rule2_wins,
            'rule1_losses': losses - rule2_losses
        }


def export_to_csv(trade_details: List[Dict], filename: str = "trade_log.csv"):
    """导出交易详情到CSV文件"""
    if not trade_details:
        print("没有交易数据可导出")
        return
    
    # 基础字段
    fieldnames = [
        '交易编号', '策略类型', '包含关系', '方向', '入场时间', '入场价格', 
        '出场时间', '出场价格', '持仓K线数', '持仓时长', '价格变动%', '合约收益%', 
        '盈亏USDT', '累计资金USDT', '结果', '跟踪止损激活', '最高价', '最低价', '跟踪止损价',
        'K1开盘', 'K1最高', 'K1最低', 'K1收盘',
        'K2开盘', 'K2最高', 'K2最低', 'K2收盘',
        'K3开盘', 'K3最高', 'K3最低', 'K3收盘'
    ]
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for trade in trade_details:
                row_data = {
                    '交易编号': trade['trade_id'],
                    '策略类型': trade['signal_type'],
                    '包含关系': '是' if trade.get('signal_type') == 'rule2' else '否',
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
                    '跟踪止损激活': '是' if trade.get('trailing_activated') else '否',
                    '最高价': f"{trade['highest_price']:.2f}" if trade.get('highest_price') else '',
                    '最低价': f"{trade['lowest_price']:.2f}" if trade.get('lowest_price') else '',
                    '跟踪止损价': f"{trade['trailing_stop_price']:.2f}" if trade.get('trailing_stop_price') else '',
                    'K1开盘': f"{trade['k1_open']:.2f}",
                    'K1最高': f"{trade['k1_high']:.2f}",
                    'K1最低': f"{trade['k1_low']:.2f}",
                    'K1收盘': f"{trade['k1_close']:.2f}",
                    'K2开盘': f"{trade['k2_open']:.2f}",
                    'K2最高': f"{trade['k2_high']:.2f}",
                    'K2最低': f"{trade['k2_low']:.2f}",
                    'K2收盘': f"{trade['k2_close']:.2f}",
                }
                
                # 如果是包含关系，添加K3信息
                if 'k3_open' in trade:
                    row_data['K3开盘'] = f"{trade['k3_open']:.2f}"
                    row_data['K3最高'] = f"{trade['k3_high']:.2f}"
                    row_data['K3最低'] = f"{trade['k3_low']:.2f}"
                    row_data['K3收盘'] = f"{trade['k3_close']:.2f}"
                else:
                    row_data['K3开盘'] = ''
                    row_data['K3最高'] = ''
                    row_data['K3最低'] = ''
                    row_data['K3收盘'] = ''
                
                writer.writerow(row_data)
        
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
            f.write(f"包含关系交易数(rule2): {stats.get('rule2_trades', 0)} (胜: {stats.get('rule2_wins', 0)} / 负: {stats.get('rule2_losses', 0)})\n")
            f.write(f"非包含关系交易数(rule1): {stats.get('rule1_trades', stats.get('total_trades', 0) - stats.get('rule2_trades', 0))} (胜: {stats.get('rule1_wins', stats.get('wins', 0) - stats.get('rule2_wins', 0))} / 负: {stats.get('rule1_losses', stats.get('losses', 0) - stats.get('rule2_losses', 0))})\n")
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
                f.write(f"  是否包含关系: {'是' if trade.get('signal_type') == 'rule2' else '否'}\n")
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
                f.write(f"  跟踪止损: {'已激活' if trade.get('trailing_activated') else '未激活'}\n")
                if trade.get('trailing_activated'):
                    # 安全地格式化highest_price和lowest_price
                    if trade.get('highest_price') is not None:
                        f.write(f"  最高价: {trade['highest_price']:.2f} USDT\n")
                    if trade.get('lowest_price') is not None:
                        f.write(f"  最低价: {trade['lowest_price']:.2f} USDT\n")
                    if trade.get('trailing_stop_price') is not None:
                        f.write(f"  跟踪止损价: {trade['trailing_stop_price']:.2f} USDT\n")
                f.write(f"  \n")
                f.write(f"  K1 - 开:{trade['k1_open']:.2f} 高:{trade['k1_high']:.2f} 低:{trade['k1_low']:.2f} 收:{trade['k1_close']:.2f}\n")
                f.write(f"  K2 - 开:{trade['k2_open']:.2f} 高:{trade['k2_high']:.2f} 低:{trade['k2_low']:.2f} 收:{trade['k2_close']:.2f}\n")
                # 如果是包含关系，添加K3信息
                if 'k3_open' in trade:
                    f.write(f"  K3 - 开:{trade['k3_open']:.2f} 高:{trade['k3_high']:.2f} 低:{trade['k3_low']:.2f} 收:{trade['k3_close']:.2f}\n")
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
    leverage = 140              # 杠杆倍数
    profit_target_percent = 330  # 止盈百分比（合约收益%）
    stop_loss_percent = 530       # 止损百分比（合约亏损%）
    initial_capital = 1.0       # 每次投入资金（USDT）
    min_k1_range_percent = 0.21  # 第一根K线开收涨跌幅要求（%）
    # 0.47/0.42收益确实很高 做的交易笔数相对减少 不适宜做策略的推敲，但是后续可以改为0.47
    trailing_stop_percent = 8.0  # 跟踪止损百分比（%），None表示不启用
    switch_bars = 40            # 多少根K线后切换止盈止损和启用跟踪止损
    max_concurrent_positions = 2  # 最大同时持仓数量
    # 新增二级动态调整参数候选遍历: 超过100根K线后的倍率
    after_100_tp_values = [1.0, 0.9, 0.8, 1.1, 1.2, 0.7]
    after_100_sl_values = [1.0, 0.9, 0.8, 1.1, 1.2, 0.7]
    perform_after_100_search = True  # 是否执行参数遍历
    
    # 分阶段仓位配置 - 根据K1涨跌幅动态调整投入本金
    # 设置为None则使用固定initial_capital
    # 最佳ROI(遍历): >=0.48%->2.6U, >=0.30%->1.6U, >=0.21%->1.0U
    position_tiers = [
        {'threshold': 0.48, 'capital': 2.6},   # 强信号
        {'threshold': 0.30, 'capital': 1.6},   # 中等信号
        {'threshold': 0.21, 'capital': 1.0},   # 基准
    ]
    # 不使用分阶段仓位,设置为: position_tiers = None
    # ==============================
    
    # 计算现货价格需要变动的百分比
    price_profit_target = profit_target_percent / leverage / 100
    price_stop_loss = stop_loss_percent / leverage / 100
    min_k1_range = min_k1_range_percent / 100
    trailing_stop = trailing_stop_percent / 100 if trailing_stop_percent is not None else None
    
    print("="*80)
    print("三K线策略胜率统计系统")
    print("="*80)
    print(f"交易对: BTCUSDT")
    print(f"K线周期: 15分钟")
    print(f"交易模式: 合约 ({leverage}倍杠杆)")
    print(f"数据来源: 币安API")
    print(f"持仓限制: 最多同时持有 {max_concurrent_positions} 笔")
    if trailing_stop is not None:
        activation_threshold = price_profit_target * 0.3 * 100
        print(f"跟踪止损: {trailing_stop_percent}% (持仓>{switch_bars}根K线且达到{activation_threshold:.3f}%现货收益后启用)")
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
    
    best_after_100_tp = 1.0
    best_after_100_sl = 1.0
    signals = []

    if perform_after_100_search:
        print("\n开始遍历 >100根K线后的TP/SL倍率参数...")
        combo_results = []
        for tp_r in after_100_tp_values:
            for sl_r in after_100_sl_values:
                cur_signals = strategy.find_signals(klines,
                                                    profit_target=price_profit_target,
                                                    stop_loss=price_stop_loss,
                                                    min_k1_range=min_k1_range,
                                                    switch_bars=switch_bars,
                                                    after_50_bars_tp_ratio=0.9,
                                                    after_50_bars_sl_ratio=0.3,
                                                    after_100_bars_tp_ratio=tp_r,
                                                    after_100_bars_sl_ratio=sl_r,
                                                    trailing_stop_percent=trailing_stop,
                                                    max_concurrent_positions=max_concurrent_positions)
                stats_tmp = strategy.calculate_win_rate(cur_signals,
                                                        leverage=leverage,
                                                        initial_capital=initial_capital,
                                                        position_tiers=position_tiers)
                combo_results.append({
                    'tp_ratio_100': tp_r,
                    'sl_ratio_100': sl_r,
                    'total_pnl': stats_tmp['total_pnl'],
                    'profit_factor': stats_tmp['profit_factor'],
                    'win_rate': stats_tmp['win_rate'],
                    'trades': stats_tmp['total_trades']
                })
        # 按总盈亏排序
        combo_results.sort(key=lambda x: x['total_pnl'], reverse=True)
        print("\nTop 8 组合 (按总盈亏排序):")
        for r in combo_results[:8]:
            print(f"  TP100={r['tp_ratio_100']:.2f} SL100={r['sl_ratio_100']:.2f} | 总盈亏={r['total_pnl']:+.4f} | 盈亏比={r['profit_factor']:.2f} | 胜率={r['win_rate']:.2f}% | 交易数={r['trades']}")
        # 选择最优组合(可以基于profit_factor与total_pnl的简单加权)
        best = max(combo_results, key=lambda x: (x['total_pnl'] * 0.7 + x['profit_factor'] * 0.3))
        best_after_100_tp = best['tp_ratio_100']
        best_after_100_sl = best['sl_ratio_100']
        print(f"\n选择最优组合: TP100={best_after_100_tp:.2f}, SL100={best_after_100_sl:.2f}\n")

    # 使用最优或默认组合重新计算最终signals
    signals = strategy.find_signals(klines,
                                    profit_target=price_profit_target,
                                    stop_loss=price_stop_loss,
                                    min_k1_range=min_k1_range,
                                    switch_bars=switch_bars,
                                    after_50_bars_tp_ratio=0.9,
                                    after_50_bars_sl_ratio=0.3,
                                    after_100_bars_tp_ratio=best_after_100_tp,
                                    after_100_bars_sl_ratio=best_after_100_sl,
                                    trailing_stop_percent=trailing_stop,
                                    max_concurrent_positions=max_concurrent_positions)
    print(f"最终使用参数下找到 {len(signals)} 个已平仓交易 (触发止盈/止损)")
    
    # 统计跟踪止损激活次数
    trailing_activated_count = sum(1 for s in signals if s.get('trailing_activated'))
    trailing_stop_exit_count = sum(1 for s in signals if s.get('exit_type') == 'trailing_stop')
    if trailing_stop is not None:
        print(f"跟踪止损激活次数: {trailing_activated_count}")
        print(f"跟踪止损平仓次数: {trailing_stop_exit_count}")
    
    
    # 计算胜率
    print("\n正在计算统计数据...")
    stats = strategy.calculate_win_rate(signals, 
                                        leverage=leverage, 
                                        initial_capital=initial_capital,
                                        position_tiers=position_tiers)
    
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
    if trailing_stop is not None:
        activation_threshold = price_profit_target * 0.3 * 100
        print(f"跟踪止损: {trailing_stop_percent}% (持仓>{switch_bars}根K线且达到{activation_threshold:.3f}%现货收益后启用)")
    if position_tiers:
        print(f"仓位管理: 分阶段加注")
        for tier in sorted(position_tiers, key=lambda x: x['threshold'], reverse=True):
            print(f"  K1涨跌幅 >= {tier['threshold']:.2f}%: 投入 {tier['capital']:.1f} USDT")
    else:
        print(f"仓位管理: 固定投入 {initial_capital} USDT")
    print(f"{'-'*80}")
    print(f"总交易数: {stats['total_trades']} (仅统计已触发止盈/止损的交易)")
    print(f"包含关系交易数(rule2): {stats.get('rule2_trades', 0)} (胜: {stats.get('rule2_wins', 0)} / 负: {stats.get('rule2_losses', 0)})")
    print(f"非包含关系交易数(rule1): {stats.get('rule1_trades', 0)} (胜: {stats.get('rule1_wins', 0)} / 负: {stats.get('rule1_losses', 0)})")
    print(f"盈利次数: {stats['wins']} (止盈)")
    print(f"亏损次数: {stats['losses']} (止损)")
    print(f"胜率: {stats['win_rate']:.2f}%")
    print(f"平均盈利: {stats['avg_profit']*leverage:.2f}% (合约收益)")
    print(f"平均亏损: {stats['avg_loss']*leverage:.2f}% (合约亏损)")
    print(f"平均持仓: {stats['avg_holding_bars']:.1f}根K线 ({stats['avg_holding_time']})")
    print(f"盈亏比: {stats['profit_factor']:.2f}")
    if trailing_stop is not None:
        print(f"{'-'*80}")
        print(f"跟踪止损统计:")
        print(f"  激活次数: {trailing_activated_count}")
        print(f"  平仓次数: {trailing_stop_exit_count}")
    print(f"{'-'*80}")
    print(f"资金管理:")
    print(f"  总投入: {stats['total_investment']:.2f} USDT")
    print(f"  平均每笔: {stats['total_investment'] / stats['total_trades']:.2f} USDT")
    print(f"  总盈亏: {stats['total_pnl']:+.4f} USDT")
    print(f"  最终资金: {stats['final_capital']:.4f} USDT")
    print(f"  总收益率: {(stats['total_pnl'] / stats['total_investment'] * 100):+.2f}%")
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
