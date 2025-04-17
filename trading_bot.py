import ccxt
import time

# 替换为您的 API 信息 —— 这部分一定要改成您在 OKX 创建 API 后获得的信息
api_key = '你的api_key'       # 修改：填入您自己的 API Key
secret_key = '你的Secret_Key'  # 修改：填入您自己的 Secret Key
passphrase = '你设置的密码短语'  # 修改：填入您设置的 Passphrase

# 初始化 OKX 交易所
exchange = ccxt.okx({
    'apiKey': api_key,
    'secret': secret_key,
    'password': passphrase,
    'enableRateLimit': True,
    }
})

# 交易对配置 —— 如果您想交易其他币种或交易对，请修改此处
symbol = 'BTC/USDT'  # 修改：如果需要，可以改为其他交易对

# 触发自动交易的波动幅度，这里设置为1%（即0.01）
threshold = 0.01  # 修改：如果您想调整波动幅度，可以修改该数值

# 此变量用于记录上一次的基准价格
base_price = None

while True:
    try:
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        
        # 当第一次运行时，将当前价格设为基准价格
        if base_price is None:
            base_price = current_price
            print(f'基准价格设置为: {base_price}')
        
        price_change = (current_price - base_price) / base_price

        # 当价格上涨超过设定的阈值时，执行卖出操作
        if price_change >= threshold:
            print(f'价格上涨超过1%，当前价格: {current_price}，执行卖出操作')
            # 修改：确保添加正确的交易数量，例如您希望卖出的 BTC 数量
            order = exchange.create_market_sell_order(symbol, 0.00001)
            base_price = current_price  # 重置基准价格

        # 当价格下跌超过设定的阈值时，执行买入操作
        elif price_change <= -threshold:
            print(f'价格下跌超过1%，当前价格: {current_price}，执行买入操作')
            # 修改：这下面也一样，需要根据您的资金及风险决定交易数量
            order = exchange.create_market_buy_order(symbol, 0.00001)
            base_price = current_price  # 重置基准价格
        else:
            print(f'当前价格: {current_price}，未达到波动阈值（基准价格: {base_price}）')

        # 每10秒检查一次价格，视情况调整监控间隔时间
        time.sleep(10)

    except Exception as e:
        print(f'发生错误: {e}')
        time.sleep(10)
