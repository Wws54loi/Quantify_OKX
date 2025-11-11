"""
计算每个时间段的数学期望
公式：(平均盈利额*胜率 - 平均亏损额*败率) / 平均下注额
"""
import csv
from datetime import datetime
from collections import defaultdict

def parse_csv_trades(filepath):
    """解析CSV交易数据"""
    trades = []
    
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # 解析入场时间
                entry_time_str = row['入场时间']
                entry_time = datetime.strptime(entry_time_str, '%Y-%m-%d %H:%M')
                
                # 解析盈亏
                pnl = float(row['盈亏USDT'])
                
                # 解析下注额（从K2柱体强度推导或使用固定值）
                # 根据策略：>=0.48%用4U, >=0.3%用1.6U, >=0.21%用1U
                # 这里从盈亏反推或使用默认1U
                bet_amount = 1.0  # 基础下注
                
                # 从合约收益率反推实际下注额
                contract_return_str = row['合约收益%'].rstrip('%')
                contract_return = float(contract_return_str)
                
                # 合约收益 = (pnl / bet_amount) * 100
                # 所以 bet_amount = pnl / (contract_return / 100)
                if abs(contract_return) > 0.01:  # 避免除零
                    bet_amount = abs(pnl) / abs(contract_return / 100)
                
                trades.append({
                    'entry_time': entry_time,
                    'entry_hour': entry_time.hour,
                    'pnl': pnl,
                    'bet_amount': bet_amount,
                    'is_win': pnl > 0
                })
            except Exception as e:
                print(f"解析行时出错: {e}, 行数据: {row}")
                continue
    
    return trades


def calculate_expectation_by_hour(trades):
    """按小时计算数学期望"""
    hourly_data = defaultdict(lambda: {
        'total': 0,
        'wins': 0,
        'losses': 0,
        'win_pnl_sum': 0,
        'loss_pnl_sum': 0,
        'bet_sum': 0
    })
    
    for trade in trades:
        hour = trade['entry_hour']
        hourly_data[hour]['total'] += 1
        hourly_data[hour]['bet_sum'] += trade['bet_amount']
        
        if trade['is_win']:
            hourly_data[hour]['wins'] += 1
            hourly_data[hour]['win_pnl_sum'] += trade['pnl']
        else:
            hourly_data[hour]['losses'] += 1
            hourly_data[hour]['loss_pnl_sum'] += abs(trade['pnl'])  # 取绝对值
    
    # 计算每小时的期望值
    expectations = []
    
    for hour in sorted(hourly_data.keys()):
        data = hourly_data[hour]
        
        if data['total'] == 0:
            continue
        
        # 计算各项指标
        win_rate = data['wins'] / data['total']
        loss_rate = data['losses'] / data['total']
        
        # 平均盈利额（仅盈利交易）
        avg_win = data['win_pnl_sum'] / data['wins'] if data['wins'] > 0 else 0
        
        # 平均亏损额（仅亏损交易）
        avg_loss = data['loss_pnl_sum'] / data['losses'] if data['losses'] > 0 else 0
        
        # 平均下注额
        avg_bet = data['bet_sum'] / data['total']
        
        # 140倍杠杆下的手续费率：9.8% (对本金的影响)
        # 原始手续费约0.07% * 140倍 ≈ 9.8%
        fee_rate = 0.098
        
        # 每笔交易的手续费成本（相对于本金）
        avg_fee = avg_bet * fee_rate
        
        # 考虑手续费后的平均盈利
        avg_win_after_fee = avg_win - avg_fee
        
        # 数学期望 = ((平均盈利 - 手续费) * 胜率 - 平均亏损 * 败率) / 平均下注额
        expectation = (avg_win_after_fee * win_rate - avg_loss * loss_rate) / avg_bet if avg_bet > 0 else 0
        
        # 每笔交易的期望盈利（USDT）- 考虑手续费
        expected_profit_per_trade = avg_win_after_fee * win_rate - avg_loss * loss_rate
        
        expectations.append({
            'hour': hour,
            'total_trades': data['total'],
            'wins': data['wins'],
            'losses': data['losses'],
            'win_rate': win_rate * 100,
            'loss_rate': loss_rate * 100,
            'avg_win': avg_win,
            'avg_win_after_fee': avg_win_after_fee,
            'avg_loss': avg_loss,
            'avg_bet': avg_bet,
            'avg_fee': avg_fee,
            'expectation': expectation,
            'expected_profit_per_trade': expected_profit_per_trade,
            'total_pnl': data['win_pnl_sum'] - data['loss_pnl_sum']
        })
    
    return expectations


