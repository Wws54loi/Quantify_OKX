"""
检查K线数据文件中是否包含指定日期的数据
"""
import json
from datetime import datetime


def check_date_in_klines(json_file: str, target_date: str) -> dict:
    """
    检查K线JSON文件中是否包含指定日期的K线数据
    
    参数:
        json_file: K线数据JSON文件路径
        target_date: 目标日期，格式 'YYYY-MM-DD' 如 '2025-09-06'
    
    返回:
        字典包含:
        - found: bool, 是否找到该日期
        - count: int, 该日期的K线数量
        - first_kline: 该日期第一根K线信息
        - last_kline: 该日期最后一根K线信息
        - date_range: 文件中的日期范围
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            klines = json.load(f)
        
        if not klines:
            return {
                'found': False,
                'count': 0,
                'first_kline': None,
                'last_kline': None,
                'date_range': None
            }
        
        # 获取整个数据的时间范围
        first_ts = int(klines[0][0])
        last_ts = int(klines[-1][0])
        first_date = datetime.fromtimestamp(first_ts / 1000).strftime('%Y-%m-%d %H:%M')
        last_date = datetime.fromtimestamp(last_ts / 1000).strftime('%Y-%m-%d %H:%M')
        
        # 查找目标日期的K线
        target_klines = []
        for kline in klines:
            timestamp = int(kline[0])
            kline_date = datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d')
            
            if kline_date == target_date:
                target_klines.append({
                    'timestamp': timestamp,
                    'datetime': datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d %H:%M'),
                    'open': float(kline[1]),
                    'high': float(kline[2]),
                    'low': float(kline[3]),
                    'close': float(kline[4]),
                    'volume': float(kline[5])
                })
        
        return {
            'found': len(target_klines) > 0,
            'count': len(target_klines),
            'first_kline': target_klines[0] if target_klines else None,
            'last_kline': target_klines[-1] if target_klines else None,
            'date_range': f"{first_date} 至 {last_date}",
            'total_klines': len(klines)
        }
        
    except FileNotFoundError:
        print(f"错误: 文件 {json_file} 不存在")
        return {
            'found': False,
            'count': 0,
            'first_kline': None,
            'last_kline': None,
            'date_range': None
        }
    except Exception as e:
        print(f"错误: {e}")
        return {
            'found': False,
            'count': 0,
            'first_kline': None,
            'last_kline': None,
            'date_range': None
        }


def main():
    """主函数 - 检查btcusdt_15m_klines.json中的日期"""
    json_file = r"c:\Users\BinBin\Documents\GitHub\Quantify_OKX\btcusdt_15m_klines.json"
    target_date = "2025-09-06"
    
    print("="*80)
    print(f"检查K线数据文件中是否包含 {target_date} 的数据")
    print("="*80)
    
    result = check_date_in_klines(json_file, target_date)
    
    if result['date_range']:
        print(f"\n文件信息:")
        print(f"  总K线数: {result['total_klines']} 根")
        print(f"  时间范围: {result['date_range']}")
    
    if result['found']:
        print(f"\n✓ 找到 {result['count']} 根包含 {target_date} 的K线数据:\n")
        
        first = result['first_kline']
        last = result['last_kline']
        
        print(f"  第一根K线:")
        print(f"    时间: {first['datetime']}")
        print(f"    开盘: {first['open']:.2f}")
        print(f"    最高: {first['high']:.2f}")
        print(f"    最低: {first['low']:.2f}")
        print(f"    收盘: {first['close']:.2f}")
        print()
        
        if result['count'] > 1:
            print(f"  最后一根K线:")
            print(f"    时间: {last['datetime']}")
            print(f"    开盘: {last['open']:.2f}")
            print(f"    最高: {last['high']:.2f}")
            print(f"    最低: {last['low']:.2f}")
            print(f"    收盘: {last['close']:.2f}")
            print()
    else:
        print(f"\n✗ 未找到包含 {target_date} 的K线数据")
    
    print("="*80)


if __name__ == '__main__':
    main()
