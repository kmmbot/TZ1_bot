import configparser
from telegram import Bot
from telegram.ext import Application, MessageHandler, filters
from cryptography.fernet import Fernet

# Чтение конфигурации
config = configparser.ConfigParser()
config.read("config.cfg")
token = config["sender"]["token"]
key = config["telegram"]["key"]
cipher = Fernet(key)
existing_chat_ids = config["telegram"].get("chat_id", "")
chat_id_list = existing_chat_ids.split(",") if existing_chat_ids else []
decripted = [cipher.decrypt(item).decode('utf-8') for item in chat_id_list]
bot = Bot(token = config["telegram"]["token"])
async def get_message(update, context):
    message = update.message.text
    for chat_id in decripted:
        await bot.send_message(chat_id = chat_id, text=message)


def main():
    application = Application.builder().token(token).build()

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, get_message))

    application.run_polling()


if __name__ == "__main__":
    main()