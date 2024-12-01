#7729901539:AAEO8QbhybeSXO-jgx50-bfNgp-w1D-o2gk
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# Глобальный словарь для хранения данных пользователей (опционально)
user_data = {}

# Функция для кнопки "Запустить"
async def begin_action(update, context):
    keyboard_con_or_log = [
        [InlineKeyboardButton("ПОДКЛЮЧИТЬСЯ", callback_data='connect')],
        [InlineKeyboardButton("ВОЙТИ", callback_data='login')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_con_or_log)
    await update.callback_query.message.reply_text(
        "Если Вы хотите подключиться к высокоскоростному Интернету у себя дома нажмите кнопку "
        "«ПОДКЛЮЧИТЬСЯ». Если Вы уже являетесь нашим абонентом, нажмите кнопку «ВОЙТИ».",
        reply_markup=reply_markup
    )

# Функция для кнопки "Подключиться"
async def connect_action(update, context):
    await update.callback_query.message.reply_text("Введите Ваше ФИО:")
    context.user_data['next_action'] = 'ask_phone'  # Устанавливаем состояние для следующего шага

# Функция для кнопки "Войти"
async def login_action(update, context):
    await update.callback_query.message.reply_text(
        "Введите, пожалуйста, Ваш номер абонентского договора. "
        "Этот номер совпадает с логином для входа в Ваш личный кабинет."
    )

# Первый вход
async def start(update, context):
    if update.message:  # Проверяем, что сообщение существует
        keyboard_start = [[InlineKeyboardButton("Запустить", callback_data='begin')]]
        reply_markup = InlineKeyboardMarkup(keyboard_start)
        await update.message.reply_text(
            "Здравствуйте! Вас приветствует бот-помощник ZEXTEl.\nЧто умеет этот чат-бот: ляляля",
            reply_markup=reply_markup
        )

# Обработчик нажатий на кнопки
async def button(update, context):
    query = update.callback_query
    await query.answer()  # Уведомление Telegram, что запрос обработан
    if query.data == 'begin':
        await begin_action(update, context)
    elif query.data == 'connect':
        await connect_action(update, context)
    elif query.data == 'login':
        await login_action(update, context)

    # Убираем кнопки, чтобы предотвратить повторное нажатие
    #await query.edit_message_reply_markup(reply_markup=None)

# Обработка пользовательских сообщений
async def handle_message(update, context):
    if 'next_action' in context.user_data:
        # Проверяем текущее состояние
        if context.user_data['next_action'] == 'ask_phone':
            user_name = update.message.text  # Получаем введенное ФИО
            user_data[update.message.chat_id] = {'name': user_name}  # Сохраняем в глобальный словарь
            await update.message.reply_text("Теперь введите номер телефона:")
            context.user_data['next_action'] = 'finish_registration'  # Обновляем состояние
        elif context.user_data['next_action'] == 'finish_registration':
            user_phone = update.message.text  # Получаем введенный номер телефона
            user_data[update.message.chat_id]['phone'] = user_phone  # Сохраняем в глобальный словарь
            name = user_data[update.message.chat_id]['name']
            await update.message.reply_text(f"Регистрация завершена! Проверьте, всё ли верно:\nВаше ФИО: {name}\nВаш телефон: {user_phone}.")
            # Очищаем состояние
            context.user_data.pop('next_action', None)

# Главная функция
def main():
    # Создаем приложение
    application = Application.builder().token("7729901539:AAEO8QbhybeSXO-jgx50-bfNgp-w1D-o2gk").build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))  # Обработка текста

    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main()
