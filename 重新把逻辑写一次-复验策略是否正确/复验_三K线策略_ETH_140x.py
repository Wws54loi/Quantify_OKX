"""复验 三K线策略 (ETH 15m, 杠杆140x)

目标:
    使用本地 `ethusdt_15m_klines.json` (若不足或为空自动向币安补抓至30000根) 回测以下规则:

入场定义:
  1. k1: 15m K线开收涨跌幅 >= 0.21% (绝对值)
  2. k2: 上影线或下影线突破 k1 的最高或最低价 (二选一, 不能同时突破) 且 k2 实体仍完全位于 k1 的高低价区间内
  3. k2 实体 / k1 实体 比值在 0.5 - 1.6 之间
     - 仅下破成立 => 做多 (预期反弹)  仅上破成立 => 做空 (预期回落)  双破视为无效
  4. 头寸规模随 k1 实体百分比(开收差 / 开盘价):
        >=0.48% : 4 USDT 保证金
        >=0.30% 且 <0.48% : 1.6 USDT
        >=0.21% 且 <0.30% : 1.0 USDT

初始风险/收益 (均为合约层面杠杆后的百分比):
    止盈 330%  止损 530%  (换算为现货价格百分比 = 目标 ÷ 140)

持仓动态规则 (按持仓经过的 bar 数, bar = 15m):
  A. 持仓 <=30 根: 使用初始 TP/SL。
  B. 超过30根后若当前浮盈 < TP目标的30% => "弱势持仓":
        - 固定止盈不变 (330%)
        - 固定止损收紧 15% -> 530% * 0.85 = 450.5%
        - 若跟踪止损尚未启动, 立即以 6% (合约回撤百分比) 启动跟踪止损 (替代默认 8%)。
  C. 未进入弱势逻辑且达到第40根 => 启动默认 8% 跟踪止损。
  D. 持仓 >40 根 (首次超过即刻生效): 应用 "区间止损/止盈缩放":
        TP = 330% * 0.9 = 297% ; SL = 530% * 0.3 = 159%
        - 若之前存在弱势紧缩或跟踪, 本缩放在其基础上覆盖固定 TP/SL (跟踪保持激活)。
  E. 互斥 & 优先级: 跟踪止损激活后优先判定回撤是否达到阈值; 固定 SL 仅在未触发跟踪或回撤未满足时检查。
     盈利条件始终优先于止损/跟踪 (单根同时命中时按 TP 处理)。

并发持仓:
    最多同时 4 笔。检测到新信号且已满则跳过该信号。
    信号扫描逐根推进 (滑动窗口 k1,k2) 同时对所有活跃持仓更新退出条件。

统计输出 (仅已退出持仓):
    终端: 总交易数, 胜率, 盈亏比(Profit Factor), 平均持仓bars, 总盈亏USDT, 跟踪止损激活次数, 跟踪止损出场次数。
    CSV: 每笔交易(入场/出场时间, 方向, 头寸资金, 入场价, 出场价, 杠杆收益%, 实际盈亏USDT, 持仓bars, 是否弱势, 是否触发跟踪, 是否跟踪出场, 出场类型, k1实体%, k2实体比值)。
    TXT: 可读逐笔日志。

实现假设(歧义解释):
  - "止损倍率缩紧15%" 解释为乘以 (1-0.15)。
  - 跟踪止损百分比为合约层面的回撤百分比 (即杠杆后的浮盈峰值回撤幅度)。换算到现货价格回撤 = 跟踪百分比 ÷ 杠杆。
  - 弱势逻辑与40根区间缩放可同时发生; 缩放覆盖固定 TP/SL 数值, 跟踪参数保持其已激活的更紧版本 (6% 或 8%)。
  - 胜率定义: 盈利 USDT > 0 为胜 (含跟踪止损正收益)。
  - 盈亏比 Profit Factor = 总盈利(USDT)/总亏损绝对值(USDT)。无亏损则为 inf。
  - 若数据文件少于需求(或为空)则向币安抓取最新 30000 根, 不做去重拼接历史; 文件中假定格式为标准币安 klines 数组。
  - 双破 (同时上影与下影越界) 视为无效信号。
  - 价格滑点忽略, 入场价取 k2 收盘价。
  - 跟踪止损基准为激活后最高(做多)/最低(做空)的合约收益百分比峰值。

后续潜在改进 (未实现):
  - 满仓时合并方向一致持仓 (保证金翻倍分段止盈)。
  - 手续费滑点影响。
  - 资金复利或动态保证金调整。

使用: 直接运行本文件。生成 `三K线复验结果_ETH_时间戳.csv` 与同名 .txt 日志。
"""

