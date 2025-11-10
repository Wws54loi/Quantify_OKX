import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode


class BinanceTrader:

    def get_symbol_info(self, symbol: str):
        """
        获取交易对信息（如最小下单量、步进等）
        """
        data = self._request('GET', f"/fapi/v1/exchangeInfo", signed=False)
        for s in data['symbols']:
            if s['symbol'] == symbol:
                return s
        raise ValueError(f"找不到交易对信息: {symbol}")

    def __init__(self, api_key: str, api_secret: str, use_testnet: bool = False, base_url: str | None = None):
        """
        初始化交易客户端

        参数:
            api_key: API Key
            api_secret: API Secret
            use_testnet: 是否使用期货测试网
            base_url: 自定义Base URL（优先级最高）
        """
        self.api_key = api_key
        self.api_secret = api_secret
        # UM-Perp Futures: 主网与测试网
        default_url = "https://fapi.binance.com" if not use_testnet else "https://testnet.binancefuture.com"
        self.base_url = base_url or default_url
        self.headers = {
            'X-MBX-APIKEY': self.api_key,
        }
        # 与服务器时间的毫秒级偏移（正数表示本地比服务器慢）
        self.time_offset_ms = 0
        # 尝试同步时间（忽略失败，遇到-1021再重试）
        try:
            self.sync_time()
        except Exception:
            pass
    
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
            params['timestamp'] = int(time.time() * 1000) + int(self.time_offset_ms)
            params.setdefault('recvWindow', 5000)
            params['signature'] = self._sign(params)

        try:
            if method == 'GET':
                response = requests.get(url, headers=self.headers, params=params, timeout=10)
            elif method == 'POST':
                # 币安官方推荐：所有参数拼到URL上，body为空
                from urllib.parse import urlencode
                full_url = url + '?' + urlencode(params)
                response = requests.post(full_url, headers=self.headers, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")

            text = response.text
            try:
                data = response.json()
            except ValueError:
                data = None

            if response.status_code >= 400:
                if isinstance(data, dict) and 'code' in data and 'msg' in data:
                    raise RuntimeError(f"HTTP {response.status_code} | Binance error {data['code']}: {data['msg']}")
                raise RuntimeError(f"HTTP {response.status_code} | Body: {text}")

            if isinstance(data, dict) and 'code' in data and data.get('code') not in (0, 200):
                raise RuntimeError(f"Binance API error {data.get('code')}: {data.get('msg')}")

            return data
        except requests.RequestException as e:
            raise RuntimeError(f"HTTP request failed: {e}") from e
        except ValueError as e:
            raise RuntimeError(f"Invalid response: {e}") from e

    def sync_time(self) -> None:
        """与交易所服务器时间同步，计算时间偏移（毫秒）。"""
        url = f"{self.base_url}/fapi/v1/time"
        start = int(time.time() * 1000)
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        server_time = resp.json().get('serverTime')
        end = int(time.time() * 1000)
        # 简单网络往返校正：取中点时间
        local_mid = (start + end) // 2
        self.time_offset_ms = int(server_time - local_mid)
    
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
    
    def set_margin_mode(self, symbol: str, margin_type: str = "ISOLATED"):
        """
        设置保证金模式
        
        参数:
            symbol: 交易对，如 ETHUSDT
            margin_type: ISOLATED(逐仓) 或 CROSSED(全仓)
        """
        params = {
            'symbol': symbol,
            'marginType': margin_type
        }
        return self._request('POST', "/fapi/v1/marginType", params, signed=True)
    
    def set_leverage(self, symbol: str, leverage: int):
        """
        设置杠杆倍数
        
        参数:
            symbol: 交易对
            leverage: 杠杆倍数 (1-125)
        """
        params = {
            'symbol': symbol,
            'leverage': leverage
        }
        return self._request('POST', "/fapi/v1/leverage", params, signed=True)
    
    def get_price(self, symbol: str):
        """
        获取当前市场价格
        
        参数:
            symbol: 交易对
        """
        result = self._request('GET', f"/fapi/v1/ticker/price?symbol={symbol}", signed=False)
        return float(result.get('price', 0))
    
    def add_position_margin(self, symbol: str, amount: float, position_side: str = "BOTH", type_: int = 1):
        """
        追加或减少逐仓保证金
        symbol: 交易对
        amount: 增加/减少的保证金数量（USDT）
        position_side: BOTH(单向持仓), LONG, SHORT
        type_: 1=增加保证金, 2=减少保证金
        """
        params = {
            'symbol': symbol,
            'amount': amount,
            'type': type_,
            'positionSide': position_side
        }
        return self._request('POST', '/fapi/v2/positionMargin', params, signed=True)

    def buy(self, symbol: str = "ETHUSDT", quantity: float = None, usdt_amount: float = None,
            leverage: int = None, margin_type: str = None, extra_margin: float = None,
            side: str = "BUY", position_side: str = "BOTH"):
        """
        市价开仓（支持做多/做空）并可选追加保证金
        参数：
            symbol: 交易对
            quantity: 币数量
            usdt_amount: USDT金额（自动换算数量）
            leverage: 杠杆倍数
            margin_type: ISOLATED/CROSSED
            extra_margin: 追加保证金
            side: "BUY"(做多) 或 "SELL"(做空)
            position_side: "BOTH"(单向), "LONG", "SHORT"
        """
        # 如果提供了USDT金额，自动计算数量
        if usdt_amount is not None:
            price = self.get_price(symbol)
            quantity = usdt_amount / price

        # 获取交易对最小下单量和精度
        symbol_info = self.get_symbol_info(symbol)
        lot_size = None
        step_size = None
        min_qty = None
        qty_precision = 3
        for f in symbol_info['filters']:
            if f['filterType'] == 'LOT_SIZE':
                min_qty = float(f['minQty'])
                step_size = float(f['stepSize'])
                # 计算精度
                qty_precision = 0
                step = f['stepSize']
                if '.' in step:
                    qty_precision = len(step.rstrip('0').split('.')[-1])
                break
        if quantity is not None:
            # 对齐最小下单量和步进，向下取整
            import math
            quantity = math.floor(quantity / step_size) * step_size
            # 保证不小于最小下单量
            if quantity < min_qty:
                quantity = min_qty
            # 格式化为字符串，精度对齐
            quantity = f"{quantity:.{qty_precision}f}"
        
        if quantity is None:
            raise ValueError("必须提供 quantity 或 usdt_amount 其中之一")

        # 校验名义价值（notional）是否满足币安最小要求（20 USDT）
        # 注意：名义价值 = 数量 × 当前价格，和杠杆无关，杠杆只影响保证金，不影响下单最小金额
        notional = float(quantity) * self.get_price(symbol)
        if notional < 20:
            raise ValueError(f"下单名义价值为 {notional:.2f} USDT，低于币安最小要求20 USDT。请增大下单金额或数量。\n（杠杆倍数不影响最小下单金额要求）")
        
    # ...不再强制切换逐仓模式，避免重复设置导致-4046错误
        
        # 先设置保证金模式（如果提供）
        if margin_type:
            try:
                self.set_margin_mode(symbol, margin_type)
            except RuntimeError as e:
                # 如果已经是目标模式，忽略错误
                if "No need to change margin type" not in str(e):
                    raise
        
        # 再设置杠杆（如果提供）
        if leverage:
            self.set_leverage(symbol, leverage)
        
        # 执行买入，下单前打印所有参数，便于排查404问题
        params = {
            'symbol': symbol,
            'side': side,
            'type': 'MARKET',
            'quantity': quantity,
            'positionSide': position_side
        }
        from urllib.parse import urlencode
        print(f"[DEBUG] 下单参数: {params}")
        print(f"[DEBUG] 完整请求URL: {self.base_url}/fapi/v1/order?{urlencode(params)}")
        order_result = self._request('POST', "/fapi/v1/order", params, signed=True)
        # 下单后追加保证金
        if extra_margin is not None and extra_margin > 0:
            self.add_position_margin(symbol, extra_margin, position_side=position_side, type_=1)
        return order_result

    def close_cross_margin_mode(self, symbol: str):
        """
        切换为逐仓模式（关闭联合保证金/全仓模式）
        """
        return self.set_margin_mode(symbol, margin_type="ISOLATED")
