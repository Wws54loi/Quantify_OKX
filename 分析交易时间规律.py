"""
分析交易日志中的时间规律
找出高频交易时段、高胜率时段
"""
import re
from datetime import datetime
from collections import defaultdict
import csv

def parse_trade_log(filepath):
    """解析交易日志文件"""
    trades = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 分割每笔交易
    trade_blocks = re.split(r'交易 #\d+ - ', content)[1:]  # 跳过前面的摘要部分
    
    for block in trade_blocks:
        try:
            # 提取出场结果（止盈/止损）
            result_match = re.search(r'^(止盈|止损)', block)
            if not result_match:
                continue
            result = result_match.group(1)
            
            # 提取方向
            direction_match = re.search(r'交易方向: (做多|做空)', block)
            direction = direction_match.group(1) if direction_match else None
            
            # 提取入场时间
            entry_time_match = re.search(r'入场时间: (\d{4}-\d{2}-\d{2} \d{2}:\d{2})', block)
            if not entry_time_match:
                continue
            entry_time_str = entry_time_match.group(1)
            entry_time = datetime.strptime(entry_time_str, '%Y-%m-%d %H:%M')
            
            # 提取出场时间
            exit_time_match = re.search(r'出场时间: (\d{4}-\d{2}-\d{2} \d{2}:\d{2})', block)
            if not exit_time_match:
                continue
            exit_time_str = exit_time_match.group(1)
            exit_time = datetime.strptime(exit_time_str, '%Y-%m-%d %H:%M')
            
            # 提取持仓时长
            duration_match = re.search(r'持仓时长: (\d+)根K线', block)
            duration_bars = int(duration_match.group(1)) if duration_match else 0
            
            # 提取盈亏
            pnl_match = re.search(r'本次盈亏: ([+-]\d+\.\d+) USDT', block)
            pnl = float(pnl_match.group(1)) if pnl_match else 0
            
            # 提取合约收益率
            contract_return_match = re.search(r'合约收益: ([+-]?\d+\.\d+)%', block)
            contract_return = float(contract_return_match.group(1)) if contract_return_match else 0
            
            trades.append({
                'result': result,
                'direction': direction,
                'entry_time': entry_time,
                'exit_time': exit_time,
                'entry_hour': entry_time.hour,
                'entry_minute': entry_time.minute,
                'exit_hour': exit_time.hour,
                'exit_minute': exit_time.minute,
                'entry_weekday': entry_time.weekday(),  # 0=周一, 6=周日
                'entry_date': entry_time.date(),
                'duration_bars': duration_bars,
                'pnl': pnl,
                'contract_return': contract_return,
                'is_win': result == '止盈'
            })
        except Exception as e:
            print(f"解析交易块时出错: {e}")
            continue
    
    return trades


def analyze_hourly_patterns(trades):
    """按小时分析交易规律"""
    hourly_stats = defaultdict(lambda: {'total': 0, 'wins': 0, 'losses': 0, 'pnl': 0, 'long': 0, 'short': 0})
    
    for trade in trades:
        hour = trade['entry_hour']
        hourly_stats[hour]['total'] += 1
        if trade['is_win']:
            hourly_stats[hour]['wins'] += 1
        else:
            hourly_stats[hour]['losses'] += 1
        hourly_stats[hour]['pnl'] += trade['pnl']
        
        if trade['direction'] == '做多':
            hourly_stats[hour]['long'] += 1
        else:
            hourly_stats[hour]['short'] += 1
    
    # 计算胜率
    hourly_results = []
    for hour in sorted(hourly_stats.keys()):
        stats = hourly_stats[hour]
        win_rate = (stats['wins'] / stats['total'] * 100) if stats['total'] > 0 else 0
        avg_pnl = stats['pnl'] / stats['total'] if stats['total'] > 0 else 0
        
        hourly_results.append({
            'hour': hour,
            'total': stats['total'],
            'wins': stats['wins'],
            'losses': stats['losses'],
            'win_rate': win_rate,
            'total_pnl': stats['pnl'],
            'avg_pnl': avg_pnl,
            'long': stats['long'],
            'short': stats['short']
        })
    
    return hourly_results


