# 参数优化LOG文件导出功能

## 功能说明

现在参数优化脚本会自动生成两个文件：

1. **CSV文件** - 包含所有参数组合的完整结果（Excel可打开）
2. **LOG文件** - 包含TOP 10盈利策略的详细信息（文本格式，易读）

## LOG文件内容

LOG文件包含以下信息：

### 1. 总体信息
- 生成时间
- 固定参数（杠杆、投入资金等）
- 测试组合数和有效组合数

### 2. 每个策略详情（TOP 10）

#### 【参数设置】
- 杠杆倍数
- 止盈/止损百分比
- K1涨跌幅要求
- 对应的现货价格变动

#### 【交易统计】
- 总交易数
- 胜率
- 盈亏比
- 平均持仓时间（普通版本）

#### 【资金收益】
- 总投入
- 总盈亏
- 最终资金
- 收益率

#### 【复制参数代码】
```python
leverage = 50
profit_target_percent = 30
stop_loss_percent = 20
initial_capital = 1.0
min_k1_range_percent = 0.21
```
可以直接复制到策略文件中使用！

## 使用方法

### 普通版本（带超时机制）
```bash
python optimize_parameters.py
```
生成文件：
- `optimization_results_YYYYMMDD_HHMMSS.csv`
- `optimization_top10_YYYYMMDD_HHMMSS.log`

### 收盘价强制平仓版本
```bash
python optimize_parameters_close_exit.py
```
生成文件：
- `optimization_results_close_exit_YYYYMMDD_HHMMSS.csv`
- `optimization_top10_YYYYMMDD_HHMMSS.log`

## LOG文件示例

```
================================================================================
第 1 名 - 最优参数组合
================================================================================

【参数设置】
  杠杆倍数: 50x
  止盈设置: 30% (合约收益)
  止损设置: 99% (合约亏损)
  K1涨跌幅要求: 0.21%
  每次投入: 1.0 USDT
  超时平仓: 止盈>41根K线, 止损>102根K线
  (对应现货价格变动: 止盈=0.60%, 止损=1.98%)

【交易统计】
  总交易数: 620 笔
  胜率: 67.42%
  盈亏比: 1.22
  平均持仓: 22.8 根K线

【资金收益】
  总投入: 620.00 USDT
  总盈亏: +17.8117 USDT
  最终资金: 637.8117 USDT
  收益率: +2.87%

【复制参数代码】
leverage = 50
profit_target_percent = 30
stop_loss_percent = 99
initial_capital = 1.0
min_k1_range_percent = 0.21
max_holding_bars_tp = 41
max_holding_bars_sl = 102
```

## 优势

1. **易读性** - LOG格式清晰，直接打开就能看懂
2. **完整性** - 包含所有关键参数和统计指标
3. **可复制** - 直接复制参数代码到策略文件
4. **可追溯** - 文件名包含时间戳，方便管理多次优化结果
5. **双格式** - CSV用于数据分析，LOG用于快速查阅

## 注意事项

- LOG文件仅包含TOP 10策略
- CSV文件包含所有测试组合的完整数据
- 建议保存好每次优化的LOG文件，便于对比不同时间段的最优参数
- 历史回测结果不代表未来收益，需结合实际情况调整参数
