import json
from datetime import datetime
import configparser

config = configparser.ConfigParser()
config.read("config.cfg")
LOG_FILE = config["logger"]["file"]


def log_activity(user_id, action):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"{timestamp} | User {user_id} | {action}\n"

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_entry)