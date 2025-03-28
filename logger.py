from fastapi import FastAPI, Request
import uvicorn, json, configparser
from datetime import datetime

app = FastAPI()
config = configparser.ConfigParser()
config.read("config.cfg")
LOG_FILE = config["logger"]["file"]


@app.post("/")
async def log_activity(request: Request):
    data = await request.json()
    user_id = data.get("id", "unknown")
    action = data.get("action", "unknown")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_entry = f"{timestamp} | User {user_id} | {action}\n"

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry)

    return {"status": "logged"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)