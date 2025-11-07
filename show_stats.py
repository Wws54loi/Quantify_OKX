import os

files = [f for f in os.listdir('策略分析/止损K线图') if f.endswith('.png')]
trade_files = [f for f in files if f.startswith('trade_')]
summary_files = [f for f in files if f.startswith('summary')]

long_trades = len([f for f in trade_files if '做多' in f])
short_trades = len([f for f in trade_files if '做空' in f])

print('\n' + '='*60)
print('📊 止损K线图表生成统计')
print('='*60)
print(f'\n总计生成: {len(files)} 个图表文件')
print(f'  - 个体K线图: {len(trade_files)} 张')
print(f'  - 汇总分析图: {len(summary_files)} 张')
print(f'\n交易方向分布:')
print(f'  - 做多止损: {long_trades} 笔 ({long_trades/len(trade_files)*100:.1f}%)')
print(f'  - 做空止损: {short_trades} 笔 ({short_trades/len(trade_files)*100:.1f}%)')
print(f'\n图表保存位置: 策略分析/止损K线图/')
print('='*60)
