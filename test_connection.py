"""
取得結果の確認用スクリプト（Teamsには送信しない）
notify.py の get_today_leaves() と get_leave_label() を使って
実際に取得されるデータをログに表示する
"""
import os
from notify import get_today_leaves, get_leave_label
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

records = get_today_leaves()
today_str = datetime.now(JST).strftime("%m/%d").lstrip("0")

print(f"=== {today_str} の休暇申請（{len(records)}件） ===")

for record in records:
    shaiin = record.get("社員", {}).get("value", [])
    name = shaiin[0].get("name", "不明") if shaiin else "不明"
    label = get_leave_label(record)
    print(f"・{name}　{label}")
