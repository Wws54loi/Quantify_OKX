"""
止损交易K线形态分析
- 从止损交易日志中提取交易信息
- 调用币安API获取对应K线数据
- 可视化K1和K2的形态
- 分析止损交易的共同特征
"""

import re
import urllib.request
import json
import time
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Rectangle
from typing import List, Dict, Tuple

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False


class BinanceAPI:
    """币安API接口"""
    BASE_URL = "https://api.binance.com"
    
    @staticmethod
    def get_klines_by_time(symbol: str, interval: str, start_time: int, end_time: int) -> List[List]:
        """
        根据时间范围获取K线数据
        
        参数:
            symbol: 交易对
            interval: K线周期
            start_time: 开始时间戳(毫秒)
            end_time: 结束时间戳(毫秒)
        """
        url = f"{BinanceAPI.BASE_URL}/api/v3/klines?symbol={symbol}&interval={interval}&startTime={start_time}&endTime={end_time}&limit=1000"
        
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return data
        except Exception as e:
            print(f"获取K线数据失败: {e}")
            return []


class KLine:
    """K线数据类"""
    def __init__(self, kline_data: List):
        self.timestamp = int(kline_data[0])
        self.open = float(kline_data[1])
        self.high = float(kline_data[2])
        self.low = float(kline_data[3])
        self.close = float(kline_data[4])
        self.volume = float(kline_data[5])
        
        self.body_high = max(self.open, self.close)
        self.body_low = min(self.open, self.close)
        self.body_length = abs(self.close - self.open)
        self.upper_shadow = self.high - self.body_high
        self.lower_shadow = self.body_low - self.low
        self.total_shadow = self.upper_shadow + self.lower_shadow
        self.total_range = self.high - self.low
        
    def is_bullish(self):
        """是否阳线"""
        return self.close > self.open
    
    def get_body_ratio(self):
        """实体占总长度的比例"""
        if self.total_range == 0:
            return 0
        return self.body_length / self.total_range
    
    def get_shadow_ratio(self):
        """影线占总长度的比例"""
        if self.total_range == 0:
            return 0
        return self.total_shadow / self.total_range
    
    def get_upper_shadow_ratio(self):
        """上影线占总长度的比例"""
        if self.total_range == 0:
            return 0
        return self.upper_shadow / self.total_range
    
    def get_lower_shadow_ratio(self):
        """下影线占总长度的比例"""
        if self.total_range == 0:
            return 0
        return self.lower_shadow / self.total_range


def parse_trade_log(file_path: str) -> List[Dict]:
    """解析交易日志，提取止损交易信息"""
    trades = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 分割每笔交易
    trade_blocks = re.split(r'-{80,}', content)
    
    for block in trade_blocks:
        if '止损' not in block or 'K1区间' not in block:
            continue
        
        trade = {}
        
        # 提取交易编号
        match = re.search(r'交易 #(\d+)', block)
        if match:
            trade['id'] = int(match.group(1))
        
        # 提取方向
        match = re.search(r'交易方向: (做多|做空)', block)
        if match:
            trade['direction'] = match.group(1)
        
        # 提取入场时间
        match = re.search(r'入场时间: (\d{4}-\d{2}-\d{2} \d{2}:\d{2})', block)
        if match:
            trade['entry_time'] = match.group(1)
        
        # 提取入场价格
        match = re.search(r'入场价格: ([\d.]+)', block)
        if match:
            trade['entry_price'] = float(match.group(1))
        
        # 提取K1区间
        match = re.search(r'K1区间: \[([\d.]+) - ([\d.]+)\]', block)
        if match:
            trade['k1_low'] = float(match.group(1))
            trade['k1_high'] = float(match.group(2))
        
        # 提取K2区间
        match = re.search(r'K2区间: \[([\d.]+) - ([\d.]+)\]', block)
        if match:
            trade['k2_low'] = float(match.group(1))
            trade['k2_high'] = float(match.group(2))
        
        # 提取策略类型
        match = re.search(r'策略类型: (rule\d+)', block)
        if match:
            trade['rule_type'] = match.group(1)
        
        if 'entry_time' in trade and 'k1_low' in trade:
            trades.append(trade)
    
    return trades


