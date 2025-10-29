import time  # 用于设置时间间隔
from datetime import datetime
import urllib.request, urllib.parse, json
from 顶底分型 import detect_fenxing

# 使用原生 HTTP 调用 Binance 公共接口（不依赖 ccxt）
API_BASE = "https://api.binance.com"  # 生产环境
# TESTNET_BASE = "https://testnet.binance.vision"  # 如需测试网可切换


def fetch_klines_raw(symbol: str, interval: str, limit: int = 500, base: str = API_BASE):
    """
    使用 Binance REST API 获取 K 线（公共接口），返回与 ccxt.fetch_ohlcv 格式相似的列表：
    [timestamp, open, high, low, close, volume]
    """
    symbol_norm = symbol.replace('/', '').upper()
    qs = urllib.parse.urlencode({'symbol': symbol_norm, 'interval': interval, 'limit': limit})
    url = f"{base}/api/v3/klines?{qs}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        body = resp.read().decode('utf-8')
    data = json.loads(body)
    # data 每项为 [openTime, open, high, low, close, volume, closeTime, ...]
    out = []
    for item in data:
        out.append([item[0], float(item[1]), float(item[2]), float(item[3]), float(item[4]), float(item[5])])
    return out
class FractalAnalyzer:
    """缠论顶底分型分析器"""
    
    def __init__(self, exchange):
        self.exchange = exchange
    
    
    def get_fractal_signals(self, symbol='BTC/USDT', timeframe='15m', limit=50):
        """获取顶底分型信号"""
        
        print(f"🔍 正在分析 {symbol} {timeframe} 顶底分型...")
        
        try:
            # 获取K线数据
            klines = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            # 此处打印顶分型结果
            # detect_fenxing(klines)
        except Exception as e:
            print(f"❌ 分型分析失败: {e}")
            return None

    def find_kline_by_time(self, klines, time_str):
        """
        在已获取的klines中查找指定时间点（格式 'YYYY-MM-DD HH:MM'）对应的K线并返回高/低等信息。

        Args:
            klines: list, fetch_ohlcv 返回的 K 线列表，每项为 [timestamp, open, high, low, close, volume]
            time_str: str, 要查找的时间，形如 '2025-10-29 10:00'

        Returns:
            dict 或 None: {'timestamp':..., 'open':..., 'high':..., 'low':..., 'close':..., 'volume':..., 'time_str':...}
        """
        target = time_str.strip()
        for k in klines:
            ts = k[0]
            t_fmt = datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d %H:%M')
            if t_fmt == target:
                return {
                    'timestamp': ts,
                    'time_str': t_fmt,
                    'open': k[1],
                    'high': k[2],
                    'low': k[3],
                    'close': k[4],
                    'volume': k[5] if len(k) > 5 else None,
                }
        return None

    def fetch_and_find_kline(self, symbol, timeframe, time_str, limit=500):
        """
        便捷函数：先fetch_ohlcv，然后查找指定时间点的K线（返回高/低等）。

        Args:
            symbol: 交易对，如 'BTC/USDT'
            timeframe: K线周期，如 '15m'
            time_str: 要查找的时间字符串 'YYYY-MM-DD HH:MM'
            limit: fetch_ohlcv 的 limit

        Returns:
            dict 或 None: 与 find_kline_by_time 相同
        """
        try:
            klines = fetch_klines_raw(symbol, timeframe, limit=limit)
        except Exception as e:
            print(f"❌ 无法获取K线数据: {e}")
            return None

        result = self.find_kline_by_time(klines, time_str)
        if result is None:
            print(f"⚠ 未找到时间点 {time_str} 的K线（使用 limit={limit}）")
        return result

def test_fractal_analysis():
    """测试缠论分型分析"""
    
    print("🧠 缠论顶底分型分析系统")
    print("=" * 50)
    # 创建分型分析器（无需 ccxt exchange）
    analyzer = FractalAnalyzer(None)
    # 示例：查找指定时间点的K线
    res = analyzer.fetch_and_find_kline('BTC/USDT', '15m', '2025-10-29 11:15', limit=500)
    if res:
        print(res)
    else:
        print('未找到该时间点的K线')

# 运行测试
if __name__ == "__main__":
    test_fractal_analysis()

