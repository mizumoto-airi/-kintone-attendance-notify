import requests
import base64
import os
from datetime import datetime, timezone, timedelta

KINTONE_SUBDOMAIN = "iu9b8ymlk83t"
LEAVE_APP_ID = 79

KINTONE_USERNAME = os.environ["KINTONE_USERNAME"]
KINTONE_PASSWORD = os.environ["KINTONE_PASSWORD"]
TEAMS_WEBHOOK_URL = os.environ["TEAMS_WEBHOOK_URL"]

JST = timezone(timedelta(hours=9))


def get_auth_header():
    credentials = base64.b64encode(
        f"{KINTONE_USERNAME}:{KINTONE_PASSWORD}".encode()
    ).decode()
    return {
        "X-Cybozu-Authorization": credentials,
        "Content-Type": "application/json",
    }


def get_today_leaves():
    today = datetime.now(JST)
    today_start = today.strftime("%Y-%m-%dT00:00:00+09:00")
    today_end = today.strftime("%Y-%m-%dT23:59:59+09:00")
    query = f'From <= "{today_end}" and To >= "{today_start}"'
    url = f"https://{KINTONE_SUBDOMAIN}.cybozu.com/k/v1/records.json"
    params = {
        "app": LEAVE_APP_ID,
        "query": query,
    }
    response = requests.get(url, headers=get_auth_header(), params=params)
    response.raise_for_status()
    return response.json()["records"]


def get_leave_label(record):
    leave_type = record.get("休暇種別", {}).get("value", "")
    from_str = record.get("From", {}).get("value", "")
    to_str = record.get("To", {}).get("value", "")
    time_label = "休暇"
    if from_str and to_str:
        from_dt = datetime.fromisoformat(from_str)
        to_dt = datetime.fromisoformat(to_str)
        if from_dt.hour <= 9 and to_dt.hour >= 17:
            time_label = "終日"
        elif to_dt.hour <= 13:
            time_label = "午前半休"
        elif from_dt.hour >= 13:
            time_label = "午後半休"
    if leave_type:
        return f"{leave_type}（{time_label}）"
    return time_label


def send_teams_notification(records):
    today = datetime.now(JST)
    today_str = today.strftime("%m/%d").lstrip("0")
    if not records:
        print("本日の休暇申請はありません。通知をスキップします。")
        return
    lines = []
    for record in records:
        tantousha = record.get("担当者", {}).get("value", [])
        if isinstance(tantousha, list) and tantousha:
            name = tantousha[0].get("name", "不明")
        else:
            name = str(tantousha) if tantousha else "不明"
        dept = record.get("所属", {}).get("value", "")
        label = get_leave_label(record)
        lines.append(f"・{name}（{dept}）　{label}")
    body_text = "\n".join(lines)
    total = len(records)
    message_text = (
        f"📅 今日（{today_str}）のお休み\n"
        f"━━━━━━━━━━━━━━\n"
        f"{body_text}\n"
        f"━━━━━━━━━━━━━━\n"
        f"合計 {total}名"
    )
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
                        {
                            "type": "TextBlock",
                            "text": message_text,
                            "wrap": True,
                            "fontType": "Monospace",
                        }
                    ],
                },
            }
        ],
    }
    response = requests.post(TEAMS_WEBHOOK_URL, json=payload)
    response.raise_for_status()
    print(f"通知送信完了：{total}名分")


if __name__ == "__main__":
    records = get_today_leaves()
    send_teams_notification(records)