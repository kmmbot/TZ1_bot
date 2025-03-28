from fastapi import FastAPI, Request
import requests, datetime, configparser, uvicorn

app = FastAPI()
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

@app.post("/")
async def receive_webhook(request: Request):
    data = await request.json()
    user_id = data.get("from", {}).get("id", "unknown")
    print(user_id)
    message_text = data.get("text", "unknown")

    #print(f"Получено сообщение от {user_id}: {message_text}")

    # Создаём сделку
    deal_response = create_deal(str(user_id), message_text)

    return {"bitrix_response": deal_response}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)