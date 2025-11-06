"""
实时K线监听器 - 币安ETH包含关系策略
作者: 
日期: 2025-11-06

监听规则（包含关系策略）:
1. 监听15分钟K线和1分钟K线
2. 当第一根15分钟K线的开收盘涨跌幅 >= 0.21% 时（K1）
3. 当第二根15分钟K线的最高点和最低点都在K1的范围内时（包含关系）
4. 监听第三根15分钟K线（当前K线的1分钟K线）:
   - 1分钟K线的最高价突破了K1的最高价，但收盘价回到区间内（做空信号）
   - 1分钟K线的最低价突破了K1的最低价，但收盘价回到区间内（做多信号）
5. 在15分钟周期的最后三根1分钟K线中，任意一根在区间内则发送微信通知

微信通知配置:
1. 使用Server酱服务: https://sct.ftqq.com/
2. 注册账号后获取SendKey
3. 在main()函数中填入你的SENDKEY
"""

import urllib.request
import urllib.error
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
import winsound  # Windows系统通知音
import ctypes  # Windows消息框
import threading  # 多线程播放声音


class BinanceLiveAPI:
    """币安实时API接口，带多端点与重试"""
    BASE_URLS = [
        "https://api.binance.com",
        "https://api1.binance.com",
        "https://api2.binance.com",
        "https://api3.binance.com",
    ]
    
    @staticmethod
    def get_latest_klines(symbol: str = "ETHUSDT", interval: str = "1m", limit: int = 2, max_retries: int = 3) -> List[List]:
        """
        获取最新的K线数据（带重试机制）
        
        参数:
            symbol: 交易对
            interval: K线周期
            limit: 返回数量
            max_retries: 最大重试次数
        """
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Python-urllib/monitor"}
        
        for attempt in range(max_retries):
            base = BinanceLiveAPI.BASE_URLS[attempt % len(BinanceLiveAPI.BASE_URLS)]
            url = f"{base}/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
            try:
                req = urllib.request.Request(url, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    return data
            except urllib.error.URLError as e:
                # 网络连接错误
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 递增等待时间: 2秒, 4秒, 6秒
                    print(f"\n⚠️ 网络请求失败(尝试{attempt+1}/{max_retries}): {e}")
                    print(f"   等待{wait_time}秒后重试...")
                    time.sleep(wait_time)
                else:
                    print(f"\n✗ 获取K线数据失败，已重试{max_retries}次: {e}")
                    return []
            except urllib.error.HTTPError as e:
                # HTTP状态码错误
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"\n⚠️ HTTP错误(尝试{attempt+1}/{max_retries}): {e.code} {e.reason}")
                    print(f"   等待{wait_time}秒后重试...")
                    time.sleep(wait_time)
                else:
                    print(f"\n✗ 获取K线数据失败(HTTP {e.code})，已重试{max_retries}次")
                    return []
            except json.JSONDecodeError as e:
                print(f"\n✗ 解析JSON失败: {e}")
                return []
            except Exception as e:
                print(f"\n✗ 未知错误: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    return []
        
        return []
    
    @staticmethod
    def get_server_time(max_retries: int = 3) -> int:
        """
        获取服务器时间（带重试机制）
        
        参数:
            max_retries: 最大重试次数
        """
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Python-urllib/monitor"}
        
        for attempt in range(max_retries):
            base = BinanceLiveAPI.BASE_URLS[attempt % len(BinanceLiveAPI.BASE_URLS)]
            url = f"{base}/api/v3/time"
            try:
                req = urllib.request.Request(url, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    return data['serverTime']
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"\n⚠️ 获取服务器时间失败(尝试{attempt+1}/{max_retries}): {e}")
                    print(f"   等待{wait_time}秒后重试...")
                    time.sleep(wait_time)
                else:
                    print(f"\n✗ 获取服务器时间失败，使用本地时间")
                    return int(time.time() * 1000)
        
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
    
    def is_contained_by(self, other):
        """检查自己是否被另一根K线包含"""
        return self.high <= other.high and self.low >= other.low
    
    def __repr__(self):
        dt = datetime.fromtimestamp(self.timestamp / 1000)
        return f"K[{dt.strftime('%H:%M')}, O:{self.open:.2f}, H:{self.high:.2f}, L:{self.low:.2f}, C:{self.close:.2f}]"


class LiveMonitorContain:
    """实时监听器 - 包含关系策略"""
    
    def __init__(self, min_k1_range_percent: float = 0.21, serverchan_sendkey: str = None):
        self.min_k1_range = min_k1_range_percent / 100  # 转换为小数
        self.k1_15m = None  # 第一根15分钟K线（符合涨跌幅条件）
        self.k2_15m = None  # 第二根15分钟K线（被K1包含）
        self.current_15m_start_time = 0  # 当前15分钟K线（第三根）的开始时间
        self.alerted_signals = set()  # 已通知的信号(避免重复通知)
        self.api = BinanceLiveAPI()
        
        # 状态：waiting_k1 -> waiting_k2 -> monitoring_k3
        self.state = "waiting_k1"
        
        # 突破状态记录（针对第三根K线）
        self.breakout_high = False  # 是否已突破最高点
        self.breakout_low = False   # 是否已突破最低点
        self.breakout_high_price = 0.0  # 突破最高点的价格
        self.breakout_low_price = 0.0   # 突破最低点的价格
        
        # 信号记录(用于延迟弹窗通知)
        self.pending_signal = None  # 待通知的信号
        self.popup_notified = False  # 本周期是否已弹窗通知
        
        # 微信通知配置
        self.serverchan_sendkey = serverchan_sendkey
        
    def check_k1_qualification(self, k1: SimpleKLine) -> bool:
        """检查K1是否符合涨跌幅要求"""
        body_range = k1.get_body_range()
        return body_range >= self.min_k1_range
    
    def check_signal(self, k1_15m: SimpleKLine, k1_1m: SimpleKLine) -> Optional[Dict]:
        """
        检查1分钟K线是否满足信号条件（相对于K1）
        
        逻辑:
        1. 检测1分钟K线是否突破K1的最高/最低点
        2. 后续1分钟K线收盘价回到K1区间内时,触发信号
        3. 如果同时突破最高点和最低点(吞噬),返回'engulfed'
        
        参数:
            k1_15m: 第一根15分钟K线（参考K线）
            k1_1m: 当前1分钟K线
        
        返回:
            如果满足条件返回信号字典,否则返回None
        """
        # 检测是否突破最高点
        if k1_1m.high > k1_15m.high:
            if not self.breakout_high:
                self.breakout_high = True
                self.breakout_high_price = k1_1m.high
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ⬆️ 检测到向上突破! 突破价:{k1_1m.high:.2f} > K1最高:{k1_15m.high:.2f}")
                print(f"    等待收盘价回到区间内 [{k1_15m.low:.2f} - {k1_15m.high:.2f}] 以触发做空信号...")
        
        # 检测是否突破最低点
        if k1_1m.low < k1_15m.low:
            if not self.breakout_low:
                self.breakout_low = True
                self.breakout_low_price = k1_1m.low
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ⬇️ 检测到向下突破! 突破价:{k1_1m.low:.2f} < K1最低:{k1_15m.low:.2f}")
                print(f"    等待收盘价回到区间内 [{k1_15m.low:.2f} - {k1_15m.high:.2f}] 以触发做多信号...")
        
        # 检测吞噬形态: 同时突破最高点和最低点
        if self.breakout_high and self.breakout_low:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 检测到吞噬形态! 1分钟K线同时突破K1上下边界")
            print(f"    最高突破: {self.breakout_high_price:.2f} > {k1_15m.high:.2f}")
            print(f"    最低突破: {self.breakout_low_price:.2f} < {k1_15m.low:.2f}")
            print(f"    策略失效，重新寻找符合条件的K1...")
            return {'type': 'engulfed'}
        
        # 检查收盘价是否回到区间内
        close_in_range = k1_15m.low <= k1_1m.close <= k1_15m.high
        
        if not close_in_range:
            return None
        
        # 如果之前向上突破过,现在收盘价回到区间 -> 做空信号
        if self.breakout_high:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ✅ 收盘价已回到K1区间内! 当前价:{k1_1m.close:.2f} 在 [{k1_15m.low:.2f} - {k1_15m.high:.2f}]")
            return {
                'type': 'short',
                'direction': '做空',
                'k1_15m': k1_15m,
                'k2_15m': self.k2_15m,
                'k1m': k1_1m,
                'breakout_type': '向上突破K1后回落',
                'breakout_price': self.breakout_high_price,
                'reference_price': k1_15m.high,
                'current_price': k1_1m.close,
                'timestamp': k1_1m.timestamp,
                'strategy': 'contain'  # 标记为包含关系策略
            }
        
        # 如果之前向下突破过,现在收盘价回到区间 -> 做多信号
        if self.breakout_low:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ✅ 收盘价已回到K1区间内! 当前价:{k1_1m.close:.2f} 在 [{k1_15m.low:.2f} - {k1_15m.high:.2f}]")
            return {
                'type': 'long',
                'direction': '做多',
                'k1_15m': k1_15m,
                'k2_15m': self.k2_15m,
                'k1m': k1_1m,
                'breakout_type': '向下突破K1后回升',
                'breakout_price': self.breakout_low_price,
                'reference_price': k1_15m.low,
                'current_price': k1_1m.close,
                'timestamp': k1_1m.timestamp,
                'strategy': 'contain'  # 标记为包含关系策略
            }
        
        return None
    
    def send_wechat_notification(self, signal: Dict):
        """
        发送微信通知 (通过Server酱)
        
        参数:
            signal: 信号字典
        """
        if not self.serverchan_sendkey:
            print("未配置Server酱SendKey，跳过微信通知")
            return False
        
        try:
            direction = signal['direction']
            current_price = signal['current_price']
            reference_price = signal['reference_price']
            breakout_type = signal['breakout_type']
            signal_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 构建通知标题和内容 - 特殊标记包含关系策略
            title = f"📊 ETH包含策略信号 - {direction}"
            
            # 使用Markdown格式构建内容
            content = f"""
## 交易信号提醒 (包含关系策略)

**策略类型:** 包含关系 - 三K线形态  
**方向:** {direction}  
**当前价格:** {current_price:.2f} USDT  
**参考价格(K1):** {reference_price:.2f} USDT  
**突破类型:** {breakout_type}  

---

**K1区间:** [{signal['k1_15m'].low:.2f} - {signal['k1_15m'].high:.2f}]  
**K2区间:** [{signal['k2_15m'].low:.2f} - {signal['k2_15m'].high:.2f}] (被K1包含)  

---

**时间:** {signal_time}  
**策略:** ETH 15分钟包含关系策略  

> 💡 15分钟周期即将结束，建议立即查看行情！
"""
            
            # Server酱API地址
            url = f"https://sctapi.ftqq.com/{self.serverchan_sendkey}.send"
            
            # 构建POST数据
            data = {
                'title': title,
                'desp': content
            }
            
            # URL编码
            import urllib.parse
            post_data = urllib.parse.urlencode(data).encode('utf-8')
            
            # 发送请求
            req = urllib.request.Request(url, data=post_data, method='POST')
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                
                if result.get('code') == 0:
                    print(f"✓ 微信通知发送成功!")
                    return True
                else:
                    print(f"✗ 微信通知发送失败: {result.get('message', '未知错误')}")
                    return False
                    
        except Exception as e:
            print(f"✗ 微信通知发送异常: {e}")
            return False
    
    def send_notification(self, signal: Dict, show_popup: bool = False):
        """
        发送通知
        
        参数:
            signal: 信号字典
            show_popup: 是否显示弹窗(仅在15分钟周期快结束时显示)
        """
        # 格式化通知信息
        signal_time = datetime.now().strftime('%H:%M:%S')
        direction = signal['direction']
        current_price = signal['current_price']
        breakout_type = signal['breakout_type']
        reference_price = signal['reference_price']
        
        # 控制台通知
        print(f"\n{'='*80}")
        print(f"📊📊📊 包含关系策略信号触发! 📊📊📊")
        print(f"{'='*80}")
        print(f"时间: {signal_time}")
        print(f"方向: {direction}")
        print(f"当前价格: {current_price:.2f}")
        print(f"参考价格(K1): {reference_price:.2f}")
        print(f"突破类型: {breakout_type}")
        print(f"{'='*80}\n")
        
        # 只在需要弹窗时才执行以下操作
        if not show_popup:
            print("(信号已记录，将在15分钟周期倒数第二根1分钟K线时通知)")
            return
        
        # 发送微信通知
        print("\n正在发送微信通知...")
        self.send_wechat_notification(signal)
        
        # 1. 播放急促的警报声(在后台线程中播放,避免阻塞)
        def play_alert_sound():
            try:
                for i in range(5):
                    # 高低交替的警报声
                    winsound.Beep(1500, 200)  # 高音
                    winsound.Beep(1000, 200)  # 低音
            except:
                pass
        
        sound_thread = threading.Thread(target=play_alert_sound, daemon=True)
        sound_thread.start()
        
        # 2. Windows系统弹窗(最强提示!)
        try:
            # 构建弹窗消息
            message = (
                f"📊 包含策略信号提醒!\n\n"
                f"方向: {direction}\n"
                f"当前价格: {current_price:.2f}\n"
                f"参考价格(K1): {reference_price:.2f}\n"
                f"突破类型: {breakout_type}\n\n"
                f"15分钟周期即将结束，请查看行情!"
            )
            title = f"⚠️ {direction}信号 - ETH包含策略"
            
            # MB_ICONWARNING (0x30) = 警告图标
            # MB_TOPMOST (0x40000) = 窗口置顶
            MessageBox = ctypes.windll.user32.MessageBoxW
            
            # 在后台线程中显示弹窗,避免阻塞主循环
            def show_messagebox():
                MessageBox(None, message, title, 0x30 | 0x40000)
            
            mb_thread = threading.Thread(target=show_messagebox, daemon=True)
            mb_thread.start()
            
        except Exception as e:
            print(f"弹窗通知失败: {e}")
        
        # 3. 闪烁控制台标题
        try:
            for i in range(10):
                if i % 2 == 0:
                    ctypes.windll.kernel32.SetConsoleTitleW(f"📊📊📊 {direction}信号! 📊📊📊")
                else:
                    ctypes.windll.kernel32.SetConsoleTitleW(f"包含策略监听器 - ETH")
                time.sleep(0.3)
            # 恢复原标题
            ctypes.windll.kernel32.SetConsoleTitleW("包含策略监听器 - ETH 15分钟")
        except:
            pass
    
    def update_15m_klines(self):
        """更新15分钟K线数据并检查包含关系"""
        klines_15m = self.api.get_latest_klines(symbol="ETHUSDT", interval="15m", limit=3)
        if len(klines_15m) < 3:
            if len(klines_15m) == 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 获取15分钟K线失败，跳过本次检查", end='\r')
            return False
        
        # 解析K线
        k_minus2 = SimpleKLine(klines_15m[-3])  # 倒数第三根（已完成）
        k_minus1 = SimpleKLine(klines_15m[-2])  # 倒数第二根（已完成）
        k_current = SimpleKLine(klines_15m[-1])  # 当前K线（未完成）
        
        # 状态机逻辑
        if self.state == "waiting_k1":
            # 等待K1：倒数第三根符合涨跌幅条件
            if self.check_k1_qualification(k_minus2):
                self.k1_15m = k_minus2
                self.state = "waiting_k2"
                print(f"\n✓ [{datetime.now().strftime('%H:%M:%S')}] 找到K1! 涨跌幅:{k_minus2.get_body_range()*100:.3f}%")
                print(f"   K1区间: [{k_minus2.low:.2f} - {k_minus2.high:.2f}]")
                print(f"   等待K2（检查包含关系）...")
                
        elif self.state == "waiting_k2":
            # 检查K2是否被K1包含
            # 如果K1的timestamp发生了变化，说明进入了新周期，需要重新检查
            if k_minus2.timestamp != self.k1_15m.timestamp:
                # K1已经不是倒数第三根了，重置状态
                print(f"\n✗ [{datetime.now().strftime('%H:%M:%S')}] K1已过期，重新寻找...")
                self.state = "waiting_k1"
                self.k1_15m = None
                self.k2_15m = None
                return False
            
            # 检查倒数第二根（k_minus1）是否被K1包含
            if k_minus1.is_contained_by(self.k1_15m):
                self.k2_15m = k_minus1
                self.current_15m_start_time = k_current.timestamp
                self.state = "monitoring_k3"
                
                # 清空突破状态
                self.alerted_signals.clear()
                self.breakout_high = False
                self.breakout_low = False
                self.breakout_high_price = 0.0
                self.breakout_low_price = 0.0
                self.pending_signal = None
                self.popup_notified = False
                
                print(f"\n✓ [{datetime.now().strftime('%H:%M:%S')}] 找到包含关系!")
                print(f"   K1区间: [{self.k1_15m.low:.2f} - {self.k1_15m.high:.2f}]")
                print(f"   K2区间: [{k_minus1.low:.2f} - {k_minus1.high:.2f}] (被K1包含)")
                print(f"   开始监听K3的1分钟K线...")
                return True
            else:
                # K2没有被K1包含，重新寻找K1
                print(f"\n✗ [{datetime.now().strftime('%H:%M:%S')}] K2不满足包含关系，重新寻找K1...")
                print(f"   K1区间: [{self.k1_15m.low:.2f} - {self.k1_15m.high:.2f}]")
                print(f"   K2区间: [{k_minus1.low:.2f} - {k_minus1.high:.2f}] (超出K1范围)")
                self.state = "waiting_k1"
                self.k1_15m = None
                self.k2_15m = None
                
        elif self.state == "monitoring_k3":
            # 监听K3中，检查K3是否还是当前K线
            if k_current.timestamp != self.current_15m_start_time:
                # K3已经结束，重新开始
                print(f"\n✗ [{datetime.now().strftime('%H:%M:%S')}] K3周期已结束，重新寻找K1...")
                self.state = "waiting_k1"
                self.k1_15m = None
                self.k2_15m = None
                self.current_15m_start_time = 0
                self.alerted_signals.clear()
                self.breakout_high = False
                self.breakout_low = False
                self.breakout_high_price = 0.0
                self.breakout_low_price = 0.0
                self.pending_signal = None
                self.popup_notified = False
        
        return False
    
    def check_1m_klines(self):
        """检查1分钟K线（仅在monitoring_k3状态下）"""
        if self.state != "monitoring_k3" or self.k1_15m is None:
            return

        # 获取最新的1分钟K线
        klines_1m = self.api.get_latest_klines(symbol="ETHUSDT", interval="1m", limit=1)
        if not klines_1m:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 获取1分钟K线失败，跳过本次检查", end='\r')
            return

        k1m = SimpleKLine(klines_1m[0])

        # 计算当前1分钟K线在15分钟周期中的位置
        time_since_15m_start = (k1m.timestamp - self.current_15m_start_time) / 60000  # 转换为分钟
        minutes_in_period = int(time_since_15m_start)

        # 检查是否还在当前15分钟周期内
        if k1m.timestamp < self.current_15m_start_time or minutes_in_period >= 15:
            if minutes_in_period >= 15:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] K3周期已结束，等待下一个K1...")
                self.state = "waiting_k1"
                self.k1_15m = None
                self.k2_15m = None
                self.current_15m_start_time = 0
            return

        # 打印每分钟K线
        status = ""
        if self.breakout_high:
            status = " [已突破K1上方]"
        elif self.breakout_low:
            status = " [已突破K1下方]"

        if self.pending_signal and not self.popup_notified:
            status += f" [有信号-等待第13分钟弹窗]"

        print(f"[{datetime.now().strftime('%H:%M:%S')}] K3-1分钟({minutes_in_period+1}/15): O:{k1m.open:.2f} H:{k1m.high:.2f} L:{k1m.low:.2f} C:{k1m.close:.2f}{status}", end='\r')

        # 检查是否满足信号条件（相对于K1）
        signal = self.check_signal(self.k1_15m, k1m)

        if signal:
            # 检测到吞噬形态,策略失效
            if signal.get('type') == 'engulfed':
                print(f"\n{'='*80}")
                print(f"⚠️ 吞噬形态导致策略失效,重新寻找K1")
                print(f"{'='*80}\n")
                self.state = "waiting_k1"
                self.k1_15m = None
                self.k2_15m = None
                self.current_15m_start_time = 0
                self.alerted_signals.clear()
                self.breakout_high = False
                self.breakout_low = False
                self.breakout_high_price = 0.0
                self.breakout_low_price = 0.0
                self.pending_signal = None
                self.popup_notified = False
                return
            
            # 生成唯一标识
            signal_key = f"{signal['type']}_{k1m.timestamp}"

            if signal_key not in self.alerted_signals:
                print(f"\n>>> 检测到包含策略信号! 类型:{signal['type']} 价格:{signal['current_price']:.2f}")
                self.send_notification(signal, show_popup=False)
                self.alerted_signals.add(signal_key)
                if self.pending_signal is None:
                    self.pending_signal = signal

        # 检查是否到了倒数第二根1分钟K线
        if minutes_in_period == 12 and self.pending_signal and not self.popup_notified:
            klines_1m_last3 = self.api.get_latest_klines(symbol="ETHUSDT", interval="1m", limit=3)
            if len(klines_1m_last3) == 3:
                any_in_range = False
                in_range_count = 0
                
                print(f"\n\n{'='*80}")
                print(f"📊 检查后三根1分钟K线 (K1区间: [{self.k1_15m.low:.2f} - {self.k1_15m.high:.2f}])")
                print(f"{'-'*80}")
                
                for i, kline_data in enumerate(klines_1m_last3, 1):
                    k = SimpleKLine(kline_data)
                    is_in_range = self.k1_15m.low <= k.close <= self.k1_15m.high
                    status = "✓ 在K1区间内" if is_in_range else "✗ 不在K1区间内"
                    time_str = datetime.fromtimestamp(k.timestamp/1000).strftime('%H:%M')
                    print(f"  第{i}根 [{time_str}]: 收盘价 {k.close:.2f} {status}")
                    
                    if is_in_range:
                        any_in_range = True
                        in_range_count += 1
                
                print(f"{'-'*80}")
                print(f"统计: {in_range_count}/3 根K线在K1区间内")
                print(f"{'='*80}")
                
                if any_in_range:
                    print(f"✅ 发送微信通知! (有{in_range_count}根K线在K1区间内)")
                    print(f"{'='*80}\n")
                    self.send_notification(self.pending_signal, show_popup=True)
                    self.popup_notified = True
                else:
                    print(f"❌ 不发送微信通知 (后三根K线均不在K1区间内)")
                    print(f"{'='*80}\n")
            else:
                print(f"\n\n{'='*80}")
                print(f"⚠️ 获取后三根1分钟K线失败(网络问题)，不发送微信通知!")
                print(f"{'='*80}\n")
    
    def run(self, check_interval: int = 10):
        """
        运行监听器
        
        参数:
            check_interval: 检查间隔(秒)
        """
        print("="*80)
        print(f"包含关系策略监听器启动 | 交易对:ETHUSDT | K1涨跌幅>={self.min_k1_range*100:.2f}% | 间隔:{check_interval}秒")
        print("="*80)
        print("策略说明:")
        print("  1. 寻找K1（涨跌幅>=0.21%）")
        print("  2. 检查K2是否被K1包含")
        print("  3. 监听K3突破K1的最高/最低价并回到区间")
        print("="*80)
        
        last_15m_check = 0
        
        try:
            while True:
                current_time = time.time()
                
                # 每分钟检查一次15分钟K线
                if current_time - last_15m_check >= 60 or last_15m_check == 0:
                    self.update_15m_klines()
                    last_15m_check = current_time
                
                # 如果正在监听K3，检查1分钟K线
                if self.state == "monitoring_k3":
                    self.check_1m_klines()
                else:
                    status_msg = {
                        "waiting_k1": "等待符合条件的K1（涨跌幅>=0.21%）...",
                        "waiting_k2": "等待K2（检查包含关系）..."
                    }
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {status_msg.get(self.state, '未知状态')}", end='\r')
                
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            print("\n\n监听器已停止")
            print("="*80)