def get_klines_for_trade(trade: Dict) -> Tuple[KLine, KLine]:
    """获取交易对应的K1和K2的K线数据"""
    entry_time = datetime.strptime(trade['entry_time'], '%Y-%m-%d %H:%M')
    
    # 根据策略类型确定需要获取的K线范围
    # 入场时间是K2(rule1)或K3(rule2)的收盘时间
    # 需要向前获取3根K线以确保包含K1和K2
    start_time = entry_time - timedelta(hours=1)  # 向前1小时(4根15分钟K线)
    end_time = entry_time + timedelta(minutes=15)
    
    # 转换为毫秒时间戳
    start_ts = int(start_time.timestamp() * 1000)
    end_ts = int(end_time.timestamp() * 1000)
    
    # 获取K线数据
    klines_data = BinanceAPI.get_klines_by_time('BTCUSDT', '15m', start_ts, end_ts)
    
    if len(klines_data) < 3:
        return None, None
    
    klines = [KLine(k) for k in klines_data]
    
    # 查找匹配K1和K2的K线
    # 通过K1和K2的区间来匹配
    k1, k2 = None, None
    
    for i in range(len(klines) - 1):
        kline1 = klines[i]
        kline2 = klines[i + 1]
        
        # 检查是否匹配K1
        if (abs(kline1.low - trade['k1_low']) < 1 and 
            abs(kline1.high - trade['k1_high']) < 1):
            k1 = kline1
            k2 = kline2
            break
    
    return k1, k2


def plot_kline_pair(k1: KLine, k2: KLine, trade: Dict, save_path: str = None):
    """绘制K1和K2的K线图"""
    fig, ax = plt.subplots(figsize=(12, 8))
    
    klines = [k1, k2]
    x_positions = [0, 1]
    labels = ['K1', 'K2']
    
    for i, (kline, x, label) in enumerate(zip(klines, x_positions, labels)):
        # 确定颜色
        color = 'green' if kline.is_bullish() else 'red'
        
        # 绘制影线
        ax.plot([x, x], [kline.low, kline.high], color='black', linewidth=1)
        
        # 绘制实体
        body_height = abs(kline.close - kline.open)
        body_bottom = min(kline.open, kline.close)
        rect = Rectangle((x - 0.3, body_bottom), 0.6, body_height, 
                         facecolor=color, edgecolor='black', linewidth=1.5, alpha=0.8)
        ax.add_patch(rect)
        
        # 添加标签
        ax.text(x, kline.low - (k1.high - k1.low) * 0.05, label, 
               ha='center', fontsize=12, fontweight='bold')
        
        # 添加价格标注
        ax.text(x + 0.35, kline.high, f'H: {kline.high:.2f}', fontsize=9, color='blue')
        ax.text(x + 0.35, kline.low, f'L: {kline.low:.2f}', fontsize=9, color='purple')
        ax.text(x + 0.35, kline.open, f'O: {kline.open:.2f}', fontsize=9, color='orange')
        ax.text(x + 0.35, kline.close, f'C: {kline.close:.2f}', fontsize=9, color='brown')
    
    # 绘制K1的高低点参考线
    ax.axhline(y=k1.high, color='blue', linestyle='--', linewidth=1, alpha=0.5, label='K1最高点')
    ax.axhline(y=k1.low, color='purple', linestyle='--', linewidth=1, alpha=0.5, label='K1最低点')
    
    # 标注入场价格
    entry_price = trade.get('entry_price', 0)
    if entry_price > 0:
        ax.axhline(y=entry_price, color='red', linestyle='-', linewidth=2, alpha=0.7, label=f'入场价: {entry_price:.2f}')
    
    # 设置标题和标签
    direction = trade.get('direction', '')
    trade_id = trade.get('id', '')
    entry_time = trade.get('entry_time', '')
    
    title = f"交易 #{trade_id} - {direction} - {entry_time}\n"
    title += f"K1实体率: {k1.get_body_ratio()*100:.1f}%  K1影线率: {k1.get_shadow_ratio()*100:.1f}%\n"
    title += f"K2实体率: {k2.get_body_ratio()*100:.1f}%  K2影线率: {k2.get_shadow_ratio()*100:.1f}%"
    
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    ax.set_ylabel('价格 (USDT)', fontsize=12)
    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels)
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"  已保存图表: {save_path}")
    
    plt.close()


