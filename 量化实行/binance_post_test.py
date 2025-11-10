import requests
import hmac
import hashlib
import time
import urllib.parse

api_key = "Xq2X0xMjmsbArOBmYIxgL0IOQvJZuMK7ec29w3HTogwA737i18cwmUkH81QzjDYu"
secret_key = "sfGu8nnBwdO6xCODFOCmkymwCWkfXCWBUsmADnPLEQcbqD47MO6qBEcljrOfrFxA"
base_url = "https://fapi.binance.com"

# 先设置杠杆为30倍
leverage_path = '/fapi/v1/leverage'
leverage_params = {
    "symbol": "ETHUSDT",
    "leverage": 50,
    "timestamp": round(time.time() * 1000)
}
leverage_query = urllib.parse.urlencode(leverage_params)
leverage_signature = hmac.new(secret_key.encode('utf-8'), msg=leverage_query.encode('utf-8'), digestmod=hashlib.sha256).hexdigest()
leverage_url = base_url + leverage_path + '?' + leverage_query + '&signature=' + leverage_signature
print("设置杠杆URL:", leverage_url)
headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'X-MBX-APIKEY': api_key
}
leverage_resp = requests.post(leverage_url, headers=headers)
print("杠杆设置状态码:", leverage_resp.status_code)
try:
    print("杠杆设置响应:", leverage_resp.json())
except Exception:
    print("杠杆设置响应内容:", leverage_resp.text)

path = '/fapi/v1/order'
timestamp = round(time.time() * 1000)

params = {
    "symbol": "ETHUSDT",
    "type": "MARKET",
    "side": "BUY",
    "quantity": 0.006,
    "positionSide": "LONG",
    "timestamp": timestamp
}
querystring = urllib.parse.urlencode(params)
signature = hmac.new(secret_key.encode('utf-8'), msg=querystring.encode('utf-8'), digestmod=hashlib.sha256).hexdigest()
url = base_url + path + '?' + querystring + '&signature=' + signature
print("请求URL:", url)
headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'X-MBX-APIKEY': api_key
}

response = requests.post(url, headers=headers)
print("状态码:", response.status_code)
try:
    result = response.json()
    print("响应:", result)
except Exception as e:
    print("响应内容:", response.text)
