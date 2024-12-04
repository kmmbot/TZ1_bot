import httpx, json, configparser, random
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# Глобальный словарь для хранения данных пользователей (опционально)
user_data = {
    "1234": {"name": "Пупкин Иван Иванович", "phone": "использовал личный номер для тестирования", "balance": "550", "service":"Базовый", "cost": "1300", "payment": "0", "utilities":"Интернет и ТВ"}
}
new_user_data = {} # Словарь для хранения данных новых пользователей (чтоб им потом перезвонили)

# Чтение токена из файла конфигурации
config = configparser.ConfigParser()
config.read("config.cfg")
token = config["telegram"]["token"]
API = config["telegram"]["API"]

# Валидация номера договора
async def contr_validation(update, context, contract):
    if not contract.isnumeric() or len(contract) > 4 or not (1 <= int(contract) <= 9999):
        await update.message.reply_text(
            "Неверный формат номера договора. Пожалуйста, введите номер договора, состоящий из 2-4 цифр."
        )
        return

# Код в СМС
async def send_sms(update, context):

    #Отправляет SMS через SMSPilot.
    #:param phone: Номер телефона в формате 79XXXXXXXXX.
    #:param text: Текст сообщения (до 70 символов для одного SMS).
    #:param sender: Имя отправителя, зарегистрированное в SMSPilot.
    #:param apikey: Ваш API-ключ от SMSPilot.
    #:return: Ответ от SMSPilot в формате JSON.
    user = context.user_data.get('user_contract')
    phone = user_data[user]['phone']
    code = random.randint(100000, 999999)
    context.user_data['key'] = code
    url = "https://smspilot.ru/api.php"
    params = {
        "send": f"Ваш код: {code}",
        "to": phone,
        "from": "INFORM",
        "apikey": API,
        "format": "json"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params)
            response_data = response.json()
            if "error" in response_data:
                return f"Ошибка: {response_data['error']['description_ru']}"
            else:
                return response_data
        except Exception as e:
            return f"Произошла ошибка: {str(e)}"

# Проверка на кол-во оставшихся попыток
async def attempts_check(update, context, check):
    if check > 0:
        await update.message.reply_text(
            "Такого номера договора не существует. Если Вы уверены, что вводите номер правильно, "
            "обратитесь в техническую поддержку по телефону +7(812)448-53-23.\n"
            f"Попыток осталось: {check}. Пожалуйста, введите номер ещё раз."
        )
    else:
        # Превышено количество попыток
        await update.message.reply_text(
            "К нашему огромному сожалению, Вы пять раз ввели неверный номер договора. "
            "Для возобновления доступа обратитесь, пожалуйста, в нашу службу технической поддержки."
        )
        # Завершаем состояние
        context.user_data.pop('next_action', None)
        context.user_data.pop('attempts', None)

