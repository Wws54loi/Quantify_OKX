import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode


class BinanceTrader:
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://fapi.binance.com"
        self.headers = {'X-MBX-APIKEY': self.api_key}
    
    def _sign(self, params: dict) -> str:
        query_string = urlencode(params)
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _request(self, method: str, endpoint: str, params: dict = None, signed: bool = False):
        url = f"{self.base_url}{endpoint}"
        if params is None:
            params = {}
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            # 提高时间容忍度，避免 -1021 时间偏差错误
            params.setdefault('recvWindow', 5000)
            params['signature'] = self._sign(params)

        try:
            if method == 'GET':
                response = requests.get(url, headers=self.headers, params=params, timeout=10)
            elif method == 'POST':
                response = requests.post(url, headers=self.headers, params=params, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            data = response.json()

            # 币安错误通常为 { code: -xxxx, msg: '...' }
            if isinstance(data, dict) and 'code' in data and data.get('code') not in (0, 200):
                raise RuntimeError(f"Binance API error {data.get('code')}: {data.get('msg')}")

            return data
        except requests.RequestException as e:
            raise RuntimeError(f"HTTP request failed: {e}") from e
        except ValueError as e:
            # JSON 解码失败或其他值错误
            raise RuntimeError(f"Invalid response: {e}") from e
    
    def get_balance(self):
        """获取USDT余额"""
        result = self._request('GET', "/fapi/v2/balance", signed=True)
        # 预期返回为列表
        if isinstance(result, list):
            for item in result:
                if isinstance(item, dict) and item.get('asset') == 'USDT':
                    return float(item.get('balance', 0))
            return 0.0
        # 若为字典，可能为错误返回
        raise RuntimeError(f"Unexpected balance response: {result}")
    
    def buy(self, symbol: str = "ETHUSDT", quantity: float = 0.001):
        """市价买入"""
        params = {
            'symbol': symbol,
            'side': 'BUY',
            'type': 'MARKET',
            'quantity': quantity
        }
        return self._request('POST', "/fapi/v1/order", params, signed=True)
