"""
遍历动态止盈止损参数优化（包含切换K线数）
测试在持仓N根K线后降低止盈止损点的效果

策略逻辑：
- 前N根K线：使用原始止盈止损点
- N根K线后：按比例调整止盈止损点
  - switch_bars: 切换的K线数（5, 10, 15, ..., 50）
  - after_switch_tp_ratio: 止盈调整比例（<1降低，=1不变，>1提高）
  - after_switch_sl_ratio: 止损调整比例（<1降低，=1不变，>1提高）
"""

import json
import os
from datetime import datetime
from typing import List, Dict
import csv
import sys

# 导入核心策略类
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from 留存单k线策略改 import KLine, ThreeKlineStrategy


def load_klines(cache_file: str = "ethusdt_15m_klines.json") -> List[KLine]:
    """加载K线数据"""
    if not os.path.exists(cache_file):
        print(f"错误: 找不到缓存文件 {cache_file}")
        print("请先运行主策略文件生成缓存数据")
        return None
    
    print(f"正在读取K线数据: {cache_file}")
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            raw_klines = json.load(f)
        klines = [KLine(k) for k in raw_klines]
        print(f"✓ 成功加载 {len(klines)} 根K线数据")
        return klines
    except Exception as e:
        print(f"✗ 读取数据失败: {e}")
        return None


def test_parameter_combination(klines: List[KLine], 
                               leverage: int,
                               profit_target_percent: float,
                               stop_loss_percent: float,
                               min_k1_range_percent: float,
                               initial_capital: float,
                               switch_bars: int,
                               after_switch_tp_ratio: float,
                               after_switch_sl_ratio: float) -> Dict:
    """测试单组参数组合"""
    
    # 计算现货价格需要变动的百分比
    price_profit_target = profit_target_percent / leverage / 100
    price_stop_loss = stop_loss_percent / leverage / 100
    min_k1_range = min_k1_range_percent / 100
    
    # 创建策略实例
    strategy = ThreeKlineStrategy()
    
    # 查找信号
    signals = strategy.find_signals(
        klines, 
        profit_target=price_profit_target,
        stop_loss=price_stop_loss,
        min_k1_range=min_k1_range,
        switch_bars=switch_bars,
        after_50_bars_tp_ratio=after_switch_tp_ratio,
        after_50_bars_sl_ratio=after_switch_sl_ratio
    )
    
    # 计算统计结果
    stats = strategy.calculate_win_rate(signals, leverage=leverage, initial_capital=initial_capital)
    
    return {
        'leverage': leverage,
        'profit_target_percent': profit_target_percent,
        'stop_loss_percent': stop_loss_percent,
        'min_k1_range_percent': min_k1_range_percent,
        'switch_bars': switch_bars,
        'after_switch_tp_ratio': after_switch_tp_ratio,
        'after_switch_sl_ratio': after_switch_sl_ratio,
        'total_trades': stats['total_trades'],
        'wins': stats['wins'],
        'losses': stats['losses'],
        'win_rate': stats['win_rate'],
        'avg_profit': stats['avg_profit'],
        'avg_loss': stats['avg_loss'],
        'avg_holding_bars': stats['avg_holding_bars'],
        'profit_factor': stats['profit_factor'],
        'total_pnl': stats['total_pnl'],
        'final_capital': stats['final_capital'],
        'total_return_percent': (stats['total_pnl'] / (stats['total_trades'] * initial_capital) * 100) if stats['total_trades'] > 0 else 0
    }


