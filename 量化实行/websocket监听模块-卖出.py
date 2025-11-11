import asyncio
import websockets
import json
import csv
import os
import time
from datetime import datetime

CSV_PATH = "trade_signals.csv"
SYMBOL = "ethusdt"
WS_URL = f"wss://fstream.binance.com/ws/{SYMBOL}@kline_1m"
TAKE_PROFIT_PCT = 0.0236  # 2.36%
STOP_LOSS_PCT = 0.0379    # 3.79%

# 追踪止损相关参数（与回测口径保持一致）
LEVERAGE = 140  # 杠杆用于将价格变动%换算为合约收益%
TP_BASE_CONTRACT_PCT = 330.0  # 基准TP(合约收益%)，用于30%门槛的换算
TRAIL_PCT_WEAK = 0.06   # 弱势持仓追踪幅度 6%
TRAIL_PCT_NORMAL = 0.08 # 正常持仓追踪幅度 8%
# 正常持仓激活门槛（按价格百分比计算）：330% / 140 × 30% ≈ 0.7071%
PRICE_PROFIT_GATE_PCT = (TP_BASE_CONTRACT_PCT / LEVERAGE) * 0.30
# 弱势判定门槛（按合约收益%计算）：330% × 30% = 99%
WEAK_CONTRACT_THRESHOLD = TP_BASE_CONTRACT_PCT * 0.30


def load_open_positions(csv_path: str):
    """
    读取未平仓的仓位记录。
    返回 dict: {trade_id: {"entry_price": float, "direction": str, "entry_time": str}}
    要求 CSV 表头至少包含：时间, 仓位ID, 方向, 入场价, 是否平仓
    """
    open_positions = {}
    if not os.path.exists(csv_path):
        return open_positions

    try:
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
            if not rows:
                return open_positions
            header = rows[0]
            # 兼容表头找索引
            def idx(name, default=-1):
                return header.index(name) if name in header else default

            idx_time = idx('时间')
            idx_id = idx('仓位ID')
            idx_dir = idx('方向')
            idx_entry = idx('入场价')
            idx_closed = idx('是否平仓')

            # 基本校验
            if idx_dir == -1 or idx_entry == -1:
                return open_positions

            for row in rows[1:]:
                try:
                    direction = row[idx_dir]
                    entry_price = float(row[idx_entry])
                    closed_flag = row[idx_closed] if idx_closed != -1 and idx_closed < len(row) else '未平仓'

                    if closed_flag != '未平仓':
                        continue

                    trade_id = row[idx_id] if idx_id != -1 and idx_id < len(row) else f"NO_ID_{row[idx_entry]}_{row[idx_dir]}"
                    entry_time = row[idx_time] if idx_time != -1 and idx_time < len(row) else ""
                    open_positions[trade_id] = {
                        "entry_price": entry_price,
                        "direction": direction,
                        "entry_time": entry_time,
                    }
                except Exception:
                    continue
    except Exception:
        # CSV 正在被写入时可能读失败，忽略
        return open_positions

    return open_positions


