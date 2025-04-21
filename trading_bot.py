import ccxt  # 导入 ccxt 库，用于连接交易所
import time  # 用于设置时间间隔

# 设置 OKX API 访问参数（请自行填写为你自己的 API 信息）
api_key = '你的API_KEY'
secret_key = '你的SECRET_KEY'
passphrase = '你的API_PASSPHRASE'

symbol = 'BTC/USDT'         # 设置交易对
threshold = 0.005           # 固定波动阈值（例如 0.5%）
min_threshold = 0.003       # 最小阈值限制（防止频繁交易）
min_profit = 0.003          # 手续费保护（确保卖出价格高于买入价0.3%）
base_price = None           # 基准价格（会初始化为第一次获取的价格）
buy_price = None            # 记录上次买入时的价格（用于持仓判断）
last_reset_time = time.time()  # 上次基准价更新时间
reset_interval = 3600        # 基准价每 1小时 可更新一次（单位秒）

# 无限循环，不断检查行情
while True:
    try:
        # 获取当前市场价格
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']

        # 初始化基准价格（首次运行）
        if base_price is None:
            base_price = current_price
            print(f'✅ 初始化基准价格: {base_price}')

        # 计算价格变化幅度（当前价 - 基准价）÷ 基准价
        price_change = (current_price - base_price) / base_price

        # 显示波动信息
        print(f'📊 当前价格: {current_price}，涨跌幅: {price_change * 100:.2f}%（基准价: {base_price}）')

        # 查询账户余额
        balance = exchange.fetch_balance()
        btc_amount = balance['BTC']['free']
        usdt_amount = balance['USDT']['free']

        # 卖出逻辑：价格上涨超阈值 + 有持仓 + 超过手续费
        if (
            btc_amount > 0 and
            buy_price is not None and
            price_change >= threshold and
            current_price >= buy_price * (1 + min_profit)
        ):
            order = exchange.create_market_sell_order(symbol, btc_amount)
            print(f'✅ 卖出 {btc_amount} BTC，价格: {current_price}')
            base_price = current_price  # 更新基准价格
            buy_price = None  # 清空买入记录（表示已平仓）

        # 买入逻辑：价格下跌超阈值 + 有足够 USDT
        elif price_change <= -threshold and usdt_amount > 10:
            amount_to_buy = usdt_amount / current_price
            order = exchange.create_market_buy_order(symbol, amount_to_buy)
            print(f'✅ 买入 {amount_to_buy:.6f} BTC，价格: {current_price}')
            base_price = current_price  # 更新基准价格
            buy_price = current_price   # 记录买入价用于未来卖出判断

        # 定时更新基准价逻辑（仅在空仓时执行）
        elif btc_amount == 0 and (time.time() - last_reset_time > reset_interval):
            # 仅当波动幅度在阈值范围一半以内时才更新，避免错过交易机会
            if abs(price_change) < threshold * 0.5:
                base_price = current_price
                last_reset_time = time.time()
                print(f'🕒 空仓状态，波动较小，重置基准价格为: {base_price}')

        else:
            print("⏳ 无交易条件成立，继续观察...")

        # 每隔 10 秒执行一次循环
        time.sleep(10)

    except Exception as e:
        print(f'❌ 发生错误: {e}')
        time.sleep(10)
