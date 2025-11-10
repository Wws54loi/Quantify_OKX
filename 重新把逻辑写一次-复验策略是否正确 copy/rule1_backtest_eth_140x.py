# -*- coding: utf-8 -*-
"""
Rule1 回测脚本（ETHUSDT 15m, 杠杆 140x）

数据源: 读取同目录下的 `ethusdt_15m_klines.json`（Binance 标准 kline 数组）。
使用最后 30000 根 K 线进行信号识别与回测。

策略要点:
1. K1: 15m 实体强度 |close-open|/open >= 0.21%
2. K2: 上/下影线突破 K1 高/低，且 K2 收盘仍回包在 K1 高低之间；
   同时 K2 实体与 K1 实体比值在 [0.5, 1.6] 内；
   方向: 若同时上下突破，先判 k2.low < k1.low 则做多，否则若 k2.high > k1.high 则做空。
3. 仓位(USDT):
   - K1 实体 >= 0.48% -> 4u
   - [0.30%, 0.48%) -> 1.6u
   - [0.21%, 0.30%) -> 1u
4. 止盈/止损（均为“合约收益”百分比，即已乘 140x 杠杆后的回报）:
   - 持仓 30 根内: SL=530%, TP=330%
   - 超过 30 根且浮盈 < TP 的 30%: 判为弱势，SL×0.85（缩紧 15%），并立刻启用 6% 追踪止损
   - 正常行情超过 40 根: 启用 8% 追踪止损
   - 超过 40 根: 固定 TP×0.9，SL×0.3（与追踪不叠加，追踪优先级更高）
5. 最多同时 4 笔持仓，满仓时跳过新信号。
6. 仅统计真正出场的订单（有 exit）。

输出:
- 终端简报: 总交易数、胜率、盈亏比、平均持仓、总盈亏、盈利率、跟踪止损激活/出场次数
- CSV: 每笔交易明细
- TXT: 文本日志，格式仿照示例

注: 追踪止损的 6%/8% 按价格百分比计算（非杠杆回报），参照样例日志推断。
"""
from __future__ import annotations
import os
import json
import csv
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Any
from datetime import datetime, timezone
import math
import argparse

# ------------------------- 配置参数 -------------------------
LEVERAGE = 140.0
K1_BODY_MIN = 0.0021  # 0.21%
SIZE_TIERS = [
    (0.0048, 4.0),    # >=0.48% -> 4u
    (0.0030, 1.6),    # [0.30, 0.48) -> 1.6u
    (0.0021, 1.0),    # [0.21, 0.30) -> 1u
]

TP_BASE = 330.0  # 合约收益 %
SL_BASE = 530.0  # 合约收益 %
WEAK_FLOATING_TP_RATIO = 0.30  # 浮盈 < TP*30%
WEAK_SL_TIGHTEN = 0.85        # SL 乘 0.85（缩紧 15%）
TRAIL_PCT_NORMAL = 0.08       # 价格 8% 追踪
TRAIL_PCT_WEAK = 0.06         # 价格 6% 追踪
MAX_HOLD_BARS_SLTP = 30
TRAIL_START_BARS = 40
POST40_TP_FACTOR = 0.9
POST40_SL_FACTOR = 0.3
MAX_CONCURRENT_POS = 4

CSV_NAME = "rule1_results_eth_140x.csv"
TXT_NAME = "rule1_results_eth_140x.txt"

# ------------------------- 工具函数 -------------------------

def ts_ms_to_str(ts_ms: int) -> str:
    # Binance ms -> local naive string
    return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def body_strength(o: float, c: float) -> float:
    if o <= 0:
        return 0.0
    return abs(c - o) / o


def leveraged_return_pct(entry: float, price: float, direction: str) -> float:
    """返回合约收益百分比（已乘杠杆）。正数为盈利，负数为亏损。"""
    if direction == 'long':
        raw = (price - entry) / entry
    else:
        raw = (entry - price) / entry
    return raw * LEVERAGE * 100.0


