from datetime import datetime
import os

def connect_bi(res):
    """
    将分型连接成笔（顶底交替）
    输入 res = {'tops': [(high, low, dt_str), ...], 'bottoms': [...]}
    返回每笔结构：
    {
        'top_max': ...,
        'top_min': ...,
        'bottom_max': ...,
        'bottom_min': ...,
        'start_time': ...,
        'end_time': ...
    }
    """
    tops = sorted(res['tops'], key=lambda x: x[2])
    bottoms = sorted(res['bottoms'], key=lambda x: x[2])
    
    # 合并为统一列表，标记类型
    points = []
    for h, l, t in tops:
        points.append({'type': 'top', 'high': h, 'low': l, 'time': t})
    for h, l, t in bottoms:
        points.append({'type': 'bottom', 'high': h, 'low': l, 'time': t})
    
    # 按时间排序
    points.sort(key=lambda x: x['time'])
    
    bi_list = []
    i = 0
    while i < len(points) - 1:
        cur = points[i]
        nxt = points[i + 1]
        
        # 顶底必须交替
        if cur['type'] == nxt['type']:
            i += 1
            continue
        
        # 顶必须高于底
        if cur['type'] == 'top' and cur['high'] <= nxt['high']:
            i += 1
            continue
        if cur['type'] == 'bottom' and cur['low'] >= nxt['low']:
            i += 1
            continue
        
        # 生成笔
        if cur['type'] == 'top':
            bi = {
                'top_max': cur['high'],
                'top_min': cur['low'],
                'bottom_max': nxt['high'],
                'bottom_min': nxt['low'],
                'start_time': cur['time'],
                'end_time': nxt['time']
            }
        else:
            bi = {
                'top_max': nxt['high'],
                'top_min': nxt['low'],
                'bottom_max': cur['high'],
                'bottom_min': cur['low'],
                'start_time': cur['time'],
                'end_time': nxt['time']
            }
        
        bi_list.append(bi)
        i += 1  # 下一笔从下一个分型开始
    format_and_save_bi_with_direction(bi_list)
    return bi_list


def format_and_save_bi_with_direction(bi_list, log_dir='logs', log_file='bi.log'):
    """
    将笔列表格式化为中文文本（带方向），并保存到 logs 文件夹
    """
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_path = os.path.join(log_dir, log_file)
    
    lines = []
    for bi in bi_list:
        direction = "顶部到底部" if bi['top_max'] >= bi['bottom_max'] else "底部到顶部"
        line = (
            f"笔方向: {direction}, "
            f"时间区间: {bi['start_time']} - {bi['end_time']}, "
            f"顶部最大值: {bi['top_max']}, 顶部最小值: {bi['top_min']}, "
            f"底部最大值: {bi['bottom_max']}, 底部最小值: {bi['bottom_min']}"
        )
        lines.append(line)
    
    # 保存到日志文件
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"已保存 {len(lines)} 条笔信息到 {log_path}")
    return log_path

# 用法示例：
# bi_result = connect_bi(res)
# format_and_save_bi_with_direction(bi_result)