def print_expectation_report(expectations):
    """打印期望值报告"""
    print("=" * 120)
    print("数学期望分析报告（按小时）- 含手续费")
    print("=" * 120)
    print()
    print("公式：数学期望 = ((平均盈利 - 手续费) × 胜率 - 平均亏损 × 败率) / 平均下注额")
    print("手续费率: 9.8% (140倍杠杆下对本金的影响)")
    print()
    print("=" * 120)
    
    # 表头
    print(f"{'时段':<8} {'交易数':<6} {'胜/负':<10} {'胜率':<8} "
          f"{'平均盈利':<10} {'扣费后':<10} {'平均亏损':<10} {'手续费':<10} "
          f"{'数学期望':<10} {'期望盈利/笔':<12} {'累计盈亏':<10}")
    print("-" * 120)
    
    for exp in expectations:
        print(f"{exp['hour']:02d}:00   "
              f"{exp['total_trades']:<6} "
              f"{exp['wins']}/{exp['losses']:<7} "
              f"{exp['win_rate']:>6.2f}%  "
              f"{exp['avg_win']:>8.4f}  "
              f"{exp['avg_win_after_fee']:>8.4f}  "
              f"{exp['avg_loss']:>8.4f}  "
              f"{exp['avg_fee']:>8.4f}  "
              f"{exp['expectation']:>8.4f}  "
              f"{exp['expected_profit_per_trade']:>10.4f}  "
              f"{exp['total_pnl']:>8.4f}")
    
    print("=" * 120)
    print()
    
    # 排序分析
    print("=" * 120)
    print("【TOP 5 最高数学期望时段】")
    print("=" * 120)
    top_expectations = sorted(expectations, key=lambda x: x['expectation'], reverse=True)[:5]
    
    for i, exp in enumerate(top_expectations, 1):
        print(f"{i}. {exp['hour']:02d}:00-{exp['hour']+1:02d}:00")
        print(f"   数学期望: {exp['expectation']:.4f}")
        print(f"   期望盈利(扣费): {exp['expected_profit_per_trade']:.4f} USDT/笔")
        print(f"   胜率: {exp['win_rate']:.2f}% ({exp['wins']}/{exp['total_trades']})")
        print(f"   平均盈利: {exp['avg_win']:.4f} USDT (扣费后: {exp['avg_win_after_fee']:.4f} USDT)")
        print(f"   平均亏损: {exp['avg_loss']:.4f} USDT | 手续费: {exp['avg_fee']:.4f} USDT")
        print(f"   累计盈亏: {exp['total_pnl']:.4f} USDT")
        print()
    
    print("=" * 120)
    print("【TOP 5 最低数学期望时段】")
    print("=" * 120)
    bottom_expectations = sorted(expectations, key=lambda x: x['expectation'])[:5]
    
    for i, exp in enumerate(bottom_expectations, 1):
        print(f"{i}. {exp['hour']:02d}:00-{exp['hour']+1:02d}:00")
        print(f"   数学期望: {exp['expectation']:.4f}")
        print(f"   期望盈利(扣费): {exp['expected_profit_per_trade']:.4f} USDT/笔")
        print(f"   胜率: {exp['win_rate']:.2f}% ({exp['wins']}/{exp['total_trades']})")
        print(f"   平均盈利: {exp['avg_win']:.4f} USDT (扣费后: {exp['avg_win_after_fee']:.4f} USDT)")
        print(f"   平均亏损: {exp['avg_loss']:.4f} USDT | 手续费: {exp['avg_fee']:.4f} USDT")
        print(f"   累计盈亏: {exp['total_pnl']:.4f} USDT")
        print()
    
    # 策略建议
    print("=" * 120)
    print("【策略建议】")
    print("=" * 120)
    
    # 正期望时段
    positive_exp = [e for e in expectations if e['expectation'] > 0]
    negative_exp = [e for e in expectations if e['expectation'] <= 0]
    
    print(f"✓ 正数学期望时段: {len(positive_exp)}/24 小时")
    print(f"✗ 负数学期望时段: {len(negative_exp)}/24 小时")
    print()
    
    # 推荐时段（期望>0.5且交易数>=10）
    recommended = [e for e in expectations if e['expectation'] > 0.5 and e['total_trades'] >= 10]
    if recommended:
        print("✓ 强烈推荐交易时段（期望>0.5 且 交易>=10笔）:")
        for exp in sorted(recommended, key=lambda x: x['expectation'], reverse=True):
            print(f"  {exp['hour']:02d}:00  期望={exp['expectation']:.4f}, "
                  f"胜率={exp['win_rate']:.2f}%, 交易{exp['total_trades']}笔, "
                  f"累计{exp['total_pnl']:.2f}U")
    
    print()
    
    # 避开时段（期望<0）
    avoid = [e for e in expectations if e['expectation'] < 0 and e['total_trades'] >= 5]
    if avoid:
        print("⚠ 建议避开时段（期望<0 且 交易>=5笔）:")
        for exp in sorted(avoid, key=lambda x: x['expectation']):
            print(f"  {exp['hour']:02d}:00  期望={exp['expectation']:.4f}, "
                  f"胜率={exp['win_rate']:.2f}%, 交易{exp['total_trades']}笔, "
                  f"累计{exp['total_pnl']:.2f}U")
    
    print()
    print("=" * 120)
    
    # 整体期望
    total_trades = sum(e['total_trades'] for e in expectations)
    total_expected_profit = sum(e['expected_profit_per_trade'] * e['total_trades'] for e in expectations)
    overall_expectation = total_expected_profit / total_trades if total_trades > 0 else 0
    
    # 计算总手续费
    total_fees = sum(e['avg_fee'] * e['total_trades'] for e in expectations)
    
    print(f"整体数学期望（加权平均，扣费后）: {overall_expectation:.4f} USDT/笔")
    print(f"总交易数: {total_trades}")
    print(f"理论总期望盈利（扣费后）: {total_expected_profit:.4f} USDT")
    print(f"总手续费成本: {total_fees:.4f} USDT")
    
    actual_total_pnl = sum(e['total_pnl'] for e in expectations)
    print(f"实际总盈亏（不含手续费）: {actual_total_pnl:.4f} USDT")
    print(f"扣除手续费后净盈亏: {actual_total_pnl - total_fees:.4f} USDT")
    print(f"偏差: {abs(actual_total_pnl - total_expected_profit - total_fees):.4f} USDT")
    print("=" * 120)


