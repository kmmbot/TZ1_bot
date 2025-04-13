import requests, datetime, configparser

config = configparser.ConfigParser()
config.read("config.cfg")
bitrix_webhook_url = config["bitrix"]["url"]

def create_deal(user_id, message_text):
    now = datetime.datetime.utcnow().isoformat()
    close_date = (datetime.datetime.utcnow() + datetime.timedelta(days=10)).isoformat()

    deal_data = {
        "FIELDS": {
            "TITLE": "TEST",
            "TYPE_ID": "Новое обращение",
            "CATEGORY_ID": 3,
            "STAGE_ID": "DEAL_STAGE_4",
            "CURRENCY_ID": "RUB",
            "OPPORTUNITY": 0,
            "BEGINDATE": now,
            "CLOSEDATE": close_date,
            "COMMENTS": message_text,
            "SOURCE_ID": "CALLBACK",
            "SOURCE_DESCRIPTION": "Сообщение из бота",
            "UTM_SOURCE": "telegram",
            "UTM_MEDIUM": "bot"
        }
    }

    headers = {"Content-Type": "application/json"}
    response = requests.post(bitrix_webhook_url, json=deal_data, headers=headers)

    return response.json()

def receive_webhook(data):
    user_id = data.get("from", {}).get("id", "unknown")
    message_text = data.get("text", "unknown")
    return create_deal(str(user_id), message_text)