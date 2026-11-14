# -*- coding: utf-8 -*-
"""
Telegram-бот для сервиса RfmAnalytics PRO (@rfmanalytics_pro_bot)
Включает описание сервиса, тарифы, публичную оферту, условия возврата и реквизиты.
"""

import sys
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

TOKEN = "9130209345:AAGP_FnklylgXOiUeXyte8bx3TIQkUU4ofY"
OFERTA_URL = "https://telegra.ph/Publichnaya-oferta-RfmAnalytics-PRO-11-14-2"
SUPPORT_TG = "@MaXXXim321"
SUPPORT_EMAIL = "maximkrabik96@gmail.com"
SUPPORT_PHONE = "+7 999 722-39-59"
SELF_EMPLOYED = "Землянухин Максим Сергеевич"
INN = "363103868376"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# Текст команды /info и кнопки "О сервисе / Оферта"
INFO_TEXT = f"""
📊 <b>Сервис RfmAnalytics PRO</b>

<b>RfmAnalytics PRO</b> — профессиональный аналитический модуль и система поддержки принятия решений (DSS) для ритейла и торговли. Разблокирует полный аналитический инструментарий без сторонних серверов по лицензионному ключу прямо на вашем устройстве.

✨ <b>Какие функции открывает PRO-подписка:</b>
• <b>Автоматический фоновый сбор чеков</b> из МойСклад API, 1С и облачных папок (WorkManager)
• <b>Расчет упущенной выручки</b> и прогнозирование рисков оттока ценных клиентов
• <b>План автозаказа поставщикам</b> по группам X/Y/Z и выявление мертвого стока
• <b>Брендирование отчетов:</b> логотип, печать и реквизиты в PDF и 4-страничных Excel (.xlsx)
• <b>Синхронизация дообученной базы знаний</b> ИИ-классификатора (.rfmrules) между сотрудниками
• <b>Резервное копирование и восстановление</b> локальной базы Room (.rfmbackup) с ротацией 5 копий
• <b>CRM-экспорт клиентов зоны риска</b> для маркетинга и промо-рассылок
• <b>Снятие ограничений на импорт чеков</b> (более 3 000 чеков в месяц)

💎 <b>Тарифные планы и точная стоимость:</b>
• <b>1 месяц</b> — <b>299 ₽</b> (299 ₽/мес) • <i>Базовый доступ на 30 дней</i>
• <b>3 месяца</b> — <b>790 ₽</b> (~263 ₽/мес) • <i>Выгода 12%</i>
• <b>6 месяцев</b> — <b>1 390 ₽</b> (~231 ₽/мес) • <i>Хит • Выгода 22% (экономия >400 ₽)</i>

⚡ <b>Выдача лицензии и условия возврата:</b>
• Лицензионный ключ выдаётся <b>мгновенно</b> после успешного подтверждения оплаты.
• <b>Возврат средств:</b> возможен в полном объёме <b>до момента активации лицензионного ключа</b> в приложении RfmAnalytics. После ввода и активации ключа в приложении обязательства считаются выполненными, услуга оказана в полном объёме.

📜 <b>Публичная оферта:</b>
Полный официальный текст договора-оферты доступен по ссылке:
<a href="{OFERTA_URL}">Ознакомиться с публичной офертой</a>

🏛 <b>Реквизиты Продавца:</b>
Самозанятый: <b>{SELF_EMPLOYED}</b>
ИНН: <code>{INN}</code>

📞 <b>Контакты для связи и поддержки:</b>
• Email: <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>
• Telegram: {SUPPORT_TG}
• Телефон: {SUPPORT_PHONE}
"""

TARIFFS_TEXT = f"""
💎 <b>Тарифные планы RfmAnalytics PRO:</b>

1️⃣ <b>Тариф «1 месяц»</b>
• Стоимость: <b>299 ₽</b>
• Полный доступ ко всем PRO-функциям на 30 дней.

2️⃣ <b>Тариф «3 месяца»</b> (Выгода 12%)
• Стоимость: <b>790 ₽</b> (всего ~263 ₽/мес)
• Доступ на 90 дней, скидка 12% по сравнению с помесячной оплатой.

3️⃣ <b>Тариф «6 месяцев»</b> (Хит • Выгода 22%)
• Стоимость: <b>1 390 ₽</b> (всего ~231 ₽/мес)
• Доступ на 180 дней, экономия более 400 ₽.

⚡ <i>Ключ активации выдаётся мгновенно после подтверждения оплаты.</i>
<i>Возврат средств возможен до момента активации ключа в приложении.</i>

Для оформления заказа или покупки ключа выберите тариф ниже или напишите нам в поддержку: {SUPPORT_TG}
"""

