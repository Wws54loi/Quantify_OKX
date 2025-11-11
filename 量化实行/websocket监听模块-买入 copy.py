import asyncio
import websockets
import json
from datetime import datetime
from utils import format_kline, format_timestamp
import csv
import os
import uuid
import time
from 微信提醒 import send_wechat_notification

def calculate_trade_amount(k1_strength_pct):
	"""
	根据K1柱体强度计算下注金额
	k1_strength_pct: K1的涨跌幅百分比
	返回: (本金, 手续费, 净本金, 下单金额, 保证金)

	定义说明:
	- 本金(principal): 初始投入
	- 手续费(fee): 本金的9.8%
	- 净本金(actual_margin): 扣除手续费后的实际可用本金
	- 下单金额(order_amount): 净本金的5.3倍（总持仓规模）
	- 保证金(guaranteed_margin): 下单金额减去原始本金 = (净本金*5.3) - principal
	"""
	# 确定本金
	if k1_strength_pct >= 0.48:
		principal = 4.0
	elif k1_strength_pct >= 0.3:
		principal = 1.6
	else:  # >= 0.21
		principal = 1.0

	fee = principal * 0.098
	actual_margin = principal - fee
	order_amount = actual_margin * 5.3
	guaranteed_margin = order_amount - principal
	return principal, fee, actual_margin, order_amount, guaranteed_margin

def write_trade_log(direction, entry_price, k1_high, k1_low, breakout_direction, k1_strength_pct, timestamp):
	"""写入交易日志到CSV，并返回唯一仓位ID"""
	log_file = "trade_signals.csv"
	file_exists = os.path.exists(log_file)
	principal, fee, actual_margin, order_amount, guaranteed_margin = calculate_trade_amount(k1_strength_pct)
	# 唯一仓位ID = 毫秒时间戳 + 8位uuid前缀
	trade_id = f"{int(timestamp)}-{uuid.uuid4().hex[:8]}"
	with open(log_file, 'a', newline='', encoding='utf-8') as f:
		writer = csv.writer(f)
		if not file_exists:
			writer.writerow([
				'仓位ID','时间','方向','入场价','K1最高价','K1最低价','突破方向',
				'K1强度(%)','本金(U)','手续费(U)','净本金(U)','下单金额(U)','保证金(U)','是否平仓','备注'
			])
		writer.writerow([
			trade_id,
			datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S'),
			direction,
			f"{entry_price:.2f}",
			f"{k1_high:.2f}",
			f"{k1_low:.2f}",
			breakout_direction,
			f"{k1_strength_pct:.4f}",
			f"{principal:.2f}",
			f"{fee:.4f}",
			f"{actual_margin:.4f}",
			f"{order_amount:.4f}",
			f"{guaranteed_margin:.4f}",
			'未平仓',
			f"基于K1区间的{'向上' if breakout_direction == 'up' else '向下'}突破回归信号"
		])
	print(f"📝 交易信号已记录到 {log_file}")
	print(f"   🆔 仓位ID: {trade_id}")
	print(f"   💵 本金: {principal:.2f}U | 手续费: {fee:.4f}U | 净本金: {actual_margin:.4f}U | 下单金额: {order_amount:.4f}U | 保证金: {guaranteed_margin:.4f}U")
	return trade_id

