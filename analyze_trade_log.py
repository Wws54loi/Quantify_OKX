"""
交易日志分析脚本 - 分析止盈止损的持仓时长
"""

import re
from collections import defaultdict
import statistics


def parse_trade_log(filename: str = "trade_log.txt"):
    """
    解析交易日志文件
    
    参数:
        filename: 日志文件名
    
    返回:
        (止盈交易列表, 止损交易列表)
    """
    take_profit_trades = []  # 止盈交易
    stop_loss_trades = []    # 止损交易
    
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取所有交易记录
    trade_pattern = r'交易 #(\d+) - (止盈|止损) \((.+?)\).*?持仓时长: (\d+)根K线'
    matches = re.findall(trade_pattern, content, re.DOTALL)
    
    for match in matches:
        trade_id = int(match[0])
        result_type = match[1]  # 止盈或止损
        direction = match[2]     # 做多或做空
        holding_bars = int(match[3])  # 持仓K线数
        
        trade_info = {
            'id': trade_id,
            'type': result_type,
            'direction': direction,
            'holding_bars': holding_bars
        }
        
        if result_type == '止盈':
            take_profit_trades.append(trade_info)
        else:
            stop_loss_trades.append(trade_info)
    
    return take_profit_trades, stop_loss_trades


def analyze_holding_bars(trades, trade_type):
    """
    分析持仓K线数统计
    
    参数:
        trades: 交易列表
        trade_type: 交易类型（'止盈'或'止损'）
    """
    if not trades:
        print(f"\n{trade_type}交易: 无数据")
        return
    
    holding_bars_list = [t['holding_bars'] for t in trades]
    
    # 基础统计
    total_count = len(holding_bars_list)
    min_bars = min(holding_bars_list)
    max_bars = max(holding_bars_list)
    avg_bars = statistics.mean(holding_bars_list)
    median_bars = statistics.median(holding_bars_list)
    
    # 计算标准差
    if len(holding_bars_list) > 1:
        std_dev = statistics.stdev(holding_bars_list)
    else:
        std_dev = 0
    
    # 分组统计（按K线数区间）
    ranges = [
        (1, 10, '1-10根'),
        (11, 20, '11-20根'),
        (21, 30, '21-30根'),
        (31, 50, '31-50根'),
        (51, 100, '51-100根'),
        (101, float('inf'), '100根以上')
    ]
    
    range_counts = defaultdict(int)
    for bars in holding_bars_list:
        for min_r, max_r, label in ranges:
            if min_r <= bars <= max_r:
                range_counts[label] += 1
                break
    
    # 百分位数
    percentiles = [25, 50, 75, 90, 95]
    percentile_values = {}
    sorted_bars = sorted(holding_bars_list)
    for p in percentiles:
        idx = int(len(sorted_bars) * p / 100)
        if idx >= len(sorted_bars):
            idx = len(sorted_bars) - 1
        percentile_values[p] = sorted_bars[idx]
    
    # 打印结果
    print(f"\n{'='*80}")
    print(f"{trade_type}交易分析 (共{total_count}笔)")
    print(f"{'='*80}")
    
    print(f"\n基础统计:")
    print(f"  最小持仓: {min_bars}根K线 ({min_bars * 15}分钟 = {min_bars * 15 / 60:.1f}小时)")
    print(f"  最大持仓: {max_bars}根K线 ({max_bars * 15}分钟 = {max_bars * 15 / 60:.1f}小时)")
    print(f"  平均持仓: {avg_bars:.1f}根K线 ({avg_bars * 15:.0f}分钟 = {avg_bars * 15 / 60:.1f}小时)")
    print(f"  中位数持仓: {median_bars}根K线 ({median_bars * 15}分钟 = {median_bars * 15 / 60:.1f}小时)")
    print(f"  标准差: {std_dev:.1f}根K线")
    
    print(f"\n百分位数分布:")
    for p in percentiles:
        bars = percentile_values[p]
        print(f"  {p}%分位: {bars}根K线 ({bars * 15}分钟 = {bars * 15 / 60:.1f}小时)")
    
    print(f"\n区间分布:")
    for min_r, max_r, label in ranges:
        count = range_counts[label]
        percentage = (count / total_count * 100) if total_count > 0 else 0
        print(f"  {label:12s}: {count:4d}笔 ({percentage:5.1f}%)")
    
    # 做多/做空分类统计
    long_trades = [t for t in trades if t['direction'] == '做多']
    short_trades = [t for t in trades if t['direction'] == '做空']
    
    if long_trades and short_trades:
        long_avg = statistics.mean([t['holding_bars'] for t in long_trades])
        short_avg = statistics.mean([t['holding_bars'] for t in short_trades])
        
        print(f"\n方向分类:")
        print(f"  做多交易: {len(long_trades)}笔, 平均持仓 {long_avg:.1f}根K线")
        print(f"  做空交易: {len(short_trades)}笔, 平均持仓 {short_avg:.1f}根K线")
    
    print(f"{'='*80}")