def test_wechat_notification(sendkey: str):
    """测试微信通知功能"""
    print("="*80)
    print("微信通知测试 - ETH包含策略")
    print("="*80)
    
    if not sendkey:
        print("✗ 错误: 未提供SendKey")
        return False
    
    print(f"SendKey: {sendkey[:10]}...")
    print("\n正在发送测试通知到微信...")
    
    try:
        title = "🧪 ETH包含策略测试通知"
        content = f"""
## 测试通知

这是一条来自 **ETH包含关系策略监听器** 的测试通知。

---

**发送时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**状态:** ✅ 微信通知功能正常  

> 💡 如果你收到这条消息，说明微信通知配置成功！

---

### 策略说明:
- 监听三根15分钟K线的包含关系
- K2被K1包含，K3突破K1
"""
        
        url = f"https://sctapi.ftqq.com/{sendkey}.send"
        data = {'title': title, 'desp': content}
        
        import urllib.parse
        post_data = urllib.parse.urlencode(data).encode('utf-8')
        
        req = urllib.request.Request(url, data=post_data, method='POST')
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            
            if result.get('code') == 0:
                print("\n✅ 测试成功! 请检查你的微信是否收到通知")
                return True
            else:
                print(f"\n✗ 测试失败: {result.get('message', '未知错误')}")
                return False
                
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        return False


def main():
    """主函数"""
    # ========== 配置参数 ==========
    SERVERCHAN_SENDKEY = 'SCT301567TtEeQSvoSSyo0240Rbe4OUkSO'
    min_k1_range_percent = 0.21  # 15分钟K线最小涨跌幅要求(%)
    check_interval = 30  # 检查间隔(秒)
    # ==============================
    
    if SERVERCHAN_SENDKEY:
        print("✓ 已配置微信通知 (Server酱)")
        print("\n是否先测试微信通知功能? (y/n): ", end='')
        try:
            choice = input().strip().lower()
            if choice == 'y':
                test_wechat_notification(SERVERCHAN_SENDKEY)
                print("\n按回车键继续启动监听器...")
                input()
        except:
            pass
    else:
        print("⚠️ 未配置微信通知")
    
    monitor = LiveMonitorContain(
        min_k1_range_percent=min_k1_range_percent,
        serverchan_sendkey=SERVERCHAN_SENDKEY
    )
    monitor.run(check_interval=check_interval)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        SENDKEY = 'SCT301567TtEeQSvoSSyo0240Rbe4OUkSO'
        test_wechat_notification(SENDKEY)
    else:
        main()
