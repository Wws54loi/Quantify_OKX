import time  # 用于设置时间间隔
from datetime import datetime
import urllib.request, urllib.parse, json
from 顶底分型 import detect_fenxing

# 使用原生 HTTP 调用 Binance 公共接口（无需 ccxt）
API_BASE = "https://api.binance.com"


def fetch_klines_raw(symbol: str, interval: str, limit: int = 500, base: str = API_BASE):
    """Fetch klines from Binance REST API and return list in ccxt-like format

    Returns: [[timestamp, open, high, low, close, volume], ...]
    """
    symbol_norm = symbol.replace('/', '').upper()
    qs = urllib.parse.urlencode({'symbol': symbol_norm, 'interval': interval, 'limit': limit})
    url = f"{base}/api/v3/klines?{qs}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        body = resp.read().decode('utf-8')
    data = json.loads(body)
    out = []
    for item in data:
        out.append([item[0], float(item[1]), float(item[2]), float(item[3]), float(item[4]), float(item[5])])
    return out
class FractalAnalyzer:
    """缠论顶底分型分析器"""
    
    def __init__(self, exchange):
        self.exchange = exchange
    
    
    def get_fractal_signals(self, symbol='BTC/USDT', timeframe='15m', limit=500):
        """获取顶底分型信号（使用原生 Binance 接口获取 K 线）"""

        print(f"🔍 正在分析 {symbol} {timeframe} 顶底分型...")

        try:
            # 获取K线数据（使用公共接口，无需API Key）
            klines = fetch_klines_raw(symbol, timeframe, limit=limit)

            # 调用外部分型函数（如果有），否则 detect_fenxing 应处理列表输入
            try:
                res = detect_fenxing(klines)
                print(f"🔍 分型结果: {res}")
                return res
            except Exception as e:
                print(f"   ⚠ detect_fenxing 调用失败: {e}")
                return None

        except Exception as e:
            print(f"❌ 分型分析失败: {e}")
            return None

def test_fractal_analysis():
    """测试缠论分型分析"""
    
    print("🧠 缠论顶底分型分析系统")
    print("=" * 50)
    # 创建分型分析器（不需要 ccxt exchange，因为使用原生 HTTP 获取 K 线）
    analyzer = FractalAnalyzer(None)
    # 分析BTC 15分钟顶底分型（使用500根K线，约5天数据）
    analyzer.get_fractal_signals('BTC/USDT', '15m', 500)

# 运行测试
if __name__ == "__main__":
    test_fractal_analysis()

