import requests
import os
from datetime import datetime, timezone, timedelta

# ── kintoneの設定 ──────────────────────────────────────────
KINTONE_SUBDOMAIN = "iu9b8ymlk83t"  # あなたのkintoneのサブドメイン
LEAVE_APP_ID = 79   # 届出アプリ
MEMBER_APP_ID = 7   # M社員アプリ

# 環境変数からAPIトークンを取得する
# （GitHubのSecretsに登録する。コードに直接書いてはいけない！）
KINTONE_LEAVE_APP_TOKEN = os.environ["KINTONE_LEAVE_APP_TOKEN"]    # 届出アプリ用トークン
KINTONE_MEMBER_APP_TOKEN = os.environ["KINTONE_MEMBER_APP_TOKEN"]  # M社員アプリ用トークン
TEAMS_WEBHOOK_URL = os.environ["TEAMS_WEBHOOK_URL"]

# ── 日本時間の設定 ──────────────────────────────────────────
JST = timezone(timedelta(hours=9))


# ── 認証ヘッダーを作る関数 ────────────────────────────────────
# 「ヘッダー」= APIリクエストに付ける付加情報。「このトークンを持つ人だよ」とkintoneに証明する

def get_leave_header():
    """届出アプリ（ID:79）用のヘッダー"""
    return {
        "X-Cybozu-API-Token": KINTONE_LEAVE_APP_TOKEN,
        "Content-Type": "application/json",
    }

def get_member_header():
    """M社員アプリ（ID:7）用のヘッダー"""
    return {
        "X-Cybozu-API-Token": KINTONE_MEMBER_APP_TOKEN,
        "Content-Type": "application/json",
    }


# ── API接続確認用の関数 ───────────────────────────────────────

def check_api_connection():
    """両アプリにつながるか確認する。成功したら件数を表示する"""
    url = f"https://{KINTONE_SUBDOMAIN}.cybozu.com/k/v1/records.json"
    print("=== kintone API接続確認 ===")

    # 届出アプリ（ID:79）
    print(f"\n[1] 届出アプリ（ID:{LEAVE_APP_ID}）を確認中...")
    res = requests.get(url, headers=get_leave_header(), params={"app": LEAVE_APP_ID, "totalCount": True})
    if res.ok:
        print(f"    接続成功！ 総レコード数: {res.json().get('totalCount', '?')}件")
    else:
        print(f"    接続失敗！ エラー: {res.status_code} / {res.text}")

    # M社員アプリ（ID:7）
    print(f"\n[2] M社員アプリ（ID:{MEMBER_APP_ID}）を確認中...")
    res = requests.get(url, headers=get_member_header(), params={"app": MEMBER_APP_ID, "totalCount": True})
    if res.ok:
        print(f"    接続成功！ 総レコード数: {res.json().get('totalCount', '?')}件")
    else:
        print(f"    接続失敗！ エラー: {res.status_code} / {res.text}")

    print("\n=== 確認完了 ===")


# ── 今日の休暇申請を取得する関数 ──────────────────────────────

def get_today_leaves():
    """届出アプリから今日の休暇申請レコードを全件取得する"""
    today = datetime.now(JST)
    url = f"https://{KINTONE_SUBDOMAIN}.cybozu.com/k/v1/records.json"
    params = {
        "app": LEAVE_APP_ID,
    }
    response = requests.get(url, headers=get_leave_header(), params=params)
    if not response.ok:
        print("kintone error:", response.status_code, response.text)
        response.raise_for_status()
    return response.json()["records"]


def get_leave_label(record):
    """休暇の種別（終日・午前半休・午後半休など）を文字列で返す"""
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


# ── Teamsに通知を送る関数 ──────────────────────────────────────

def send_teams_notification(records):
    """取得した休暇レコードをTeamsに投稿する"""
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


# ── メイン処理 ────────────────────────────────────────────────
if __name__ == "__main__":
    check_api_connection()
    records = get_today_leaves()
    send_teams_notification(records)