def pct_to_raw_move(pct_leveraged: float) -> float:
    """将合约收益百分比转换为基础价格变动比例（未乘杠杆）。
    例如 330% -> 0.023571... (在 140x 下)
    """
    return pct_leveraged / (LEVERAGE * 100.0)


# ------------------------- 数据结构 -------------------------
@dataclass
class KLine:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    close_time: int


@dataclass
class Position:
    id: int
    direction: str  # 'long' or 'short'
    entry_index: int
    entry_time: int
    entry_price: float
    size_usdt: float

    # 动态状态
    bars_held: int = 0
    highest: float = field(default_factory=lambda: -math.inf)
    lowest: float = field(default_factory=lambda: math.inf)
    weak: bool = False
    trail_active: bool = False
    trail_pct: float = 0.0
    trail_activated_index: Optional[int] = None

    # 退出
    exit_index: Optional[int] = None
    exit_time: Optional[int] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None

    # 统计字段
    contain_relation: bool = False  # 此策略固定 False

    def _current_fixed_thresholds(self) -> Tuple[float, float]:
        """返回当前固定 TP/SL 的合约收益百分比 (tp_pct, sl_pct)。"""
        tp = TP_BASE
        sl = SL_BASE
        if self.bars_held > TRAIL_START_BARS:
            tp *= POST40_TP_FACTOR
            sl *= POST40_SL_FACTOR
        elif self.bars_held > MAX_HOLD_BARS_SLTP:
            # 超过 30 但未超过 40，仅弱势会调整 SL
            pass
        if self.weak:
            sl *= WEAK_SL_TIGHTEN
        return tp, sl

    def _ensure_trailing(self, bar_index: int):
        # 弱势：立刻启用更紧 6% 追踪（替换默认），无需满足持仓根数与浮盈阈值
        if self.weak:
            if not self.trail_active or self.trail_pct != TRAIL_PCT_WEAK:
                self.trail_active = True
                self.trail_pct = TRAIL_PCT_WEAK
                self.trail_activated_index = bar_index
            return

        # 正常：超过40根后才允许激活，且达到止盈目标30%的浮盈后再激活
        # 止盈目标的30%（价格维度）
        min_profit_raw = pct_to_raw_move(TP_BASE) * WEAK_FLOATING_TP_RATIO
        if self.bars_held > TRAIL_START_BARS and not self.trail_active:
            if self.direction == 'long':
                achieved = (self.highest - self.entry_price) / self.entry_price if self.highest > 0 else 0.0
            else:
                achieved = (self.entry_price - self.lowest) / self.entry_price if self.lowest < math.inf else 0.0
            if achieved >= min_profit_raw:
                self.trail_active = True
                self.trail_pct = TRAIL_PCT_NORMAL
                self.trail_activated_index = bar_index

    def update_extremes(self, bar: KLine):
        self.highest = max(self.highest, bar.high)
        self.lowest = min(self.lowest, bar.low)

    def maybe_mark_weak(self, last_price: float):
        if self.bars_held > MAX_HOLD_BARS_SLTP and not self.weak:
            tp_pct, _ = self._current_fixed_thresholds()
            cur_lr = leveraged_return_pct(self.entry_price, last_price, self.direction)
            if cur_lr < tp_pct * WEAK_FLOATING_TP_RATIO:
                self.weak = True

    def compute_trail_price(self) -> Optional[float]:
        if not self.trail_active or self.trail_pct <= 0:
            return None
        if self.direction == 'long':
            return self.highest * (1.0 - self.trail_pct)
        else:
            return self.lowest * (1.0 + self.trail_pct)

    def compute_fixed_prices(self) -> Tuple[float, float]:
        tp_pct, sl_pct = self._current_fixed_thresholds()
        tp_raw = pct_to_raw_move(tp_pct)
        sl_raw = pct_to_raw_move(sl_pct)
        if self.direction == 'long':
            tp_price = self.entry_price * (1.0 + tp_raw)
            sl_price = self.entry_price * (1.0 - sl_raw)
        else:
            tp_price = self.entry_price * (1.0 - tp_raw)
            sl_price = self.entry_price * (1.0 + sl_raw)
        return tp_price, sl_price

    def try_exit_on_bar(self, idx: int, bar: KLine) -> bool:
        """按优先级检查出场。返回是否出场。优先级: 追踪 > 固定SL/TP。
        使用 OHLC 近似顺序：
          - Long: 先看 trail/SL 是否触及 low，再看 TP 是否触及 high
          - Short: 先看 trail/SL 是否触及 high，再看 TP 是否触及 low
        """
        # 先更新极值
        self.update_extremes(bar)

        # 弱势判定（使用上一根收盘/当前 close）
        self.maybe_mark_weak(bar.close)
        # 确认是否需要激活追踪
        self._ensure_trailing(idx)

        # 计算追踪价与固定价
        trail_price = self.compute_trail_price()
        tp_price, sl_price = self.compute_fixed_prices()

        # 1) 追踪优先（并对亏损做固定止损上限保护，不叠加）
        if trail_price is not None:
            if self.direction == 'long':
                if bar.low <= trail_price:
                    # 以追踪价出场
                    actual_exit = trail_price
                    # 计算价格维度的固定止损阈值
                    _, sl_price = self.compute_fixed_prices()
                    # 若追踪导致的亏损超过固定SL，则强制以固定SL价出场
                    if actual_exit < sl_price:
                        actual_exit = sl_price
                        reason = 'SL'
                    else:
                        reason = 'TRAIL_%.0f' % (self.trail_pct * 100)
                    self.exit_index = idx
                    self.exit_time = bar.close_time
                    self.exit_price = actual_exit
                    self.exit_reason = reason
                    return True
            else:
                if bar.high >= trail_price:
                    actual_exit = trail_price
                    _, sl_price = self.compute_fixed_prices()
                    if actual_exit > sl_price:
                        actual_exit = sl_price
                        reason = 'SL'
                    else:
                        reason = 'TRAIL_%.0f' % (self.trail_pct * 100)
                    self.exit_index = idx
                    self.exit_time = bar.close_time
                    self.exit_price = actual_exit
                    self.exit_reason = reason
                    return True

        # 2) 固定 SL/TP（不与追踪叠加）
        if self.direction == 'long':
            # 先看 SL
            if bar.low <= sl_price:
                self.exit_index = idx
                self.exit_time = bar.close_time
                self.exit_price = sl_price
                self.exit_reason = 'SL'
                return True
            # 再看 TP
            if bar.high >= tp_price:
                self.exit_index = idx
                self.exit_time = bar.close_time
                self.exit_price = tp_price
                self.exit_reason = 'TP'
                return True
        else:
            # short: 先 SL
            if bar.high >= sl_price:
                self.exit_index = idx
                self.exit_time = bar.close_time
                self.exit_price = sl_price
                self.exit_reason = 'SL'
                return True
            # 再 TP
            if bar.low <= tp_price:
                self.exit_index = idx
                self.exit_time = bar.close_time
                self.exit_price = tp_price
                self.exit_reason = 'TP'
                return True

        # 未出场则计时+1
        self.bars_held += 1
        return False

    def pnl_usdt(self) -> float:
        if self.exit_price is None:
            return 0.0
        lr = leveraged_return_pct(self.entry_price, self.exit_price, self.direction)
        return self.size_usdt * (lr / 100.0)

    def contract_return_pct(self) -> float:
        if self.exit_price is None:
            return 0.0
        return leveraged_return_pct(self.entry_price, self.exit_price, self.direction)