def analyze_time_slot_patterns(trades):
    """按时间段分析（每15分钟一个槽位，96个槽位）"""
    slot_stats = defaultdict(lambda: {'total': 0, 'wins': 0, 'losses': 0, 'pnl': 0})
    
    for trade in trades:
        # 计算时间槽位（0-95，对应00:00-23:45）
        slot = trade['entry_hour'] * 4 + trade['entry_minute'] // 15
        slot_stats[slot]['total'] += 1
        if trade['is_win']:
            slot_stats[slot]['wins'] += 1
        else:
            slot_stats[slot]['losses'] += 1
        slot_stats[slot]['pnl'] += trade['pnl']
    
    # 计算胜率
    slot_results = []
    for slot in sorted(slot_stats.keys()):
        stats = slot_stats[slot]
        hour = slot // 4
        minute = (slot % 4) * 15
        win_rate = (stats['wins'] / stats['total'] * 100) if stats['total'] > 0 else 0
        avg_pnl = stats['pnl'] / stats['total'] if stats['total'] > 0 else 0
        
        slot_results.append({
            'slot': slot,
            'time': f'{hour:02d}:{minute:02d}',
            'total': stats['total'],
            'wins': stats['wins'],
            'losses': stats['losses'],
            'win_rate': win_rate,
            'total_pnl': stats['pnl'],
            'avg_pnl': avg_pnl
        })
    
    return slot_results


def analyze_weekday_patterns(trades):
    """按星期几分析"""
    weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    weekday_stats = defaultdict(lambda: {'total': 0, 'wins': 0, 'losses': 0, 'pnl': 0})
    
    for trade in trades:
        weekday = trade['entry_weekday']
        weekday_stats[weekday]['total'] += 1
        if trade['is_win']:
            weekday_stats[weekday]['wins'] += 1
        else:
            weekday_stats[weekday]['losses'] += 1
        weekday_stats[weekday]['pnl'] += trade['pnl']
    
    weekday_results = []
    for weekday in sorted(weekday_stats.keys()):
        stats = weekday_stats[weekday]
        win_rate = (stats['wins'] / stats['total'] * 100) if stats['total'] > 0 else 0
        avg_pnl = stats['pnl'] / stats['total'] if stats['total'] > 0 else 0
        
        weekday_results.append({
            'weekday': weekday,
            'weekday_name': weekday_names[weekday],
            'total': stats['total'],
            'wins': stats['wins'],
            'losses': stats['losses'],
            'win_rate': win_rate,
            'total_pnl': stats['pnl'],
            'avg_pnl': avg_pnl
        })
    
    return weekday_results


def analyze_duration_patterns(trades):
    """按持仓时长分析"""
    # 分组：0-10, 11-30, 31-50, 51-100, 101-200, 200+
    duration_ranges = [
        (0, 10, '0-10根'),
        (11, 30, '11-30根'),
        (31, 50, '31-50根'),
        (51, 100, '51-100根'),
        (101, 200, '101-200根'),
        (201, 999999, '200+根')
    ]
    
    duration_stats = defaultdict(lambda: {'total': 0, 'wins': 0, 'losses': 0, 'pnl': 0})
    
    for trade in trades:
        duration = trade['duration_bars']
        for min_d, max_d, label in duration_ranges:
            if min_d <= duration <= max_d:
                duration_stats[label]['total'] += 1
                if trade['is_win']:
                    duration_stats[label]['wins'] += 1
                else:
                    duration_stats[label]['losses'] += 1
                duration_stats[label]['pnl'] += trade['pnl']
                break
    
    duration_results = []
    for min_d, max_d, label in duration_ranges:
        stats = duration_stats[label]
        if stats['total'] > 0:
            win_rate = stats['wins'] / stats['total'] * 100
            avg_pnl = stats['pnl'] / stats['total']
            duration_results.append({
                'range': label,
                'total': stats['total'],
                'wins': stats['wins'],
                'losses': stats['losses'],
                'win_rate': win_rate,
                'total_pnl': stats['pnl'],
                'avg_pnl': avg_pnl
            })
    
    return duration_results


