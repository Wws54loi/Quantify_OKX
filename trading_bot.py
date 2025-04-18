import ccxt  # 导入 ccxt 库，用于连接交易所
import time  # 用于设置时间间隔

# 设置 OKX API 访问参数（请自行填写为你自己的 API 信息）
api_key = '你的API_KEY'
secret_key = '你的SECRET_KEY'
passphrase = '你的API_PASSPHRASE'

# 初始化 OKX 交易所对象
exchange = ccxt.okx({
    'apiKey': api_key,
    'secret': secret_key,
    'password': passphrase,
    'enableRateLimit': True,  # 启用限速，避免请求过快被封
    'proxies': {  # 如果你在国内，可配置代理访问 OKX 接口
        'http': 'http://XXX.X.X.X:XXXX',
        'https': 'http://XXX.X.X.X:XXXX',
    }
})

# 设置交易对，例如 BTC/USDT（比特币/泰达币）
symbol = 'BTC/USDT'

# 设置波动阈值：这里是 1%，即当价格变动超过 1% 时才执行买卖操作
threshold = 0.01

# 基准价格：首次运行时会设置为当时市场价，用于之后判断涨跌幅度
base_price = None

# 无限循环，不断检测价格波动
while True:
    try:
        # 获取当前价格（ticker 中的 last 字段代表最新成交价）
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']

        # 第一次运行时设置基准价格
        if base_price is None:
            base_price = current_price
            print(f'✅ 基准价格已设置为: {base_price}')

        # 计算价格涨跌幅（当前价格与基准价格的比值）
        price_change = (current_price - base_price) / base_price

        # 显示当前波动幅度（转换为百分比，保留两位小数）
        print(f'📊 当前波动幅度: {price_change * 100:.2f}%')

        # 如果上涨超过设定阈值，执行卖出操作
        if price_change >= threshold:
            print(f'📈 价格上涨超过1%，当前价格: {current_price}，执行全仓卖出操作')
            
            # 查询账户中的 BTC 余额
            balance = exchange.fetch_balance()
            btc_amount = balance['BTC']['free']

            # 如果余额足够，执行卖出
            if btc_amount > 0:
                order = exchange.create_market_sell_order(symbol, btc_amount)
                print(f'✅ 成功卖出 {btc_amount} BTC')
                base_price = current_price  # 更新基准价格
            else:
                print('⚠️ 警告：账户中 BTC 余额不足，无法卖出')

        # 如果下跌超过设定阈值，执行买入操作
        elif price_change <= -threshold:
            print(f'📉 价格下跌超过1%，当前价格: {current_price}，执行全仓买入操作')

            # 查询账户中 USDT 余额
            balance = exchange.fetch_balance()
            usdt_amount = balance['USDT']['free']

            # 获取当前 BTC 价格，计算最多可以买多少 BTC
            if usdt_amount > 10:  # 设置最低买入金额，避免金额过小出错
                amount_to_buy = usdt_amount / current_price
                order = exchange.create_market_buy_order(symbol, amount_to_buy)
                print(f'✅ 成功买入约 {amount_to_buy:.6f} BTC')
                base_price = current_price  # 更新基准价格
            else:
                print('⚠️ 警告：账户中 USDT 余额不足，无法买入')

        else:
            # 如果涨跌幅没达到阈值，就继续等待
            print(f'当前价格: {current_price}，未达到波动阈值（基准价格: {base_price}）')

        # 每 10 秒运行一次（可以根据需求改为更短或更长）
        time.sleep(10)

    except Exception as e:
        print(f'❌ 发生错误: {e}')
        time.sleep(10)
