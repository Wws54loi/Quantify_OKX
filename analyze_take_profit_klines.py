"""
分析完全止盈交易的K线图
从trade_log.txt中提取完全止盈的交易，并绘制对应的K1和K2的K线图
"""

import urllib.request
import json
import re
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from typing import List, Dict
import os

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号


def parse_trade_log(filename: str = "trade_log.txt") -> List[Dict]:
    """解析交易日志文件，提取完全止盈的交易信息"""
    trades = []
    
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 使用正则表达式提取每笔交易
    trade_pattern = r'交易 #(\d+) - (.*?) \((.*?)\)\n  策略类型: (.*?)\n  交易方向: (.*?)\n  入场时间: (.*?)\n  入场价格: (.*?) USDT\n  出场时间: (.*?)\n  出场价格: (.*?) USDT\n  持仓时长: (\d+)根K线.*?\n  价格变动: (.*?)%\n  合约收益: (.*?)%\n  本次盈亏: (.*?) USDT\n  累计盈亏: (.*?) USDT\n  K1区间: \[(.*?) - (.*?)\]\n  K2区间: \[(.*?) - (.*?)\]'
    
    matches = re.findall(trade_pattern, content, re.MULTILINE)
    
    for match in matches:
        trade_id, result, direction, strategy_type, trade_direction, entry_time, entry_price, exit_time, exit_price, holding_bars, \
        price_change, contract_return, pnl, cumulative, k1_low, k1_high, k2_low, k2_high = match
        
        # 只提取完全止盈的交易
        if result == '完全止盈':
            trades.append({
                'trade_id': int(trade_id),
                'result': result,
                'direction': direction,
                'entry_time': entry_time,
                'entry_price': float(entry_price),
                'exit_time': exit_time,
                'exit_price': float(exit_price),
                'holding_bars': int(holding_bars),
                'price_change': float(price_change),
                'contract_return': float(contract_return),
                'pnl': float(pnl.replace('+', '')),
                'k1_low': float(k1_low),
                'k1_high': float(k1_high),
                'k2_low': float(k2_low),
                'k2_high': float(k2_high),
            })
    
    return trades


def get_klines_for_trade(entry_time_str: str, count: int = 5) -> List[Dict]:
    """
    获取指定时间前后的K线数据
    
    参数:
        entry_time_str: 入场时间字符串 "2025-02-19 05:15"
        count: 获取K线数量（入场时间前后各取count根）
    """
    # 解析时间
    entry_time = datetime.strptime(entry_time_str, '%Y-%m-%d %H:%M')
    
    # 计算起始和结束时间（15分钟K线）
    start_time = entry_time - timedelta(minutes=15 * count)
    end_time = entry_time + timedelta(minutes=15 * count)
    
    # 转换为毫秒时间戳
    start_ts = int(start_time.timestamp() * 1000)
    end_ts = int(end_time.timestamp() * 1000)
    
    # 调用币安API
    url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&startTime={start_ts}&endTime={end_ts}&limit=1000"
    
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            
            klines = []
            for k in data:
                klines.append({
                    'timestamp': int(k[0]),
                    'time': datetime.fromtimestamp(int(k[0])/1000).strftime('%m-%d %H:%M'),
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                })
            
            return klines
    except Exception as e:
        print(f"获取K线数据失败: {e}")
        return []