# Функция для кнопки "Запустить"
async def begin_action(update, context):
    keyboard_connect_or_log = [
        [InlineKeyboardButton("ПОДКЛЮЧИТЬСЯ", callback_data = 'connect')],
        [InlineKeyboardButton("ВОЙТИ", callback_data = 'login')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_connect_or_log)
    await update.callback_query.message.reply_text(
        "Если Вы хотите подключиться к высокоскоростному Интернету у себя дома нажмите кнопку "
        "«ПОДКЛЮЧИТЬСЯ». Если Вы уже являетесь нашим абонентом, нажмите кнопку «ВОЙТИ».",
        reply_markup = reply_markup
    )

# Отработка существующего номера договора
async def valid_action(update, context, contract):
    keyboard_message = [
        [InlineKeyboardButton("Отправить СМС с кодом", callback_data = 'send')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_message)
    await update.message.reply_text(
        f"После нажатия на кнопку «Отправить СМС с кодом», на номер {user_data[contract]['phone']} "
        "указанный при заключении договора, будет отправлено СМС, в котором содержится код для входа в Личный кабинет.",
        reply_markup = reply_markup
    )

# Функция для кнопки "Отправить СМС с кодом"
async def message_action(update, context):
    sms_response = await send_sms(update, context)
    if "Ошибка" in sms_response:
        await update.callback_query.message.reply_text(f"Произошла ошибка при отправке SMS. \n{sms_response}")
    else:
        await update.callback_query.message.reply_text(
            "На Ваш номер отправлено сообщение с кодом для входа в личный кабинет.\nВведите код:")
    context.user_data['next_action'] = 'ask_key'  # Устанавливаем состояние для следующего шага

# Отработка неправильного кода из СМС
async def wrong_key_action(update, context):
    keyboard_message = [
        [InlineKeyboardButton("Повторно отправить код", callback_data = 'send')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_message)
    await update.message.reply_text("Вы ввели неверный код, пожалуйста, будьте внимательны и введите новый код. ",
        reply_markup = reply_markup
    )

# Функция для кнопки "Подключиться"
async def connect_action(update, context):
    await update.callback_query.message.reply_text("Введите Ваше ФИО:")
    context.user_data['next_action'] = 'ask_phone'  # Устанавливаем состояние для следующего шага

# Функция для кнопки "Продолжить"
async def continue_action(update, context):
    await update.callback_query.message.reply_text("Номер абонентского договора:")
    context.user_data['next_action'] = 'ask_contr_number'

# Функция для кнопки "Войти"
async def login_action(update, context):
    keyboard_login = [
        [InlineKeyboardButton("Продолжить", callback_data = 'continue')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_login)
    await update.callback_query.message.reply_text(
        "После нажатия на кнопку «Продолжить» введите, пожалуйста, номер Вашего абонентского договора. "
        "Этот номер совпадает с логином для входа в Ваш личный кабинет.",
        reply_markup = reply_markup
    )

# Функция для кнопки "Учетные данные"
async def data_action(update, context):
    keyboard_data = [
        [InlineKeyboardButton("Изменить", callback_data = 'change'),
         InlineKeyboardButton("Оплатить", callback_data = 'pay')],
        [InlineKeyboardButton("Вернуться", callback_data = 'back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_data)
    user = context.user_data.get('user_contract')
    message = await update.callback_query.message.reply_text(
        f"ФИО: {user_data[user]['name']} \nНомер договора: {user} \nНомер телефона: {user_data[user]['phone']} "
        f"\nТарифный план: {user_data[user]['service']} \nСтоимость: {user_data[user]['cost']} \nПодключенные услуги: {user_data[user]['utilities']}."
        "\nДополнительные кнопки для перехода в другие разделы",
        reply_markup = reply_markup
    )
    context.user_data['last_message_id'] = message.message_id
    context.user_data['chat_id'] = message.chat_id

# Функция для кнопки "Пополнение"
async def refill_action(update, context):
    keyboard_refill = [
        [InlineKeyboardButton("Оплатить", callback_data = 'pay'),
        InlineKeyboardButton("Вернуться", callback_data = 'back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_refill)
    user = context.user_data.get('user_contract')
    user_data[user]['payment'] = int(user_data[user]['cost']) - int(user_data[user]['balance'])
    message = await update.callback_query.message.reply_text(
        f"Текущий баланс {user_data[user]['balance']} \nРекомендуемая сумма к оплате {user_data[user]['payment']}"
        "\nДополнительные кнопки для перехода в другие разделы",
        reply_markup = reply_markup
    )
    context.user_data['last_message_id'] = message.message_id
    context.user_data['chat_id'] = message.chat_id

# Функция для кнопки "Новости"
async def news_action(update, context):
    keyboard_news = [
        [InlineKeyboardButton("❮", callback_data = 'left'), # Листать нечего, так что обе стрелки пока что неактивны
         InlineKeyboardButton("Вернуться", callback_data = 'back'),
         InlineKeyboardButton("❯", callback_data = 'right')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_news)
    user = context.user_data.get('user_contract')
    message = await update.callback_query.message.reply_text(
        "Какая-то новость, которую надо подтянуть из административного бэкенда",
        reply_markup = reply_markup
    )
    context.user_data['last_message_id'] = message.message_id
    context.user_data['chat_id'] = message.chat_id

# Функция для кнопки "Акции"
async def events_action(update, context):
    keyboard_events = [
         [InlineKeyboardButton("Вернуться", callback_data = 'back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_events)
    user = context.user_data.get('user_contract')
    message = await update.callback_query.message.reply_text(
        "Какие-то акции, которые надо подтянуть из административного бэкенда",
        reply_markup = reply_markup
    )
    context.user_data['last_message_id'] = message.message_id
    context.user_data['chat_id'] = message.chat_id

# Функция для кнопки "Вернуться"
async def back_action(update, context):
    last_message_id = context.user_data.get('last_message_id')
    chat_id = context.user_data.get('chat_id')
    await context.bot.delete_message(chat_id = chat_id, message_id = last_message_id)

# Первый вход
async def start(update, context):
    if update.message:  # Проверяем, что сообщение существует
        keyboard_start = [
            [InlineKeyboardButton("Запустить", callback_data = 'begin')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard_start)
        await update.message.reply_text(
            "Здравствуйте! Вас приветствует бот-помощник ZEXTEl.\nЧто умеет этот чат-бот: какая-то информация о боте",
            reply_markup = reply_markup
        )

# Блок-меню бота
async def menu(update, context):
    keyboard_menu = [
        [InlineKeyboardButton("Учетные данные", callback_data = 'data'),
         InlineKeyboardButton("Пополнение", callback_data = 'refill')],
        [InlineKeyboardButton("Новости", callback_data = 'news'),
         InlineKeyboardButton("Акции", callback_data = 'events')],
        [InlineKeyboardButton("Техническая поддержка", callback_data = 'supp')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_menu)
    await update.message.reply_text(
        "Вы успешно вошли в личный кабинет, теперь Вам доступны следующие разделы:",
        reply_markup = reply_markup
    )

# Обработчик нажатий на кнопки
async def button(update, context):
    query = update.callback_query
    user_contract = context.user_data.get('user_contract')
    await query.answer()  # Уведомление Telegram, что запрос обработан

    # "Запустить"
    if query.data == 'begin':
        await begin_action(update, context)

    # "Подключиться"
    elif query.data == 'connect':
        await connect_action(update, context)

    # Обработка нажатий кнопок, связанных с входом в систему
    elif query.data == 'login':
        await login_action(update, context)
    elif query.data == 'continue':
        await continue_action(update, context)
    elif query.data == 'send':
        await message_action(update, context)

    # Обработка нажатий кнопок в меню
    elif query.data == 'data':
        await data_action(update, context)
    elif query.data == 'refill':
        await refill_action(update, context)
    elif query.data == 'news':
        await news_action(update, context)
    elif query.data == 'events':
        await events_action(update, context)
    elif query.data == 'supp':
        await supp_action(update, context)

    # Обработка нажатий кнопок в разделах меню(пока что только "Вернуться")
    elif query.data == 'back':
        await back_action(update, context)


    # Убираем кнопки, чтобы предотвратить повторное нажатие, для более комфортного тестирования работы бота, функция неактивна
    #await query.edit_message_reply_markup(reply_markup=None)

# Обработка пользовательских сообщений
async def handle_message(update, context):
    if 'next_action' in context.user_data:
        # Проверяем текущее состояние
        # Ввод номера абонентского договора
        if context.user_data['next_action'] == 'ask_contr_number':
            user_contract = update.message.text  # Получаем введенный номер договора
            await contr_validation(update, context, user_contract) # Проверяем полученный номер
            if user_contract in user_data:
                context.user_data['user_contract'] = user_contract
                # Найден действительный номер договора
                await valid_action(update, context, user_contract)
                # Завершаем состояние
                context.user_data.pop('next_action', None)
            else:
                # Номер договора не найден
                attempts = context.user_data.get('attempts', 5)  # Получаем оставшиеся попытки
                attempts -= 1
                context.user_data['attempts'] = attempts  # Обновляем количество попыток
                await attempts_check(update, context, attempts)



        # Ввод номера данных для подключения нового пользователя
        elif context.user_data['next_action'] == 'ask_phone':
            # Обрабатываем введённый номер телефона
            user_name = update.message.text  # Получаем введенное ФИО
            new_user_data[update.message.chat_id] = {'name': user_name}  # Сохраняем в глобальный словарь
            await update.message.reply_text("Теперь введите номер телефона:")
            context.user_data['next_action'] = 'finish_registration'  # Обновляем состояние
        elif context.user_data['next_action'] == 'finish_registration':
            user_phone = update.message.text  # Получаем введённый номер телефона
            new_user_data[update.message.chat_id]['phone'] = user_phone  # Сохраняем в глобальный словарь
            name = new_user_data[update.message.chat_id]['name']
            await update.message.reply_text(
                f"Регистрация завершена! Проверьте, всё ли верно:\nВаше ФИО: {name}\nВаш телефон: {user_phone}"
            )
            # Очищаем состояние
            context.user_data.pop('next_action', None)

        # Ввод кода из СМС для входа в ЛК
        elif context.user_data['next_action'] == 'ask_key':
            key_for_test = context.user_data.get('key')
            user_key = update.message.text  # Получаем введенный код из СМС
            if int(user_key) != key_for_test:
                await wrong_key_action(update, context)
            else:
                await menu(update, context)


# Главная функция
def main():
    # Создаем приложение
    application = Application.builder().token(token).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))  # Обработка текста

    # Запускаем бота
    application.run_polling()
if __name__ == '__main__':
    main()