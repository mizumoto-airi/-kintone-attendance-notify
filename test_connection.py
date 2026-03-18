"""当番ロジックの確認用（Teamsには送信しない）"""
import os
from notify import get_psg_members, get_duty_pair
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

members = get_psg_members()
print(f"=== PSGメンバー一覧（{len(members)}名）===")
for i, name in enumerate(members):
    print(f"  {i}: {name}")

main_name, sub_name = get_duty_pair(members)
today = datetime.now(JST)
dow = ["月", "火", "水", "木", "金", "土", "日"][today.weekday()]
print(f"\n=== 本日（{today.month}/{today.day}（{dow}））の当番 ===")
print(f"メイン：{main_name}さん")
print(f"サブ：{sub_name}さん")