from __future__ import annotations
import json
import os
import csv
import time
import math
import urllib.request
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime

BINANCE_BASE = "https://api.binance.com"
SYMBOL = "ETHUSDT"
INTERVAL = "15m"
LEVERAGE = 140  # 固定杠杆
TARGET_LEVERAGE_PCT = 330.0  # 初始止盈(合约收益%)
STOP_LEVERAGE_PCT = 530.0    # 初始止损(合约亏损%)
WEAK_STOP_TIGHTEN_RATIO = 0.85  # 弱势后止损缩紧系数
WEAK_TRAILING_PCT = 6.0     # 弱势跟踪(合约回撤%)
DEFAULT_TRAILING_PCT = 8.0  # 正常跟踪(合约回撤%)
OVER40_TP_RATIO = 0.9       # >40根 TP 缩放
OVER40_SL_RATIO = 0.3       # >40根 SL 缩放
MAX_CONCURRENT_POS = 4
MAX_BARS_FETCH = 30000
DATA_FILE = os.path.join(os.path.dirname(__file__), "ethusdt_15m_klines.json")


def fetch_klines(symbol: str = SYMBOL, interval: str = INTERVAL, limit: int = MAX_BARS_FETCH) -> List[List[Any]]:
    """分页抓取币安K线 (最新向后)。"""
    all_klines: List[List[Any]] = []
    remaining = limit
    end_time = None
    while remaining > 0:
        batch = min(remaining, 1000)
        url = f"{BINANCE_BASE}/api/v3/klines?symbol={symbol}&interval={interval}&limit={batch}"
        if end_time:
            url += f"&endTime={end_time}"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"抓取失败: {e}")
            break
        if not data:
            break
        all_klines = data + all_klines
        end_time = data[0][0] - 1
        remaining -= len(data)
        if len(data) < batch:
            break
        time.sleep(0.15)
    return all_klines


@dataclass
class KLine:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @classmethod
    def from_raw(cls, raw: List[Any]) -> "KLine":
        return cls(ts=int(raw[0]), open=float(raw[1]), high=float(raw[2]), low=float(raw[3]), close=float(raw[4]), volume=float(raw[5]))

    @property
    def body_high(self) -> float:
        return max(self.open, self.close)

    @property
    def body_low(self) -> float:
        return min(self.open, self.close)

    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)

    @property
    def body_pct(self) -> float:
        return self.body_size / self.open  # 小数

    def dt(self) -> str:
        return datetime.fromtimestamp(self.ts/1000).strftime('%Y-%m-%d %H:%M')


class Position:
    def __init__(self, direction: str, entry_price: float, size_usdt: float, entry_index: int, k1_body_pct: float, k2_body_ratio: float, entry_time_ms: int):
        self.direction = direction  # long / short
        self.entry_price = entry_price
        self.size_usdt = size_usdt
        self.entry_index = entry_index
        self.k1_body_pct = k1_body_pct
        self.k2_body_ratio = k2_body_ratio
        self.entry_time_ms = entry_time_ms
        self.exit_price: Optional[float] = None
        self.exit_index: Optional[int] = None
        self.exit_time_ms: Optional[int] = None
        self.exit_type: Optional[str] = None
        self.leveraged_return_pct: Optional[float] = None  # 合约收益(正负)
        self.pnl_usdt: Optional[float] = None
        self.holding_bars: Optional[int] = None
        self.weak: bool = False
        self.trailing_activated: bool = False
        self.trailing_exit: bool = False
        self.trailing_pct: Optional[float] = None
        self.trailing_peak: Optional[float] = None  # 合约收益峰值百分比

    def mark_exit(self, price: float, index: int, ts: int, exit_type: str, leveraged_return_pct: float):
        self.exit_price = price
        self.exit_index = index
        self.exit_time_ms = ts
        self.exit_type = exit_type
        self.leveraged_return_pct = leveraged_return_pct
        self.pnl_usdt = self.size_usdt * leveraged_return_pct / 100.0
        self.holding_bars = index - self.entry_index
        if exit_type == 'trailing_stop':
            self.trailing_exit = True