def plot_kline_comparison(trade: Dict, klines: List[Dict], output_dir: str):
    """
    绘制K线对比图（K1和K2）
    
    参数:
        trade: 交易信息字典
        klines: K线数据列表
        output_dir: 输出目录
    """
    if len(klines) < 2:
        print(f"K线数据不足，无法绘制交易#{trade['trade_id']}")
        return
    
    # 找到入场时间对应的K线索引
    entry_time = datetime.strptime(trade['entry_time'], '%Y-%m-%d %H:%M')
    entry_ts = int(entry_time.timestamp() * 1000)
    
    # 找到最接近入场时间的K线
    k2_index = -1
    for i, k in enumerate(klines):
        if k['timestamp'] == entry_ts:
            k2_index = i
            break
    
    if k2_index == -1 or k2_index == 0:
        print(f"未找到入场时间对应的K线，交易#{trade['trade_id']}")
        return
    
    k1 = klines[k2_index - 1]
    k2 = klines[k2_index]
    
    # 创建图表
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))
    
    # 绘制K1
    plot_single_kline(ax1, k1, trade['k1_low'], trade['k1_high'], 
                      f"K1 - {k1['time']}", trade['direction'])
    
    # 绘制K2和入场价格
    plot_single_kline(ax2, k2, trade['k2_low'], trade['k2_high'], 
                      f"K2 - {k2['time']}", trade['direction'])
    ax2.axhline(y=trade['entry_price'], color='purple', linestyle='--', 
                linewidth=2, label=f'入场价: {trade["entry_price"]:.2f}')
    ax2.axhline(y=trade['exit_price'], color='green', linestyle='--', 
                linewidth=2, label=f'出场价: {trade["exit_price"]:.2f}')
    ax2.legend()
    
    # 设置总标题
    direction_text = '做多' if trade['direction'] == '做多' else '做空'
    fig.suptitle(
        f"交易 #{trade['trade_id']} - 完全止盈 ({direction_text})\n"
        f"入场: {trade['entry_time']} @ {trade['entry_price']:.2f} | "
        f"出场: {trade['exit_time']} @ {trade['exit_price']:.2f}\n"
        f"价格变动: {trade['price_change']:.3f}% | 合约收益: {trade['contract_return']:.2f}% | "
        f"盈亏: {trade['pnl']:.4f} USDT",
        fontsize=14, fontweight='bold'
    )
    
    plt.tight_layout()
    
    # 保存图片
    filename = f"trade_{trade['trade_id']:03d}_take_profit_{direction_text}.png"
    filepath = os.path.join(output_dir, filename)
    plt.savefig(filepath, dpi=100, bbox_inches='tight')
    plt.close()
    
    print(f"✓ 已保存: {filename}")


def plot_single_kline(ax, kline: Dict, k_low: float, k_high: float, title: str, direction: str):
    """绘制单根K线"""
    
    # K线颜色
    is_bullish = kline['close'] > kline['open']
    color = 'red' if is_bullish else 'green'
    
    # 绘制影线
    ax.plot([0.5, 0.5], [kline['low'], kline['high']], color=color, linewidth=1.5)
    
    # 绘制实体
    body_height = abs(kline['close'] - kline['open'])
    body_bottom = min(kline['open'], kline['close'])
    rect = patches.Rectangle((0.3, body_bottom), 0.4, body_height, 
                             linewidth=1.5, edgecolor=color, facecolor=color, alpha=0.7)
    ax.add_patch(rect)
    
    # 标注K线的高低点
    ax.axhline(y=k_high, color='orange', linestyle=':', linewidth=1.5, 
               label=f'K线最高: {k_high:.2f}')
    ax.axhline(y=k_low, color='blue', linestyle=':', linewidth=1.5, 
               label=f'K线最低: {k_low:.2f}')
    
    # 设置坐标轴
    ax.set_xlim(0, 1)
    y_margin = (kline['high'] - kline['low']) * 0.2
    ax.set_ylim(kline['low'] - y_margin, kline['high'] + y_margin)
    ax.set_xticks([])
    ax.set_ylabel('价格 (USDT)', fontsize=12)
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best', fontsize=10)
    
    # 添加K线数据标注
    info_text = f"开: {kline['open']:.2f}\n高: {kline['high']:.2f}\n低: {kline['low']:.2f}\n收: {kline['close']:.2f}"
    ax.text(0.05, 0.95, info_text, transform=ax.transAxes, 
            fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))


def main():
    """主函数"""
    print("="*80)
    print("完全止盈交易K线图分析")
    print("="*80)
    
    # 创建输出目录
    output_dir = os.path.join("策略分析", "止盈K线图")
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n输出目录: {output_dir}")
    
    # 解析交易日志
    print("\n正在解析交易日志...")
    trades = parse_trade_log("trade_log.txt")
    print(f"找到 {len(trades)} 笔完全止盈交易")
    
    if not trades:
        print("没有找到完全止盈的交易记录")
        return
    
    # 为每笔交易绘制K线图
    print(f"\n开始绘制K线图...")
    print("-"*80)
    
    for i, trade in enumerate(trades, 1):
        print(f"\n[{i}/{len(trades)}] 处理交易 #{trade['trade_id']}...")
        
        # 获取K线数据
        klines = get_klines_for_trade(trade['entry_time'], count=5)
        
        if not klines:
            print(f"  ✗ 无法获取K线数据")
            continue
        
        # 绘制K线图
        try:
            plot_kline_comparison(trade, klines, output_dir)
        except Exception as e:
            print(f"  ✗ 绘制失败: {e}")
            continue
    
    print(f"\n{'='*80}")
    print(f"完成！所有K线图已保存到: {output_dir}")
    print(f"{'='*80}")


if __name__ == '__main__':
    main()