# ------------------------- 策略逻辑 -------------------------

def parse_klines(raw: List[List[Any]], limit: int = 30000) -> List[KLine]:
    data = raw[-limit:] if limit and len(raw) > limit else raw
    out: List[KLine] = []
    for row in data:
        # 兼容: [openTime, open, high, low, close, volume, closeTime, ...]
        try:
            otime = int(row[0])
            o = float(row[1]); h = float(row[2]); l = float(row[3]); c = float(row[4])
            ctime = int(row[6]) if len(row) > 6 else (otime + 15*60*1000)
        except Exception:
            # 尝试字典结构
            otime = int(row.get('openTime'))
            o = float(row.get('open'))
            h = float(row.get('high'))
            l = float(row.get('low'))
            c = float(row.get('close'))
            ctime = int(row.get('closeTime', otime + 15*60*1000))
        out.append(KLine(otime, o, h, l, c, ctime))
    return out


def k1_k2_signal(k1: KLine, k2: KLine) -> Tuple[bool, Optional[str]]:
    # K1 条件: 实体强度 >= 0.21%
    k1_body = body_strength(k1.open, k1.close)
    if k1_body < K1_BODY_MIN:
        return False, None

    # K2 条件：影线突破 + 收盘在 K1 内 + 实体比值
    break_up = k2.high > k1.high
    break_down = k2.low < k1.low
    close_inside = (k2.close <= k1.high and k2.close >= k1.low)

    k2_body = body_strength(k2.open, k2.close)
    body_ratio = (k2_body / k1_body) if k1_body > 0 else 0
    ratio_ok = (0.5 <= body_ratio <= 1.6)

    if (break_up or break_down) and close_inside and ratio_ok:
        # 方向判定
        if break_up and break_down:
            if k2.low < k1.low:
                return True, 'long'
            elif k2.high > k1.high:
                return True, 'short'
            else:
                return False, None
        elif break_down:
            return True, 'long'
        elif break_up:
            return True, 'short'
    return False, None