def detect_signal(k1: KLine, k2: KLine) -> Optional[Dict[str, Any]]:
    # k1 body pct >= 0.21%
    if k1.body_pct < 0.0021:
        return None
    # k2 body ratio
    if k1.body_size == 0:
        return None
    k2_body_ratio = k2.body_size / k1.body_size
    if k2_body_ratio < 0.5 or k2_body_ratio > 1.6:
        return None
    # body containment
    if not (k2.body_high <= k1.high and k2.body_low >= k1.low):
        return None
    lower_break = k2.low < k1.low
    upper_break = k2.high > k1.high
    # 双破无效
    if lower_break and upper_break:
        return None
    if lower_break:
        direction = 'long'
    elif upper_break:
        direction = 'short'
    else:
        return None
    # position sizing by k1 body pct
    bp = k1.body_pct
    if bp >= 0.0048:
        size = 4.0
    elif bp >= 0.0030:
        size = 1.6
    else:  # >=0.0021
        size = 1.0
    return {
        'direction': direction,
        'entry_price': k2.close,
        'size_usdt': size,
        'k1_body_pct': bp,
        'k2_body_ratio': k2_body_ratio,
        'entry_time_ms': k2.ts
    }


def compute_leveraged_pct(direction: str, entry_price: float, k: KLine) -> float:
    if direction == 'long':
        price_return = (k.close - entry_price) / entry_price
    else:
        price_return = (entry_price - k.close) / entry_price
    return price_return * LEVERAGE * 100.0  # 合约收益%

def compute_extremes_leveraged(direction: str, entry_price: float, k: KLine) -> Dict[str, float]:
    if direction == 'long':
        high_ret = (k.high - entry_price) / entry_price
        low_ret = (k.low - entry_price) / entry_price
    else:
        high_ret = (entry_price - k.low) / entry_price  # 有利方向 (做空 高点是 entry_price - low?) 需用最大收益: entry_price - low
        low_ret = (entry_price - k.high) / entry_price  # 不利方向
    return {
        'favorable_pct': (high_ret if direction == 'long' else high_ret) * LEVERAGE * 100.0,
        'adverse_pct': (low_ret if direction == 'long' else low_ret) * LEVERAGE * 100.0,
    }


