from datetime import datetime
from fenxing_logger import format_fenxing, append_new_fenxing

import os

def merge_klines(klines):
    """处理左包右和右包左的K线合并"""
    if not klines:
        return []
    
    merged = [klines[0]]
    
    for bar in klines[1:]:
        prev = merged[-1]
        
        # 判断是否有包含关系（上下趋势的K线合并）
        if (prev[2] >= bar[2] and prev[3] <= bar[3]) or (bar[2] >= prev[2] and bar[3] <= prev[3]):
            # 合并过程：先合并当前的 K 线与前一根 K 线
            if bar[2] > prev[2]:  # 上升趋势
                # 取两个K线的高点中的最高价和低点中的最低价
                high = max(prev[2], bar[2])
                low = min(prev[3], bar[3])
                # 保留最高价对应的K线日期
                date = bar[0] if bar[2] > prev[2] else prev[0]
            elif bar[2] < prev[2]:  # 下降趋势
                # 同样取高低点
                high = min(prev[2], bar[2])
                low = max(prev[3], bar[3])
                # 保留最低价对应的K线日期
                date = bar[0] if bar[3] < prev[3] else prev[0]
            
            # 用合并后的高低点替换原来的两根K线
            merged[-1] = (date, prev[1], high, low)
        else:
            # 如果没有包含关系，则保留当前K线
            merged.append(bar)
    
    return merged

#核心处理逻辑 
def detect_fenxing(klines):
    """
    严格版缠论顶底分型（不考虑包含关系）
    规则：
    - 顶分型：中间K线的 high、low 都是三根K线中最高的
    - 底分型：中间K线的 high、low 都是三根K线中最低的
    """
    if len(klines) < 3:
        return {'tops': [], 'bottoms': []}

    tops, bottoms = [], []

    for i in range(1, len(klines) - 1):
        prev = klines[i - 1]
        cur = klines[i]
        nxt = klines[i + 1]

        highs = [prev[2], cur[2], nxt[2]]
        lows = [prev[3], cur[3], nxt[3]]

        cur_high, cur_low = cur[2], cur[3]
        dt = datetime.fromtimestamp(cur[0] / 1000).strftime('%Y-%m-%d %H:%M')

        # 顶分型：当前K线的 high、low 都是最高的
        if cur_high == max(highs) and cur_low == max(lows):
            tops.append((cur_high, cur_low, dt))

        # 底分型：当前K线的 high、low 都是最低的
        if cur_high == min(highs) and cur_low == min(lows):
            bottoms.append((cur_high, cur_low, dt))
    result = {'tops': tops, 'bottoms': bottoms}

    # 先格式化为人可读的文本（完整），以便在没有历史时使用或供打印
    try:
        full_text = format_fenxing(result)
    except NameError:
        full_text = None

    # 查找 logs 中最后记录的分型时间（跨文件），用于只追加新分型
    logs_dir = 'logs'
    # append_new_fenxing 会内部调用 find_last_logged_datetime
    last_dt = None

    # helper: 将 tuple (high, low, dt_str) -> datetime (使用 fenxing_logger 中的解析)
    def _dt_of(t):
        try:
            from fenxing_logger import _parse_datetime_str as _pdt
            return _pdt(t[2])
        except Exception:
            # 回退：尝试本地解析
            try:
                return datetime.strptime(t[2], '%Y-%m-%d %H:%M')
            except Exception:
                return None

    # 过滤出比 last_dt 更新的分型
    if last_dt is None:
        new_tops = tops[:]
        new_bottoms = bottoms[:]
    else:
        new_tops = [t for t in tops if _dt_of(t) and _dt_of(t) > last_dt]
        new_bottoms = [b for b in bottoms if _dt_of(b) and _dt_of(b) > last_dt]

    # 使用 fenxing_logger 的 append_new_fenxing 来完成增量写入并打印
    try:
        res = append_new_fenxing(new_tops, new_bottoms, full_text=full_text, logs_dir=logs_dir)
        # res 包含写入状态和消息
        return result
    except Exception as e:
        print(f"调用 append_new_fenxing 失败: {e}")
        # 回退：如果 append_new_fenxing 失败，仍返回完整结果并打印
        if full_text:
            print(full_text)
        return result
    
# 先合并 再处理
def detect_fenxing_with_merge(klines):
    merged_klines = merge_klines(klines)
    return detect_fenxing(merged_klines)