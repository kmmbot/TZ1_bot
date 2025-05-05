import logging, httpx, json, configparser, random, asyncio, requests, hmac, hashlib, aiofiles, uvicorn, mysql.connector
from html import escape
import logger, bitrix_deal
from fastapi import FastAPI, Request
from cryptography.fernet import Fernet
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from bitrix_deal import receive_webhook
from logger import log_activity

# Объявляем переменные и списки для тестирования бота локально без БД
new_user_data = {}  # Словарь для хранения данных новых пользователей (чтоб им потом перезвонили)
news_list = [
    "Новость 1",
    "Новость 2",
    "Новость 3",
    "Новость 4",
    "Новость 5"
]
action_list = [
    "started",
    "billing request",
    "bitrix request",
    "logged in",
    "timeout"
]
messages_id = []  # Массив id сообщений, которые удаляются после тайм-аута

# Чтение данных из файла конфигурации
config = configparser.ConfigParser()
config.read("config.cfg")
token = config["telegram"]["token"]
API = config["telegram"]["API"]
url_main = config["telegram"]["url_search"]
url_login = config["telegram"]["url_token"]
url_pay = config["telegram"]["url_payment"]
url_subs = config["telegram"]["url_subs"]
secret = config["telegram"]["secret"]
inactivity_timeout = timedelta(seconds=int(config["telegram"]["timeout"]))  # Тайм-аут бездействия
# Логирование
async def send_data(update, context, action):

    logger.log_activity(context.user_data.get('user_id'), action)

    return

#Данные для сделки в Bitrix
async def send_message(update, context, message_text):
    payload = {
            "from": {"id": context.user_data.get('user_contract')},
            "text": message_text
        }

    bitrix_deal.receive_webhook(payload)

    return

# Экранирование сообщений
async def sanitize(msg):
    msg = msg.replace("'", "\\'").replace('"', '\\"').replace("\\", "\\\\")
    msg = escape(msg)
    return msg

# Шифруем и записывавем chat_id
async def encryption(msg):
    KEY = config["telegram"]["key"]
    cipher = Fernet(KEY)
    existing_chat_ids = config["telegram"].get("chat_id", "")
    chat_id_list = existing_chat_ids.split(",") if existing_chat_ids else []
    decrypted = [cipher.decrypt(item).decode('utf-8') for item in chat_id_list]
    if msg not in decrypted:
        msg = msg.encode('utf-8')
        chat_id = cipher.encrypt(msg)
        chat_id_list.append(chat_id.decode('utf-8'))
        config["telegram"]["chat_id"] = ",".join(chat_id_list)
        with open("config.cfg", "w") as file:
            config.write(file)
    return

# Обращение к биллингу
async def billing_request(update, context):
    await send_data(update, context, action_list[1])

    salt = "12345"
    sign = hmac.new(secret.encode(), salt.encode(), hashlib.sha512).hexdigest()

    payload = {
        'field': 'numdogovor',
        'operator': '=',
        'value': context.user_data.get('user_contract'),
        'sign': sign,
        'salt': salt
    }

    # Заголовки запроса
    headers = {}

    # Выполняем запрос
    response = requests.request("POST", url_main, headers=headers, data=payload)

    return response.json()

# Сброс таймера
async def reset_timeout(update, context):
    if update.message:
        user_id = update.message.from_user.id
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
    context.user_data['last_active'] = datetime.now()
    if 'timeout_task' in context.user_data:
        context.user_data['timeout_task'].cancel()
    context.user_data['timeout_task'] = asyncio.create_task(timeout_handler(update, context))