def backtest(klines: List[KLine]) -> Dict[str, Any]:
    positions: List[Position] = []
    active: List[Position] = []
    trailing_activation_count = 0
    trailing_exit_count = 0

    # Pre-computed percentages (price move thresholds) not needed; use leveraged directly
    base_tp = TARGET_LEVERAGE_PCT
    base_sl = STOP_LEVERAGE_PCT

    for i in range(len(klines)-1):
        k1 = klines[i]
        k2 = klines[i+1]

        # 更新所有活跃持仓出场逻辑 (使用 k2 作为当前完成的bar close 用于判断)
        for pos in list(active):
            current_index = i+1  # k2 index
            k_current = k2
            holding_bars = current_index - pos.entry_index
            # 合约收益(收盘)
            current_ret = compute_leveraged_pct(pos.direction, pos.entry_price, k_current)
            extremes = compute_extremes_leveraged(pos.direction, pos.entry_price, k_current)
            favorable_peak_candidate = extremes['favorable_pct']

            # 动态阈值复制
            tp = base_tp
            sl = base_sl

            # >40 bars 缩放固定 TP/SL
            if holding_bars > 40:
                tp = tp * OVER40_TP_RATIO
                sl = sl * OVER40_SL_RATIO

            # 超过30 bars 检查弱势
            weak = False
            if holding_bars > 30 and current_ret < base_tp * 0.30 and pos.trailing_activated is False:
                weak = True
                pos.weak = True
                sl = base_sl * WEAK_STOP_TIGHTEN_RATIO  # 收紧
                # 弱势立即激活更紧跟踪
                pos.trailing_activated = True
                pos.trailing_pct = WEAK_TRAILING_PCT
                pos.trailing_peak = favorable_peak_candidate
                trailing_activation_count += 1

            # 正常40 bars激活跟踪 (若未弱势且还没激活)
            if holding_bars >= 40 and not pos.trailing_activated:
                pos.trailing_activated = True
                pos.trailing_pct = DEFAULT_TRAILING_PCT
                pos.trailing_peak = favorable_peak_candidate
                trailing_activation_count += 1

            # 更新峰值 (激活后才跟踪)
            if pos.trailing_activated:
                if pos.trailing_peak is None or favorable_peak_candidate > pos.trailing_peak:
                    pos.trailing_peak = favorable_peak_candidate
                # 回撤幅度
                drawdown = pos.trailing_peak - current_ret
            else:
                drawdown = 0.0

            # 优先顺序: TP (使用 favorable extremes) -> Trailing -> 固定 SL (使用 adverse extremes)
            # 使用极值判断是否触及
            favorable_hit = extremes['favorable_pct'] >= tp
            adverse_hit = extremes['adverse_pct'] <= -sl  # adverse_pct 为负数 (long 时为负数, short 时为负数)

            # Trailing 触发条件 (仅在激活后且回撤 >= trailing_pct 且当前收益>0)
            trailing_hit = False
            if pos.trailing_activated and pos.trailing_peak is not None and current_ret > 0:
                trailing_hit = drawdown >= pos.trailing_pct

            if favorable_hit:
                pos.mark_exit(price=pos.entry_price * (1 + tp/LEVERAGE/100.0) if pos.direction=='long' else pos.entry_price * (1 - tp/LEVERAGE/100.0),
                              index=current_index, ts=k_current.ts, exit_type='take_profit', leveraged_return_pct=tp)
                active.remove(pos)
                positions.append(pos)
                continue
            if trailing_hit:
                pos.mark_exit(price=k_current.close, index=current_index, ts=k_current.ts, exit_type='trailing_stop', leveraged_return_pct=current_ret)
                trailing_exit_count += 1
                active.remove(pos)
                positions.append(pos)
                continue
            if adverse_hit:
                pos.mark_exit(price=pos.entry_price * (1 - sl/LEVERAGE/100.0) if pos.direction=='long' else pos.entry_price * (1 + sl/LEVERAGE/100.0),
                              index=current_index, ts=k_current.ts, exit_type='stop_loss', leveraged_return_pct=-sl)
                active.remove(pos)
                positions.append(pos)
                continue

        # 开仓信号检测 (i 与 i+1 组成 k1/k2) 仅当还存在第二根 (已保证)
        if len(active) < MAX_CONCURRENT_POS:
            sig = detect_signal(k1, k2)
            if sig:
                pos = Position(direction=sig['direction'], entry_price=sig['entry_price'], size_usdt=sig['size_usdt'],
                                entry_index=i+1, k1_body_pct=sig['k1_body_pct'], k2_body_ratio=sig['k2_body_ratio'], entry_time_ms=sig['entry_time_ms'])
                active.append(pos)

    # 未退出的持仓不计入统计
    completed = [p for p in positions if p.exit_index is not None]

    wins = sum(1 for p in completed if p.pnl_usdt and p.pnl_usdt > 0)
    losses = sum(1 for p in completed if p.pnl_usdt and p.pnl_usdt <= 0)
    total_trades = len(completed)
    total_profit = sum(p.pnl_usdt for p in completed if p.pnl_usdt and p.pnl_usdt > 0)
    total_loss = sum(-p.pnl_usdt for p in completed if p.pnl_usdt and p.pnl_usdt <= 0)
    profit_factor = (total_profit/total_loss) if total_loss > 0 else float('inf')
    avg_holding = (sum(p.holding_bars for p in completed)/total_trades) if total_trades else 0
    total_pnl = total_profit - total_loss

    return {
        'positions': completed,
        'summary': {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate_pct': (wins/total_trades*100.0) if total_trades else 0.0,
            'profit_factor': profit_factor,
            'avg_holding_bars': avg_holding,
            'total_pnl_usdt': total_pnl,
            'trailing_activation_count': trailing_activation_count,
            'trailing_exit_count': trailing_exit_count
        }
    }


def load_or_fetch_data() -> List[KLine]:
    raw: Optional[List[List[Any]]] = None
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            if not isinstance(raw, list) or (raw and not isinstance(raw[0], list)):
                print("数据格式异常, 重新抓取...")
                raw = None
        except Exception as e:
            print(f"读取本地数据失败: {e}")
            raw = None
    if raw is None or len(raw) < 100:  # 视为不可用
        print("开始抓取币安数据 (ETH 15m) ...")
        raw = fetch_klines(limit=MAX_BARS_FETCH)
        print(f"抓取完成: {len(raw)} 根")
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(raw, f)
            print("已写入本地缓存.")
        except Exception as e:
            print(f"缓存写入失败: {e}")
    klines = [KLine.from_raw(r) for r in raw]
    return klines


