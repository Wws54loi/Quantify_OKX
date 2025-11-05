"""
测试超时平仓机制
"""

import json
from three_kline_strategy import KLine, ThreeKlineStrategy
from collections import Counter

# 加载K线数据
print("正在加载K线数据...")
with open('btcusdt_15m_klines.json', 'r', encoding='utf-8') as f:
    raw_klines = json.load(f)

klines = [KLine(k) for k in raw_klines]
print(f"✓ 加载了 {len(klines)} 根K线")

# 测试参数
leverage = 50
profit_target_percent = 30
stop_loss_percent = 99
min_k1_range_percent = 0.21
max_holding_bars_tp = 41
max_holding_bars_sl = 102

price_profit_target = profit_target_percent / leverage / 100
price_stop_loss = stop_loss_percent / leverage / 100
min_k1_range = min_k1_range_percent / 100

print("\n测试参数:")
print(f"  止盈: {profit_target_percent}% (价格变动 {price_profit_target*100:.2f}%)")
print(f"  止损: {stop_loss_percent}% (价格变动 {price_stop_loss*100:.2f}%)")
print(f"  超时: 止盈>{max_holding_bars_tp}根, 止损>{max_holding_bars_sl}根")

# 运行策略
strategy = ThreeKlineStrategy()
signals = strategy.find_signals(
    klines,
    profit_target=price_profit_target,
    stop_loss=price_stop_loss,
    min_k1_range=min_k1_range,
    max_holding_bars_tp=max_holding_bars_tp,
    max_holding_bars_sl=max_holding_bars_sl
)

print(f"\n找到 {len(signals)} 个交易信号")

# 统计出场类型
exit_types = Counter([s['exit_type'] for s in signals])

print("\n出场类型统计:")
print(f"  止盈 (take_profit): {exit_types.get('take_profit', 0)}笔")
print(f"  止损 (stop_loss): {exit_types.get('stop_loss', 0)}笔")
print(f"  超时平仓 (timeout_close): {exit_types.get('timeout_close', 0)}笔")
print(f"  超时止损 (timeout_stoploss): {exit_types.get('timeout_stoploss', 0)}笔")

# 显示超时平仓的案例
timeout_signals = [s for s in signals if s['exit_type'] in ['timeout_close', 'timeout_stoploss']]
if timeout_signals:
    print(f"\n超时平仓案例 (共{len(timeout_signals)}笔):")
    for i, sig in enumerate(timeout_signals[:5], 1):
        from datetime import datetime
        entry_time = datetime.fromtimestamp(sig['entry_time']/1000).strftime('%Y-%m-%d %H:%M')
        exit_time = datetime.fromtimestamp(sig['exit_time']/1000).strftime('%Y-%m-%d %H:%M')
        direction = '做多' if sig['direction'] == 'long' else '做空'
        print(f"\n  案例 #{i}:")
        print(f"    方向: {direction}")
        print(f"    入场时间: {entry_time}")
        print(f"    出场时间: {exit_time}")
        print(f"    持仓K线: {sig['holding_bars']}根")
        print(f"    入场价格: {sig['entry_price']:.2f}")
        print(f"    出场价格: {sig['exit_price']:.2f}")
        print(f"    收益率: {sig['return']*100:.3f}%")
        print(f"    出场原因: {sig['exit_type']}")

# 计算统计
stats = strategy.calculate_win_rate(signals, leverage=leverage, initial_capital=1.0)

print(f"\n{'='*80}")
print("统计结果:")
print(f"{'='*80}")
print(f"总交易数: {stats['total_trades']}")
print(f"盈利次数: {stats['wins']}")
print(f"亏损次数: {stats['losses']}")
print(f"胜率: {stats['win_rate']:.2f}%")
print(f"平均持仓: {stats['avg_holding_bars']:.1f}根K线")
print(f"总盈亏: {stats['total_pnl']:+.4f} USDT")
print(f"{'='*80}")
