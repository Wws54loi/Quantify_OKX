"""
实时K线监听器 - 币安BTC实时监控
作者: 
日期: 2025-11-05

监听规则:
1. 监听15分钟K线和1分钟K线
2. 当前一根15分钟K线的开收盘涨跌幅 >= 0.21% 时
3. 在当前15分钟K线的1分钟K线中，如果满足以下条件则通知：
   - 1分钟K线的最高价突破了前一根15分钟K线的最高价，但收盘价回到区间内（做空信号）
   - 1分钟K线的最低价突破了前一根15分钟K线的最低价，但收盘价回到区间内（做多信号）
"""

import urllib.request
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
import winsound  # Windows系统通知音


class BinanceLiveAPI:
    """币安实时API接口"""
    BASE_URL = "https://api.binance.com"
    
    @staticmethod
    def get_latest_klines(symbol: str = "BTCUSDT", interval: str = "1m", limit: int = 2) -> List[List]:
        """获取最新的K线数据"""
        url = f"{BinanceLiveAPI.BASE_URL}/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return data
        except Exception as e:
            print(f"获取K线数据失败: {e}")
            return []
    
    @staticmethod
    def get_server_time() -> int:
        """获取服务器时间"""
        url = f"{BinanceLiveAPI.BASE_URL}/api/v3/time"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return data['serverTime']
        except Exception as e:
            print(f"获取服务器时间失败: {e}")
            return int(time.time() * 1000)


class SimpleKLine:
    """简化的K线数据类"""
    
    def __init__(self, kline_data: List):
        self.timestamp = int(kline_data[0])
        self.open = float(kline_data[1])
        self.high = float(kline_data[2])
        self.low = float(kline_data[3])
        self.close = float(kline_data[4])
        self.volume = float(kline_data[5])
        self.close_time = int(kline_data[6])
        self.is_closed = True  # 最后一根K线可能未完成
        
    def get_body_range(self):
        """获取实体涨跌幅"""
        return abs(self.close - self.open) / self.open
    
    def __repr__(self):
        dt = datetime.fromtimestamp(self.timestamp / 1000)
        return f"K[{dt.strftime('%H:%M')}, O:{self.open:.2f}, H:{self.high:.2f}, L:{self.low:.2f}, C:{self.close:.2f}]"