def decide_size(k1: KLine) -> float:
    bs = body_strength(k1.open, k1.close)
    for thr, size in SIZE_TIERS:
        if bs >= thr:
            return size
    return 0.0


def backtest(klines: List[KLine], quick: bool = False) -> Tuple[List[Position], float, dict]:
    positions: List[Position] = []
    open_positions: List[Position] = []
    trade_id = 0

    start_idx = 1  # 使用 k1= i-1, k2 = i
    end_idx = len(klines)
    if quick:
        # 仅跑前 2000 根 K2，约 2001 根数据
        end_idx = min(len(klines), 2001)

    for i in range(start_idx, end_idx):
        k1 = klines[i-1]
        k2 = klines[i]

        # 1) 先推进所有在仓单
        still_open: List[Position] = []
        for pos in open_positions:
            closed = pos.try_exit_on_bar(i, k2)
            if closed:
                positions.append(pos)
            else:
                still_open.append(pos)
        open_positions = still_open

        # 2) 检测新信号（满仓跳过）
        if len(open_positions) < MAX_CONCURRENT_POS:
            ok, direction = k1_k2_signal(k1, k2)
            if ok and direction is not None:
                size = decide_size(k1)
                if size > 0:
                    trade_id += 1
                    pos = Position(
                        id=trade_id,
                        direction=direction,
                        entry_index=i,
                        entry_time=k2.close_time,
                        entry_price=k2.close,
                        size_usdt=size,
                    )
                    # 初始化极值
                    pos.highest = k2.close
                    pos.lowest = k2.close
                    # bars_held 从 0 开始，下一根再 +1
                    open_positions.append(pos)

    # 最终: 将未出场的不计入统计
    # positions 已包含所有已平仓单
    # 统计
    total_closed = len(positions)
    wins = 0
    losses = 0
    win_sum = 0.0
    loss_sum = 0.0
    bars_sum = 0
    trail_activated = 0
    trail_exited = 0

    for p in positions:
        pnl = p.pnl_usdt()
        if pnl >= 0:
            wins += 1
            win_sum += pnl
        else:
            losses += 1
            loss_sum += -pnl
        # 使用 exit_index-entry_index+1 作为持仓根数，避免计数偏差
        if p.exit_index is not None and p.entry_index is not None:
            held = max(0, p.exit_index - p.entry_index + 1)
        else:
            held = p.bars_held
        bars_sum += held
        if p.trail_activated_index is not None:
            trail_activated += 1
        if p.exit_reason and p.exit_reason.startswith('TRAIL'):
            trail_exited += 1

    win_rate = (wins / total_closed * 100.0) if total_closed > 0 else 0.0
    avg_hold = (bars_sum / total_closed) if total_closed > 0 else 0.0
    avg_win = (win_sum / wins) if wins > 0 else 0.0
    avg_loss = (loss_sum / losses) if losses > 0 else 0.0
    rr = (avg_win / avg_loss) if avg_loss > 0 else 0.0
    total_pnl = win_sum - loss_sum
    invested = sum(p.size_usdt for p in positions)
    roi = (total_pnl / invested * 100.0) if invested > 0 else 0.0

    stats = dict(
        total=total_closed,
        win_rate=win_rate,
        rr=rr,
        avg_hold=avg_hold,
        total_pnl=total_pnl,
        roi=roi,
        trail_activated=trail_activated,
        trail_exited=trail_exited,
    )

    return positions, total_pnl, stats


