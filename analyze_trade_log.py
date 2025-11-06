"""
交易日志分析脚本 - 统计30根K线内的盈亏比例
"""

import re


def analyze_trade_log(filename='trade_log.txt', max_bars=30):
    """
    分析交易日志文件，统计指定K线数量内的盈利和亏损比例
    
    Args:
        filename: 交易日志文件名
        max_bars: 最大K线数量阈值 (默认30根)
    """
    
    profits_within_limit = 0  # 在限制内的盈利交易
    losses_within_limit = 0   # 在限制内的亏损交易
    profits_beyond_limit = 0  # 超出限制的盈利交易
    losses_beyond_limit = 0   # 超出限制的亏损交易
    
    total_trades = 0
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 按交易分割
        trades = re.split(r'-{80,}', content)
        
        for trade in trades:
            # 查找交易类型（止盈/止损）
            trade_type_match = re.search(r'交易 #\d+ - (止盈|止损)', trade)
            if not trade_type_match:
                continue
            
            trade_type = trade_type_match.group(1)
            
            # 查找持仓时长
            holding_match = re.search(r'持仓时长: (\d+)根K线', trade)
            if not holding_match:
                continue
            
            holding_bars = int(holding_match.group(1))
            total_trades += 1
            
            # 统计分类
            is_profit = (trade_type == '止盈')
            is_within_limit = (holding_bars <= max_bars)
            
            if is_profit and is_within_limit:
                profits_within_limit += 1
            elif is_profit and not is_within_limit:
                profits_beyond_limit += 1
            elif not is_profit and is_within_limit:
                losses_within_limit += 1
            else:  # 止损且超出限制
                losses_beyond_limit += 1
        
        # 计算统计数据
        total_within_limit = profits_within_limit + losses_within_limit
        total_beyond_limit = profits_beyond_limit + losses_beyond_limit
        
        # 输出结果
        print("="*80)
        print(f"交易日志分析结果 - {max_bars}根K线内盈亏统计")
        print("="*80)
        print(f"数据来源: {filename}")
        print(f"分析总交易数: {total_trades} 笔")
        print("="*80)
        
        print(f"\n【{max_bars}根K线内的交易】")
        print(f"  盈利交易: {profits_within_limit} 笔")
        print(f"  亏损交易: {losses_within_limit} 笔")
        print(f"  小计: {total_within_limit} 笔")
        if total_within_limit > 0:
            win_rate_within = profits_within_limit / total_within_limit * 100
            print(f"  胜率: {win_rate_within:.2f}%")
            print(f"  盈亏比: {profits_within_limit}:{losses_within_limit}")
        
        print(f"\n【超过{max_bars}根K线的交易】")
        print(f"  盈利交易: {profits_beyond_limit} 笔")
        print(f"  亏损交易: {losses_beyond_limit} 笔")
        print(f"  小计: {total_beyond_limit} 笔")
        if total_beyond_limit > 0:
            win_rate_beyond = profits_beyond_limit / total_beyond_limit * 100
            print(f"  胜率: {win_rate_beyond:.2f}%")
            print(f"  盈亏比: {profits_beyond_limit}:{losses_beyond_limit}")
        
        print(f"\n【汇总统计】")
        print(f"  总盈利: {profits_within_limit + profits_beyond_limit} 笔")
        print(f"  总亏损: {losses_within_limit + losses_beyond_limit} 笔")
        print(f"  总胜率: {(profits_within_limit + profits_beyond_limit) / total_trades * 100:.2f}%")
        
        within_pct = total_within_limit / total_trades * 100 if total_trades > 0 else 0
        beyond_pct = total_beyond_limit / total_trades * 100 if total_trades > 0 else 0
        print(f"\n  {max_bars}根K线内交易占比: {within_pct:.2f}% ({total_within_limit}/{total_trades})")
        print(f"  超过{max_bars}根K线交易占比: {beyond_pct:.2f}% ({total_beyond_limit}/{total_trades})")
        
        print("="*80)
        
        # 返回统计结果
        return {
            'max_bars': max_bars,
            'total_trades': total_trades,
            'within_limit': {
                'profits': profits_within_limit,
                'losses': losses_within_limit,
                'total': total_within_limit,
                'win_rate': win_rate_within if total_within_limit > 0 else 0
            },
            'beyond_limit': {
                'profits': profits_beyond_limit,
                'losses': losses_beyond_limit,
                'total': total_beyond_limit,
                'win_rate': win_rate_beyond if total_beyond_limit > 0 else 0
            }
        }
    
    except FileNotFoundError:
        print(f"错误: 找不到文件 '{filename}'")
        return None
    except Exception as e:
        print(f"错误: 分析过程中出现异常 - {e}")
        return None


if __name__ == '__main__':
    # 分析30根K线内的交易
    result = analyze_trade_log('trade_log.txt', max_bars=30)
    
    # 可以尝试其他阈值
    print("\n\n")
    print("其他K线阈值统计:")
    print("-"*80)
    for bars in [20, 40, 50]:
        result = analyze_trade_log('trade_log.txt', max_bars=bars)
        print("\n")
