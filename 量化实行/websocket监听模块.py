import asyncio
import websockets
import json

async def main():
	url = "wss://ws.okx.com:8443/ws/v5/public"
	async with websockets.connect(url) as ws:
		# 订阅ETH-USDT 15m k线
		param = {
			"op": "subscribe",
			"args": [
				{
					"channel": "candle15m",
					"instId": "ETH-USDT"
				}
			]
		}
		await ws.send(json.dumps(param))
		print("已订阅ETH-USDT 15min K线...")
		while True:
			try:
				msg = await ws.recv()
				data = json.loads(msg)
				if 'data' in data:
					for candle in data['data']:
						# candle: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
						o = float(candle[1])
						c = float(candle[4])
						if o == 0:
							continue
						body_ratio = abs(c - o) / o
						if body_ratio >= 0.0021:
							print(f"信号: ETH-USDT 15min K线柱体超过0.21%，开盘价: {o}, 收盘价: {c}, 涨跌幅: {body_ratio*100:.3f}%")
			except Exception as e:
				print("发生异常:", e)
				await asyncio.sleep(3)

if __name__ == "__main__":
	asyncio.run(main())
