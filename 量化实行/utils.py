from datetime import datetime

"""格式化时间戳为可读时间"""
def format_timestamp(ts_ms):
	return datetime.fromtimestamp(int(ts_ms) / 1000).strftime('%Y-%m-%d %H:%M:%S')
"""格式化K线数据为易读字符串"""
def format_kline(candle, interval, meets_threshold=False):
	# candle: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
	ts = candle[0]
	o = float(candle[1])
	h = float(candle[2])
	l = float(candle[3])
	c = float(candle[4])
	vol = float(candle[5])
	confirm = candle[8]
	
	# 计算涨跌
	change = c - o
	change_pct = (change / o * 100) if o != 0 else 0
	
	# 判断方向
	direction = "🟢 做多" if change >= 0 else "🔴 做空"
	status = "✓ 已确认" if confirm == "1" else "⏳ 进行中"
	
	# 判断是否满足条件
	threshold_mark = "⭐ 满足条件 (≥0.21%)" if meets_threshold else "❌ 未满足条件 (<0.21%)"
	
	return (f"[{interval}] {format_timestamp(ts)} | {status} | {threshold_mark}\n"
	        f"  开: {o:.2f} | 高: {h:.2f} | 低: {l:.2f} | 收: {c:.2f}\n"
	        f"  {direction} 涨跌: {change:+.2f} ({change_pct:+.3f}%) | 成交量: {vol:.2f}")
