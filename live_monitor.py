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
    def get_latest_klines(symbol: str = "BTCUSDT", interval: str = "1m", limit: int = 2, max_retries: int = 3) -> List[List]:
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
    
    def __repr__(self):
        dt = datetime.fromtimestamp(self.timestamp / 1000)
        return f"K[{dt.strftime('%H:%M')}, O:{self.open:.2f}, H:{self.high:.2f}, L:{self.low:.2f}, C:{self.close:.2f}]"


class LiveMonitor:
    """实时监听器"""
    def __init__(self, min_k1_range_percent: float = 0.21, serverchan_sendkey: str = None):
        # 基本参数
        self.min_k1_range = min_k1_range_percent / 100  # 转换为小数
        self.api = BinanceLiveAPI()

        # 15m状态
        self.last_15m_kline = None  # 上一根完整的15分钟K线
        self.current_15m_start_time = 0  # 当前15分钟K线的开始时间

        # 信号去重/记录
        self.alerted_signals = set()  # 已通知的信号(避免重复通知)

        # 突破状态记录
        self.breakout_high = False  # 是否已突破最高点
        self.breakout_low = False   # 是否已突破最低点
        self.breakout_high_price = 0.0  # 突破最高点的价格
        self.breakout_low_price = 0.0   # 突破最低点的价格

        # 延迟弹窗
        self.pending_signal = None  # 待通知的信号
        self.popup_notified = False  # 本周期是否已弹窗通知

        # 微信通知配置
        self.serverchan_sendkey = serverchan_sendkey

        # 网络状态统计
        self.request_count = 0  # 总请求次数
        self.failed_count = 0   # 失败次数
        self.last_success_time = time.time()  # 上次成功请求时间

        # 15m K线内包形态状态
        self.k1_15m = None  # 第1条15m K线（满足百分比的那条）
        self.k2_15m = None  # 第2条15m K线
        self.k2_is_inside = False  # 第2条是否为内包
        self.monitoring_k3 = False  # 是否正在监听第3条15m
        self.current_k_number = 0  # 当前是第几条15m K线（1=K1, 2=K2, 3=K3）
        
    def check_k1_qualification(self, k1: SimpleKLine) -> bool:
        """检查K1是否符合涨跌幅要求"""
        body_range = k1.get_body_range()
        return body_range >= self.min_k1_range
    
    def check_signal(self, ref_15m: SimpleKLine, current_1m: SimpleKLine) -> Optional[Dict]:
        """
        检查1分钟K线是否满足信号条件
        
        逻辑:
        1. 先检测是否有1分钟K线突破过参考15分钟K线的最高/最低点(记录状态)
        2. 后续1分钟K线收盘价回到区间内时,触发信号
        
        参数:
            ref_15m: 参考的15分钟K线（可能是K1或K2，取决于是否有内包）
            current_1m: 当前1分钟K线
        
        返回:
            如果满足条件返回信号字典,否则返回None
        """
        # 检测是否突破最高点
        if current_1m.high > ref_15m.high:
            if not self.breakout_high:
                self.breakout_high = True
                self.breakout_high_price = current_1m.high
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ⬆️ 检测到向上突破! 突破价:{current_1m.high:.2f} > 参考最高:{ref_15m.high:.2f}")
                print(f"    等待收盘价回到区间内 [{ref_15m.low:.2f} - {ref_15m.high:.2f}] 以触发做空信号...")
        
        # 检测是否突破最低点
        if current_1m.low < ref_15m.low:
            if not self.breakout_low:
                self.breakout_low = True
                self.breakout_low_price = current_1m.low
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ⬇️ 检测到向下突破! 突破价:{current_1m.low:.2f} < 参考最低:{ref_15m.low:.2f}")
                print(f"    等待收盘价回到区间内 [{ref_15m.low:.2f} - {ref_15m.high:.2f}] 以触发做多信号...")
        
        # 检查收盘价是否回到区间内
        close_in_range = ref_15m.low <= current_1m.close <= ref_15m.high
        
        if not close_in_range:
            return None
        
        # 如果之前向上突破过,现在收盘价回到区间 -> 做空信号
        if self.breakout_high:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ✅ 收盘价已回到区间内! 当前价:{current_1m.close:.2f} 在 [{ref_15m.low:.2f} - {ref_15m.high:.2f}]")
            return {
                'type': 'short',
                'direction': '做空',
                'k15m': ref_15m,
                'k1m': current_1m,
                'breakout_type': '向上突破后回落',
                'breakout_price': self.breakout_high_price,
                'reference_price': ref_15m.high,
                'current_price': current_1m.close,
                'timestamp': current_1m.timestamp
            }
        
        # 如果之前向下突破过,现在收盘价回到区间 -> 做多信号
        if self.breakout_low:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ✅ 收盘价已回到区间内! 当前价:{current_1m.close:.2f} 在 [{ref_15m.low:.2f} - {ref_15m.high:.2f}]")
            return {
                'type': 'long',
                'direction': '做多',
                'k15m': ref_15m,
                'k1m': current_1m,
                'breakout_type': '向下突破后回升',
                'breakout_price': self.breakout_low_price,
                'reference_price': ref_15m.low,
                'current_price': current_1m.close,
                'timestamp': current_1m.timestamp
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
            
            # 构建通知标题和内容
            title = f"🚨 BTC交易信号 - {direction}"
            
            # 使用Markdown格式构建内容
            content = f"""
## 交易信号提醒

**方向:** {direction}  
**当前价格:** {current_price:.2f} USDT  
**参考价格:** {reference_price:.2f} USDT  
**突破类型:** {breakout_type}  

---

**时间:** {signal_time}  
**策略:** BTC 15分钟K线策略  

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

    def send_wechat_text(self, title: str, content: str) -> bool:
        """发送自定义文本到微信(通过Server酱)"""
        if not self.serverchan_sendkey:
            return False
        try:
            url = f"https://sctapi.ftqq.com/{self.serverchan_sendkey}.send"
            data = {'title': title, 'desp': content}
            import urllib.parse
            post_data = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=post_data, method='POST')
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                return result.get('code') == 0
        except Exception as e:
            print(f"微信文本通知异常: {e}")
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
        print(f"🚨🚨🚨 交易信号触发! 🚨🚨🚨")
        print(f"{'='*80}")
        print(f"时间: {signal_time}")
        print(f"方向: {direction}")
        print(f"当前价格: {current_price:.2f}")
        print(f"参考价格: {reference_price:.2f}")
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
                f"🚨 交易信号提醒!\n\n"
                f"方向: {direction}\n"
                f"当前价格: {current_price:.2f}\n"
                f"参考价格: {reference_price:.2f}\n"
                f"突破类型: {breakout_type}\n\n"
                f"15分钟周期即将结束，请查看行情!"
            )
            title = f"⚠️ {direction}信号 - BTC 15分钟策略"
            
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
                    ctypes.windll.kernel32.SetConsoleTitleW(f"🚨🚨🚨 {direction}信号! 🚨🚨🚨")
                else:
                    ctypes.windll.kernel32.SetConsoleTitleW(f"实时监听器 - BTC 15分钟策略")
                time.sleep(0.3)
            # 恢复原标题
            ctypes.windll.kernel32.SetConsoleTitleW("实时监听器 - BTC 15分钟策略")
        except:
            pass
    
    def update_15m_kline(self):
        """
        更新15分钟K线数据
        
        逻辑：
        1. 第1条15m K线满足百分比 → 保存为K1，开始监听
        2. 第2条15m K线完成时：
           - 检查是否为内包（K2完全在K1范围内）
           - 如果是内包 → 标记，继续等待K3
           - 如果不是内包 → 用K2与K1比较，在K2期间发信号
        3. 第3条15m K线（仅当K2是内包时）：
           - 用K3与K1比较，在K3期间发信号
        """
        klines_15m = self.api.get_latest_klines(symbol="BTCUSDT", interval="15m", limit=3)
        if len(klines_15m) < 2:
            if len(klines_15m) == 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 获取15分钟K线失败，跳过本次检查", end='\r')
            return False
        
        # 获取最近完成的15m K线（倒数第二根）
        prev_kline = SimpleKLine(klines_15m[-2])
        current_kline_data = klines_15m[-1]
        self.current_15m_start_time = current_kline_data[0]
        
        # === 第1条15m K线：检查百分比，开始监听 ===
        if self.k1_15m is None:
            if self.check_k1_qualification(prev_kline):
                self.k1_15m = prev_kline
                self.current_k_number = 1
                # 标记已进入监听周期（用于触发1m检查）
                self.last_15m_kline = self.k1_15m
                
                # 清空状态
                self.alerted_signals.clear()
                self.breakout_high = False
                self.breakout_low = False
                self.breakout_high_price = 0.0
                self.breakout_low_price = 0.0
                self.pending_signal = None
                self.popup_notified = False
                
                print(f"\n{'='*80}")
                print(f"✓ [{datetime.now().strftime('%H:%M:%S')}] 第1条15m K线符合条件!")
                print(f"  涨跌幅: {prev_kline.get_body_range()*100:.3f}%")
                print(f"  区间: [{prev_kline.low:.2f} - {prev_kline.high:.2f}]")
                print(f"  等待第2条15m K线...")
                print(f"{'='*80}")
                
                return True
            else:
                # 调试信息：打印未满足K1条件的原因
                actual = prev_kline.get_body_range() * 100
                need = self.min_k1_range * 100
                print(f"[{datetime.now().strftime('%H:%M:%S')}] K1未达标: 实际{actual:.3f}% < 阈值{need:.3f}%", end='\r')
                return False
        
        # === 第2条15m K线：检查是否为内包 ===
        elif self.current_k_number == 1 and prev_kline.timestamp != self.k1_15m.timestamp:
            self.k2_15m = prev_kline
            self.current_k_number = 2
            
            # 检查K2是否为内包（K2的高低完全在K1范围内）
            self.k2_is_inside = (self.k2_15m.high <= self.k1_15m.high and 
                                self.k2_15m.low >= self.k1_15m.low)
            
            if self.k2_is_inside:
                # K2是内包 → 继续等待K3，用K3与K1比较
                self.monitoring_k3 = True
                
                # 清空突破状态，准备监听K3
                self.alerted_signals.clear()
                self.breakout_high = False
                self.breakout_low = False
                self.breakout_high_price = 0.0
                self.breakout_low_price = 0.0
                self.pending_signal = None
                self.popup_notified = False
                
                print(f"\n{'='*80}")
                print(f"🔔 [{datetime.now().strftime('%H:%M:%S')}] 第2条15m K线为内包!")
                print(f"  K1区间: [{self.k1_15m.low:.2f} - {self.k1_15m.high:.2f}]")
                print(f"  K2区间: [{self.k2_15m.low:.2f} - {self.k2_15m.high:.2f}]")
                print(f"  将用第3条15m K线与第1条比较")
                print(f"{'='*80}")
                
                # 微信通知内包形态
                ts = datetime.fromtimestamp(self.k2_15m.timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
                content = (
                    f"## 15分钟内包形态\n\n"
                    f"**时间:** {ts}\n\n"
                    f"**K1区间:** [{self.k1_15m.low:.2f} - {self.k1_15m.high:.2f}]\n\n"
                    f"**K2区间:** [{self.k2_15m.low:.2f} - {self.k2_15m.high:.2f}]\n\n"
                    f"> 第2条15m K线完全被第1条包含\n\n"
                    f"> 将等待第3条15m K线，用K3与K1比较"
                )
                self.send_wechat_text("BTC 15m内包形态", content)
                
            else:
                # K2不是内包 → 直接用K2与K1比较，在K2期间发信号
                print(f"\n{'='*80}")
                print(f"✓ [{datetime.now().strftime('%H:%M:%S')}] 第2条15m K线不是内包")
                print(f"  K1区间: [{self.k1_15m.low:.2f} - {self.k1_15m.high:.2f}]")
                print(f"  K2区间: [{self.k2_15m.low:.2f} - {self.k2_15m.high:.2f}]")
                print(f"  开始监听K2期间的1m K线（用K2与K1比较）")
                print(f"{'='*80}")
                
                # 清空突破状态，准备监听K2期间
                self.alerted_signals.clear()
                self.breakout_high = False
                self.breakout_low = False
                self.breakout_high_price = 0.0
                self.breakout_low_price = 0.0
                self.pending_signal = None
                self.popup_notified = False
            
            return True
        
        # === 第3条15m K线：仅当K2是内包时才处理 ===
        elif self.current_k_number == 2 and self.monitoring_k3 and prev_kline.timestamp != self.k2_15m.timestamp:
            k3_15m = prev_kline
            self.current_k_number = 3
            
            print(f"\n{'='*80}")
            print(f"✓ [{datetime.now().strftime('%H:%M:%S')}] 第3条15m K线开始")
            print(f"  K1区间: [{self.k1_15m.low:.2f} - {self.k1_15m.high:.2f}]")
            print(f"  K3区间: [{k3_15m.low:.2f} - {k3_15m.high:.2f}]")
            print(f"  开始监听K3期间的1m K线（用K3与K1比较）")
            print(f"{'='*80}")
            
            # 清空突破状态，准备监听K3期间
            self.alerted_signals.clear()
            self.breakout_high = False
            self.breakout_low = False
            self.breakout_high_price = 0.0
            self.breakout_low_price = 0.0
            self.pending_signal = None
            self.popup_notified = False
            
            return True
        
        # === K3结束后，重置所有状态，等待新的K1 ===
        elif self.current_k_number == 3 and prev_kline.timestamp != self.current_15m_start_time:
            print(f"\n{'='*80}")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 监听周期结束，等待新的K1...")
            print(f"{'='*80}")
            
            # 重置所有状态
            self.k1_15m = None
            self.k2_15m = None
            self.k2_is_inside = False
            self.monitoring_k3 = False
            self.current_k_number = 0
            self.last_15m_kline = None
            
            self.alerted_signals.clear()
            self.breakout_high = False
            self.breakout_low = False
            self.breakout_high_price = 0.0
            self.breakout_low_price = 0.0
            self.pending_signal = None
            self.popup_notified = False
            
            return False
        
        return False
    
    def check_1m_klines(self):
        """
        检查1分钟K线
        
        逻辑：
        - K1期间：不监听（等待K2）
        - K2期间且K2不是内包：监听，用K1作为参考
        - K2期间且K2是内包：不监听（等待K3）
        - K3期间（K2是内包）：监听，用K1作为参考
        - 提醒时机：在监听期间的第13根1m K线时提醒
        """
        # 判断当前应该监听哪个阶段
        if self.current_k_number == 0:
            # 还没有K1，等待中
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 等待符合条件的15分钟K线...", end='\r')
            return
        elif self.current_k_number == 1:
            # K1期间不监听（等待K2）
            print(f"[{datetime.now().strftime('%H:%M:%S')}] K1期间，等待K2完成...", end='\r')
            return
        elif self.current_k_number == 2 and self.k2_is_inside:
            # K2是内包，不监听K2期间（等待K3）
            print(f"[{datetime.now().strftime('%H:%M:%S')}] K2为内包，等待K3完成...", end='\r')
            return
        
        # === 确定参考K线和监听阶段 ===
        if self.current_k_number == 2 and not self.k2_is_inside:
            # K2不是内包 → 监听K2期间，用K1作为参考
            ref_15m = self.k1_15m
            monitoring_stage = "K2"
        elif self.current_k_number == 3:
            # K2是内包，K3 → 监听K3期间，用K1作为参考
            ref_15m = self.k1_15m
            monitoring_stage = "K3"
        else:
            # 其他情况不监听
            return
        
        # 获取最新的1分钟K线
        klines_1m = self.api.get_latest_klines(symbol="BTCUSDT", interval="1m", limit=1)
        if not klines_1m:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ 获取1分钟K线失败，跳过本次检查", end='\r')
            return

        k1m = SimpleKLine(klines_1m[0])


        # 计算当前1分钟K线在15分钟周期中的位置
        # 15分钟 = 15根1分钟K线
        # 倒数第二根 = 第13根 (0-based index: 12)
        time_since_15m_start = (k1m.timestamp - self.current_15m_start_time) / 60000  # 转换为分钟
        minutes_in_period = int(time_since_15m_start)

        # 打印每分钟K线 (包含突破状态和周期位置)
        status = ""
        if self.breakout_high:
            status = " [已突破上方]"
        elif self.breakout_low:
            status = " [已突破下方]"

        if self.pending_signal and not self.popup_notified:
            status += f" [有信号-等待第13分钟弹窗]"

        print(f"[{datetime.now().strftime('%H:%M:%S')}] 1分钟K线({minutes_in_period+1}/15): O:{k1m.open:.2f} H:{k1m.high:.2f} L:{k1m.low:.2f} C:{k1m.close:.2f}{status}", end='\r')

        # 检查是否还在当前15分钟周期内
        if k1m.timestamp < self.current_15m_start_time:
            return

        # 检查是否满足信号条件（使用ref_15m即K1作为参考）
        signal = self.check_signal(ref_15m, k1m)

        if signal:
            # 生成唯一标识，避免重复通知同一根1分钟K线
            signal_key = f"{signal['type']}_{k1m.timestamp}"

            if signal_key not in self.alerted_signals:
                print(f"\n>>> 检测到信号! 类型:{signal['type']} 价格:{signal['current_price']:.2f}")
                # 首次检测到信号，只打印，不弹窗
                self.send_notification(signal, show_popup=False)
                self.alerted_signals.add(signal_key)
                # 保存信号，等待倒数第二根1分钟K线时弹窗
                if self.pending_signal is None:
                    self.pending_signal = signal

        # 检查是否到了倒数第三根1分钟K线 (第13根，即minutes_in_period == 12)
        # 新逻辑：只要倒数后三根1分钟K线中有任意一根的收盘价在K1区间内，就发送微信提醒
        if minutes_in_period == 12 and self.pending_signal and not self.popup_notified:
            # 获取倒数后三根1分钟K线
            klines_1m_last3 = self.api.get_latest_klines(symbol="BTCUSDT", interval="1m", limit=3)
            if len(klines_1m_last3) == 3:
                any_in_range = False
                for kline_data in klines_1m_last3:
                    k = SimpleKLine(kline_data)
                    if ref_15m.low <= k.close <= ref_15m.high:
                        any_in_range = True
                        break
                if any_in_range:
                    print(f"\n\n{'='*80}")
                    print(f"⏰ 15分钟周期倒数第三根K线，且后三根1分钟K线中有至少一根在K1区间内，发送微信通知!")
                    print(f"{'='*80}\n")
                    self.send_notification(self.pending_signal, show_popup=True)
                    self.popup_notified = True
                else:
                    print(f"\n\n{'='*80}")
                    print(f"⏰ 15分钟周期倒数第三根K线，但后三根1分钟K线都不在K1区间内，不发送微信通知!")
                    print(f"{'='*80}\n")
            else:
                print(f"\n\n{'='*80}")
                print(f"⚠️ 15分钟周期倒数第三根K线，获取后三根1分钟K线失败(网络问题)，不发送微信通知!")
                print(f"{'='*80}\n")

    
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


def test_wechat_notification(sendkey: str):
    """
    测试微信通知功能
    
    参数:
        sendkey: Server酱的SendKey
    """
    print("="*80)
    print("微信通知测试")
    print("="*80)
    
    if not sendkey:
        print("✗ 错误: 未提供SendKey")
        print("请在代码中填写你的Server酱SendKey")
        return False
    
    print(f"SendKey: {sendkey[:10]}...")
    print("\n正在发送测试通知到微信...")
    
    try:
        # 构建测试通知
        title = "🧪 BTC监听器测试通知"
        content = f"""
## 测试通知

这是一条来自 **BTC实时监听器** 的测试通知。

---

**发送时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**状态:** ✅ 微信通知功能正常  

> 💡 如果你收到这条消息，说明微信通知配置成功！

---

### 下一步操作:
1. 确认微信收到此消息
2. 运行主程序开始实时监听
3. 当交易信号出现时，你将收到类似的通知
"""
        
        # Server酱API地址
        url = f"https://sctapi.ftqq.com/{sendkey}.send"
        
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
            
            print(f"\nServer酱响应:")
            print(f"  Code: {result.get('code')}")
            print(f"  Message: {result.get('message')}")
            
            if result.get('code') == 0:
                print("\n" + "="*80)
                print("✅ 测试成功! 请检查你的微信是否收到通知")
                print("="*80)
                return True
            else:
                print("\n" + "="*80)
                print(f"✗ 测试失败: {result.get('message', '未知错误')}")
                print("="*80)
                print("\n可能的原因:")
                print("1. SendKey错误或已过期")
                print("2. Server酱服务异常")
                print("3. 今日消息额度已用完(免费版每天5条)")
                return False
                
    except Exception as e:
        print("\n" + "="*80)
        print(f"✗ 测试异常: {e}")
        print("="*80)
        print("\n可能的原因:")
        print("1. 网络连接问题")
        print("2. SendKey格式错误")
        print("3. Server酱服务不可用")
        return False


def main():
    """主函数"""
    # ========== 配置参数 ==========
    
    # Server酱配置 (微信通知)
    # 1. 访问 https://sct.ftqq.com/ 注册账号
    # 2. 获取SendKey并填写在下面
    # 3. 如果不需要微信通知，保持为None
    SERVERCHAN_SENDKEY = 'SCT301567TtEeQSvoSSyo0240Rbe4OUkSO'  # 填写你的SendKey，例如: "SCT123456xxxxx"
    
    # 策略参数
    min_k1_range_percent = 0.21  # 15分钟K线最小涨跌幅要求(%)
    check_interval = 10  # 检查间隔(秒)，可以设置为5-15秒
    # ==============================
    
    # 检查配置
    if SERVERCHAN_SENDKEY:
        print("✓ 已配置微信通知 (Server酌)")
        
        # 询问是否先测试微信通知
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
        print("⚠️ 未配置微信通知，仅使用本地弹窗和声音提醒")
        print("   如需微信通知，请访问 https://sct.ftqq.com/ 获取SendKey")
    
    # 创建并运行监听器
    monitor = LiveMonitor(
        min_k1_range_percent=min_k1_range_percent,
        serverchan_sendkey=SERVERCHAN_SENDKEY
    )
    monitor.run(check_interval=check_interval)


if __name__ == '__main__':
    import sys
    
    # 如果命令行参数是 test，则只运行测试
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        SENDKEY = 'SCT301567TtEeQSvoSSyo0240Rbe4OUkSO'  # 在这里填写你的SendKey
        test_wechat_notification(SENDKEY)
    else:
        main()