def print_report(trades):
    """打印分析报告"""
    print("=" * 80)
    print("交易时间规律分析报告")
    print("=" * 80)
    print(f"总交易数: {len(trades)}")
    total_wins = sum(1 for t in trades if t['is_win'])
    print(f"总胜率: {total_wins / len(trades) * 100:.2f}%")
    print(f"总盈亏: {sum(t['pnl'] for t in trades):.4f} USDT")
    print()
    
    # 1. 按小时分析
    print("=" * 80)
    print("【1. 按小时分析 - 入场时间】")
    print("=" * 80)
    hourly_results = analyze_hourly_patterns(trades)
    
    print(f"{'小时':<6} {'交易数':<8} {'胜/负':<12} {'胜率':<10} {'累计盈亏':<12} {'平均盈亏':<12} {'多/空':<10}")
    print("-" * 80)
    for h in hourly_results:
        print(f"{h['hour']:02d}:00  {h['total']:<8} {h['wins']}/{h['losses']:<9} "
              f"{h['win_rate']:>6.2f}%   {h['total_pnl']:>10.4f}  {h['avg_pnl']:>10.4f}  "
              f"{h['long']}/{h['short']}")
    
    # 找出高频时段
    print("\n【高频交易时段 TOP 5】")
    top_freq = sorted(hourly_results, key=lambda x: x['total'], reverse=True)[:5]
    for i, h in enumerate(top_freq, 1):
        print(f"{i}. {h['hour']:02d}:00 - 交易{h['total']}次, 胜率{h['win_rate']:.2f}%, 累计{h['total_pnl']:.4f}U")
    
    # 找出高胜率时段（至少5笔交易）
    print("\n【高胜率时段 TOP 5】（至少5笔交易）")
    high_win_rate = [h for h in hourly_results if h['total'] >= 5]
    high_win_rate = sorted(high_win_rate, key=lambda x: x['win_rate'], reverse=True)[:5]
    for i, h in enumerate(high_win_rate, 1):
        print(f"{i}. {h['hour']:02d}:00 - 胜率{h['win_rate']:.2f}%, 交易{h['total']}次, 累计{h['total_pnl']:.4f}U")
    
    # 找出高盈利时段（至少5笔交易）
    print("\n【高盈利时段 TOP 5】（至少5笔交易）")
    high_pnl = [h for h in hourly_results if h['total'] >= 5]
    high_pnl = sorted(high_pnl, key=lambda x: x['total_pnl'], reverse=True)[:5]
    for i, h in enumerate(high_pnl, 1):
        print(f"{i}. {h['hour']:02d}:00 - 累计{h['total_pnl']:.4f}U, 胜率{h['win_rate']:.2f}%, 交易{h['total']}次")
    
    print()
    
    # 2. 按15分钟时间槽分析
    print("=" * 80)
    print("【2. 按15分钟时间槽分析 - 精确入场时间】")
    print("=" * 80)
    slot_results = analyze_time_slot_patterns(trades)
    
    # 只显示交易数>=3的槽位
    active_slots = [s for s in slot_results if s['total'] >= 3]
    print(f"活跃时间槽数量（>=3笔）: {len(active_slots)}")
    print()
    
    # 找出高频时间槽
    print("【高频交易时间槽 TOP 10】")
    top_slots = sorted(slot_results, key=lambda x: x['total'], reverse=True)[:10]
    for i, s in enumerate(top_slots, 1):
        print(f"{i:2d}. {s['time']} - 交易{s['total']}次, 胜率{s['win_rate']:.2f}%, 累计{s['total_pnl']:.4f}U, 平均{s['avg_pnl']:.4f}U")
    
    # 找出高胜率时间槽（至少3笔）
    print("\n【高胜率时间槽 TOP 10】（至少3笔交易）")
    high_win_slots = [s for s in slot_results if s['total'] >= 3]
    high_win_slots = sorted(high_win_slots, key=lambda x: x['win_rate'], reverse=True)[:10]
    for i, s in enumerate(high_win_slots, 1):
        print(f"{i:2d}. {s['time']} - 胜率{s['win_rate']:.2f}%, 交易{s['total']}次, 累计{s['total_pnl']:.4f}U")
    
    print()
    
    # 3. 按星期几分析
    print("=" * 80)
    print("【3. 按星期几分析】")
    print("=" * 80)
    weekday_results = analyze_weekday_patterns(trades)
    
    print(f"{'星期':<8} {'交易数':<8} {'胜/负':<12} {'胜率':<10} {'累计盈亏':<12} {'平均盈亏':<12}")
    print("-" * 80)
    for w in weekday_results:
        print(f"{w['weekday_name']:<8} {w['total']:<8} {w['wins']}/{w['losses']:<9} "
              f"{w['win_rate']:>6.2f}%   {w['total_pnl']:>10.4f}  {w['avg_pnl']:>10.4f}")
    
    print()
    
    # 4. 按持仓时长分析
    print("=" * 80)
    print("【4. 按持仓时长分析】")
    print("=" * 80)
    duration_results = analyze_duration_patterns(trades)
    
    print(f"{'持仓时长':<12} {'交易数':<8} {'胜/负':<12} {'胜率':<10} {'累计盈亏':<12} {'平均盈亏':<12}")
    print("-" * 80)
    for d in duration_results:
        print(f"{d['range']:<12} {d['total']:<8} {d['wins']}/{d['losses']:<9} "
              f"{d['win_rate']:>6.2f}%   {d['total_pnl']:>10.4f}  {d['avg_pnl']:>10.4f}")
    
    print()
    
    # 5. 综合建议
    print("=" * 80)
    print("【5. 策略建议】")
    print("=" * 80)
    
    # 找出最佳交易窗口
    best_hours = [h for h in hourly_results if h['total'] >= 10 and h['win_rate'] >= 70]
    if best_hours:
        print("✓ 推荐交易时段（至少10笔且胜率>=70%）:")
        for h in sorted(best_hours, key=lambda x: x['win_rate'], reverse=True):
            print(f"  - {h['hour']:02d}:00-{h['hour']+1:02d}:00  胜率{h['win_rate']:.2f}%, {h['total']}笔交易, 累计{h['total_pnl']:.2f}U")
    
    # 找出需要谨慎的时段
    bad_hours = [h for h in hourly_results if h['total'] >= 10 and h['win_rate'] < 60]
    if bad_hours:
        print("\n⚠ 需谨慎的时段（至少10笔且胜率<60%）:")
        for h in sorted(bad_hours, key=lambda x: x['win_rate']):
            print(f"  - {h['hour']:02d}:00-{h['hour']+1:02d}:00  胜率{h['win_rate']:.2f}%, {h['total']}笔交易, 累计{h['total_pnl']:.2f}U")
    
    # 找出最佳星期
    best_weekday = max(weekday_results, key=lambda x: x['win_rate'])
    print(f"\n✓ 最佳交易日: {best_weekday['weekday_name']} (胜率{best_weekday['win_rate']:.2f}%, {best_weekday['total']}笔)")
    
    worst_weekday = min(weekday_results, key=lambda x: x['win_rate'])
    print(f"⚠ 最差交易日: {worst_weekday['weekday_name']} (胜率{worst_weekday['win_rate']:.2f}%, {worst_weekday['total']}笔)")
    
    # 持仓时长建议
    best_duration = max(duration_results, key=lambda x: x['win_rate'])
    print(f"\n✓ 最佳持仓时长: {best_duration['range']} (胜率{best_duration['win_rate']:.2f}%, {best_duration['total']}笔)")
    
    print()
    print("=" * 80)


