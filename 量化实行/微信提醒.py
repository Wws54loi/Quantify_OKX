# -*- coding: utf-8 -*-
"""
Server酱(方糖)微信推送封装
使用说明：
- 在系统环境变量中设置 SERVERCHAN_SENDKEY=你的SendKey
  (Server酱 Turbo版网站获取，形如 SCTxxxxxxxxxxxxxxxxxxxxxxx)
- 可选：通过函数参数覆盖 sendkey。

接口：send_wechat_notification(title, content, sendkey=None)
- title: 推送标题
- content: 推送内容(支持普通文本/Markdown)
- sendkey: 可选，默认从环境变量读取

返回：True(成功)/False(失败)
"""
from __future__ import annotations
import os
import json
import urllib.parse
import urllib.request

SERVERCHAN_ENV_KEY = "SCT301567TtEeQSvoSSyo0240Rbe4OUkSO"
SERVERCHAN_API = "https://sctapi.ftqq.com/{sendkey}.send"

def _post(url: str, data: dict) -> dict:
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=encoded, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded;charset=UTF-8")
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
        try:
            return json.loads(raw)
        except Exception:
            return {"raw": raw}

def send_wechat_notification(title: str, content: str, sendkey: str | None = None) -> bool:
    """发送Server酱微信通知。"""
    key = sendkey or os.getenv(SERVERCHAN_ENV_KEY, "").strip()
    if not key:
        print("⚠ 未设置 Server酱 SendKey，跳过微信通知。请配置环境变量 SERVERCHAN_SENDKEY。")
        return False

    url = SERVERCHAN_API.format(sendkey=key)
    data = {
        "title": title,
        "desp": content,
    }
    try:
        res = _post(url, data)
        ok = bool(res.get("data") or res.get("errno") == 0 or res.get("code") == 0)
        if ok:
            print("📨 微信提醒已发送（Server酱）")
            return True
        else:
            print(f"✗ 微信提醒发送失败：{res}")
            return False
    except Exception as e:
        print(f"✗ 微信提醒发送异常：{e}")
        return False
