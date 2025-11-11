# -*- coding: utf-8 -*-
"""
调试信号判断逻辑
"""

def body_strength(o: float, c: float) -> float:
    if o <= 0:
        return 0.0
    return abs(c - o) / o

def k1_k2_signal_debug(k1_open, k1_high, k1_low, k1_close, k2_open, k2_high, k2_low, k2_close):
    K1_BODY_MIN = 0.0021  # 0.21%
    
    # K1 条件: 实体强度 >= 0.21%
    k1_body = body_strength(k1_open, k1_close)
    print(f"K1 实体强度: {k1_body:.6f} ({k1_body*100:.4f}%)")
    if k1_body < K1_BODY_MIN:
        print(f"K1 实体强度不足，需要 >= {K1_BODY_MIN:.4f} ({K1_BODY_MIN*100:.2f}%)")
        return False, None

    # K2 条件：影线突破 + 收盘在 K1 内 + 实体比值
    break_up = k2_high > k1_high
    break_down = k2_low < k1_low
    close_inside = (k2_close <= k1_high and k2_close >= k1_low)

    print(f"K2 向上突破: {break_up} (K2.high {k2_high:.2f} > K1.high {k1_high:.2f})")
    print(f"K2 向下突破: {break_down} (K2.low {k2_low:.2f} < K1.low {k1_low:.2f})")
    print(f"K2 收盘回包: {close_inside} (K2.close {k2_close:.2f} 在 [{k1_low:.2f}, {k1_high:.2f}] 内)")

    k2_body = body_strength(k2_open, k2_close)
    body_ratio = (k2_body / k1_body) if k1_body > 0 else 0
    ratio_ok = (0.5 <= body_ratio <= 1.6)
    
    print(f"K2 实体强度: {k2_body:.6f} ({k2_body*100:.4f}%)")
    print(f"实体比值: {body_ratio:.4f} (需要在 [0.5, 1.6] 内)")
    print(f"实体比值OK: {ratio_ok}")

    if (break_up or break_down) and close_inside and ratio_ok:
        # 方向判定
        if break_up and break_down:
            print("同时上下突破，按优先级判断方向")
            if k2_low < k1_low:
                print("K2.low < K1.low，做多")
                return True, 'long'
            elif k2_high > k1_high:
                print("K2.high > K1.high，做空")
                return True, 'short'
            else:
                print("无法判断方向")
                return False, None
        elif break_down:
            print("仅向下突破，做多")
            return True, 'long'
        elif break_up:
            print("仅向上突破，做空")
            return True, 'short'
    else:
        print("条件不满足，无信号")
    return False, None

# 测试案例数据
print("=== 交易 #1415 案例分析 ===")
k1_open = 3455.58
k1_high = 3471.74
k1_low = 3454.50
k1_close = 3467.52

k2_open = 3467.52
k2_high = 3467.93
k2_low = 3448.77
k2_close = 3455.12

print(f"K1: 开:{k1_open} 高:{k1_high} 低:{k1_low} 收:{k1_close}")
print(f"K2: 开:{k2_open} 高:{k2_high} 低:{k2_low} 收:{k2_close}")
print()

ok, direction = k1_k2_signal_debug(k1_open, k1_high, k1_low, k1_close, k2_open, k2_high, k2_low, k2_close)
print(f"\n结果: 有信号={ok}, 方向={direction}")