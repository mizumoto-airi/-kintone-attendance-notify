"""M社員アプリのフィールド構造を確認する"""
import requests

SUBDOMAIN = "iu9b8ymlk83t"
TOKEN_7 = "bETQhdZ7JEi23CJnE1T6shggtbHAC1N3j5KC2VHT"

url = f"https://{SUBDOMAIN}.cybozu.com/k/v1/records.json"
res = requests.get(url, headers={"X-Cybozu-API-Token": TOKEN_7}, params={"app": 7})
records = res.json()["records"]

print("=== M社員アプリ 1件目のフィールド一覧 ===")
first = records[0]
for key, val in first.items():
    print(f"フィールド名: {key!r:30s} 型: {val.get('type','')!r:25s} 値: {val.get('value')}")

print(f"\n合計 {len(records)} 件")
