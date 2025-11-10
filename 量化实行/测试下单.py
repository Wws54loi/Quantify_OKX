from 下单模块 import BinanceTrader

# 替换为您的API密钥
API_KEY = "Xq2X0xMjmsbArOBmYIxgL0IOQvJZuMK7ec29w3HTogwA737i18cwmUkH81QzjDYu"
API_SECRET = "sfGu8nnBwdO6xCODFOCmkymwCWkfXCWBUsmADnPLEQcbqD47MO6qBEcljrOfrFxA"

# 初始化交易对象
trader = BinanceTrader(API_KEY, API_SECRET)

# 获取账户余额
balance = trader.get_balance()
print(f"账户USDT余额: {balance}")
