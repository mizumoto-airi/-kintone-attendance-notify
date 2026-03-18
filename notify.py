import requests
import os
from datetime import datetime, date, timezone, timedelta

# ── kintoneの設定 ──────────────────────────────────────────
KINTONE_SUBDOMAIN = "iu9b8ymlk83t"
LEAVE_APP_ID = 79   # 届出アプリ
MEMBER_APP_ID = 7   # M社員アプリ

KINTONE_LEAVE_APP_TOKEN = os.environ["KINTONE_LEAVE_APP_TOKEN"]
KINTONE_MEMBER_APP_TOKEN = os.environ["KINTONE_MEMBER_APP_TOKEN"]
TEAMS_WEBHOOK_URL = os.environ["TEAMS_WEBHOOK_URL"]

# ── 日本時間の設定 ──────────────────────────────────────────
JST = timezone(timedelta(hours=9))

# ── 当番ローテーションの基準日 ────────────────────────────────
# 3/17（火）のメインは 表示順で6番目の谷口さん（0始まりで index=5）
DUTY_BASE_DATE = date(2026, 3, 18)
DUTY_BASE_INDEX = 0  # 3/18から石川さんスタート


# ── 認証ヘッダーを作る関数 ────────────────────────────────────

def get_leave_header():
    return {"X-Cybozu-API-Token": KINTONE_LEAVE_APP_TOKEN}

def get_member_header():
    return {"X-Cybozu-API-Token": KINTONE_MEMBER_APP_TOKEN}


# ── API接続確認用の関数 ───────────────────────────────────────

def check_api_connection():
    url = f"https://{KINTONE_SUBDOMAIN}.cybozu.com/k/v1/records.json"
    print("=== kintone API接続確認 ===")

    print(f"\n[1] 届出アプリ（ID:{LEAVE_APP_ID}）を確認中...")
    res = requests.get(url, headers=get_leave_header(), params={"app": LEAVE_APP_ID})
    if res.ok:
        print(f"    接続成功！")
    else:
        print(f"    接続失敗！ エラー: {res.status_code} / {res.text}")

    print(f"\n[2] M社員アプリ（ID:{MEMBER_APP_ID}）を確認中...")
    res = requests.get(url, headers=get_member_header(), params={"app": MEMBER_APP_ID})
    if res.ok:
        print(f"    接続成功！")
    else:
        print(f"    接続失敗！ エラー: {res.status_code} / {res.text}")

    print("\n=== 確認完了 ===")


# ── PSG社員一覧を取得する関数 ────────────────────────────────

def get_psg_members():
    """M社員アプリからPSGの社員を表示順で取得し、名前のリストを返す"""
    url = f"https://{KINTONE_SUBDOMAIN}.cybozu.com/k/v1/records.json"
    params = {
        "app": MEMBER_APP_ID,
        "query": '部署 in ("PSG") order by レコード番号 asc',
    }
    response = requests.get(url, headers=get_member_header(), params=params)
    if not response.ok:
        print("kintone error:", response.status_code, response.text)
        response.raise_for_status()

    # 当番対象外の人を除外する
    EXCLUDE_NAMES = ["甲野 二号", "甲野 光邦"]

    members = []
    for record in response.json()["records"]:
        shaiin = record.get("社員名", {}).get("value", [])
        if shaiin:
            name = shaiin[0].get("name", "不明")
            if name not in EXCLUDE_NAMES:
                members.append(name)
    return members


# ── 今日の当番を計算する関数 ──────────────────────────────────

def count_weekdays(start, end):
    """start から end の前日まで（end当日は含まない）の平日数を数える"""
    count = 0
    current = start
    while current < end:
        if current.weekday() < 5:  # 月曜=0〜金曜=4 が平日
            count += 1
        current += timedelta(days=1)
    return count

def get_duty_pair(members):
    """今日のメインとサブの名前を返す"""
    today = datetime.now(JST).date()
    # 基準日から今日まで何平日経過したか
    elapsed = count_weekdays(DUTY_BASE_DATE, today)
    n = len(members)
    main_idx = (DUTY_BASE_INDEX + elapsed) % n
    sub_idx = (main_idx + 1) % n
    return members[main_idx], members[sub_idx]