class LiveMonitor:
    """实时监听器"""
    
    def __init__(self, min_k1_range_percent: float = 0.21):
        self.min_k1_range = min_k1_range_percent / 100  # 转换为小数
        self.last_15m_kline = None  # 上一根完整的15分钟K线
        self.current_15m_start_time = 0  # 当前15分钟K线的开始时间
        self.alerted_signals = set()  # 已通知的信号(避免重复通知)
        self.api = BinanceLiveAPI()
        
    def check_k1_qualification(self, k1: SimpleKLine) -> bool:
        """检查K1是否符合涨跌幅要求"""
        body_range = k1.get_body_range()
        return body_range >= self.min_k1_range
    
    def check_signal(self, k1_15m: SimpleKLine, k1_1m: SimpleKLine) -> Optional[Dict]:
        """
        检查1分钟K线是否满足信号条件
        
        参数:
            k1_15m: 前一根15分钟K线(已完成)
            k1_1m: 当前1分钟K线
        
        返回:
            如果满足条件返回信号字典，否则返回None
        """
        # 检查1分钟K线的收盘价是否在15分钟K线区间内
        close_in_range = k1_15m.low <= k1_1m.close <= k1_15m.high
        
        if not close_in_range:
            return None
        
        # 向上突破后回落 -> 做空信号
        if k1_1m.high > k1_15m.high:
            return {
                'type': 'short',
                'direction': '做空',
                'k15m': k1_15m,
                'k1m': k1_1m,
                'breakout_type': '向上突破',
                'breakout_price': k1_1m.high,
                'reference_price': k1_15m.high,
                'current_price': k1_1m.close,
                'timestamp': k1_1m.timestamp
            }
        
        # 向下突破后回升 -> 做多信号
        elif k1_1m.low < k1_15m.low:
            return {
                'type': 'long',
                'direction': '做多',
                'k15m': k1_15m,
                'k1m': k1_1m,
                'breakout_type': '向下突破',
                'breakout_price': k1_1m.low,
                'reference_price': k1_15m.low,
                'current_price': k1_1m.close,
                'timestamp': k1_1m.timestamp
            }
        
        return None
    
    def send_notification(self, signal: Dict):
        """发送通知"""
        # 简洁的一行通知
        print(f"\n🔔 [{datetime.now().strftime('%H:%M:%S')}] {signal['direction']}信号! 价格:{signal['current_price']:.2f} 突破:{signal['breakout_type']}")
        
        # Windows系统声音提醒(播放3次)
        try:
            for _ in range(3):
                winsound.Beep(1000, 300)
                time.sleep(0.2)
        except:
            pass
    
    def update_15m_kline(self):
        """更新15分钟K线数据"""
        klines_15m = self.api.get_latest_klines(symbol="BTCUSDT", interval="15m", limit=2)
        if len(klines_15m) < 2:
            return False
        
        # 倒数第二根是已完成的K线
        prev_kline_data = klines_15m[-2]
        prev_kline = SimpleKLine(prev_kline_data)
        
        # 如果是新的15分钟K线周期
        if self.last_15m_kline is None or prev_kline.timestamp != self.last_15m_kline.timestamp:
            # 检查是否符合涨跌幅要求
            if self.check_k1_qualification(prev_kline):
                self.last_15m_kline = prev_kline
                current_kline_data = klines_15m[-1]
                self.current_15m_start_time = current_kline_data[0]
                
                # 新周期开始，清空已通知信号
                self.alerted_signals.clear()
                
                print(f"\n✓ [{datetime.now().strftime('%H:%M:%S')}] 15分钟K线符合条件! 涨跌幅:{prev_kline.get_body_range()*100:.3f}% 开始监听1分钟K线")
                
                return True
            else:
                # 不符合条件，清除监听
                if self.last_15m_kline is not None:
                    print(f"\n✗ [{datetime.now().strftime('%H:%M:%S')}] 15分钟K线涨跌幅不足，停止监听")
                self.last_15m_kline = None
                self.current_15m_start_time = 0
                self.alerted_signals.clear()
        
        return False
    
    def check_1m_klines(self):
        """检查1分钟K线"""
        if self.last_15m_kline is None:
            return
        
        # 获取最新的1分钟K线
        klines_1m = self.api.get_latest_klines(symbol="BTCUSDT", interval="1m", limit=1)
        if not klines_1m:
            return
        
        k1m = SimpleKLine(klines_1m[0])
        
        # 打印每分钟K线
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 1分钟K线: O:{k1m.open:.2f} H:{k1m.high:.2f} L:{k1m.low:.2f} C:{k1m.close:.2f}", end='\r')
        
        # 检查是否还在当前15分钟周期内
        if k1m.timestamp < self.current_15m_start_time:
            return
        
        # 检查是否满足信号条件
        signal = self.check_signal(self.last_15m_kline, k1m)
        
        if signal:
            # 生成唯一标识，避免重复通知同一根1分钟K线
            signal_key = f"{signal['type']}_{k1m.timestamp}"
            
            if signal_key not in self.alerted_signals:
                self.send_notification(signal)
                self.alerted_signals.add(signal_key)
    
    def run(self, check_interval: int = 10):
        """
        运行监听器
        
        参数:
            check_interval: 检查间隔(秒)
        """
        print("="*80)
        print(f"实时监听器启动 | 交易对:BTCUSDT | K1涨跌幅>={self.min_k1_range*100:.2f}% | 间隔:{check_interval}秒")
        print("="*80)
        
        last_15m_check = 0
        
        try:
            while True:
                current_time = time.time()
                
                # 每分钟检查一次15分钟K线(或首次运行)
                if current_time - last_15m_check >= 60 or last_15m_check == 0:
                    self.update_15m_kline()
                    last_15m_check = current_time
                
                # 如果正在监听，检查1分钟K线
                if self.last_15m_kline is not None:
                    self.check_1m_klines()
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] 等待符合条件的15分钟K线...", end='\r')
                
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            print("\n\n监听器已停止")
            print("="*80)


def main():
    """主函数"""
    # 设置参数
    min_k1_range_percent = 0.21  # 15分钟K线最小涨跌幅要求(%)
    check_interval = 10  # 检查间隔(秒)，可以设置为5-15秒
    
    # 创建并运行监听器
    monitor = LiveMonitor(min_k1_range_percent=min_k1_range_percent)
    monitor.run(check_interval=check_interval)


if __name__ == '__main__':
    main()