def main():
    """主函数"""
    print("="*80)
    print("动态止盈止损参数优化（包含切换K线数遍历）")
    print("="*80)
    
    # 加载K线数据
    klines = load_klines("ethusdt_15m_klines.json")
    if not klines:
        return
    
    # ====== 固定参数 ======
    leverage = 140
    profit_target_percent = 330
    stop_loss_percent = 500
    min_k1_range_percent = 0.21
    initial_capital = 1.0
    # =====================
    
    print(f"\n固定参数:")
    print(f"  杠杆: {leverage}x")
    print(f"  止盈: {profit_target_percent}%")
    print(f"  止损: {stop_loss_percent}%")
    print(f"  K1涨跌幅: {min_k1_range_percent}%")
    print(f"  每次投入: {initial_capital} USDT")
    
    # ====== 遍历参数范围 ======
    # 切换K线数：从5到50，步进5
    switch_bars_list = list(range(5, 51, 5))
    
    # N根K线后止盈比例：测试降低到0.3-1.0倍
    tp_ratios = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    
    # N根K线后止损比例：测试降低到0.3-1.0倍
    sl_ratios = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    
    print(f"\n遍历参数:")
    print(f"  切换K线数: {switch_bars_list}")
    print(f"  切换后止盈比例: {tp_ratios}")
    print(f"  切换后止损比例: {sl_ratios}")
    print(f"  总组合数: {len(switch_bars_list) * len(tp_ratios) * len(sl_ratios)}")
    # =========================
    
    results = []
    total_combinations = len(switch_bars_list) * len(tp_ratios) * len(sl_ratios)
    current = 0
    
    print("\n开始遍历测试...")
    print("-"*80)
    
    for switch_bars in switch_bars_list:
        for tp_ratio in tp_ratios:
            for sl_ratio in sl_ratios:
                current += 1
                print(f"[{current}/{total_combinations}] 测试: 切换K线={switch_bars}, TP比例={tp_ratio}, SL比例={sl_ratio}      ", end='\r')
                
                result = test_parameter_combination(
                    klines=klines,
                    leverage=leverage,
                    profit_target_percent=profit_target_percent,
                    stop_loss_percent=stop_loss_percent,
                    min_k1_range_percent=min_k1_range_percent,
                    initial_capital=initial_capital,
                    switch_bars=switch_bars,
                    after_switch_tp_ratio=tp_ratio,
                    after_switch_sl_ratio=sl_ratio
                )
                
                results.append(result)
    
    print("\n" + "-"*80)
    print(f"✓ 完成所有测试")
    
    # 按总收益率排序
    results.sort(key=lambda x: x['total_return_percent'], reverse=True)
    
    # 显示前10名结果
    print("\n" + "="*80)
    print("Top 10 最佳参数组合 (按总收益率排序)")
    print("="*80)
    
    for i, result in enumerate(results[:10], 1):
        print(f"\n排名 #{i}")
        print(f"  切换K线数: {result['switch_bars']}根")
        print(f"  切换后止盈比例: {result['after_switch_tp_ratio']:.1f}x (原{profit_target_percent}%变为{profit_target_percent*result['after_switch_tp_ratio']:.0f}%)")
        print(f"  切换后止损比例: {result['after_switch_sl_ratio']:.1f}x (原{stop_loss_percent}%变为{stop_loss_percent*result['after_switch_sl_ratio']:.0f}%)")
        print(f"  总交易数: {result['total_trades']}")
        print(f"  胜率: {result['win_rate']:.2f}%")
        print(f"  盈亏比: {result['profit_factor']:.2f}")
        print(f"  平均持仓: {result['avg_holding_bars']:.1f}根K线")
        print(f"  总盈亏: {result['total_pnl']:+.4f} USDT")
        print(f"  总收益率: {result['total_return_percent']:+.2f}%")
        print("-"*80)
    
    # 导出完整结果到CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"参数优化结果_动态止盈止损_含K线数_{timestamp}.csv"
    
    print(f"\n正在导出完整结果到: {csv_filename}")
    
    try:
        with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = [
                '杠杆', '止盈%', '止损%', 'K1涨跌幅%',
                '切换K线数', '切换后止盈比例', '切换后止损比例',
                '总交易数', '盈利次数', '亏损次数', '胜率%',
                '平均盈利%', '平均亏损%', '平均持仓K线数', '盈亏比',
                '总盈亏USDT', '最终资金USDT', '总收益率%'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                writer.writerow({
                    '杠杆': result['leverage'],
                    '止盈%': result['profit_target_percent'],
                    '止损%': result['stop_loss_percent'],
                    'K1涨跌幅%': result['min_k1_range_percent'],
                    '切换K线数': result['switch_bars'],
                    '切换后止盈比例': f"{result['after_switch_tp_ratio']:.1f}",
                    '切换后止损比例': f"{result['after_switch_sl_ratio']:.1f}",
                    '总交易数': result['total_trades'],
                    '盈利次数': result['wins'],
                    '亏损次数': result['losses'],
                    '胜率%': f"{result['win_rate']:.2f}",
                    '平均盈利%': f"{result['avg_profit']:.2f}",
                    '平均亏损%': f"{result['avg_loss']:.2f}",
                    '平均持仓K线数': f"{result['avg_holding_bars']:.1f}",
                    '盈亏比': f"{result['profit_factor']:.2f}",
                    '总盈亏USDT': f"{result['total_pnl']:.4f}",
                    '最终资金USDT': f"{result['final_capital']:.4f}",
                    '总收益率%': f"{result['total_return_percent']:.2f}"
                })
        
        print(f"✓ 结果已导出到: {csv_filename}")
        
    except Exception as e:
        print(f"✗ 导出失败: {e}")
    
    # 统计分析
    print("\n" + "="*80)
    print("统计分析")
    print("="*80)
    
    # 找出最佳切换K线数
    best_by_switch_bars = {}
    for result in results:
        bars = result['switch_bars']
        if bars not in best_by_switch_bars or result['total_return_percent'] > best_by_switch_bars[bars]['total_return_percent']:
            best_by_switch_bars[bars] = result
    
    print("\n各切换K线数的最佳表现:")
    for bars in sorted(best_by_switch_bars.keys()):
        r = best_by_switch_bars[bars]
        print(f"  {bars}根K线: 收益率 {r['total_return_percent']:+.2f}% (TP={r['after_switch_tp_ratio']:.1f}x, SL={r['after_switch_sl_ratio']:.1f}x)")
    
    # 找出最佳止盈比例
    best_by_tp = {}
    for result in results:
        tp = result['after_switch_tp_ratio']
        if tp not in best_by_tp or result['total_return_percent'] > best_by_tp[tp]['total_return_percent']:
            best_by_tp[tp] = result
    
    print("\n各止盈比例的最佳表现:")
    for tp in sorted(best_by_tp.keys()):
        r = best_by_tp[tp]
        print(f"  止盈比例 {tp:.1f}x: 收益率 {r['total_return_percent']:+.2f}% (切换={r['switch_bars']}根, SL={r['after_switch_sl_ratio']:.1f}x)")
    
    # 找出最佳止损比例
    best_by_sl = {}
    for result in results:
        sl = result['after_switch_sl_ratio']
        if sl not in best_by_sl or result['total_return_percent'] > best_by_sl[sl]['total_return_percent']:
            best_by_sl[sl] = result
    
    print("\n各止损比例的最佳表现:")
    for sl in sorted(best_by_sl.keys()):
        r = best_by_sl[sl]
        print(f"  止损比例 {sl:.1f}x: 收益率 {r['total_return_percent']:+.2f}% (切换={r['switch_bars']}根, TP={r['after_switch_tp_ratio']:.1f}x)")
    
    print("\n" + "="*80)
    print("优化建议:")
    best = results[0]
    print(f"  推荐切换K线数: {best['switch_bars']}根")
    print(f"  推荐止盈比例: {best['after_switch_tp_ratio']:.1f}x")
    print(f"  推荐止损比例: {best['after_switch_sl_ratio']:.1f}x")
    print(f"  预期收益率: {best['total_return_percent']:+.2f}%")
    print(f"  交易次数: {best['total_trades']}")
    print(f"  胜率: {best['win_rate']:.2f}%")
    print("="*80)


if __name__ == '__main__':
    main()
