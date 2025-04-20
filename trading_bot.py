import ccxt  # 导入 ccxt 库，用于连接交易所
import time  # 用于设置时间间隔
import datetime # 用于处理时间戳和时间格式

# 设置 OKX API 访问参数（请自行填写为你自己的 API 信息）
api_key = '你的API_KEY'
secret_key = '你的SECRET_KEY'
passphrase = '你的API_PASSPHRASE'

# 初始化 OKX 交易所对象
exchange = ccxt.okx({
    'apiKey': api_key,
    'secret': secret_key,
    'password': passphrase,
    'enableRateLimit': True,  # 开启限速保护，避免被封IP
    'proxies': {  # 如果你在中国大陆访问OKX，推荐配置代理
        'http': 'http://XXX.X.X.X:XXXX',
        'https': 'http://XXX.X.X.X:XXXX',
    }
})

symbol = 'BTC/USDT'      # 设置交易对为 BTC/USDT
threshold = 0.005        # 设置波动阈值为 0.5%
min_profit = 0.003       # 设置最小盈利比例为 0.3%，用于手续费保护
base_price = None        # 用于记录基准价格
buy_price = None         # 用于记录买入价格
last_base_update = time.time()  # 记录上次基准价更新时间
update_interval = 3600    # 设置基准价更新时间间隔为 3600秒（1小时）

# 无限循环，持续监听价格变动
while True:
    try:
        # 获取当前最新市场价格
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']

        # 初始化基准价（程序首次启动时）
        if base_price is None:
            base_price = current_price
            print(f'✅ 首次设置基准价格为: {base_price:.2f}')

        # 计算价格波动幅度
        price_change = (current_price - base_price) / base_price
        print(f'📊 当前价格: {current_price:.2f}，波动幅度: {price_change * 100:.2f}%（基准价: {base_price:.2f}）')

        # 查询账户余额
        balance = exchange.fetch_balance()
        btc_amount = balance['BTC']['free']
        usdt_amount = balance['USDT']['free']

        # ======================= 卖出逻辑 ========================
        # 如果当前有BTC持仓，并且价格上涨幅度超过threshold且高于买入价0.3%
        if btc_amount > 0 and price_change >= threshold and current_price >= buy_price * (1 + min_profit):
            print(f'📈 价格上涨超过{threshold * 100:.2f}%，且超过买入价 {min_profit * 100:.2f}%，执行卖出操作')
            order = exchange.create_market_sell_order(symbol, btc_amount)
            print(f'✅ 卖出 {btc_amount:.6f} BTC 成功，成交价：{current_price:.2f}')
            base_price = current_price  # 卖出成功后更新基准价格
            buy_price = None  # 清空买入价格记录

        # ======================= 买入逻辑 ========================
        # 如果当前持仓为0，并且价格下跌超过threshold
        elif btc_amount == 0 and price_change <= -threshold:
            if usdt_amount > 10:  # 避免因余额太小而报错
                amount_to_buy = usdt_amount / current_price
                order = exchange.create_market_buy_order(symbol, amount_to_buy)
                print(f'✅ 买入 {amount_to_buy:.6f} BTC 成功，成交价：{current_price:.2f}')
                base_price = current_price  # 买入成功后更新基准价格
                buy_price = current_price  # 记录买入价格用于未来卖出判断
            else:
                print('⚠️ USDT余额不足，无法执行买入操作')

        else:
            print('⏳ 未达到交易条件，继续观察...')

        # ======================= 定时更新基准价格 ========================
        now = time.time()
        # 仅在“空仓状态”下，每5分钟更新一次基准价，以防价格长时间不触发交易
        if btc_amount == 0 and now - last_base_update >= update_interval:
            # 判断是否波动较小才更新基准价，避免频繁错过机会
            if abs(price_change) < threshold * 0.5:
                base_price = current_price
                last_base_update = now
                print(f'🔄 空仓状态下基准价已定时更新为: {base_price:.2f}')

        # 每10秒运行一次
        time.sleep(10)

    except Exception as e:
        print(f'❌ 发生错误: {e}')
        time.sleep(10)
