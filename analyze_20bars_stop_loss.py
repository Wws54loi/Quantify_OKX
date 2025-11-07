"""
分析20根K线内止损的交易K线图
从trade_log.txt中提取持仓时长≤20根K线的止损交易，并绘制对应的K1和K2的K线图
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
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False


def parse_trade_log(filename: str = "trade_log.txt") -> List[Dict]:
    """解析交易日志文件，提取20根K线内止损的交易信息"""
    trades = []
    
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 使用正则表达式提取每笔交易
    trade_pattern = r'交易 #(\d+) - (.*?) \((.*?)\)\n  策略类型: (.*?)\n  交易方向: (.*?)\n  入场时间: (.*?)\n  入场价格: (.*?) USDT\n  出场时间: (.*?)\n  出场价格: (.*?) USDT\n  持仓时长: (\d+)根K线.*?\n  价格变动: (.*?)%\n  合约收益: (.*?)%\n  本次盈亏: (.*?) USDT\n  累计盈亏: (.*?) USDT\n  K1区间: \[(.*?) - (.*?)\]\n  K2区间: \[(.*?) - (.*?)\]'
    
    matches = re.findall(trade_pattern, content, re.MULTILINE)
    
    for match in matches:
        trade_id, result, direction, strategy_type, trade_direction, entry_time, entry_price, exit_time, exit_price, holding_bars, \
        price_change, contract_return, pnl, cumulative, k1_low, k1_high, k2_low, k2_high = match
        
        holding_bars_int = int(holding_bars)
        
        # 只提取止损且持仓≤20根K线的交易
        if result == '止损' and holding_bars_int <= 20:
            trades.append({
                'trade_id': int(trade_id),
                'result': result,
                'direction': direction,
                'entry_time': entry_time,
                'entry_price': float(entry_price),
                'exit_time': exit_time,
                'exit_price': float(exit_price),
                'holding_bars': holding_bars_int,
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
    """获取指定时间前后的K线数据"""
    entry_time = datetime.strptime(entry_time_str, '%Y-%m-%d %H:%M')
    
    start_time = entry_time - timedelta(minutes=15 * count)
    end_time = entry_time + timedelta(minutes=15 * count)
    
    start_ts = int(start_time.timestamp() * 1000)
    end_ts = int(end_time.timestamp() * 1000)
    
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
    """绘制K线对比图（K1和K2）"""
    if len(klines) < 2:
        print(f"K线数据不足，无法绘制交易#{trade['trade_id']}")
        return
    
    # 找到入场时间对应的K线索引
    entry_time = datetime.strptime(trade['entry_time'], '%Y-%m-%d %H:%M')
    entry_ts = int(entry_time.timestamp() * 1000)
    
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
    ax2.axhline(y=trade['exit_price'], color='red', linestyle='--', 
                linewidth=2, label=f'止损价: {trade["exit_price"]:.2f}')
    ax2.legend()
    
    # 设置总标题
    direction_text = '做多' if trade['direction'] == '做多' else '做空'
    fig.suptitle(
        f"交易 #{trade['trade_id']} - 止损 ({direction_text}) - 持仓{trade['holding_bars']}根K线\n"
        f"入场: {trade['entry_time']} @ {trade['entry_price']:.2f} | "
        f"出场: {trade['exit_time']} @ {trade['exit_price']:.2f}\n"
        f"价格变动: {trade['price_change']:.3f}% | 合约亏损: {trade['contract_return']:.2f}% | "
        f"亏损: {trade['pnl']:.4f} USDT",
        fontsize=14, fontweight='bold'
    )
    
    plt.tight_layout()
    
    # 保存图片
    filename = f"trade_{trade['trade_id']:03d}_stop_loss_{trade['holding_bars']}bars_{direction_text}.png"
    filepath = os.path.join(output_dir, filename)
    plt.savefig(filepath, dpi=100, bbox_inches='tight')
    plt.close()
    
    print(f"✓ 已保存: {filename}")


def plot_single_kline(ax, kline: Dict, k_low: float, k_high: float, title: str, direction: str):
    """绘制单根K线"""
    
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
    print("20根K线内止损交易K线图分析")
    print("="*80)
    
    # 创建输出目录
    output_dir = os.path.join("策略分析", "20根内止损K线图")
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n输出目录: {output_dir}")
    
    # 解析交易日志
    print("\n正在解析交易日志...")
    trades = parse_trade_log("trade_log.txt")
    print(f"找到 {len(trades)} 笔20根K线内止损交易")
    
    if not trades:
        print("没有找到符合条件的交易记录")
        return
    
    # 统计分析
    print("\n" + "="*80)
    print("止损交易统计分析")
    print("="*80)
    
    holding_bars_list = [t['holding_bars'] for t in trades]
    price_changes = [t['price_change'] for t in trades]
    k1_ranges = [(t['k1_high'] - t['k1_low']) / t['k1_low'] * 100 for t in trades]
    k2_ranges = [(t['k2_high'] - t['k2_low']) / t['k2_low'] * 100 for t in trades]
    long_trades = [t for t in trades if t['direction'] == '做多']
    short_trades = [t for t in trades if t['direction'] == '做空']
    
    print(f"\n总交易数: {len(trades)}")
    print(f"做多: {len(long_trades)} ({len(long_trades)/len(trades)*100:.1f}%)")
    print(f"做空: {len(short_trades)} ({len(short_trades)/len(trades)*100:.1f}%)")
    
    print(f"\n持仓时长统计:")
    print(f"  平均: {sum(holding_bars_list)/len(holding_bars_list):.1f} 根K线")
    print(f"  最短: {min(holding_bars_list)} 根K线")
    print(f"  最长: {max(holding_bars_list)} 根K线")
    print(f"  中位数: {sorted(holding_bars_list)[len(holding_bars_list)//2]} 根K线")
    
    # 持仓分布
    very_fast = sum(1 for h in holding_bars_list if h <= 5)
    fast = sum(1 for h in holding_bars_list if 6 <= h <= 10)
    medium = sum(1 for h in holding_bars_list if 11 <= h <= 15)
    slow = sum(1 for h in holding_bars_list if 16 <= h <= 20)
    
    print(f"\n持仓时长分布:")
    print(f"  ≤5根: {very_fast} ({very_fast/len(holding_bars_list)*100:.1f}%)")
    print(f"  6-10根: {fast} ({fast/len(holding_bars_list)*100:.1f}%)")
    print(f"  11-15根: {medium} ({medium/len(holding_bars_list)*100:.1f}%)")
    print(f"  16-20根: {slow} ({slow/len(holding_bars_list)*100:.1f}%)")
    
    print(f"\n价格变动统计:")
    print(f"  平均: {sum(price_changes)/len(price_changes):.3f}%")
    print(f"  最小: {min(price_changes):.3f}%")
    print(f"  最大: {max(price_changes):.3f}%")
    
    print(f"\nK1振幅统计:")
    print(f"  平均: {sum(k1_ranges)/len(k1_ranges):.3f}%")
    print(f"  最小: {min(k1_ranges):.3f}%")
    print(f"  最大: {max(k1_ranges):.3f}%")
    
    print(f"\nK2振幅统计:")
    print(f"  平均: {sum(k2_ranges)/len(k2_ranges):.3f}%")
    print(f"  最小: {min(k2_ranges):.3f}%")
    print(f"  最大: {max(k2_ranges):.3f}%")
    
    # 为每笔交易绘制K线图
    print(f"\n{'='*80}")
    print("开始绘制K线图...")
    print("-"*80)
    
    for i, trade in enumerate(trades, 1):
        print(f"\n[{i}/{len(trades)}] 处理交易 #{trade['trade_id']} (持仓{trade['holding_bars']}根K线)...")
        
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
    
    # 生成分析报告
    print(f"\n{'='*80}")
    print("生成分析报告...")
    
    report_content = f"""# 20根K线内止损交易分析报告

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
分析对象: 持仓≤20根K线的止损交易
数据来源: trade_log.txt

