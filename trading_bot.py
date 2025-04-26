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
    'enableRateLimit': True,  # 开启限速保护，避免被封IP
    'proxies': {  # 如果你在中国大陆访问OKX，推荐配置代理
        'http': 'http://X.X.X.X:XXXX',
        'https': 'http://X.X.X.X:XXXX',
    }
})

symbol = 'BTC/USDT'
threshold = 0.005          # 固定波动阈值（0.5%）
min_profit = 0.003         # 手续费保护（0.3%）
reset_interval = 3600      # 基准价每小时更新一次

# 追踪买入参数
trailing_buy_trigger = 0.005    # 启动追踪买入的下跌幅度
trailing_buy_rebound = 0.001    # 反弹买入条件（从最低点反弹0.1%）

# 追踪止盈参数
trailing_sell_trigger = 0.005   # 启动追踪止盈的上涨幅度
trailing_sell_drawdown = 0.003  # 回撤0.3%触发止盈

base_price = None
buy_price = None
last_reset_time = time.time()

# 状态变量
tracking_buy_mode = False
lowest_price_during_drop = None

tracking_sell_mode = False
peak_price_during_rise = None

while True:
    try:
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']

        if base_price is None:
            base_price = current_price
            print(f'✅ 初始化基准价格: {base_price}')

        price_change = (current_price - base_price) / base_price
        print(f'\n📊 当前价格: {current_price}，涨跌幅: {price_change * 100:.2f}%（基准价: {base_price}）')

        balance = exchange.fetch_balance()
        btc_amount = balance['BTC']['free']
        usdt_amount = balance['USDT']['free']

        # === 追踪止盈逻辑（持仓且价格涨超0.5%开始追踪，回撤0.3%则止盈）===
        if btc_amount > 0 and buy_price:
            profit_ratio = (current_price - buy_price) / buy_price

            # 启动追踪止盈
            if not tracking_sell_mode and profit_ratio >= trailing_sell_trigger:
                tracking_sell_mode = True
                peak_price_during_rise = current_price
                print(f'🚀 启动追踪止盈模式，记录高点: {peak_price_during_rise}')

            # 追踪中更新高点
            if tracking_sell_mode and current_price > peak_price_during_rise:
                peak_price_during_rise = current_price
                print(f'📈 新高，更新追踪高点: {peak_price_during_rise}')

            # 回撤触发止盈
            elif tracking_sell_mode and current_price <= peak_price_during_rise * (1 - trailing_sell_drawdown):
                order = exchange.create_market_sell_order(symbol, btc_amount)
                print(f'✅ 追踪止盈卖出 {btc_amount} BTC，价格: {current_price}')
                base_price = current_price
                buy_price = None
                tracking_sell_mode = False
                peak_price_during_rise = None
                tracking_buy_mode = False
                lowest_price_during_drop = None
                continue  # 本轮已卖出，跳过后面买入逻辑

        # === 正常卖出逻辑（若没进入追踪止盈） ===
        elif (
            btc_amount > 0 and
            buy_price is not None and
            price_change >= threshold and
            current_price >= buy_price * (1 + min_profit)
        ):
            order = exchange.create_market_sell_order(symbol, btc_amount)
            print(f'✅ 卖出 {btc_amount} BTC，价格: {current_price}')
            base_price = current_price
            buy_price = None
            tracking_sell_mode = False
            peak_price_during_rise = None
            tracking_buy_mode = False
            lowest_price_during_drop = None

        # === 追踪买入逻辑（跌超0.5%后开启追踪，反弹0.1%才买） ===
        elif btc_amount == 0:
            if not tracking_buy_mode and price_change <= -trailing_buy_trigger:
                tracking_buy_mode = True
                lowest_price_during_drop = current_price
                print(f'📉 启动追踪买入模式，记录最低价: {lowest_price_during_drop}')

            elif tracking_buy_mode:
                if current_price < lowest_price_during_drop:
                    lowest_price_during_drop = current_price
                    print(f'🔄 更新最低价: {lowest_price_during_drop}')
                elif current_price >= lowest_price_during_drop * (1 + trailing_buy_rebound) and usdt_amount > 10:
                    amount_to_buy = usdt_amount / current_price
                    order = exchange.create_market_buy_order(symbol, amount_to_buy)
                    print(f'✅ 追踪买入 {amount_to_buy:.6f} BTC，价格: {current_price}')
                    buy_price = current_price
                    base_price = current_price
                    tracking_buy_mode = False
                    lowest_price_during_drop = None
                    tracking_sell_mode = False
                    peak_price_during_rise = None

        # === 空仓定时更新基准价 ===
        if btc_amount == 0 and (time.time() - last_reset_time > reset_interval):
            if abs(price_change) < threshold * 0.5:
                base_price = current_price
                last_reset_time = time.time()
                print(f'🕒 空仓波动小，更新基准价为: {base_price}')
                tracking_buy_mode = False
                lowest_price_during_drop = None

        time.sleep(10)

    except Exception as e:
        print(f'❌ 发生错误: {e}')
        time.sleep(10)