def analyze_kline_features(trades_with_klines: List[Tuple[Dict, KLine, KLine]]):
    """分析K线特征统计"""
    print("\n" + "="*80)
    print("K线特征分析")
    print("="*80)
    
    stats = {
        'k1_body_ratios': [],
        'k1_shadow_ratios': [],
        'k1_upper_shadow_ratios': [],
        'k1_lower_shadow_ratios': [],
        'k2_body_ratios': [],
        'k2_shadow_ratios': [],
        'k2_upper_shadow_ratios': [],
        'k2_lower_shadow_ratios': [],
        'k1_bullish_count': 0,
        'k2_bullish_count': 0,
        'long_trades': 0,
        'short_trades': 0,
    }
    
    for trade, k1, k2 in trades_with_klines:
        stats['k1_body_ratios'].append(k1.get_body_ratio())
        stats['k1_shadow_ratios'].append(k1.get_shadow_ratio())
        stats['k1_upper_shadow_ratios'].append(k1.get_upper_shadow_ratio())
        stats['k1_lower_shadow_ratios'].append(k1.get_lower_shadow_ratio())
        
        stats['k2_body_ratios'].append(k2.get_body_ratio())
        stats['k2_shadow_ratios'].append(k2.get_shadow_ratio())
        stats['k2_upper_shadow_ratios'].append(k2.get_upper_shadow_ratio())
        stats['k2_lower_shadow_ratios'].append(k2.get_lower_shadow_ratio())
        
        if k1.is_bullish():
            stats['k1_bullish_count'] += 1
        if k2.is_bullish():
            stats['k2_bullish_count'] += 1
        
        if trade['direction'] == '做多':
            stats['long_trades'] += 1
        else:
            stats['short_trades'] += 1
    
    total = len(trades_with_klines)
    
    print(f"\n分析样本数: {total}")
    print(f"\n交易方向分布:")
    print(f"  做多: {stats['long_trades']} ({stats['long_trades']/total*100:.1f}%)")
    print(f"  做空: {stats['short_trades']} ({stats['short_trades']/total*100:.1f}%)")
    
    print(f"\nK1 特征统计:")
    print(f"  阳线比例: {stats['k1_bullish_count']/total*100:.1f}%")
    print(f"  平均实体率: {sum(stats['k1_body_ratios'])/total*100:.1f}%")
    print(f"  平均影线率: {sum(stats['k1_shadow_ratios'])/total*100:.1f}%")
    print(f"  平均上影线率: {sum(stats['k1_upper_shadow_ratios'])/total*100:.1f}%")
    print(f"  平均下影线率: {sum(stats['k1_lower_shadow_ratios'])/total*100:.1f}%")
    
    print(f"\nK2 特征统计:")
    print(f"  阳线比例: {stats['k2_bullish_count']/total*100:.1f}%")
    print(f"  平均实体率: {sum(stats['k2_body_ratios'])/total*100:.1f}%")
    print(f"  平均影线率: {sum(stats['k2_shadow_ratios'])/total*100:.1f}%")
    print(f"  平均上影线率: {sum(stats['k2_upper_shadow_ratios'])/total*100:.1f}%")
    print(f"  平均下影线率: {sum(stats['k2_lower_shadow_ratios'])/total*100:.1f}%")
    
    # 影线比实体长的比例
    k2_shadow_gt_body = sum(1 for i in range(total) 
                            if stats['k2_shadow_ratios'][i] > stats['k2_body_ratios'][i])
    print(f"\nK2影线>实体的比例: {k2_shadow_gt_body/total*100:.1f}%")
    
    return stats