OFERTA_TEXT = f"""
📜 <b>Публичная оферта и правила возврата</b>

Настоящий документ регулирует порядок приобретения цифровых лицензий RfmAnalytics PRO.

📌 <b>Ключевые условия:</b>
1. <b>Мгновенная доставка:</b> Лицензионный ключ генерируется и выдается покупателю сразу после подтверждения транзакции в платежном шлюзе.
2. <b>Правила возврата:</b> Возврат денежных средств возможен по запросу Покупателя в полном объеме <b>до момента активации лицензионного ключа</b> в приложении RfmAnalytics. После активации ключа в приложении цифровой товар считается использованным.
3. <b>Продавец:</b> Самозанятый {SELF_EMPLOYED}, ИНН {INN}.

🔗 Полная редакция договора-оферты:
<a href="{OFERTA_URL}">Открыть публичную оферту на Telegraph</a>
"""

SUPPORT_TEXT = f"""
👨‍💻 <b>Служба поддержки и контакты:</b>

По всем вопросам работы сервиса, активации лицензии, оптовых заказов или возврата средств:

• <b>Telegram:</b> {SUPPORT_TG}
• <b>Email:</b> <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>
• <b>Телефон:</b> {SUPPORT_PHONE}
• <b>Самозанятый:</b> {SELF_EMPLOYED} (ИНН <code>{INN}</code>)

Время ответа поддержки: обычно в течение 10–30 минут с 09:00 до 21:00 МСК.
"""

def get_main_reply_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_info = types.KeyboardButton("ℹ️ О сервисе / Оферта")
    btn_tariffs = types.KeyboardButton("💎 Тарифы")
    btn_oferta = types.KeyboardButton("📜 Публичная оферта")
    btn_support = types.KeyboardButton("👨‍💻 Поддержка")
    markup.add(btn_info, btn_tariffs)
    markup.add(btn_oferta, btn_support)
    return markup

# Хранилище сессий пользователей (Device ID и выбранный тариф)
user_sessions = {}

def get_tariffs_inline_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_1m = types.InlineKeyboardButton("💳 Оформить 1 месяц — 299 ₽", callback_data="buy_1m")
    btn_3m = types.InlineKeyboardButton("💳 Оформить 3 месяца — 790 ₽ (Выгода 12%)", callback_data="buy_3m")
    btn_6m = types.InlineKeyboardButton("💳 Оформить 6 месяцев — 1 390 ₽ (Хит -22%)", callback_data="buy_6m")
    
    markup.add(btn_1m)
    markup.add(btn_3m)
    markup.add(btn_6m)
    
    row_links = [
        types.InlineKeyboardButton("📜 Оферта", url=OFERTA_URL),
        types.InlineKeyboardButton("💬 Поддержка", url="https://t.me/MaXXXim321")
    ]
    markup.row(*row_links)
    return markup

def get_info_inline_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_tariffs_action = types.InlineKeyboardButton("💎 Выбрать тариф и оплатить", callback_data="show_tariffs")
    row_links = [
        types.InlineKeyboardButton("📜 Открыть оферту", url=OFERTA_URL),
        types.InlineKeyboardButton("💬 Поддержка", url="https://t.me/MaXXXim321")
    ]
    markup.add(btn_tariffs_action)
    markup.row(*row_links)
    return markup

@bot.message_handler(commands=["start"])
def handle_start(message):
    args = message.text.split(maxsplit=1)
    deep_link = args[1] if len(args) > 1 else None

    welcome_msg = (
        f"Здравствуйте, <b>{message.from_user.first_name or 'пользователь'}</b>!\n\n"
        "Добро пожаловать в официальный бот <b>RfmAnalytics PRO</b>.\n"
        "Здесь вы можете узнать подробную информацию о сервисе, тарифах, ознакомиться с публичной офертой и получить лицензионный ключ.\n\n"
        "Выберите интересующий раздел в меню ниже 👇"
    )

    if deep_link:
        plan_names = {
            "pro_1m": ("1 месяц (299 ₽)", 299),
            "pro_3m": ("3 месяца (790 ₽)", 790),
            "pro_6m": ("6 месяцев (1 390 ₽)", 1390),
            "pro_12m": ("12 месяцев", 2490)
        }
        parts = deep_link.split("_", 2)
        if len(parts) >= 3 and f"{parts[0]}_{parts[1]}" in plan_names:
            plan_key = f"{parts[0]}_{parts[1]}"
            plan_title, price = plan_names.get(plan_key)
            device_id = parts[2]
            user_sessions[message.from_user.id] = {"device_id": device_id, "tariff": {"name": plan_title, "price": price}}
            welcome_msg += (
                f"\n\n🎯 <b>Выбранный тариф:</b> {plan_title}\n"
                f"📱 <b>Device ID устройства:</b> <code>{device_id}</code>\n\n"
                f"Нажмите кнопку ниже, чтобы перейти к оформлению и получить лицензионный ключ:"
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(f"💳 Оплатить {price} ₽", url=f"https://t.me/MaXXXim321?text=Здравствуйте!%20Хочу%20оплатить%20RfmAnalytics%20PRO%20({plan_title})%20для%20устройства%20{device_id}"))
            markup.add(types.InlineKeyboardButton("💎 Выбрать другой тариф", callback_data="show_tariffs"))
            bot.send_message(message.chat.id, welcome_msg, reply_markup=markup)
            return
        else:
            welcome_msg += f"\n\n<i>Получен параметр активации: <code>{deep_link}</code></i>"

    bot.send_message(
        message.chat.id,
        welcome_msg,
        reply_markup=get_main_reply_keyboard()
    )

