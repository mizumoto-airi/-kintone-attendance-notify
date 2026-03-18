import requests

SUBDOMAIN = "iu9b8ymlk83t"
TOKEN_79 = "HmzoN2qoPgXyD5ZpfNLZopUTbrSAl9BUDLmVDRri"
TOKEN_7  = "bETQhdZ7JEi23CJnE1T6shggtbHAC1N3j5KC2VHT"

url = f"https://{SUBDOMAIN}.cybozu.com/k/v1/records.json"

print("=== 届出アプリ（ID:79）===")
res = requests.get(url, headers={"X-Cybozu-API-Token": TOKEN_79}, params={"app": 79})
print(f"ステータス: {res.status_code}")
print(res.text[:300])

print("\n=== M社員アプリ（ID:7）===")
res = requests.get(url, headers={"X-Cybozu-API-Token": TOKEN_7}, params={"app": 7})
print(f"ステータス: {res.status_code}")
print(res.text[:300])
