import requests
import json

SUBDOMAIN = "iu9b8ymlk83t"
TOKEN_79 = "HmzoN2qoPgXyD5ZpfNLZopUTbrSAl9BUDLmVDRri"

url = f"https://{SUBDOMAIN}.cybozu.com/k/v1/records.json"

res = requests.get(url, headers={"X-Cybozu-API-Token": TOKEN_79}, params={"app": 79})
records = res.json()["records"]

print("=== 1件目のレコードの全フィールド ===")
first = records[0]
for key, val in first.items():
    print(f"フィールド名: {key!r:30s} 型: {val.get('type','')!r:20s} 値: {val.get('value')}")