---

## 一、基本统计

### 1.1 交易分布
- **总交易数**: {len(trades)}笔
- **做多交易**: {len(long_trades)}笔 ({len(long_trades)/len(trades)*100:.1f}%)
- **做空交易**: {len(short_trades)}笔 ({len(short_trades)/len(trades)*100:.1f}%)

### 1.2 持仓时长
- **平均持仓**: {sum(holding_bars_list)/len(holding_bars_list):.1f}根K线 ({sum(holding_bars_list)/len(holding_bars_list)*15:.0f}分钟)
- **最短持仓**: {min(holding_bars_list)}根K线 ({min(holding_bars_list)*15}分钟)
- **最长持仓**: {max(holding_bars_list)}根K线 ({max(holding_bars_list)*15}分钟)
- **中位数**: {sorted(holding_bars_list)[len(holding_bars_list)//2]}根K线

### 1.3 持仓分布
| 时长区间 | 数量 | 占比 |
|---------|------|------|
| ≤5根 | {very_fast} | {very_fast/len(holding_bars_list)*100:.1f}% |
| 6-10根 | {fast} | {fast/len(holding_bars_list)*100:.1f}% |
| 11-15根 | {medium} | {medium/len(holding_bars_list)*100:.1f}% |
| 16-20根 | {slow} | {slow/len(holding_bars_list)*100:.1f}% |

---

## 二、K线形态特征

### 2.1 K1振幅
- **平均振幅**: {sum(k1_ranges)/len(k1_ranges):.3f}%
- **最小振幅**: {min(k1_ranges):.3f}%
- **最大振幅**: {max(k1_ranges):.3f}%

### 2.2 K2振幅
- **平均振幅**: {sum(k2_ranges)/len(k2_ranges):.3f}%
- **最小振幅**: {min(k2_ranges):.3f}%
- **最大振幅**: {max(k2_ranges):.3f}%

### 2.3 K1 vs K2对比
- K1平均振幅: {sum(k1_ranges)/len(k1_ranges):.3f}%
- K2平均振幅: {sum(k2_ranges)/len(k2_ranges):.3f}%
- 差异: {sum(k1_ranges)/len(k1_ranges) - sum(k2_ranges)/len(k2_ranges):.3f}%

---

## 三、亏损特征

### 3.1 价格变动
- **平均变动**: {sum(price_changes)/len(price_changes):.3f}%
- **最小变动**: {min(price_changes):.3f}%
- **最大变动**: {max(price_changes):.3f}%

### 3.2 关键洞察

**持仓时长**:
- {very_fast/len(holding_bars_list)*100:.1f}%的止损发生在5根K线内 - 说明这些交易很快就反向突破
- 平均持仓{sum(holding_bars_list)/len(holding_bars_list):.1f}根K线 - 相比完全止盈的5.7根略长

**K线振幅**:
- K1平均振幅{sum(k1_ranges)/len(k1_ranges):.3f}% {'<' if sum(k1_ranges)/len(k1_ranges) < 0.943 else '>'} 完全止盈K1的0.943%
- K2平均振幅{sum(k2_ranges)/len(k2_ranges):.3f}% {'<' if sum(k2_ranges)/len(k2_ranges) < 0.732 else '>'} 完全止盈K2的0.732%

---

## 四、失败原因分析

基于{len(trades)}笔止损交易的K线图分析:

### 可能的失败模式

1. **K1振幅不足** - 如果K1振幅小于完全止盈的平均值，可能空间不够
2. **K2突破过深** - K2影线过长，突破力度太强
3. **趋势判断错误** - 真突破而非假突破
4. **快速反转** - 入场后立即反向，持仓≤5根K线即止损

### 优化建议

查看K线图后可以考虑:
- 提高K1最小振幅要求
- 强化K2影线过滤
- 增加趋势确认条件

---

## 五、附件

- **K线图目录**: `策略分析/20根内止损K线图/`
- **图片数量**: {len(trades)}张
- **命名格式**: `trade_XXX_stop_loss_XXbars_做多/做空.png`

---

**报告生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**分析工具**: Python + matplotlib
**数据来源**: Binance BTCUSDT 15分钟K线
"""
    
    report_file = os.path.join("策略分析", "20根内止损交易分析报告.md")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    print(f"✓ 分析报告已保存到: {report_file}")
    
    print(f"\n{'='*80}")
    print(f"完成！所有K线图已保存到: {output_dir}")
    print(f"分析报告已保存到: {report_file}")
    print(f"{'='*80}")


if __name__ == '__main__':
    main()
