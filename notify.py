import requests
import os
import jpholiday
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
    """start から end の前日まで（end当日は含まない）の営業日数を数える（祝日除く）"""
    count = 0
    current = start
    while current < end:
        if current.weekday() < 5 and not jpholiday.is_holiday(current):
            count += 1
        current += timedelta(days=1)
    return count

def get_next_weekday(d):
    """dの翌営業日を返す（土日祝を飛ばす）"""
    next_day = d + timedelta(days=1)
    while next_day.weekday() >= 5 or jpholiday.is_holiday(next_day):
        next_day += timedelta(days=1)
    return next_day

def get_duty_pair(members):
    """明日（次の平日）のメインとサブの名前と日付を返す"""
    today = datetime.now(JST).date()
    target = get_next_weekday(today)  # 明日 or 翌月曜
    # 基準日からtargetまで何平日経過したか
    elapsed = count_weekdays(DUTY_BASE_DATE, target)
    n = len(members)
    main_idx = (DUTY_BASE_INDEX + elapsed) % n
    sub_idx = (main_idx + 1) % n
    return members[main_idx], members[sub_idx], target




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


# ── 今月の休暇予定を取得する関数 ──────────────────────────────

def get_monthly_leaves():
    """今日以降〜月末のPSG社員の承認済み休暇を取得する"""
    import calendar
    today = datetime.now(JST)
    today_str = today.strftime("%Y-%m-%d")
    # 月末日を計算する
    last_day = calendar.monthrange(today.year, today.month)[1]
    end_str = today.strftime(f"%Y-%m-{last_day:02d}")

    query = (
        f'当該日時From >= "{today_str}T00:00:00+09:00"'
        f' and 当該日時From <= "{end_str}T23:59:59+09:00"'
        f' and 所属部署 in ("PSG")'
        f' and ステータス = "届出「承認済」"'
        f' order by 当該日時From asc'
    )
    url = f"https://{KINTONE_SUBDOMAIN}.cybozu.com/k/v1/records.json"
    params = {"app": LEAVE_APP_ID, "query": query}
    response = requests.get(url, headers=get_leave_header(), params=params)
    if not response.ok:
        print("kintone error:", response.status_code, response.text)
        response.raise_for_status()
    return response.json()["records"]


# ── Teamsに当番＋お休みをまとめて送る関数 ────────────────────

def send_teams_notification(main_name, sub_name, target_date, members, records, monthly_records):
    """当番とお休み情報を1つにまとめてTeamsに投稿する"""
    today = datetime.now(JST)
    today_dow = ["月", "火", "水", "木", "金", "土", "日"][today.weekday()]
    today_str = f"{today.month}/{today.day}（{today_dow}）"

    # 明日（次の平日）の日付表示
    target_dow = ["月", "火", "水", "木", "金", "土", "日"][target_date.weekday()]
    target_str = f"{target_date.month}/{target_date.day}（{target_dow}）"

    # 当番パート：明日の当番
    duty_title = f"☀️ {target_str} の朝会スマビジ当番"

    # 当番一覧（全メンバーをリスト表示）
    roster_lines = []
    for i, name in enumerate(members):
        roster_lines.append(f"{i + 1}. {name}")
    roster_text = "\n".join(roster_lines)

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

    # 今月の休暇予定パート
    dow_list = ["月", "火", "水", "木", "金", "土", "日"]
    if not monthly_records:
        monthly_text = "今月の予定はありません"
    else:
        monthly_lines = []
        for record in monthly_records:
            shaiin = record.get("社員", {}).get("value", [])
            name = shaiin[0].get("name", "不明") if shaiin else "不明"
            label = get_leave_label(record)
            from_str = record.get("当該日時From", {}).get("value", "")
            if from_str:
                # UTCで保存されているのでJSTに変換して日付を取得
                dt = datetime.fromisoformat(from_str.replace("Z", "+00:00")).astimezone(JST)
                d_str = f"{dt.month}/{dt.day}（{dow_list[dt.weekday()]}）"
            else:
                d_str = "日付不明"
            monthly_lines.append(f"{d_str}　{name}　{label}")
        monthly_text = "\n".join(monthly_lines)

    # お休みがいる場合はwarning（黄）、いない場合はgood（緑）の背景
    holiday_style = "good" if not records else "warning"  # なし=緑、あり=黄

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
                        # 当番セクション（attention = 赤ピンク）
                        {
                            "type": "Container",
                            "style": "attention",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": duty_title,
                                    "wrap": True,
                                    "weight": "Bolder",
                                    "size": "Medium",
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
                        # 当番一覧セクション（accent = 青紫）
                        {
                            "type": "Container",
                            "style": "accent",
                            "spacing": "Small",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": "📋 当番一覧",
                                    "wrap": True,
                                    "weight": "Bolder",
                                },
                                {
                                    "type": "TextBlock",
                                    "text": roster_text,
                                    "wrap": True,
                                    "isSubtle": True,
                                },
                            ],
                        },
                        # 今日のお休みセクション（緑 or 黄の背景）
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
                        # 今月の休暇予定セクション（emphasis = グレー）
                        {
                            "type": "Container",
                            "style": "emphasis",
                            "spacing": "Medium",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": "📆 今月の休暇予定",
                                    "wrap": True,
                                    "weight": "Bolder",
                                },
                                {
                                    "type": "TextBlock",
                                    "text": monthly_text,
                                    "wrap": True,
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
    total = len(records)
    print(f"通知送信完了：メイン={main_name}、サブ={sub_name}、お休み={total}名")


# ── メイン処理 ────────────────────────────────────────────────
if __name__ == "__main__":
    today = datetime.now(JST).date()

    # 今日が祝日なら通知しない
    if jpholiday.is_holiday(today):
        print(f"今日（{today}）は祝日のため通知をスキップします。")
    else:
        check_api_connection()
        members = get_psg_members()
        main_name, sub_name, target_date = get_duty_pair(members)
        records = get_today_leaves()
        monthly_records = get_monthly_leaves()
        send_teams_notification(main_name, sub_name, target_date, members, records, monthly_records)