@bot.message_handler(commands=["info"])
def handle_info(message):
    bot.send_message(
        message.chat.id,
        INFO_TEXT,
        reply_markup=get_info_inline_keyboard(),
        disable_web_page_preview=False
    )

@bot.message_handler(commands=["tariffs"])
def handle_tariffs(message):
    bot.send_message(
        message.chat.id,
        TARIFFS_TEXT,
        reply_markup=get_tariffs_inline_keyboard()
    )

@bot.callback_query_handler(func=lambda call: call.data == "show_tariffs")
def callback_show_tariffs(call):
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        TARIFFS_TEXT,
        reply_markup=get_tariffs_inline_keyboard()
    )

@bot.callback_query_handler(func=lambda call: call.data in ["buy_1m", "buy_3m", "buy_6m"])
def callback_buy_tariff(call):
    bot.answer_callback_query(call.id)
    tariffs_map = {
        "buy_1m": {"name": "1 месяц (30 дней)", "price": 299, "days": 30},
        "buy_3m": {"name": "3 месяца (90 дней)", "price": 790, "days": 90},
        "buy_6m": {"name": "6 месяцев (180 дней)", "price": 1390, "days": 180},
    }
    selected = tariffs_map.get(call.data)
    user_id = call.from_user.id
    
    session = user_sessions.get(user_id, {})
    session["tariff"] = selected
    user_sessions[user_id] = session

    device_id = session.get("device_id")
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # Кнопка связи с продавцом для мгновенной оплаты и выдачи
    btn_pay = types.InlineKeyboardButton(
        f"💳 Оплатить {selected['price']} ₽ (Робокасса / СБП)",
        url=f"https://t.me/MaXXXim321?text=Здравствуйте!%20Хочу%20оплатить%20RfmAnalytics%20PRO%20на%20{selected['name']}%20за%20{selected['price']}р"
    )
    btn_change = types.InlineKeyboardButton("🔄 Выбрать другой тариф", callback_data="show_tariffs")
    markup.add(btn_pay, btn_change)

    device_info = f"<code>{device_id}</code>" if device_id else "<i>(будет привязан автоматически при переходе из приложения)</i>"

    text = f"""
🛒 <b>Оформление подписки RfmAnalytics PRO</b>

• <b>Выбранный тариф:</b> {selected['name']}
• <b>Сумма к оплате:</b> <b>{selected['price']} ₽</b>
• <b>ID устройства (Device ID):</b> {device_info}

⚡ <b>Как происходит выдача:</b>
1. После подтверждения оплаты лицензионный ключ высылается <b>мгновенно</b> в этот диалог.
2. Возврат возможен до момента активации ключа в приложении.

Нажмите кнопку ниже для подтверждения и оплаты через Робокассу (СБП, банковские карты РФ) 👇
"""
    bot.send_message(call.message.chat.id, text, reply_markup=markup)

@bot.message_handler(commands=["oferta"])
def handle_oferta(message):
    bot.send_message(
        message.chat.id,
        OFERTA_TEXT,
        reply_markup=get_info_inline_keyboard(),
        disable_web_page_preview=False
    )

@bot.message_handler(commands=["support"])
def handle_support(message):
    bot.send_message(
        message.chat.id,
        SUPPORT_TEXT,
        reply_markup=get_info_inline_keyboard()
    )

@bot.message_handler(func=lambda msg: True)
def handle_text_buttons(message):
    text = (message.text or "").strip()

    if text in ["ℹ️ О сервисе / Оферта", "О сервисе", "О сервисе / Оферта", "Инфо", "Информация"]:
        handle_info(message)
    elif text in ["💎 Тарифы", "Тарифы", "Цены"]:
        handle_tariffs(message)
    elif text in ["📜 Публичная оферта", "Оферта", "Публичная оферта"]:
        handle_oferta(message)
    elif text in ["👨‍💻 Поддержка", "Поддержка", "Контакты"]:
        handle_support(message)
    else:
        bot.send_message(
            message.chat.id,
            "Используйте кнопки меню ниже или команду /info, чтобы узнать о сервисе и тарифах:",
            reply_markup=get_main_reply_keyboard()
        )

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK: RfmAnalytics PRO bot is running 24/7\n")

    def log_message(self, format, *args):
        pass

def run_healthcheck_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"Healthcheck HTTP server running on port {port}")
    server.serve_forever()

if __name__ == "__main__":
    # Запуск легковесного веб-сервера для Render / облачных платформ
    t = threading.Thread(target=run_healthcheck_server, daemon=True)
    t.start()

    print("Бот @rfmanalytics_pro_bot успешно запущен...")
    try:
        bot.infinity_polling(timeout=15, long_polling_timeout=10)
    except Exception as e:
        print(f"Ошибка polling: {e}")
