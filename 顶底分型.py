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
    last_dt = find_last_logged_datetime(logs_dir)

    # helper: 将 tuple (high, low, dt_str) -> datetime
    def _dt_of(t):
        return _parse_datetime_str(t[2])

    # 过滤出比 last_dt 更新的分型
    if last_dt is None:
        new_tops = tops[:]
        new_bottoms = bottoms[:]
    else:
        new_tops = [t for t in tops if _dt_of(t) and _dt_of(t) > last_dt]
        new_bottoms = [b for b in bottoms if _dt_of(b) and _dt_of(b) > last_dt]

    # 如果没有新分型则跳过写入（但仍打印信息）
    if not new_tops and not new_bottoms:
        print(f"没有检测到晚于 {last_dt.strftime('%Y-%m-%d %H:%M') if last_dt else '开始'} 的新分型，跳过写入日志。")
        # 仍返回完整结果
        if full_text:
            print(full_text)
        return result

    # 构造要追加的小块文本，只包含新增分型，便于日志增量续写
    lines = []
    header = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines.append(header)
    if last_dt:
        lines.append(f"新增分型（晚于 {last_dt.strftime('%Y-%m-%d %H:%M')}）：")
    else:
        lines.append("新增分型（首次记录全部分型）：")

    if new_tops:
        lines.append("\n🟥 新顶分型：")
        for high, low, dt in new_tops:
            lines.append(f"  ▪ 最高价 = {high:>10,.2f} | 最低价 = {low:>10,.2f} | 时间 = {dt}")

    if new_bottoms:
        lines.append("\n🟩 新底分型：")
        for high, low, dt in new_bottoms:
            lines.append(f"  ▪ 最高价 = {high:>10,.2f} | 最低价 = {low:>10,.2f} | 时间 = {dt}")

    block_text = '\n'.join(lines)

    # 打印新增块到 stdout
    print(block_text)

    # 追加到当日日志文件
    try:
        os.makedirs(logs_dir, exist_ok=True)
        date_str = datetime.now().strftime('%Y%m%d')
        filename = os.path.join(logs_dir, f'fenxing-{date_str}.log')
        with open(filename, 'a', encoding='utf-8') as f:
            f.write(block_text)
            f.write('\n\n')
    except Exception as e:
        print(f"写入增量日志失败: {e}")

    return result


def print_fenxing(fractals):
    # 使用 format_fenxing 构造字符串并打印（format_fenxing 在下方定义）
    try:
        s = format_fenxing(fractals)
        print(s)
    except NameError:
        # 兼容：如果 format_fenxing 未定义，保留旧行为
        print("\n📈 顶底分型列表（中间K线信息）")
        print("=" * 50)

        print("\n🟥 顶分型（Top Fractals）:")
        if not fractals["tops"]:
            print("  暂无顶分型")
        else:
            for high, low, dt in fractals["tops"]:
                print(f"  ▪ 最高价 = {high:>10,.2f} | 最低价 = {low:>10,.2f} | 时间 = {dt}")

        print("\n🟩 底分型（Bottom Fractals）:")
        if not fractals["bottoms"]:
            print("  暂无底分型")
        else:
            for high, low, dt in fractals["bottoms"]:
                print(f"  ▪ 最高价 = {high:>10,.2f} | 最低价 = {low:>10,.2f} | 时间 = {dt}")

        print("=" * 50 + "\n")


def format_fenxing(fractals):
    """返回格式化的顶底分型文本（不打印），以便可以同时打印和写入日志文件。"""
    lines = []
    lines.append("\n📈 顶底分型列表（中间K线信息）")
    lines.append("=" * 50)

    lines.append("\n🟥 顶分型（Top Fractals）:")
    if not fractals["tops"]:
        lines.append("  暂无顶分型")
    else:
        for high, low, dt in fractals["tops"]:
            lines.append(f"  ▪ 最高价 = {high:>10,.2f} | 最低价 = {low:>10,.2f} | 时间 = {dt}")

    lines.append("\n🟩 底分型（Bottom Fractals）:")
    if not fractals["bottoms"]:
        lines.append("  暂无底分型")
    else:
        for high, low, dt in fractals["bottoms"]:
            lines.append(f"  ▪ 最高价 = {high:>10,.2f} | 最低价 = {low:>10,.2f} | 时间 = {dt}")

    lines.append("=" * 50 + "\n")
    return "\n".join(lines)