def export_results(result: Dict[str, Any]):
    positions: List[Position] = result['positions']
    summary: Dict[str, Any] = result['summary']
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_name = f"三K线复验结果_ETH_{timestamp}.csv"
    txt_name = f"三K线复验结果_ETH_{timestamp}.txt"

    # CSV
    if positions:
        with open(csv_name, 'w', newline='', encoding='utf-8-sig') as f:
            fieldnames = [
                'entry_time','exit_time','direction','size_usdt','entry_price','exit_price','leveraged_return_pct','pnl_usdt','holding_bars',
                'weak','trailing_activated','trailing_exit','exit_type','k1_body_pct%','k2_body_ratio'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for p in positions:
                writer.writerow({
                    'entry_time': datetime.fromtimestamp(p.entry_time_ms/1000).strftime('%Y-%m-%d %H:%M'),
                    'exit_time': datetime.fromtimestamp(p.exit_time_ms/1000).strftime('%Y-%m-%d %H:%M') if p.exit_time_ms else '',
                    'direction': p.direction,
                    'size_usdt': f"{p.size_usdt:.2f}",
                    'entry_price': f"{p.entry_price:.4f}",
                    'exit_price': f"{p.exit_price:.4f}" if p.exit_price else '',
                    'leveraged_return_pct': f"{p.leveraged_return_pct:.2f}" if p.leveraged_return_pct is not None else '',
                    'pnl_usdt': f"{p.pnl_usdt:.4f}" if p.pnl_usdt is not None else '',
                    'holding_bars': p.holding_bars if p.holding_bars is not None else '',
                    'weak': int(p.weak),
                    'trailing_activated': int(p.trailing_activated),
                    'trailing_exit': int(p.trailing_exit),
                    'exit_type': p.exit_type or '',
                    'k1_body_pct%': f"{p.k1_body_pct*100:.4f}",
                    'k2_body_ratio': f"{p.k2_body_ratio:.4f}",
                })
        print(f"CSV已输出: {csv_name}")
    else:
        print("无已完成持仓, 未生成CSV。")

    # TXT 日志
    with open(txt_name, 'w', encoding='utf-8') as f:
        f.write("三K线策略复验 - ETH 15m\n")
        f.write(f"总交易数: {summary['total_trades']}\n")
        f.write(f"胜率: {summary['win_rate_pct']:.2f}%  盈亏比(ProfitFactor): {summary['profit_factor']:.2f}\n")
        f.write(f"平均持仓: {summary['avg_holding_bars']:.2f} bars  总盈亏USDT: {summary['total_pnl_usdt']:.4f}\n")
        f.write(f"跟踪止损激活: {summary['trailing_activation_count']} 次  跟踪止损出场: {summary['trailing_exit_count']} 次\n")
        f.write("="*80 + "\n\n")
        for idx, p in enumerate(positions, 1):
            f.write(f"#{idx} {p.direction.upper()}  入:{datetime.fromtimestamp(p.entry_time_ms/1000).strftime('%Y-%m-%d %H:%M')} 出:{datetime.fromtimestamp(p.exit_time_ms/1000).strftime('%Y-%m-%d %H:%M')}  持仓:{p.holding_bars}bars  结果:{p.exit_type}  收益:{p.leveraged_return_pct:.2f}%  PnL:{p.pnl_usdt:.4f}USDT  弱势:{p.weak} 跟踪:{p.trailing_activated} 跟踪出场:{p.trailing_exit}\n")
    print(f"TXT日志已输出: {txt_name}")

    return csv_name, txt_name


def main():
    print("="*90)
    print("复验 三K线策略 ETH 15m (杠杆140x)")
    print("="*90)
    klines = load_or_fetch_data()
    print(f"数据量: {len(klines)} 根  起始:{klines[0].dt()}  结束:{klines[-1].dt()}")
    result = backtest(klines)
    summary = result['summary']
    print("\n回测结果:")
    print(f"总交易数: {summary['total_trades']}  胜率: {summary['win_rate_pct']:.2f}%  盈亏比(ProfitFactor): {summary['profit_factor']:.2f}")
    print(f"平均持仓bars: {summary['avg_holding_bars']:.2f}  总盈亏USDT: {summary['total_pnl_usdt']:.4f}")
    print(f"跟踪止损激活次数: {summary['trailing_activation_count']}  跟踪止损出场次数: {summary['trailing_exit_count']}")
    csv_name, txt_name = export_results(result)
    print("\n输出文件:")
    print(f"  {csv_name}\n  {txt_name}")
    print("完成。")


if __name__ == '__main__':
    main()