def export_to_csv(trades, hourly_results, slot_results, weekday_results, duration_results):
    """导出分析结果到CSV"""
    
    # 导出小时统计
    with open('时间分析_按小时.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['小时', '交易数', '胜利', '失败', '胜率%', '累计盈亏', '平均盈亏', '做多', '做空'])
        for h in hourly_results:
            writer.writerow([
                f"{h['hour']:02d}:00",
                h['total'], h['wins'], h['losses'],
                f"{h['win_rate']:.2f}",
                f"{h['total_pnl']:.4f}",
                f"{h['avg_pnl']:.4f}",
                h['long'], h['short']
            ])
    
    # 导出15分钟槽统计
    with open('时间分析_按15分钟槽.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['时间', '交易数', '胜利', '失败', '胜率%', '累计盈亏', '平均盈亏'])
        for s in slot_results:
            writer.writerow([
                s['time'],
                s['total'], s['wins'], s['losses'],
                f"{s['win_rate']:.2f}",
                f"{s['total_pnl']:.4f}",
                f"{s['avg_pnl']:.4f}"
            ])
    
    # 导出星期统计
    with open('时间分析_按星期.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['星期', '交易数', '胜利', '失败', '胜率%', '累计盈亏', '平均盈亏'])
        for w in weekday_results:
            writer.writerow([
                w['weekday_name'],
                w['total'], w['wins'], w['losses'],
                f"{w['win_rate']:.2f}",
                f"{w['total_pnl']:.4f}",
                f"{w['avg_pnl']:.4f}"
            ])
    
    # 导出持仓时长统计
    with open('时间分析_按持仓时长.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['持仓时长', '交易数', '胜利', '失败', '胜率%', '累计盈亏', '平均盈亏'])
        for d in duration_results:
            writer.writerow([
                d['range'],
                d['total'], d['wins'], d['losses'],
                f"{d['win_rate']:.2f}",
                f"{d['total_pnl']:.4f}",
                f"{d['avg_pnl']:.4f}"
            ])
    
    print("✓ CSV文件已导出:")
    print("  - 时间分析_按小时.csv")
    print("  - 时间分析_按15分钟槽.csv")
    print("  - 时间分析_按星期.csv")
    print("  - 时间分析_按持仓时长.csv")


if __name__ == '__main__':
    # 读取日志文件
    log_file = 'trade_log.txt'
    
    print(f"正在读取日志文件: {log_file}")
    trades = parse_trade_log(log_file)
    
    if not trades:
        print("未能解析到交易数据，请检查日志文件格式")
        exit(1)
    
    print(f"成功解析 {len(trades)} 笔交易\n")
    
    # 分析数据
    hourly_results = analyze_hourly_patterns(trades)
    slot_results = analyze_time_slot_patterns(trades)
    weekday_results = analyze_weekday_patterns(trades)
    duration_results = analyze_duration_patterns(trades)
    
    # 打印报告
    print_report(trades)
    
    # 导出CSV
    print()
    export_to_csv(trades, hourly_results, slot_results, weekday_results, duration_results)