def update_trade_as_closed(csv_path: str, *, trade_id: str, entry_price: float, direction: str,
                           close_price: float, reason: str, pct: float, close_ts_ms: int, retries: int = 3) -> bool:
    """
    将 CSV 中的对应仓位标记为已平仓，并在备注中追加信息。
    优先按 仓位ID 匹配；若无ID列，则回退按 方向+入场价 匹配首个未平仓行。
    返回 True 表示成功更新。
    """
    attempt = 0
    while attempt < retries:
        attempt += 1
        try:
            if not os.path.exists(csv_path):
                return False

            with open(csv_path, 'r', newline='', encoding='utf-8') as f:
                rows = list(csv.reader(f))
            if not rows:
                return False

            header = rows[0]
            def idx(name, default=-1):
                return header.index(name) if name in header else default

            idx_id = idx('仓位ID')
            idx_dir = idx('方向')
            idx_entry = idx('入场价')
            idx_closed = idx('是否平仓')
            idx_remark = idx('备注')
            idx_out_time = idx('出场时间')
            idx_out_price = idx('出场价格')
            idx_time = idx('时间')
            idx_hold_bars = idx('持仓K线数')
            idx_hold_dur = idx('持仓时长')
            idx_price_change = idx('价格变动%')
            idx_contract_ret = idx('合约收益%')
            idx_pnl = idx('盈亏USDT')
            idx_order_amt = idx('下单金额(U)')

            if idx_dir == -1 or idx_entry == -1 or idx_closed == -1:
                return False

            target_row_index = -1
            if idx_id != -1:
                for i in range(1, len(rows)):
                    row = rows[i]
                    if idx_closed < len(row) and row[idx_closed] == '未平仓' and idx_id < len(row) and row[idx_id] == trade_id:
                        target_row_index = i
                        break
            else:
                # 回退匹配：方向 + 入场价字符串（两位小数）
                entry_str = f"{entry_price:.2f}"
                for i in range(1, len(rows)):
                    row = rows[i]
                    if idx_closed < len(row) and row[idx_closed] == '未平仓':
                        if idx_dir < len(row) and row[idx_dir] == direction and idx_entry < len(row) and row[idx_entry] == entry_str:
                            target_row_index = i
                            break

            if target_row_index == -1:
                return False

            # 更新目标行
            row = rows[target_row_index]
            row[idx_closed] = '已平仓'
            close_time_str = datetime.fromtimestamp(close_ts_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')
            extra = f"平仓:{reason} 价:{close_price:.2f} 时:{close_time_str} 幅:{pct:.2f}%"
            # 写出场时间与出场价格（若有列）
            if idx_out_time != -1:
                # 确保行长度足够
                if idx_out_time >= len(row):
                    row += [''] * (idx_out_time - len(row) + 1)
                row[idx_out_time] = close_time_str
            if idx_out_price != -1:
                if idx_out_price >= len(row):
                    row += [''] * (idx_out_price - len(row) + 1)
                row[idx_out_price] = f"{close_price:.2f}"
            if idx_remark != -1 and idx_remark < len(row):
                if row[idx_remark]:
                    row[idx_remark] = f"{row[idx_remark]} | {extra}"
                else:
                    row[idx_remark] = extra

            # 计算持仓统计与收益类字段
            try:
                # 入场时间
                entry_time_str = row[idx_time] if idx_time != -1 and idx_time < len(row) else ''
                entry_ts = int(datetime.strptime(entry_time_str, '%Y-%m-%d %H:%M:%S').timestamp() * 1000) if entry_time_str else None
            except Exception:
                entry_ts = None

            # 持仓K线数（按1m bar估算）与时长
            if entry_ts is not None:
                hold_ms = max(0, close_ts_ms - entry_ts)
                hold_secs = hold_ms // 1000
                hold_mins = hold_secs // 60
                # 近似K线数=分钟数，至少为1（若存在持仓）
                hold_bars = int(hold_mins) if hold_mins > 0 else (1 if hold_ms > 0 else 0)
                # 写入
                if idx_hold_bars != -1:
                    if idx_hold_bars >= len(row):
                        row += [''] * (idx_hold_bars - len(row) + 1)
                    row[idx_hold_bars] = str(hold_bars)
                if idx_hold_dur != -1:
                    if idx_hold_dur >= len(row):
                        row += [''] * (idx_hold_dur - len(row) + 1)
                    row[idx_hold_dur] = f"{int(hold_mins)}分{int(hold_secs % 60)}秒"

            # 价格变动%（签名：收-入/入），合约收益%（方向修正），盈亏USDT（基于下单金额）
            price_change_pct = None
            contract_ret_pct = None
            pnl_usdt = None
            try:
                if entry_price and entry_price > 0:
                    price_change_pct = (close_price - entry_price) / entry_price * 100.0
                    contract_ret_pct = price_change_pct if direction == '做多' else -price_change_pct
                    order_amt = None
                    if idx_order_amt != -1 and idx_order_amt < len(row):
                        try:
                            order_amt = float(row[idx_order_amt])
                        except Exception:
                            order_amt = None
                    if order_amt is not None:
                        pnl_usdt = order_amt * (contract_ret_pct / 100.0)
            except Exception:
                pass

            def set_cell(idx_col, value_str):
                if idx_col == -1:
                    return
                if idx_col >= len(row):
                    row += [''] * (idx_col - len(row) + 1)
                row[idx_col] = value_str

            if price_change_pct is not None:
                set_cell(idx_price_change, f"{price_change_pct:.2f}")
            if contract_ret_pct is not None:
                set_cell(idx_contract_ret, f"{contract_ret_pct:.2f}")
            if pnl_usdt is not None:
                set_cell(idx_pnl, f"{pnl_usdt:.4f}")
            # 写回文件
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            return True
        except Exception:
            # 可能是并发写入，稍后重试
            time.sleep(0.2)
    return False


async def run_ws():
    sold_ids = set()  # 运行期去重，避免重复打印
    # 记录各仓位追踪状态：高/低、水位、激活类型与追踪幅度
    # {trade_id: {"high": float, "low": float, "activated": None|"weak"|"normal", "trail_pct": float, "entry_ts": int}}
    trail_state = {}

    while True:
        try:
            async with websockets.connect(WS_URL) as ws:
                print("=" * 80)
                print("卖出监听已连接 Binance 1m K线 (ETHUSDT)")
                print("目标: 做多上涨≥2.36% 或 做空下跌≥2.36% 打印仓位ID 卖出")
                print("=" * 80)
                print()

                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    if 'e' in data and data['e'] == 'kline':
                        k = data['k']
                        current_price = float(k['c'])  # 实时价格（k线的当前收盘）

                        # 刷新未平仓列表（允许买入端新增仓位后即时纳入追踪）
                        open_positions = load_open_positions(CSV_PATH)
                        if not open_positions:
                            continue

                        for trade_id, info in open_positions.items():
                            if trade_id in sold_ids:
                                continue

                            entry = info['entry_price']
                            direction = info['direction']
                            entry_time = info.get('entry_time') or ''

                            # 初始化追踪状态
                            state = trail_state.get(trade_id)
                            if state is None:
                                try:
                                    entry_ts = int(datetime.strptime(entry_time, '%Y-%m-%d %H:%M:%S').timestamp() * 1000) if entry_time else None
                                except Exception:
                                    entry_ts = None
                                state = {
                                    'high': entry,
                                    'low': entry,
                                    'activated': None,  # None | 'weak' | 'normal'
                                    'trail_pct': None,
                                    'entry_ts': entry_ts,
                                }
                                trail_state[trade_id] = state

                            # 更新持仓以来极值
                            if direction == '做多' and current_price > state['high']:
                                state['high'] = current_price
                            if direction == '做空' and current_price < state['low']:
                                state['low'] = current_price

                            # 估算持仓分钟数 -> bars（1m）
                            now_ts = int(k['T'])
                            bars_held = 0
                            if state['entry_ts'] is not None:
                                bars_held = max(0, (now_ts - state['entry_ts']) // 60000)

                            # 当前浮盈(价格%) 与 合约收益%
                            price_profit_pct = 0.0
                            if entry > 0:
                                if direction == '做多':
                                    price_profit_pct = (current_price - entry) / entry * 100.0
                                else:
                                    price_profit_pct = (entry - current_price) / entry * 100.0
                            contract_profit_pct = price_profit_pct * LEVERAGE

                            # 激活追踪（弱势优先）
                            if state['activated'] is None:
                                # 弱势：bars>30 且 合约收益 < 99%
                                if bars_held > 30 and contract_profit_pct < WEAK_CONTRACT_THRESHOLD:
                                    state['activated'] = 'weak'
                                    state['trail_pct'] = TRAIL_PCT_WEAK
                                    print(f"🔔 激活追踪[弱势] 仓位ID {trade_id} | bars {bars_held} | 合约收益 {contract_profit_pct:.2f}% < {WEAK_CONTRACT_THRESHOLD:.2f}% -> 6%追踪")
                                # 正常：bars>40 且 价格浮盈 ≥ 0.7071%
                                elif bars_held > 40 and price_profit_pct >= PRICE_PROFIT_GATE_PCT:
                                    state['activated'] = 'normal'
                                    state['trail_pct'] = TRAIL_PCT_NORMAL
                                    print(f"🔔 激活追踪[正常] 仓位ID {trade_id} | bars {bars_held} | 价格浮盈 {price_profit_pct:.4f}% ≥ {PRICE_PROFIT_GATE_PCT:.4f}% -> 8%追踪")

                            if direction == '做多':
                                if state['activated'] is not None:
                                    trail_pct = state['trail_pct']
                                    highest = state['high']
                                    trailing_price = highest * (1 - trail_pct)
                                    fixed_sl_price = entry * (1 - STOP_LOSS_PCT)
                                    effective_stop = max(trailing_price, fixed_sl_price)  # SL保护
                                    if current_price <= effective_stop:
                                        pct = (entry - current_price) / entry * 100
                                        print(f"📤 卖出(追踪止损): 仓位ID {trade_id} | 做多 | 入场 {entry:.2f} | 当前 {current_price:.2f} | 触发线 {effective_stop:.2f} | 回撤 {pct:.2f}%")
                                        updated = update_trade_as_closed(CSV_PATH, trade_id=trade_id, entry_price=entry, direction=direction,
                                                                         close_price=current_price, reason='追踪止损', pct=pct, close_ts_ms=now_ts)
                                        if updated:
                                            sold_ids.add(trade_id); continue
                                    # 未触发追踪 -> 检查固定TP
                                    if current_price >= entry * (1 + TAKE_PROFIT_PCT):
                                        pct = (current_price - entry) / entry * 100
                                        print(f"📤 卖出(止盈): 仓位ID {trade_id} | 做多 | 入场 {entry:.2f} | 当前 {current_price:.2f} | 涨幅 {pct:.2f}%")
                                        updated = update_trade_as_closed(CSV_PATH, trade_id=trade_id, entry_price=entry, direction=direction,
                                                                         close_price=current_price, reason='止盈', pct=pct, close_ts_ms=now_ts)
                                        if updated:
                                            sold_ids.add(trade_id); continue
                                # 未激活追踪：固定TP/SL
                                if current_price >= entry * (1 + TAKE_PROFIT_PCT):
                                    pct = (current_price - entry) / entry * 100
                                    print(f"📤 卖出(止盈): 仓位ID {trade_id} | 方向 做多 | 入场 {entry:.2f} | 当前 {current_price:.2f} | 涨幅 {pct:.2f}%")
                                    updated = update_trade_as_closed(CSV_PATH, trade_id=trade_id, entry_price=entry, direction=direction,
                                                                     close_price=current_price, reason='止盈', pct=pct, close_ts_ms=now_ts)
                                    if updated:
                                        sold_ids.add(trade_id); continue
                                if current_price <= entry * (1 - STOP_LOSS_PCT):
                                    pct = (entry - current_price) / entry * 100
                                    print(f"📤 卖出(止损): 仓位ID {trade_id} | 方向 做多 | 入场 {entry:.2f} | 当前 {current_price:.2f} | 回撤 {pct:.2f}%")
                                    updated = update_trade_as_closed(CSV_PATH, trade_id=trade_id, entry_price=entry, direction=direction,
                                                                     close_price=current_price, reason='止损', pct=pct, close_ts_ms=now_ts)
                                    if updated:
                                        sold_ids.add(trade_id); continue
                            elif direction == '做空':
                                if state['activated'] is not None:
                                    trail_pct = state['trail_pct']
                                    lowest = state['low']
                                    trailing_price = lowest * (1 + trail_pct)
                                    fixed_sl_price = entry * (1 + STOP_LOSS_PCT)
                                    effective_stop = min(trailing_price, fixed_sl_price)  # SL保护
                                    if current_price >= effective_stop:
                                        pct = (current_price - entry) / entry * 100
                                        print(f"📤 卖出(追踪止损): 仓位ID {trade_id} | 做空 | 入场 {entry:.2f} | 当前 {current_price:.2f} | 触发线 {effective_stop:.2f} | 反弹 {pct:.2f}%")
                                        updated = update_trade_as_closed(CSV_PATH, trade_id=trade_id, entry_price=entry, direction=direction,
                                                                         close_price=current_price, reason='追踪止损', pct=pct, close_ts_ms=now_ts)
                                        if updated:
                                            sold_ids.add(trade_id); continue
                                    if current_price <= entry * (1 - TAKE_PROFIT_PCT):
                                        pct = (entry - current_price) / entry * 100
                                        print(f"📤 卖出(止盈): 仓位ID {trade_id} | 做空 | 入场 {entry:.2f} | 当前 {current_price:.2f} | 跌幅 {pct:.2f}%")
                                        updated = update_trade_as_closed(CSV_PATH, trade_id=trade_id, entry_price=entry, direction=direction,
                                                                         close_price=current_price, reason='止盈', pct=pct, close_ts_ms=now_ts)
                                        if updated:
                                            sold_ids.add(trade_id); continue
                                if current_price <= entry * (1 - TAKE_PROFIT_PCT):
                                    pct = (entry - current_price) / entry * 100
                                    print(f"📤 卖出(止盈): 仓位ID {trade_id} | 方向 做空 | 入场 {entry:.2f} | 当前 {current_price:.2f} | 跌幅 {pct:.2f}%")
                                    updated = update_trade_as_closed(CSV_PATH, trade_id=trade_id, entry_price=entry, direction=direction,
                                                                     close_price=current_price, reason='止盈', pct=pct, close_ts_ms=now_ts)
                                    if updated:
                                        sold_ids.add(trade_id); continue
                                if current_price >= entry * (1 + STOP_LOSS_PCT):
                                    pct = (current_price - entry) / entry * 100
                                    print(f"📤 卖出(止损): 仓位ID {trade_id} | 方向 做空 | 入场 {entry:.2f} | 当前 {current_price:.2f} | 反弹 {pct:.2f}%")
                                    updated = update_trade_as_closed(CSV_PATH, trade_id=trade_id, entry_price=entry, direction=direction,
                                                                     close_price=current_price, reason='止损', pct=pct, close_ts_ms=now_ts)
                                    if updated:
                                        sold_ids.add(trade_id); continue
        except websockets.exceptions.ConnectionClosed:
            print("⚠ WebSocket连接断开，3秒后重连...")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"⚠ 发生异常: {e}")
            await asyncio.sleep(2)


if __name__ == '__main__':
    print("启动 卖出监听模块 (Binance ETHUSDT 1m)...")
    try:
        asyncio.run(run_ws())
    except KeyboardInterrupt:
        print("\n已停止")
