from datetime import datetime
import os
import re
import glob


def _parse_datetime_str(s):
    try:
        return datetime.strptime(s, '%Y-%m-%d %H:%M')
    except Exception:
        return None


def find_last_logged_datetime(logs_dir='logs'):
    """扫描 logs 目录下所有 fenxing-YYYYMMDD.log，提取已记录的分型时间并返回最新的 datetime（或 None）。"""
    if not os.path.isdir(logs_dir):
        return None

    dt_pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})")
    latest = None
    for path in glob.glob(os.path.join(logs_dir, 'fenxing-*.log')):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
        except Exception:
            continue
        for m in dt_pattern.findall(text):
            dt = _parse_datetime_str(m)
            if dt is None:
                continue
            if latest is None or dt > latest:
                latest = dt
    return latest


def format_fenxing(fractals):
    """返回格式化的顶底分型文本（不打印），以便可以同时打印和写入日志文件。"""
    # 合并顶/底分型为统一列表，并按时间排序，输出时在前面标注类型
    entries = []
    for high, low, dt in fractals.get("tops", []):
        entries.append(("顶", high, low, dt))
    for high, low, dt in fractals.get("bottoms", []):
        entries.append(("底", high, low, dt))

    def _key(e):
        dt = _parse_datetime_str(e[3])
        return dt if dt is not None else datetime.max

    entries.sort(key=_key)

    lines = []
    lines.append("\n� 顶底分型列表（按时间排序）")
    lines.append("=" * 50)

    if not entries:
        lines.append("  暂无分型")
    else:
        for typ, high, low, dt in entries:
            prefix = "🟥 顶" if typ == "顶" else "🟩 底"
            lines.append(f"  ▪ {prefix} | 最高价 = {high:>10,.2f} | 最低价 = {low:>10,.2f} | 时间 = {dt}")

    lines.append("=" * 50 + "\n")
    return "\n".join(lines)


def append_new_fenxing(tops, bottoms, full_text=None, logs_dir='logs'):
    """根据已记录的最后时间，只把新分型追加到当日日志。

    参数:
      - tops, bottoms: 列表，每项为 (high, low, dt_str)
      - full_text: 可选，完整格式化文本（在没有历史时可打印）
      - logs_dir: 日志目录

    返回一个字典，包含写入结果与信息。
    """
    last_dt = find_last_logged_datetime(logs_dir)

    def _dt_of(t):
        return _parse_datetime_str(t[2])

    if last_dt is None:
        new_tops = tops[:]
        new_bottoms = bottoms[:]
    else:
        new_tops = [t for t in tops if _dt_of(t) and _dt_of(t) > last_dt]
        new_bottoms = [b for b in bottoms if _dt_of(b) and _dt_of(b) > last_dt]

    # 没有新分型
    if not new_tops and not new_bottoms:
        msg = f"没有检测到晚于 {last_dt.strftime('%Y-%m-%d %H:%M') if last_dt else '开始'} 的新分型，跳过写入日志。"
        # 若提供了 full_text（完整文本），仍打印以便查看
        if full_text:
            print(full_text)
        print(msg)
        return {'written': False, 'message': msg}

    # 合并新增顶/底并按时间排序
    entries = []
    for high, low, dt in new_tops:
        entries.append(("顶", high, low, dt))
    for high, low, dt in new_bottoms:
        entries.append(("底", high, low, dt))

    def _key2(e):
        dt = _parse_datetime_str(e[3])
        return dt if dt is not None else datetime.max

    entries.sort(key=_key2)

    # 构造新增块文本（按时间合并展示）
    lines = []
    header = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines.append(header)
    if last_dt:
        lines.append(f"新增分型（晚于 {last_dt.strftime('%Y-%m-%d %H:%M')}）：")
    else:
        lines.append("新增分型（首次记录全部分型）：")

    lines.append("\n� 按时间合并排序的新分型：")
    for typ, high, low, dt in entries:
        prefix = "🟥 顶" if typ == "顶" else "🟩 底"
        lines.append(f"  ▪ {prefix} | 最高价 = {high:>10,.2f} | 最低价 = {low:>10,.2f} | 时间 = {dt}")

    block_text = '\n'.join(lines)

    # 打印并追加到当日日志
    # print(block_text)
    try:
        os.makedirs(logs_dir, exist_ok=True)
        date_str = datetime.now().strftime('%Y%m%d')
        filename = os.path.join(logs_dir, f'fenxing-{date_str}.log')
        with open(filename, 'a', encoding='utf-8') as f:
            f.write(block_text)
            f.write('\n\n')
        return {'written': True, 'filename': filename, 'block_text': block_text}
    except Exception as e:
        msg = f"写入增量日志失败: {e}"
        print(msg)
        return {'written': False, 'message': msg}