# Обработка тайм-аута
async def timeout_handler(update, context):
    await asyncio.sleep(inactivity_timeout.total_seconds())
    if datetime.now() - context.user_data.get('last_active', datetime.now()) >= inactivity_timeout:

        keyboard_timeout = [
            [InlineKeyboardButton("ВОЙТИ", callback_data='login')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard_timeout)
        if update.message:
            await update.message.reply_text(
                "Вы были неактивны слишком долго. Сессия завершена. \nЧтобы продолжить работу войдите в личный кабинет",
                reply_markup=reply_markup
            )
        else:
            await update.callback_query.message.reply_text(
                "Вы были неактивны слишком долго. Сессия завершена. \nЧтобы продолжить работу войдите в личный кабинет",
                reply_markup=reply_markup
            )

        if context.user_data.get('last_message_id') and context.user_data.get('last_message_id') not in messages_id:
            messages_id.append(context.user_data.get('last_message_id'))
        if context.user_data.get('buffer') and context.user_data.get('buffer') not in messages_id:
            messages_id.append(context.user_data.get('buffer'))

        chat_id = update.effective_chat.id
        for msg in messages_id:
            try:
                await context.bot.delete_message(chat_id, msg)
            except Exception as e:
                print(f"Не удалось удалить сообщение {msg}: {e}")
        messages_id.clear()
        await send_data(update, context, action_list[4])
        context.user_data.clear()  # Очистка данных пользователя

# Валидация номера договора
async def contr_validation(update, context, contract):
    if not contract.isnumeric() or len(contract) > 4 or not (1 <= int(contract) <= 9999):
        msg = await update.message.reply_text(
            "Неверный формат номера договора. Пожалуйста, введите номер договора, состоящий из 2-4 цифр."
        )
        messages_id.append(msg.message_id)
        return

# Валидация кода из СМС
async def key_validation(update, context, key):
    if not key.isnumeric() or len(key) > 6 or not (100000 <= int(key) <= 999999):
        msg = await update.message.reply_text(
            "Неверный формат кода. Пожалуйста, внимательно введите код еще раз."
        )
        messages_id.append(msg.message_id)
        return 0
    return key

# Код в СМС
async def send_sms(update, context):

    # Отправляет SMS через SMSPilot.
    #:param phone: Номер телефона в формате 79XXXXXXXXX.
    #:param text: Текст сообщения (до 70 символов для одного SMS).
    #:param sender: Имя отправителя, зарегистрированное в SMSPilot.
    #:param apikey: Ваш API-ключ от SMSPilot.
    #:return: Ответ от SMSPilot в формате JSON.
    user = context.user_data.get('user_contract')
    phone = context.user_data.get('phone')
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

# Проверка на кол-во оставшихся попыток + отработка неправильного кода из СМС
async def attempts_check(update, context, check):
    if context.user_data['next_action'] == 'ask_contr_number':
        if check > 0:
            msg = await update.message.reply_text(
                "Такого номера договора не существует. Если Вы уверены, что вводите номер правильно, "
                "обратитесь в техническую поддержку по телефону +7(812)448-53-23.\n"
                f"Попыток осталось: {check}. Пожалуйста, введите номер ещё раз."
            )
        else:
            # Превышено количество попыток
            msg = await update.message.reply_text(
                "К нашему огромному сожалению, Вы пять раз ввели неверный номер договора. "
                "Для возобновления доступа обратитесь, пожалуйста, в нашу службу технической поддержки."
            )
            # Завершаем состояние
            context.user_data.pop('next_action', None)
            context.user_data.pop('attempts', None)

    elif context.user_data['next_action'] == 'ask_key':
        if check > 0:
            keyboard_message = [
                [InlineKeyboardButton("Повторно отправить код", callback_data='send')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard_message)
            msg = await update.message.reply_text(
                "Введен неверный код. Если Вы уверены, что вводите код правильно, "
                "обратитесь в техническую поддержку по телефону +7(812)448-53-23.\n"
                f"Попыток осталось: {check}. Пожалуйста, введите код ещё раз.",
                reply_markup=reply_markup
            )
            await reset_timeout(update, context)
        else:
            # Превышено количество попыток
            msg = await update.message.reply_text(
                "Вы истратили все попытки ввода кода. "
                "Для возобновления доступа обратитесь, пожалуйста, в нашу службу технической поддержки."
            )
            # Завершаем состояние
            context.user_data.pop('next_action', None)
            context.user_data.pop('attempts', None)

    messages_id.append(msg.message_id)

# Функция для кнопки "Запустить"
async def begin_action(update, context):
    keyboard_connect_or_log = [
        [InlineKeyboardButton("ПОДКЛЮЧИТЬСЯ", callback_data='connect')],
        [InlineKeyboardButton("ВОЙТИ", callback_data='login')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_connect_or_log)
    msg = await update.callback_query.message.reply_text(
        "Если Вы хотите подключиться к высокоскоростному Интернету у себя дома нажмите кнопку "
        "«ПОДКЛЮЧИТЬСЯ». Если Вы уже являетесь нашим абонентом, нажмите кнопку «ВОЙТИ».",
        reply_markup=reply_markup
    )

    context.user_data['buffer'] = None
    messages_id.append(msg.message_id)
    await reset_timeout(update, context)
    await back_action(update, context)

# Отработка существующего номера договора
async def valid_action(update, context, contract):
    data = await billing_request(update, context)

    keyboard_message = [
        [InlineKeyboardButton("Отправить СМС с кодом", callback_data='send')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_message)
    phone = data['data'][0]['sms_tel']
    context.user_data['phone'] = phone[1:]
    msg = await update.message.reply_text(
        f"После нажатия на кнопку «Отправить СМС с кодом», на номер {phone[:3]}*******{phone[-2:]}, "
        "указанный при заключении договора, будет отправлено СМС, в котором содержится код для входа в Личный кабинет.",
        reply_markup=reply_markup
    )
    messages_id.append(msg.message_id)
    del data

# Функция для кнопки "Отправить СМС с кодом"
async def message_action(update, context):
    #sms_response = await send_sms(update, context)
    #if "Ошибка" in sms_response:
    #   message = await update.callback_query.message.reply_text(
    #       f"Произошла ошибка при отправке SMS. \n{sms_response}"
    #   )
    #else:
    message = await update.callback_query.message.reply_text(
        f"На вышеуказанный номер отправлено сообщение с кодом для входа в личный кабинет.\nВведите код:"
    )
    messages_id.append(message.message_id)

    code = random.randint(100000, 999999)
    context.user_data['key'] = code
    phone = context.user_data.get('phone')
    print(code)

    context.user_data['next_action'] = 'ask_key'
    await reset_timeout(update, context)

# Функция для кнопки "Подключиться"
async def connect_action(update, context):
    await update.callback_query.message.reply_text("Введите Ваше ФИО:")
    context.user_data['next_action'] = 'ask_phone'
    await reset_timeout(update, context)

# Функция для кнопки "Продолжить"
async def continue_action(update, context):
    msg = await update.callback_query.message.reply_text("Номер абонентского договора:")
    context.user_data['next_action'] = 'ask_contr_number'
    await reset_timeout(update, context)
    messages_id.append(msg.message_id)

# Функция для кнопки "Войти"
async def login_action(update, context):
    keyboard_login = [
        [InlineKeyboardButton("Продолжить", callback_data='continue')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_login)
    msg = await update.callback_query.message.reply_text(
        "После нажатия на кнопку «Продолжить» введите, пожалуйста, номер Вашего абонентского договора. "
        "Этот номер совпадает с логином для входа в Ваш личный кабинет.",
        reply_markup=reply_markup
    )

    messages_id.append(msg.message_id)
    await reset_timeout(update, context)

# Функция для кнопки "Профиль"
async def data_action(update, context):
    data = await billing_request(update, context)
    await send_data(update, context, action_list[1])

    keyboard_data = [
        [InlineKeyboardButton("Изменить данные", callback_data='change'),
         InlineKeyboardButton("Назад", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_data)
    user = context.user_data.get('user_contract')
    '''
    phone = str(data['data'][0]['mob_tel'])
    email = str(data['data'][0]['email'])
    dog = email.find("@")
    dot = email.find(".")

    connection = mysql.connector.connect(
        host = config["sql"]["host"],  # IP-адрес виртуальной машины
        port = config["sql"]["port"],  # Порт базы данных
        user = config["sql"]["user"],  # Имя пользователя
        password = config["sql"]["password"],  # Пароль
        database = config["sql"]["database"]  # Имя базы данных
    )
    cursor = connection.cursor()

    query = f"SELECT packet, speed_rate, fixed_cost FROM packets WHERE gid = {data['data'][0]['gid']}"
    cursor.execute(query)
    info_packet = cursor.fetchall()
    name = info_packet[0][0]
    speed = round(info_packet[0][1] / 1024)
    cost = info_packet[0][2]'''

    url = config["telegram"]["url_gid"] + str(data['data'][0]['gid'])
    payload = {'': ''}
    files = []
    headers = {
        'Authorization': ''
    }

    response = requests.request("GET", url, headers=headers, data=payload, files=files)
    response.json()
    message = await update.callback_query.message.reply_text(
        f"Номер договора: {data['data'][0]['numdogovor']} \nСтатус: {"Активен" if data['data'][0]['state'] != 1 else "Неактивен"}"
        f"\nНомер телефона: {phone[:4]}* *** **{phone[-2:]} \nE-mail: {email[:3] + "*" * abs(len(email[3:dog])) + email[dog - 2:(dog + 1)] + 
                                                                      "*" * len(email[(dog+1):dot]) + email[dot:]}"
        f"\nТарифный план: {response['data'][0]['packet']}/s {float(response['data'][0]['fixed_cost']):.2f} руб/мес \nБаланс: {float(data['data'][0]['deposit']):.2f}",
        reply_markup=reply_markup
    )

    await reset_timeout(update, context)
    context.user_data['last_message_id'] = message.message_id
    context.user_data['chat_id'] = message.chat_id
    del data
    del info_packet

# Функция для кнопки "Изменить данные"
async def change_action(update, context):
    url = "https://zextel.bitrix24site.ru/personal_data_update/"
    link_text = "ССЫЛКА НА ФОРМУ"
    keyboard_change = [
        [InlineKeyboardButton("Назад", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_change)
    user = context.user_data.get('user_contract')
    message = await update.callback_query.message.reply_text(
        "С целью соблюдения требований законодательства Российской Федерации согласно статьи 18 "
        "Федерального закона «О персональных данных» предусмотрена обязанность Оператора по обеспечению записи, систематизации, "
        "накопления, хранения, уточнения (обновления, изменения), извлечения персональных данных граждан Российской Федерации с использованием баз данных, "
        "находящихся на территории Российской Федерации. ООО «Прогресс Технология» просит Вас предоставить актуальные паспортные данные, "
        "в обязательном порядке содержащие следующую информацию: ФИО, дата рождения, серия и номер паспорта, кем выдан, дата выдачи, код подразделения, адрес регистрации. "
        f"Актуальные паспортные данные необходимо предоставить на адрес электронной почты Оператора: info@zextel.ru или заполнить форму [{link_text}]({url}) "
        "не позднее 10 (десять) рабочих дней с момента получения уведомления. ООО «Прогресс Технология» "
        "гарантирует конфиденциальность полученных персональных данных. \nС уважением, Ваш Zextel",
        reply_markup=reply_markup,
        parse_mode='Markdown'  # Указываем режим разметки
    )
    context.user_data['buffer'] = context.user_data.get('last_message_id')
    context.user_data['last_message_id'] = message.message_id
    context.user_data['chat_id'] = message.chat_id
    await reset_timeout(update, context)

# Функция для кнопки "Оплатить" в меню
async def refill_action(update, context):
    keyboard_refill = [
        [InlineKeyboardButton("Оплатить", callback_data='pay'),
         InlineKeyboardButton("Вернуться", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_refill)

    host = config["sql"]["host"]
    port = config["sql"]["port"]
    user = config["sql"]["user"]
    password = config["sql"]["password"]
    database = config["sql"]["database"]
    connection = mysql.connector.connect(
        host=host,  # IP-адрес виртуальной машины
        port=port,  # Порт базы данных
        user=user,  # Имя пользователя
        password=password,  # Пароль
        database=database  # Имя базы данных
    )

    data = await billing_request(update, context)
    await send_data(update, context, action_list[1])

    cursor = connection.cursor()

    query = f"SELECT fixed_cost FROM packets WHERE gid = {data['data'][0]['gid']}"
    cursor.execute(query)
    info = cursor.fetchall()

    bill = float(info[0][0]) - float(data['data'][0]['deposit'])

    cursor.close()
    connection.close()

    message = await update.callback_query.message.reply_text(
        f"Текущий баланс: {float(data['data'][0]['deposit']):.2f} руб. \n"
        f"Стоимость услуг по тарифу: {info[0][0]} руб. \n"
        f"Рекомендуемая сумма к оплате: {bill} руб.",
        reply_markup=reply_markup
    )

    context.user_data['last_message_id'] = message.message_id
    context.user_data['chat_id'] = message.chat_id
    await reset_timeout(update, context)
    del data
    del info

# Функции для кнопки "Оплатить" и непосредственно для оплаты
async def pay_action(update, context):
    keyboard = [
        [InlineKeyboardButton("Вернуться", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await update.callback_query.message.reply_text(
        "Введите сумму, которую хотите положить на счет:",
        reply_markup = reply_markup
    )

    context.user_data['next_action'] = 'ask_amount'
    context.user_data['last_message_id'] = message.message_id
    context.user_data['chat_id'] = message.chat_id
    await reset_timeout(update, context)
async def payment(update, context, amount):
    data_1 = await billing_request(update, context)
    await send_data(update, context, action_list[1])

    payload = {'login': data_1['data'][0]['user'],
               'password': data_1['data'][0]['password']}

    del data_1

    data = requests.request("POST", url_login, data=payload)

    data = data.json()
    token = str(data['data']['token']).split()
    token = token[1]
    del data

    payload = {'amount': amount}
    headers = {
        'Authorization': token
    }

    response = requests.request("POST", url_pay, headers=headers, data=payload)
    response = response.json()
    link = response['data']['action_url']
    del response
    message = await update.message.reply_text(link)

    del link
    context.user_data['last_message_id'] = message.message_id
    context.user_data['chat_id'] = message.chat_id
    await reset_timeout(update, context)

# Функции для кнопки "Подписки" и для управления подписками
async def subs_action(update, context):
    data_1 = await billing_request(update, context)
    await send_data(update, context, action_list[1])

    payload = {'login': data_1['data'][0]['user'],
               'password': data_1['data'][0]['password']}

    del data_1

    data = requests.request("POST", url_login, data=payload)

    data = data.json()
    token = str(data['data']['token']).split()
    token = token[1]
    del data

    headers = {
        'Authorization': token
    }

    response = requests.request("GET", url_subs, headers=headers)
    response = response.json()
    msg = ""
    for item in response['data']:
        id = item['id']
        name = item['name']
        cost = item['info']['service_price']
        description = item['info']['description']
        msg = msg + str(name).upper() + ", id = " + id + "\n Стоимость услуг: " + cost + "\n Описание: " + description + "\n"

    keyboard_subs = [
        [InlineKeyboardButton("Вернуться", callback_data='back')],
        [InlineKeyboardButton("Управление подписками", callback_data='manage')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_subs)

    message = await update.callback_query.message.reply_text(
                msg,
        reply_markup=reply_markup
    )
    context.user_data['last_message_id'] = message.message_id
    context.user_data['chat_id'] = message.chat_id
    await reset_timeout(update, context)
async def bridge_action(update, context):
    keyboard = [
        [InlineKeyboardButton("Вернуться", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await update.callback_query.message.reply_text(
        "Введите id подписки, которую хотите подключить(1) или отключить(0), с соответсвующим кодом действия, который указан в скобках.\n"
        "Сначала id, потом код действия без запятых через пробел:",
        reply_markup = reply_markup
    )

    context.user_data['next_action'] = 'ask_sub'
    context.user_data['last_message_id'] = message.message_id
    context.user_data['chat_id'] = message.chat_id
    await reset_timeout(update, context)
async def manage_action(update, context, id, action):
    data_1 = await billing_request(update, context)
    await send_data(update, context, action_list[1])

    payload = {'login': data_1['data'][0]['user'],
               'password': data_1['data'][0]['password']}

    del data_1

    data = requests.request("POST", url_login, data=payload)

    data = data.json()
    token = str(data['data']['token']).split()
    token = token[1]
    del data

    headers = {
        'Authorization': token
    }

    payload = {'activate': action,
               'id': id}

    response = requests.request("POST", url_subs, headers=headers, data=payload)
    response = response.json()
    if response['success'] and response['message'] == "ОК":
        message = await update.message.reply_text("Статус подписки успешно изменен!")
    else:
        message = await update.message.reply_text("Возникла непредвиденная ошибка, повторите попытку позже.")
        print(response)

    context.user_data['last_message_id'] = message.message_id
    context.user_data['chat_id'] = message.chat_id
    await reset_timeout(update, context)


# Функция для кнопки "Акции"
async def events_action(update, context):
    keyboard_events = [
        [InlineKeyboardButton("Вернуться", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_events)
    user = context.user_data.get('user_contract')
    message = await update.callback_query.message.reply_text(
        "Какие-то акции, которые надо подтянуть из административного бэкенда",
        reply_markup=reply_markup
    )
    context.user_data['last_message_id'] = message.message_id
    context.user_data['chat_id'] = message.chat_id
    await reset_timeout(update, context)

# Функция для кнопки "Техническая поддержка"
async def supp_action(update, context):
    await send_data(update, context, action_list[2])
    keyboard_supp = [
        [InlineKeyboardButton("Вернуться", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_supp)
    message = await update.callback_query.message.reply_text(
        "Пока что непонятно, как будет происходить обращение в техничесскую поддержку, но сообщение сохраняется для дальнейшего использования."
        " Фильтр на нецензурную брань не установлен",
        reply_markup=reply_markup
    )
    context.user_data['last_message_id'] = message.message_id
    context.user_data['chat_id'] = message.chat_id
    context.user_data['next_action'] = 'ask_appeal'
    await reset_timeout(update, context)

# Функция для кнопки "Назад"
async def back_action(update, context):
    last_message_id = context.user_data.get('last_message_id')
    chat_id = context.user_data.get('chat_id')
    await context.bot.delete_message(chat_id=chat_id, message_id=last_message_id)
    context.user_data['last_message_id'] = context.user_data.get('buffer')
    context.user_data['buffer'] = None
    context.user_data['next_action'] = None
    await reset_timeout(update, context)

# Первый вход
async def start(update, context):
    if update.message:  # Проверяем, что сообщение существует
        chat_id = str(update.message.chat_id)
        await encryption(chat_id)
        context.user_data['user_id'] = update.message.from_user.id
        await send_data(update, context, action_list[0])
        keyboard_start = [
            [InlineKeyboardButton("Запустить", callback_data='begin')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard_start)
        message = await update.message.reply_text(
            "Здравствуйте! Вас приветствует бот-помощник ZEXTEl.\nЧто умеет этот чат-бот: какая-то информация о боте",
            reply_markup=reply_markup
        )
        context.user_data['last_message_id'] = message.message_id
        context.user_data['chat_id'] = message.chat_id
        await reset_timeout(update, context)

# Блок-меню бота
async def menu(update, context):
    keyboard_menu = [
        [InlineKeyboardButton("Профиль", callback_data='data'),
         InlineKeyboardButton("Оплатить", callback_data='refill')],
        [InlineKeyboardButton("Подписки", callback_data='subs'),
         InlineKeyboardButton("Акции", callback_data='events')],
        [InlineKeyboardButton("Техническая поддержка", callback_data='supp')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_menu)
    msg = await update.message.reply_text(
        "Вы успешно вошли в личный кабинет, теперь Вам доступны следующие разделы:",
        reply_markup=reply_markup
    )
    messages_id.append(msg.message_id)

# Обработчик нажатий на кнопки
async def button(update, context):
    query = update.callback_query
    user_contract = context.user_data.get('user_contract')
    news_index = context.user_data.get('news_index', 0)
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
    elif query.data == 'subs':
        await subs_action(update, context)
    elif query.data == 'events':
        await events_action(update, context)
    elif query.data == 'supp':
        await supp_action(update, context)

    # Обработка нажатий кнопок в разделах меню
    elif query.data == 'back':
        await back_action(update, context)
    elif query.data == 'change':
        await change_action(update, context)
    elif query.data == 'pay':
        await pay_action(update, context)
    elif query.data == 'manage':
        await bridge_action(update, context)

    # Убираем кнопки, чтобы предотвратить повторное нажатие, для более комфортного тестирования работы бота, функция неактивна
    # await query.edit_message_reply_markup(reply_markup=None)

# Обработка пользовательских сообщений
async def handle_message(update, context):
    if 'next_action' in context.user_data:
        # Проверяем текущее состояние
        # Ввод номера абонентского договора
        if context.user_data['next_action'] == 'ask_contr_number':
            user_contract = update.message.text  # Получаем введенный номер договора
            messages_id.append(update.message.message_id)
            await reset_timeout(update, context)
            await contr_validation(update, context, user_contract)  # Проверяем полученный номер
            user_contract = await sanitize(user_contract)
            context.user_data['user_contract'] = user_contract
            data = await billing_request(update, context)
            if data['success'] and len(data['data']) > 0:
                await valid_action(update, context, user_contract)
                del data
                # Завершаем состояние
                context.user_data.pop('next_action', None)
            else:
                # Номер договора не найден
                context.user_data['user_contract'] = None
                attempts = context.user_data.get('attempts', 5)  # Получаем оставшиеся попытки
                attempts -= 1
                context.user_data['attempts'] = attempts  # Обновляем количество попыток
                del data
                await attempts_check(update, context, attempts)



        # Ввод номера данных для подключения нового пользователя
        elif context.user_data['next_action'] == 'ask_phone':
            # Обрабатываем введённый номер телефона
            user_name = update.message.text  # Получаем введенное ФИО
            await reset_timeout(update, context)
            messages_id.append(update.message.message_id)
            new_user_data[update.message.chat_id] = {'name': user_name}  # Сохраняем в глобальный словарь
            await update.message.reply_text("Теперь введите номер телефона:")
            context.user_data['next_action'] = 'finish_registration'  # Обновляем состояние
        elif context.user_data['next_action'] == 'finish_registration':
            user_phone = update.message.text  # Получаем введённый номер телефона
            await reset_timeout(update, context)
            messages_id.append(update.message.message_id)
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
            await reset_timeout(update, context)
            user_key = await key_validation(update, context, user_key)
            user_key = await sanitize(user_key)
            if int(user_key) != key_for_test:
                attempts = context.user_data.get('attempts', 3)  # Получаем оставшиеся попытки
                attempts -= 1
                context.user_data['attempts'] = attempts  # Обновляем количество попыток
                await attempts_check(update, context, attempts)
            else:
                messages_id.append(update.message.message_id)
                await send_data(update, context, action_list[3])
                await menu(update, context)

        # Запрос пользователя в ТП
        elif context.user_data['next_action'] == 'ask_appeal':
            user_appeal = update.message.text
            user_appeal = await sanitize(user_appeal)
            await reset_timeout(update, context)
            await send_message(update, context, user_appeal)

        # Ввод суммы для оплаты
        elif context.user_data['next_action'] == 'ask_amount':
            amount = update.message.text
            if amount.isnumeric() and int(amount) > 0:
                await payment(update, context, amount)
            else:
                await update.message.reply_text("Вы ввели некорректную сумму.")
            await reset_timeout(update, context)

        # Управление подписками
        elif context.user_data['next_action'] == 'ask_sub':
            sub = str(update.message.text)
            sub = sub.split()
            if (sub[0].isnumeric() and int(sub[0]) > 0) and (sub[1] == "0"  or sub[1] == "1"):
                await manage_action(update, context, sub[0], sub[1])
            else:
                await update.message.reply_text("Вы ввели некорректные данные.")
            await reset_timeout(update, context)


# Главная функция
def main():
    #async .run(app, host="0.0.0.0", port=8000)
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