"""最小化示例：ping Binance 公共接口 /api/v3/ping（不依赖外部库）

用法:
    python binance_ping.py
"""

import urllib.request
import sys

PING_URL = "https://api.binance.com/api/v3/ping"


def ping():
    try:
        with urllib.request.urlopen(PING_URL, timeout=10) as resp:
            status = getattr(resp, 'status', None) or resp.getcode()
            body = resp.read().decode('utf-8')
            print(f"HTTP status: {status}")
            print(f"Response body: {body if body else '{}'}")
            return True
    except Exception as e:
        print(f"Ping failed: {e}")
        return False


if __name__ == '__main__':
    ok = ping()
    sys.exit(0 if ok else 1)