def export_expectation_to_csv(expectations):
    """导出期望值数据到CSV"""
    filename = '数学期望分析_按小时_含手续费.csv'
    
    with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
        fieldnames = [
            '时段', '交易数', '胜利', '失败', '胜率%', '败率%',
            '平均盈利(USDT)', '扣费后盈利(USDT)', '平均亏损(USDT)', 
            '平均下注(USDT)', '手续费(USDT)',
            '数学期望', '期望盈利/笔(USDT)', '累计盈亏(USDT)'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for exp in expectations:
            writer.writerow({
                '时段': f"{exp['hour']:02d}:00",
                '交易数': exp['total_trades'],
                '胜利': exp['wins'],
                '失败': exp['losses'],
                '胜率%': f"{exp['win_rate']:.2f}",
                '败率%': f"{exp['loss_rate']:.2f}",
                '平均盈利(USDT)': f"{exp['avg_win']:.4f}",
                '扣费后盈利(USDT)': f"{exp['avg_win_after_fee']:.4f}",
                '平均亏损(USDT)': f"{exp['avg_loss']:.4f}",
                '平均下注(USDT)': f"{exp['avg_bet']:.4f}",
                '手续费(USDT)': f"{exp['avg_fee']:.4f}",
                '数学期望': f"{exp['expectation']:.4f}",
                '期望盈利/笔(USDT)': f"{exp['expected_profit_per_trade']:.4f}",
                '累计盈亏(USDT)': f"{exp['total_pnl']:.4f}"
            })
    
    print(f"\n✓ 数学期望分析（含手续费）已导出到: {filename}")


if __name__ == '__main__':
    csv_file = 'trade_log.csv'
    
    print(f"正在读取交易数据: {csv_file}")
    trades = parse_csv_trades(csv_file)
    
    if not trades:
        print("未能解析到交易数据")
        exit(1)
    
    print(f"成功解析 {len(trades)} 笔交易\n")
    
    # 计算期望值
    expectations = calculate_expectation_by_hour(trades)
    
    # 打印报告
    print_expectation_report(expectations)
    
    # 导出CSV
    export_expectation_to_csv(expectations)
