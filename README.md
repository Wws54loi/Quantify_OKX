# OKX自动化交易

一个基于 Python 的自动化比特币交易机器人，利用 欧易OKX 接口实时监控 BTC/USDT 的价格波动，当波动幅度超过设定阈值时，自动执行买入或卖出操作。适合量化交易初学者、编程教学和自动化交易入门实战使用。

# OKX 自动搬砖套利机器人 🤖💰

一个基于 [ccxt](https://github.com/ccxt/ccxt) 库编写的自动化套利机器人，监控 OKX 上的 BTC/USDT 价格波动，当涨跌幅超过设定阈值（默认1%）时自动买入或卖出。

## 功能介绍

- 自动连接 OKX 实时行情
- 支持代理访问（适配翻墙）
- 自动监测 BTC/USDT 价格波动
- 达到设定阈值（如 ±1%）后自动下单交易
- 支持自定义交易币种、阈值、交易频率

## 准备工具

欧易API 可在官网获取
www.okx.com

python
www.python.org

安装依赖
```bash
pip install ccxt