def main():
    """主函数"""
    print("="*80)
    print("交易日志分析工具 - 持仓时长统计")
    print("="*80)
    
    # 解析日志文件
    print("\n正在读取交易日志...")
    try:
        take_profit_trades, stop_loss_trades = parse_trade_log("trade_log.txt")
        print(f"✓ 成功解析交易日志")
        print(f"  止盈交易: {len(take_profit_trades)}笔")
        print(f"  止损交易: {len(stop_loss_trades)}笔")
    except FileNotFoundError:
        print("✗ 找不到 trade_log.txt 文件!")
        print("请确保文件在当前目录下")
        return
    except Exception as e:
        print(f"✗ 解析失败: {e}")
        return
    
    # 分析止盈交易
    analyze_holding_bars(take_profit_trades, "止盈")
    
    # 分析止损交易
    analyze_holding_bars(stop_loss_trades, "止损")
    
    # 对比分析
    if take_profit_trades and stop_loss_trades:
        tp_avg = statistics.mean([t['holding_bars'] for t in take_profit_trades])
        sl_avg = statistics.mean([t['holding_bars'] for t in stop_loss_trades])
        
        print(f"\n{'='*80}")
        print("止盈 vs 止损对比")
        print(f"{'='*80}")
        print(f"止盈平均持仓: {tp_avg:.1f}根K线 ({tp_avg * 15:.0f}分钟 = {tp_avg * 15 / 60:.1f}小时)")
        print(f"止损平均持仓: {sl_avg:.1f}根K线 ({sl_avg * 15:.0f}分钟 = {sl_avg * 15 / 60:.1f}小时)")
        
        if tp_avg > sl_avg:
            ratio = tp_avg / sl_avg
            print(f"\n结论: 止盈交易平均持仓时长是止损的 {ratio:.2f} 倍")
            print(f"      止盈需要更长时间才能达到目标价格")
        else:
            ratio = sl_avg / tp_avg
            print(f"\n结论: 止损交易平均持仓时长是止盈的 {ratio:.2f} 倍")
            print(f"      止损触发更快")
        print(f"{'='*80}")
    
    # 给出建议
    print(f"\n{'='*80}")
    print("策略建议")
    print(f"{'='*80}")
    
    if take_profit_trades:
        tp_median = statistics.median([t['holding_bars'] for t in take_profit_trades])
        tp_75 = sorted([t['holding_bars'] for t in take_profit_trades])[int(len(take_profit_trades) * 0.75)]
        print(f"\n止盈特征:")
        print(f"  - 50%的止盈在 {tp_median}根K线 ({tp_median * 15}分钟) 内完成")
        print(f"  - 75%的止盈在 {tp_75}根K线 ({tp_75* 15}分钟) 内完成")
        print(f"  - 建议: 如果持仓超过{tp_75}根K线仍未止盈，可考虑调整策略")
    
    if stop_loss_trades:
        sl_median = statistics.median([t['holding_bars'] for t in stop_loss_trades])
        sl_75 = sorted([t['holding_bars'] for t in stop_loss_trades])[int(len(stop_loss_trades) * 0.75)]
        print(f"\n止损特征:")
        print(f"  - 50%的止损在 {sl_median}根K线 ({sl_median * 15}分钟) 内触发")
        print(f"  - 75%的止损在 {sl_75}根K线 ({sl_75 * 15}分钟) 内触发")
        print(f"  - 建议: 大部分止损会在较短时间内触发，需要快速反应")
    
    print(f"\n{'='*80}")


if __name__ == '__main__':
    main()