def write_csv_txt(out_dir: str, klines: List[KLine], positions: List[Position]):
    csv_path = os.path.join(out_dir, CSV_NAME)
    txt_path = os.path.join(out_dir, TXT_NAME)

    # CSV
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow([
            'trade_id', 'strategy', 'contain', 'direction',
            'entry_time', 'entry_price', 'exit_time', 'exit_price',
            'bars_held', 'price_change_%', 'contract_return_%', 'pnl_usdt', 'cum_pnl_usdt',
            'trailing_activated', 'weak', 'highest', 'lowest', 'trail_price_at_exit',
            'k1_open','k1_high','k1_low','k1_close','k2_open','k2_high','k2_low','k2_close'
        ])
        cum = 0.0
        for p in positions:
            # 获取入场时刻的 k1/k2 以便记录
            i = p.entry_index
            k1 = klines[i-1]
            k2 = klines[i]
            lr = p.contract_return_pct()
            pnl = p.pnl_usdt()
            cum += pnl
            price_change = (p.exit_price - p.entry_price)/p.entry_price*100.0 if p.direction=='long' else (p.entry_price - p.exit_price)/p.entry_price*100.0

            trail_price_exit = ''
            if p.exit_reason and p.exit_reason.startswith('TRAIL'):
                # 复算当时 trail 价
                tprice = p.compute_trail_price()
                trail_price_exit = f"{tprice:.2f}" if tprice else ''

            w.writerow([
                p.id, 'rule1', '否', '做多' if p.direction=='long' else '做空',
                ts_ms_to_str(p.entry_time), f"{p.entry_price:.2f}", ts_ms_to_str(p.exit_time) if p.exit_time else '', f"{(p.exit_price or 0):.2f}",
                p.bars_held, f"{price_change:.3f}", f"{lr:.2f}", f"{pnl:.4f}", f"{cum:.4f}",
                '是' if p.trail_activated_index is not None else '否', '是' if p.weak else '否', f"{p.highest:.2f}", f"{p.lowest:.2f}", trail_price_exit,
                f"{k1.open:.2f}", f"{k1.high:.2f}", f"{k1.low:.2f}", f"{k1.close:.2f}", f"{k2.open:.2f}", f"{k2.high:.2f}", f"{k2.low:.2f}", f"{k2.close:.2f}"
            ])

    # TXT（仿样例）
    with open(txt_path, 'w', encoding='utf-8') as f:
        cum = 0.0
        for p in positions:
            lr = p.contract_return_pct()
            pnl = p.pnl_usdt()
            cum += pnl
            k1 = klines[p.entry_index-1]
            k2 = klines[p.entry_index]
            outcome = '止盈' if pnl >= 0 else '止损'
            direction_cn = '做多' if p.direction=='long' else '做空'
            f.write(f"交易 #{p.id} - {outcome} ({direction_cn})\n")
            f.write(f"  策略类型: rule1\n")
            f.write(f"  是否包含关系: 否\n")
            f.write(f"  交易方向: {direction_cn}\n")
            f.write(f"  入场时间: {ts_ms_to_str(p.entry_time)}\n")
            f.write(f"  入场价格: {p.entry_price:.2f} USDT\n")
            f.write(f"  出场时间: {ts_ms_to_str(p.exit_time)}\n")
            f.write(f"  出场价格: {p.exit_price:.2f} USDT\n")
            f.write(f"  持仓时长: {p.bars_held}根K线 ({p.bars_held*15}分钟)\n")
            price_change = (p.exit_price - p.entry_price)/p.entry_price*100.0 if p.direction=='long' else (p.entry_price - p.exit_price)/p.entry_price*100.0
            f.write(f"  价格变动: {price_change:.3f}%\n")
            f.write(f"  合约收益: {lr:.2f}%\n")
            f.write(f"  本次盈亏: {p.pnl_usdt():+.4f} USDT\n")
            f.write(f"  累计盈亏: {cum:+.4f} USDT\n")
            f.write(f"  跟踪止损: {'已激活' if p.trail_activated_index is not None else '未激活'}\n")
            f.write(f"  弱势收紧: {'是' if p.weak else '否'}\n")
            if p.direction=='long':
                f.write(f"  最高价: {p.highest:.2f} USDT\n")
            else:
                f.write(f"  最低价: {p.lowest:.2f} USDT\n")
            if p.exit_reason and p.exit_reason.startswith('TRAIL'):
                tprice = p.compute_trail_price()
                if tprice is not None:
                    f.write(f"  跟踪止损价: {tprice:.2f} USDT\n")
            f.write("  \n")
            f.write(f"  K1 - 开:{k1.open:.2f} 高:{k1.high:.2f} 低:{k1.low:.2f} 收:{k1.close:.2f}\n")
            f.write(f"  K2 - 开:{k2.open:.2f} 高:{k2.high:.2f} 低:{k2.low:.2f} 收:{k2.close:.2f}\n")
            f.write("-"*80 + "\n")

    return csv_path, txt_path


def load_json(path: str) -> List[List[Any]]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--quick', action='store_true', help='仅快速验证（~2000根）')
    parser.add_argument('--limit', type=int, default=30000, help='使用最近N根K线')
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, 'ethusdt_15m_klines.json')

    raw = load_json(json_path)
    kl = parse_klines(raw, limit=args.limit)

    positions, total_pnl, stats = backtest(kl, quick=args.quick)

    # 输出文件
    csv_path, txt_path = write_csv_txt(base_dir, kl, positions)

    # 终端简报
    print("\n===== 回测简报 (rule1, ETH 15m, 140x) =====")
    print(f"交易数: {stats['total']}")
    print(f"胜率: {stats['win_rate']:.2f}%")
    print(f"盈亏比: {stats['rr']:.2f}")
    print(f"平均持仓: {stats['avg_hold']:.2f} 根")
    print(f"总盈亏: {stats['total_pnl']:+.4f} USDT")
    print(f"盈利率: {stats['roi']:.2f}% (以总开仓金额为分母)")
    print(f"跟踪止损: 激活 {stats['trail_activated']} 次 / 出场 {stats['trail_exited']} 次")
    print(f"CSV: {csv_path}")
    print(f"TXT: {txt_path}")


if __name__ == '__main__':
    main()
