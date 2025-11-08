# -*- coding: utf-8 -*-
"""
分析 trade_log.txt（TXT文本日志）中：
- 盈利与亏损在不同持有K线区间(1-10, 11-20, ... , 91-100)的分布
- 额外分组：全部、包含关系(是否包含关系: 是)、非包含关系(是否包含关系: 否)

使用方法（在本文件夹下执行）：
    python 用于计算交易持仓k数区间.py [可选: trade_log路径]

默认会读取上一级目录下的 trade_log.txt。
"""
import os
import re
import sys
from collections import defaultdict


def parse_trade_log_txt(file_path):
    """解析 TXT 交易日志，返回 [{'holding': int, 'pnl': float, 'contain': bool|None}, ...]
    contain: True=包含关系: 是, False=否, None=日志无该字段
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到日志文件: {file_path}")

    records = []
    trade = {}
    in_detail = False

    with open(file_path, 'r', encoding='utf-8') as f:
        for raw in f:
            line = raw.strip()
            if line.startswith('详细交易记录:'):
                in_detail = True
                continue
            if not in_detail:
                continue

            # 新交易开始
            if line.startswith('交易 #'):
                if trade:
                    # 仅在同时有持仓和盈亏时入库
                    if 'holding' in trade and 'pnl' in trade:
                        records.append(trade)
                trade = {}
                continue

            # 持仓时长: X根K线 (xxx分钟)
            if '持仓时长:' in line:
                m = re.search(r'(\d+)根K线', line)
                if m:
                    trade['holding'] = int(m.group(1))
                continue

            # 是否包含关系: 是 / 否
            if line.startswith('是否包含关系') or '是否包含关系:' in line:
                # 仅提取冒号后的值，避免把“是否”中的“是”误判
                m = re.search(r'是否包含关系\s*:\s*(是|否)', line)
                if m:
                    trade['contain'] = (m.group(1) == '是')
                else:
                    # 无法解析则置为 None（不影响“全部”分布）
                    trade['contain'] = None
                continue

            # 本次盈亏: +0.4000 USDT / -0.9900 USDT
            if '本次盈亏:' in line:
                m = re.search(r'([+-]?[\d\.]+)\s*USDT', line)
                if m:
                    try:
                        trade['pnl'] = float(m.group(1))
                    except ValueError:
                        pass
                continue

        # 文件结束，补上最后一笔
        if trade and 'holding' in trade and 'pnl' in trade:
            records.append(trade)

    return records


def group_distribution(records, max_bar=100, step=10):
    """按区间汇总盈利/亏损次数。
    区间: 1-10, 11-20, ..., 91-100（超过100的忽略）。
    返回: Ordered dict-like { '1-10': {'win': n, 'loss': m}, ... }
    """
    # 构造区间标签
    bins = list(range(1, max_bar + 1, step))  # 1,11,21,...,91
    labels = [f"{b}-{min(b+step-1, max_bar)}" for b in bins]

    dist = {lab: {'win': 0, 'loss': 0} for lab in labels}

    for r in records:
        h = r.get('holding')
        pnl = r.get('pnl')
        if h is None or pnl is None:
            continue
        if h < 1 or h > max_bar:
            # 超过100或小于1的忽略
            continue
        # 找到所在区间
        idx = (h - 1) // step
        lab = labels[idx]
        if pnl > 0:
            dist[lab]['win'] += 1
        elif pnl < 0:
            dist[lab]['loss'] += 1
        # pnl == 0 的忽略

    return dist


def print_distribution(dist):
    print('区间\t盈利次数\t亏损次数')
    for lab in dist:
        print(f"{lab}\t{dist[lab]['win']}\t{dist[lab]['loss']}")


def main():
    # 默认读取上级目录的 trade_log.txt；可通过命令行传入自定义路径
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'trade_log.txt'))

    try:
        records = parse_trade_log_txt(file_path)
    except FileNotFoundError as e:
        print(str(e))
        return

    # 全部
    print("\n===== 全部交易（包含+非包含） =====")
    dist_all = group_distribution(records, max_bar=100, step=10)
    print_distribution(dist_all)

    # 仅包含关系: 是否包含关系: 是
    contain_records = [r for r in records if r.get('contain') is True]
    print("\n===== 仅包含关系（是否包含关系: 是） =====")
    if contain_records:
        dist_contain = group_distribution(contain_records, max_bar=100, step=10)
        print_distribution(dist_contain)
    else:
        print("无包含关系样本")

    # 非包含关系: 是否包含关系: 否
    non_contain_records = [r for r in records if r.get('contain') is False]
    print("\n===== 非包含关系（是否包含关系: 否） =====")
    if non_contain_records:
        dist_non = group_distribution(non_contain_records, max_bar=100, step=10)
        print_distribution(dist_non)
    else:
        print("无非包含关系样本")


if __name__ == '__main__':
    main()