async def main():
	url = "wss://fstream.binance.com/ws/ethusdt@kline_15m/ethusdt@kline_1m"
	
	# 状态变量
	monitoring_state = "waiting_15m"  # waiting_15m, monitoring_1m, key_focus
	k15m_reference = None  # 参考的15分钟K线数据 {high, low, open, close}
	k1_strength_pct = 0  # K1的柱体强度（涨跌幅百分比）
	has_breakout = False  # 是否发生突破
	breakout_direction = None  # 突破方向: 'up' 或 'down'
	one_min_count = 0  # 当前15分钟内的1分钟K线计数
	k2_last_check_done = False  # K2最后一根1分钟K线是否已检查
	signal_recorded = False  # 交易信号是否已记录（避免重复记录）
	# 去重控制：仅在每个15m周期内首次突破时提示（使用 has_breakout 控制），无需额外变量
	
	try:
		async with websockets.connect(url) as ws:
			print("=" * 80)
			print("WebSocket 已连接到 Binance")
			print("已订阅 ETHUSDT 的 15分钟 和 1分钟 K线")
			print("=" * 80)
			print()
			print("📡 状态: 等待满足条件的15分钟K线...")
			print()
			
			while True:
				try:
					msg = await ws.recv()
					data = json.loads(msg)
					
					# 币安K线数据格式
					if 'e' in data and data['e'] == 'kline':
						kline = data['k']
						interval = kline['i']
						# ==================== 处理15分钟K线和状态转换 ====================
						if interval == '15m':
							# 只处理已完结的15m K线
							if not kline['x']:
								continue
							# 解析数据
							o = float(kline['o']); 
							h = float(kline['h']); 
							l = float(kline['l']); 
							c = float(kline['c']);
							change_pct = abs((c - o) / o * 100) if o != 0 else 0
							meets_threshold = change_pct >= 0.21
							candle = [int(kline['t']), kline['o'], kline['h'], kline['l'], kline['c'], kline['v'], '', '', '1']
							print(format_kline(candle, '15分钟', meets_threshold))
							print("-" * 80)
							# 状态转换到监控1m
							if monitoring_state == "waiting_15m" and meets_threshold:
								monitoring_state = "monitoring_1m"
								k15m_reference = {'high': h, 'low': l, 'open': o, 'close': c}
								k1_strength_pct = change_pct
								has_breakout = False; breakout_direction = None; one_min_count = 0; signal_recorded = False
								principal, fee, actual_margin, order_amount, guaranteed_margin = calculate_trade_amount(change_pct)
								print()
								print("🎯 " + "=" * 70)
								print("   触发监听！开始监控1分钟K线")
								print(f"   参考区间: 高 {h:.2f} | 低 {l:.2f}")
								print(f"   K1强度: {change_pct:.4f}% | 本金: {principal:.2f}U | 净本金: {actual_margin:.4f}U | 下单金额: {order_amount:.4f}U | 保证金: {guaranteed_margin:.4f}U")
								print("=" * 70)
								print()
							elif monitoring_state in ["monitoring_1m", "key_focus"]:
								# 新的15m结束周期，重置
								print(); print("🔄 15分钟周期结束，重置状态，等待下一个信号..."); print()
								monitoring_state = "waiting_15m"; k15m_reference = None; has_breakout = False; breakout_direction = None
								one_min_count = 0; k2_last_check_done = False; signal_recorded = False
						# ==================== 处理1分钟K线 ====================
						elif interval == '1m':
							# 只在监控状态下处理
							if monitoring_state not in ["monitoring_1m", "key_focus"]:
								continue
							
							# 获取K线数据
							h = float(kline['h'])
							l = float(kline['l'])
							o = float(kline['o'])
							c = float(kline['c'])
							ts = int(kline['t'])
							is_closed = kline['x']
							
							# 已完结的K线才计数
							if is_closed:
								one_min_count += 1
								
								# 检测突破（向上/向下）
								breakout_up = h > k15m_reference['high']
								breakout_down = l < k15m_reference['low']
								# 仅在当前15m周期内首次发生突破时打印（去重）
								if (breakout_up or breakout_down) and not has_breakout:
									# 同时上下突破，打印两次并优先记录向下方向
									if breakout_up and breakout_down:
										print(f"⚡ 第{one_min_count}根1分钟K线发生突破！向上突破")
										print(f"   当前价: 高 {h:.2f} | 低 {l:.2f}")
										print(f"   参考区间: 高 {k15m_reference['high']:.2f} | 低 {k15m_reference['low']:.2f}")
										print("-" * 80)
										print(f"⚡ 第{one_min_count}根1分钟K线发生突破！向下突破（优先）")
										print(f"   当前价: 高 {h:.2f} | 低 {l:.2f}")
										print(f"   参考区间: 高 {k15m_reference['high']:.2f} | 低 {k15m_reference['low']:.2f}")
										print("-" * 80)
										breakout_direction = 'down'
									else:
										print(f"⚡ 第{one_min_count}根1分钟K线发生突破！")
										print(f"   方向: {'向上突破' if breakout_up else '向下突破（优先）'}")
										print(f"   当前价: 高 {h:.2f} | 低 {l:.2f}")
										print(f"   参考区间: 高 {k15m_reference['high']:.2f} | 低 {k15m_reference['low']:.2f}")
										print("-" * 80)
										breakout_direction = 'down' if breakout_down else 'up'
									has_breakout = True
								
								# 检测倒数第二根回归（第14根1分钟K线）
								if monitoring_state == "monitoring_1m" and has_breakout and one_min_count == 14:
									# 检查是否回到区间内
									back_in_range = (l >= k15m_reference['low'] and h <= k15m_reference['high'])
									
									if back_in_range:
										monitoring_state = "key_focus"
										k2_last_check_done = False
										print()
										print("🔥 " + "=" * 70)
										print(f"   ⭐⭐⭐ 重点关注信号！⭐⭐⭐")
										print(f"   倒数第二根1分钟K线已回归区间")
										print(f"   突破方向: {'向上' if breakout_direction == 'up' else '向下'}")
										print(f"   当前价: 高 {h:.2f} | 低 {l:.2f}")
										print(f"   区间: {k15m_reference['low']:.2f} - {k15m_reference['high']:.2f}")
										print(f"   等待K2最后一根1分钟K线...")
										print("=" * 70)
										print()
									else:
										print(f"⚠ 第14根1分钟K线未回归区间")
										print(f"   当前: 高 {h:.2f} | 低 {l:.2f}")
										print(f"   区间: {k15m_reference['low']:.2f} - {k15m_reference['high']:.2f}")
										print("-" * 80)
							
							# K2最后一根1分钟K线的最后5秒检查（进行中的K线）
							if monitoring_state == "key_focus" and one_min_count == 14 and not signal_recorded and not is_closed:
								# 计算K线剩余时间
								current_time = datetime.now().timestamp() * 1000
								kline_end_time = ts + 60000  # 1分钟 = 60000ms
								time_remaining = (kline_end_time - current_time) / 1000
								
								# 最后5秒内持续检查
								if time_remaining <= 5:
									# 检查是否仍在K1区间内
									still_in_range = (l >= k15m_reference['low'] and h <= k15m_reference['high'])
									
									if still_in_range:
										# 计算K2实体柱与K1实体柱的比值
										k1_body = abs(k15m_reference['close'] - k15m_reference['open'])
										k2_body = abs(c - o)  # K2的实体：当前价格 - K2开盘价
										
										# 避免除零错误
										if k1_body == 0:
											body_ratio = 0
										else:
											body_ratio = k2_body / k1_body
										
										# 检查实体柱比值是否在0.5-1.6之间
										body_ratio_valid = 0.5 <= body_ratio <= 1.6
										
										if body_ratio_valid:
											# 确定交易方向（反向逻辑）
											if breakout_direction == 'up':
												trade_direction = "做空"  # 向上突破后回归，做空
											else:
												trade_direction = "做多"  # 向下突破后回归，做多
											
											entry_price = c  # 使用当前收盘价作为入场价
											
											print()
											print("🎯 " + "=" * 70)
											print(f"   💰 交易信号确认！")
											print(f"   方向: {trade_direction}")
											print(f"   入场价: {entry_price:.2f}")
											print(f"   理由: K2最后一根1分钟K线在最后{time_remaining:.1f}秒时仍在K1区间内")
											print(f"   K1实体: {k1_body:.2f} | K2实体: {k2_body:.2f} | 比值: {body_ratio:.2f}")
											print(f"   K1区间: {k15m_reference['low']:.2f} - {k15m_reference['high']:.2f}")
											print(f"   当前价位: 高 {h:.2f} | 低 {l:.2f} | 收 {c:.2f}")
											print("=" * 70)
											print()
											# 写入交易日志并取得仓位ID
											trade_id = write_trade_log(
												trade_direction,
												entry_price,
												k15m_reference['high'],
												k15m_reference['low'],
												breakout_direction,
												k1_strength_pct,
												int(current_time)
											)
											# 计算金额信息用于通知
											principal, fee, actual_margin, order_amount, guaranteed_margin = calculate_trade_amount(k1_strength_pct)
											# 构造通知
											title = f"ETH-{trade_direction}-投入{principal:.2f}U"
											content_lines = [
												f"仓位ID: {trade_id}",
												f"时间: {datetime.fromtimestamp(int(current_time)/1000).strftime('%Y-%m-%d %H:%M:%S')}",
												f"方向: {trade_direction}",
												f"入场价: {entry_price:.2f}",
												f"K1强度: {k1_strength_pct:.4f}%", 
												f"K1区间: {k15m_reference['low']:.2f} - {k15m_reference['high']:.2f}",
												f"突破方向: {'向上' if breakout_direction=='up' else '向下'} -> 反向 {trade_direction}",
												f"K2/K1实体比: {body_ratio:.2f}",
												f"本金: {principal:.2f}U  手续费: {fee:.4f}U", 
												f"净本金: {actual_margin:.4f}U  下单金额: {order_amount:.4f}U", 
												f"保证金: {guaranteed_margin:.4f}U", 
											]
											content = "\n".join(content_lines)
											# 发送微信通知
											send_wechat_notification(title, content)
										
											signal_recorded = True  # 标记信号已记录，避免重复
										else:
											# 实体柱比值不满足条件
											if not signal_recorded:
												print(f"⚠ K2实体柱比值不满足条件: {body_ratio:.2f} (要求: 0.5-1.6)")
												print(f"   K1实体: {k1_body:.2f} | K2实体: {k2_body:.2f}")
												signal_recorded = True  # 标记避免重复打印
									elif time_remaining <= 1 and not signal_recorded:
										# 如果最后1秒仍未满足条件，记录未触发信息
										print(f"⚠ K2最后5秒检查: 价格已脱离K1区间，不生成交易信号")
										print(f"   当前: 高 {h:.2f} | 低 {l:.2f}")
										print(f"   K1区间: {k15m_reference['low']:.2f} - {k15m_reference['high']:.2f}")
										print("-" * 80)
										signal_recorded = True  # 避免重复打印
				
				except websockets.exceptions.ConnectionClosed:
					print("⚠ WebSocket 连接已断开，尝试重连...")
					await asyncio.sleep(3)
					break
				except Exception as e:
					print(f"⚠ 发生异常: {e}")
					await asyncio.sleep(1)
	
	except Exception as e:
		print(f"✗ 连接失败: {e}")

if __name__ == "__main__":
	print("启动 ETHUSDT K线监听程序 (Binance)...")
	print("监控所有 15分钟K线")
	print()
	
	while True:
		try:
			asyncio.run(main())
		except KeyboardInterrupt:
			print("\n程序已停止")
			break
		except Exception as e:
			print(f"程序异常: {e}")
			print("3秒后重启...")
			time.sleep(3)
