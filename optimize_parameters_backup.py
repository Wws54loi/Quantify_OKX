"""
参数优化脚本 - 寻找最优的止盈、止损和K1涨跌幅参数（备份版本）
"""

import json
import os
from datetime import datetime
from three_kline_strategy_backup import KLine, ThreeKlineStrategy
import itertools


def optimize_parameters():
    """遍历参数组合，寻找最优参数"""
    
    # ====== 固定参数 ======
    leverage = 50  # 固定杠杆倍数
    initial_capital = 1.0  # 每次投入
    
    # ====== 参数搜索范围 ======
    profit_target_range = range(20, 101, 1)  # 止盈: 20%, 21%, 22%, ..., 100%
    stop_loss_range = range(10, 101, 1)      # 止损: 10%, 11%, 12%, ..., 100%
    min_k1_range_range = [round(i * 0.01, 2) for i in range(10, 101)]  # K1涨跌幅: 0.10%, 0.11%, 0.12%, ..., 1.00%
    
    print("="*80)
    print("参数优化系统 - 寻找最优止盈止损参数（备份版本）")
    print("="*80)
    print(f"固定参数:")
    print(f"  杠杆倍数: {leverage}x")
    print(f"  每次投入: {initial_capital} USDT")
    print(f"\n搜索范围:")
    print(f"  止盈百分比: {min(profit_target_range)}% ~ {max(profit_target_range)}%")
    print(f"  止损百分比: {min(stop_loss_range)}% ~ {max(stop_loss_range)}%")
    print(f"  K1涨跌幅要求: {min(min_k1_range_range)}% ~ {max(min_k1_range_range)}%")
    
    # 计算总组合数
    total_combinations = len(list(profit_target_range)) * len(list(stop_loss_range)) * len(min_k1_range_range)
    print(f"\n总共需要测试: {total_combinations} 种参数组合")
    print("="*80)
    
    # 加载K线数据
    cache_file = "btcusdt_15m_klines.json"
    if not os.path.exists(cache_file):
        print("错误: 找不到K线数据缓存文件!")
        print("请先运行 three_kline_strategy.py 生成数据缓存")
        return
    
    print(f"\n正在读取K线数据...")
    with open(cache_file, 'r', encoding='utf-8') as f:
        raw_klines = json.load(f)
    
    klines = [KLine(k) for k in raw_klines]
    print(f"✓ 成功读取 {len(klines)} 根K线数据")
    
    # 存储所有结果
    results = []
    best_result = None
    best_profit = float('-inf')
    
    # 遍历所有参数组合
    print(f"\n开始参数优化...")
    print("-"*80)
    
    count = 0
    for profit_pct, stop_pct, k1_pct in itertools.product(profit_target_range, stop_loss_range, min_k1_range_range):
        count += 1
        
        # 计算现货价格变动百分比
        price_profit_target = profit_pct / leverage / 100
        price_stop_loss = stop_pct / leverage / 100
        min_k1_range = k1_pct / 100
        
        # 运行策略
        strategy = ThreeKlineStrategy()
        signals = strategy.find_signals(
            klines,
            profit_target=price_profit_target,
            stop_loss=price_stop_loss,
            min_k1_range=min_k1_range
        )
        
        # 计算统计
        stats = strategy.calculate_win_rate(signals, leverage=leverage, initial_capital=initial_capital)
        
        # 只记录有交易的结果
        if stats['total_trades'] > 0:
            result = {
                'profit_target_percent': profit_pct,
                'stop_loss_percent': stop_pct,
                'min_k1_range_percent': k1_pct,
                'total_trades': stats['total_trades'],
                'win_rate': stats['win_rate'],
                'total_pnl': stats['total_pnl'],
                'final_capital': stats['final_capital'],
                'profit_factor': stats['profit_factor'],
                'avg_holding_bars': stats['avg_holding_bars'],
                'return_rate': (stats['total_pnl'] / (stats['total_trades'] * initial_capital) * 100) if stats['total_trades'] > 0 else 0
            }
            results.append(result)
            
            # 更新最佳结果（以总盈亏为标准）
            if stats['total_pnl'] > best_profit:
                best_profit = stats['total_pnl']
                best_result = result
        
        # 显示进度
        if count % 100 == 0 or count == total_combinations:
            print(f"进度: {count}/{total_combinations} ({count/total_combinations*100:.1f}%) - 当前最佳盈亏: {best_profit:+.4f} USDT", end='\r')
    
    print("\n" + "-"*80)
    print(f"✓ 优化完成! 共测试了 {len(results)} 个有效参数组合")
    
    # 按总盈亏排序
    results.sort(key=lambda x: x['total_pnl'], reverse=True)
    
    # 显示TOP 10结果
    print("\n" + "="*80)
    print("TOP 10 最佳参数组合 (按总盈亏排序)")
    print("="*80)
    
    for i, result in enumerate(results[:10], 1):
        print(f"\n第 {i} 名:")
        print(f"  止盈: {result['profit_target_percent']}% | 止损: {result['stop_loss_percent']}% | K1涨跌幅: {result['min_k1_range_percent']}%")
        print(f"  总交易数: {result['total_trades']}")
        print(f"  胜率: {result['win_rate']:.2f}%")
        print(f"  总盈亏: {result['total_pnl']:+.4f} USDT")
        print(f"  收益率: {result['return_rate']:+.2f}%")
        print(f"  盈亏比: {result['profit_factor']:.2f}")
        print(f"  平均持仓: {result['avg_holding_bars']:.1f}根K线")
    
    # 导出完整结果到CSV和LOG
    print("\n" + "="*80)
    print("导出优化结果")
    print("="*80)
    
    import csv
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"optimization_results_backup_{timestamp}.csv"
    logfilename = f"optimization_top10_backup_{timestamp}.log"
    
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        fieldnames = [
            '排名', '止盈%', '止损%', 'K1涨跌幅%', '总交易数', '胜率%', 
            '总盈亏USDT', '收益率%', '盈亏比', '平均持仓K线数'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for i, result in enumerate(results, 1):
            writer.writerow({
                '排名': i,
                '止盈%': result['profit_target_percent'],
                '止损%': result['stop_loss_percent'],
                'K1涨跌幅%': result['min_k1_range_percent'],
                '总交易数': result['total_trades'],
                '胜率%': f"{result['win_rate']:.2f}",
                '总盈亏USDT': f"{result['total_pnl']:.4f}",
                '收益率%': f"{result['return_rate']:.2f}",
                '盈亏比': f"{result['profit_factor']:.2f}",
                '平均持仓K线数': f"{result['avg_holding_bars']:.1f}"
            })
    
    print(f"✓ 完整结果已导出到: {filename}")
    
    # 导出前10条盈利策略到LOG文件
    try:
        with open(logfilename, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("参数优化结果 - TOP 10 盈利策略（备份版本）\n")
            f.write("="*80 + "\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"固定参数: 杠杆={leverage}x, 每次投入={initial_capital} USDT\n")
            f.write(f"测试组合数: {total_combinations} 种\n")
            f.write(f"有效组合数: {len(results)} 种\n")
            f.write("="*80 + "\n\n")
            
            for i, result in enumerate(results[:10], 1):
                f.write(f"{'='*80}\n")
                f.write(f"第 {i} 名 - 最优参数组合\n")
                f.write(f"{'='*80}\n\n")
                
                f.write(f"【参数设置】\n")
                f.write(f"  杠杆倍数: {leverage}x\n")
                f.write(f"  止盈设置: {result['profit_target_percent']}% (合约收益)\n")
                f.write(f"  止损设置: {result['stop_loss_percent']}% (合约亏损)\n")
                f.write(f"  K1涨跌幅要求: {result['min_k1_range_percent']}%\n")
                f.write(f"  每次投入: {initial_capital} USDT\n")
                
                price_profit = result['profit_target_percent'] / leverage
                price_stop = result['stop_loss_percent'] / leverage
                f.write(f"  (对应现货价格变动: 止盈={price_profit:.2f}%, 止损={price_stop:.2f}%)\n\n")
                
                f.write(f"【交易统计】\n")
                f.write(f"  总交易数: {result['total_trades']} 笔\n")
                f.write(f"  胜率: {result['win_rate']:.2f}%\n")
                f.write(f"  盈亏比: {result['profit_factor']:.2f}\n")
                f.write(f"  平均持仓: {result['avg_holding_bars']:.1f} 根K线\n\n")
                
                f.write(f"【资金收益】\n")
                f.write(f"  总投入: {result['total_trades'] * initial_capital:.2f} USDT\n")
                f.write(f"  总盈亏: {result['total_pnl']:+.4f} USDT\n")
                f.write(f"  最终资金: {result['final_capital']:.4f} USDT\n")
                f.write(f"  收益率: {result['return_rate']:+.2f}%\n\n")
                
                f.write(f"【复制参数代码】\n")
                f.write(f"leverage = {leverage}\n")
                f.write(f"profit_target_percent = {result['profit_target_percent']}\n")
                f.write(f"stop_loss_percent = {result['stop_loss_percent']}\n")
                f.write(f"initial_capital = {initial_capital}\n")
                f.write(f"min_k1_range_percent = {result['min_k1_range_percent']}\n\n")
            
            f.write("="*80 + "\n")
            f.write("说明:\n")
            f.write("- 以上策略按总盈亏从高到低排序\n")
            f.write("- 实际交易需考虑手续费、滑点、资金费率等因素\n")
            f.write("- 历史回测结果不代表未来收益\n")
            f.write("- 建议根据自身风险承受能力选择合适参数\n")
            f.write("="*80 + "\n")
        
        print(f"✓ TOP 10策略已导出到: {logfilename}")
    except Exception as e:
        print(f"✗ 导出LOG失败: {e}")
    
    # 显示最佳参数建议
    if best_result:
        print("\n" + "="*80)
        print("最佳参数建议（备份版本）")
        print("="*80)
        print(f"leverage = {leverage}")
        print(f"profit_target_percent = {best_result['profit_target_percent']}")
        print(f"stop_loss_percent = {best_result['stop_loss_percent']}")
        print(f"initial_capital = {initial_capital}")
        print(f"min_k1_range_percent = {best_result['min_k1_range_percent']}")
        print("="*80)
        print(f"\n使用此参数预期结果:")
        print(f"  总交易数: {best_result['total_trades']}")
        print(f"  胜率: {best_result['win_rate']:.2f}%")
        print(f"  总盈亏: {best_result['total_pnl']:+.4f} USDT")
        print(f"  收益率: {best_result['return_rate']:+.2f}%")
        print(f"  盈亏比: {best_result['profit_factor']:.2f}")
        print(f"  平均持仓: {best_result['avg_holding_bars']:.1f}根K线")
    
    return results


if __name__ == '__main__':
    optimize_parameters()
