from 下单模块 import BinanceTrader

# 替换为您的API密钥
API_KEY = "Xq2X0xMjmsbArOBmYIxgL0IOQvJZuMK7ec29w3HTogwA737i18cwmUkH81QzjDYu"
API_SECRET = "sfGu8nnBwdO6xCODFOCmkymwCWkfXCWBUsmADnPLEQcbqD47MO6qBEcljrOfrFxA"

# 初始化交易对象
trader = BinanceTrader(API_KEY, API_SECRET)

print("=" * 60)
print("币安合约交易演示")
print("=" * 60)

# 1. 获取账户余额
print("\n【1. 查询账户余额】")
balance = trader.get_balance()
print(f"账户USDT余额: {balance}")

# 2. 设置交易参数
SYMBOL = "ETHUSDT"      # 交易对
QUANTITY = 0.006         # 用0.001 ETH开仓
LEVERAGE = 30           # 杠杆倍数
MARGIN_TYPE = "ISOLATED"  # 逐仓模式
EXTRA_MARGIN = 0.006     # 追加保证金

print(f"\n【2. 交易参数】")
print(f"交易对: {SYMBOL}")
print(f"金额: {QUANTITY} ETH")
print(f"杠杆: {LEVERAGE}x")
print(f"模式: {MARGIN_TYPE} (逐仓)")

# 3. 做多
print(f"\n【3. 做多开仓】")
try:
    result_long = trader.buy(
        symbol=SYMBOL,
        quantity=QUANTITY,
        leverage=LEVERAGE,
        extra_margin=EXTRA_MARGIN,
        margin_type=MARGIN_TYPE,
        side="BUY",
        position_side="LONG"
    )
    print("✓ 做多成功！")
    print(f"订单ID: {result_long.get('orderId')}")
    print(f"成交价格: {result_long.get('avgPrice', 'N/A')}")
    print(f"成交数量: {result_long.get('executedQty')}")
    print(f"订单状态: {result_long.get('status')}")
except Exception as e:
    print(f"✗ 做多失败: {e}")

# 4. 做空
# print(f"\n【4. 做空开仓】")
# try:
#     result_short = trader.buy(
#         symbol=SYMBOL,
#         usdt_amount=USDT_AMOUNT,
#         leverage=LEVERAGE,
#         extra_margin=EXTRA_MARGIN,
#         margin_type=MARGIN_TYPE,
#         side="SELL",
#         position_side="SHORT"
#     )
#     print("✓ 做空成功！")
#     print(f"订单ID: {result_short.get('orderId')}")
#     print(f"成交价格: {result_short.get('avgPrice', 'N/A')}")
#     print(f"成交数量: {result_short.get('executedQty')}")
#     print(f"订单状态: {result_short.get('status')}")
# except Exception as e:
#     print(f"✗ 做空失败: {e}")

print("\n" + "=" * 60)
print("演示完成")
print("=" * 60)