# ── 今日の休暇申請を取得する関数 ──────────────────────────────

def get_today_leaves():
    """届出アプリから今日のPSG社員の休暇申請レコードを取得する"""
    today_str = datetime.now(JST).strftime("%Y-%m-%d")
    query = (
        f'当該日時From >= "{today_str}T00:00:00+09:00"'
        f' and 当該日時From <= "{today_str}T23:59:59+09:00"'
        f' and 所属部署 in ("PSG")'
    )
    url = f"https://{KINTONE_SUBDOMAIN}.cybozu.com/k/v1/records.json"
    params = {"app": LEAVE_APP_ID, "query": query}
    response = requests.get(url, headers=get_leave_header(), params=params)
    if not response.ok:
        print("kintone error:", response.status_code, response.text)
        response.raise_for_status()
    return response.json()["records"]


def get_leave_label(record):
    leave_type = record.get("休暇種別", {}).get("value", "") or ""
    unit = record.get("休暇単位", {}).get("value", "") or ""
    if leave_type and unit:
        return f"{leave_type}（{unit}）"
    return leave_type or unit or "休暇"


# ── Teamsに当番＋お休みをまとめて送る関数 ────────────────────

def send_teams_notification(main_name, sub_name, records):
    """当番とお休み情報を1つにまとめてTeamsに投稿する（ちょっと可愛く整形）"""
    today = datetime.now(JST)
    dow = ["月", "火", "水", "木", "金", "土", "日"][today.weekday()]
    today_str = f"{today.month}/{today.day}（{dow}）"

    # 当番パート（タイトルを少し可愛く）
    duty_title = f"☀️ {today_str} の朝会スマビジ当番"
    duty_main = f"メイン：**{main_name} さん**"
    duty_sub = f"サブ：**{sub_name} さん**"

    # お休みパート
    holiday_title = "📅 今日のお休み"
    if not records:
        holiday_body = "お休みの方はいません"
        footer = "🎉 **全員出席です！**"
    else:
        lines = []
        for record in records:
            shaiin = record.get("社員", {}).get("value", [])
            name = shaiin[0].get("name", "不明") if shaiin else "不明"
            label = get_leave_label(record)
            lines.append(f"・{name}　{label}")
        holiday_body = "\n".join(lines)
        total = len(records)
        footer = f"合計 **{total}名**"

    # お休みがいる場合はwarning（黄）、いない場合はgood（緑）の背景
    holiday_style = "good" if not records else "warning"

    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.2",
                    "body": [
                        # 当番セクション（accent = 青紫系の背景）
                        {
                            "type": "Container",
                            "style": "accent",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": duty_title,
                                    "wrap": True,
                                    "weight": "Bolder",
                                    "size": "Medium",
                                    "color": "Light",
                                },
                                {
                                    "type": "FactSet",
                                    "facts": [
                                        {"title": "メイン", "value": f"{main_name} さん"},
                                        {"title": "サブ　", "value": f"{sub_name} さん"},
                                    ],
                                },
                            ],
                        },
                        # お休みセクション（緑 or 黄の背景）
                        {
                            "type": "Container",
                            "style": holiday_style,
                            "spacing": "Medium",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": holiday_title,
                                    "wrap": True,
                                    "weight": "Bolder",
                                },
                                {
                                    "type": "TextBlock",
                                    "text": holiday_body,
                                    "wrap": True,
                                },
                                {
                                    "type": "TextBlock",
                                    "text": footer,
                                    "wrap": True,
                                    "spacing": "Small",
                                    "isSubtle": True,
                                },
                            ],
                        },
                    ],
                },
            }
        ],
    }
    response = requests.post(TEAMS_WEBHOOK_URL, json=payload)
    response.raise_for_status()
    print(f"通知送信完了：メイン={main_name}、サブ={sub_name}、お休み={total}名")


# ── メイン処理 ────────────────────────────────────────────────
if __name__ == "__main__":
    check_api_connection()

    members = get_psg_members()
    main_name, sub_name = get_duty_pair(members)
    records = get_today_leaves()
    send_teams_notification(main_name, sub_name, records)