def create_summary_chart(stats: dict, save_path: str):
    """创建汇总统计图表"""
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    
    # 1. K1和K2的实体率对比
    ax1 = axes[0, 0]
    k1_body = [r * 100 for r in stats['k1_body_ratios']]
    k2_body = [r * 100 for r in stats['k2_body_ratios']]
    ax1.hist([k1_body, k2_body], bins=20, label=['K1', 'K2'], alpha=0.7)
    ax1.set_xlabel('实体率 (%)')
    ax1.set_ylabel('频数')
    ax1.set_title('K1和K2实体率分布对比')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. K1和K2的影线率对比
    ax2 = axes[0, 1]
    k1_shadow = [r * 100 for r in stats['k1_shadow_ratios']]
    k2_shadow = [r * 100 for r in stats['k2_shadow_ratios']]
    ax2.hist([k1_shadow, k2_shadow], bins=20, label=['K1', 'K2'], alpha=0.7, color=['blue', 'orange'])
    ax2.set_xlabel('影线率 (%)')
    ax2.set_ylabel('频数')
    ax2.set_title('K1和K2影线率分布对比')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. K2上下影线分布
    ax3 = axes[1, 0]
    k2_upper = [r * 100 for r in stats['k2_upper_shadow_ratios']]
    k2_lower = [r * 100 for r in stats['k2_lower_shadow_ratios']]
    ax3.scatter(k2_upper, k2_lower, alpha=0.6)
    ax3.set_xlabel('K2上影线率 (%)')
    ax3.set_ylabel('K2下影线率 (%)')
    ax3.set_title('K2上下影线分布')
    ax3.grid(True, alpha=0.3)
    
    # 4. 实体率vs影线率散点图
    ax4 = axes[1, 1]
    ax4.scatter(k2_body, k2_shadow, alpha=0.6, color='green')
    ax4.plot([0, 100], [0, 100], 'r--', label='实体=影线')
    ax4.set_xlabel('K2实体率 (%)')
    ax4.set_ylabel('K2影线率 (%)')
    ax4.set_title('K2实体率 vs 影线率')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"\n已保存汇总图表: {save_path}")
    plt.close()


def main():
    """主函数"""
    print("="*80)
    print("止损交易K线形态分析工具")
    print("="*80)
    
    # 读取止损交易日志
    log_file = "策略分析/trade_log_止损交易.txt"
    print(f"\n正在读取日志文件: {log_file}")
    trades = parse_trade_log(log_file)
    print(f"找到 {len(trades)} 笔止损交易")
    
    # 创建输出目录
    import os
    output_dir = "策略分析/止损K线图"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 获取K线数据并绘图
    print("\n正在获取K线数据并生成图表...")
    trades_with_klines = []
    
    # 限制处理数量以避免API限制
    max_trades = min(30, len(trades))  # 最多处理30笔交易
    
    for i, trade in enumerate(trades[:max_trades]):
        print(f"\n处理交易 #{trade['id']} ({i+1}/{max_trades})")
        
        k1, k2 = get_klines_for_trade(trade)
        
        if k1 and k2:
            trades_with_klines.append((trade, k1, k2))
            
            # 绘制K线图
            save_path = f"{output_dir}/trade_{trade['id']}_{trade['direction']}.png"
            plot_kline_pair(k1, k2, trade, save_path)
        else:
            print(f"  ✗ 无法获取K线数据")
        
        # 避免请求过快
        if i < max_trades - 1:
            time.sleep(0.5)
    
    print(f"\n成功获取 {len(trades_with_klines)} 笔交易的K线数据")
    
    # 分析K线特征
    if trades_with_klines:
        stats = analyze_kline_features(trades_with_klines)
        
        # 生成汇总图表
        summary_path = f"{output_dir}/summary_analysis.png"
        create_summary_chart(stats, summary_path)
        
        print("\n" + "="*80)
        print("分析完成!")
        print(f"图表已保存到目录: {output_dir}")
        print("="*80)


if __name__ == '__main__':
    main()
