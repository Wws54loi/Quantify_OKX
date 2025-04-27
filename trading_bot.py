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
    'enableRateLimit': True,  # 开启限速保护
    'proxies': {  # 可选：如果你在大陆访问
        'http': 'http://127.0.0.1:7890',
        'https': 'http://127.0.0.1:7890',
    }
})

# === 交易参数 ===
symbol = 'BTC/USDT'
threshold = 0.005           # 0.5% 波动阈值
min_profit = 0.003          # 0.3% 手续费保护
min_position = 0.0001       # 0.0001 BTC以下不算持仓
reset_interval = 3600       # 空仓基准价每1小时更新
track_profit_threshold = 0.005  # 涨幅超过0.5%开始追踪止盈
track_profit_callback = 0.003   # 从最高价回撤0.3%止盈
track_buy_trigger = 0.005       # 下跌超过0.5%后开启追踪低点买入
track_buy_callback = 0.001      # 回弹0.1%后买入

# === 变量初始化 ===
base_price = None
buy_price = None
last_reset_time = time.time()
tracking_high = None
tracking_low = None
tracking_buy_mode = False

# === 无限循环 ===
while True:
    try:
        # === 获取最新价格 ===
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']

        # === 初始化基准价格（首次启动） ===
        if base_price is None:
            base_price = current_price
            print(f'✅ 初始化基准价: {base_price}')

        # === 计算涨跌幅 ===
        price_change = (current_price - base_price) / base_price

        # === 查询余额 ===
        balance = exchange.fetch_balance()
        btc_amount = balance['BTC']['free']
        usdt_amount = balance['USDT']['free']

        # === 是否持仓（保护超小余额误判）===
        is_holding = btc_amount > min_position
        is_buy_price_recorded = buy_price is not None

        # === 打印状态 ===
        print(f"\n📈 当前价: {current_price}，涨跌幅: {price_change * 100:.2f}%")
        print(f"🎯 基准价: {base_price}，持仓量: {btc_amount:.6f} BTC，USDT余额: {usdt_amount:.2f}")
        print(f"🔍 当前状态: {'持仓中' if is_holding else '空仓'}，追踪买入模式: {'启用' if tracking_buy_mode else '关闭'}")

        # === 追踪止盈逻辑（持仓且涨超0.5%开始追踪高点）===
        if is_holding and is_buy_price_recorded:
            gain_from_buy = (current_price - buy_price) / buy_price

            if tracking_high is None and gain_from_buy >= track_profit_threshold:
                tracking_high = current_price
                print(f'🚀 启动追踪止盈，高点记录为: {tracking_high}')

            if tracking_high is not None:
                tracking_high = max(tracking_high, current_price)
                if (tracking_high - current_price) / tracking_high >= track_profit_callback:
                    # 回撤达到止盈要求，卖出
                    order = exchange.create_market_sell_order(symbol, btc_amount)
                    print(f'✅ [止盈卖出] {btc_amount:.6f} BTC，成交价: {current_price}')
                    base_price = current_price
                    buy_price = None
                    tracking_high = None
                    continue  # 重新开始下一轮循环（避免下面再触发其他逻辑）

        # === 正常卖出逻辑（无追踪止盈时）===
        if (
            is_holding and
            is_buy_price_recorded and
            price_change >= threshold and
            current_price >= buy_price * (1 + min_profit) and
            tracking_high is None  # 没有启动追踪止盈
        ):
            order = exchange.create_market_sell_order(symbol, btc_amount)
            print(f'✅ 卖出 {btc_amount:.6f} BTC，价格: {current_price}')
            base_price = current_price
            buy_price = None
            tracking_high = None
            continue

        # === 追踪低点买入逻辑 ===
        if not is_holding:
            if not tracking_buy_mode and price_change <= -track_buy_trigger:
                tracking_buy_mode = True
                tracking_low = current_price
                print(f'📉 触发追踪买入模式，记录初始低点: {tracking_low}')

            if tracking_buy_mode:
                tracking_low = min(tracking_low, current_price)
                rebound = (current_price - tracking_low) / tracking_low
                print(f"🔎 追踪中：最低点 {tracking_low}，当前回弹: {rebound * 100:.3f}%")

                if rebound >= track_buy_callback:
                    if usdt_amount > 10:
                        amount_to_buy = usdt_amount / current_price
                        order = exchange.create_market_buy_order(symbol, amount_to_buy)
                        print(f'✅ [追踪买入] {amount_to_buy:.6f} BTC，价格: {current_price}')
                        base_price = current_price
                        buy_price = current_price
                        tracking_low = None
                        tracking_buy_mode = False
                        continue

        # === 定时更新基准价（空仓且波动很小才更新） ===
        if not is_holding and (time.time() - last_reset_time > reset_interval):
            if abs(price_change) < threshold * 0.5:
                base_price = current_price
                last_reset_time = time.time()
                print(f'🕒 空仓且波动小，重置基准价格为: {base_price}')

        # === 如果没有买卖发生 ===
        print("⏳ 暂无交易条件，继续等待...")

        time.sleep(10)

    except Exception as e:
        print(f'❌ 发生错误: {e}')
        time.sleep(10)
