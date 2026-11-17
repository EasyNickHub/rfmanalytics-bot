"""Telegram-бот техподдержки RFM Pro (@rfmpro_support_bot) и бэкенд оплаты ЮKassa без БД."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import OrderedDict
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

MAX_CACHE_SIZE = 5000
DEVICE_ID_RE = re.compile(r"^RFM-[A-Z0-9]{4}-[A-Z0-9]{4}$")
ORDER_TOKEN_RE = re.compile(r"^[a-f0-9]{32}$")
SITE_RETURN_URL = "https://rfmpro.ru/"
SUPPORT_BOT_URL = "https://t.me/rfmpro_support_bot"
YOOKASSA_API_URL = "https://api.yookassa.ru/v3/payments"

PLANS: dict[str, dict[str, Any]] = {
    "pro_1m": {"title": "1 месяц (30 дней)", "days": 30, "amount": "299.00"},
    "pro_3m": {"title": "3 месяца (90 дней)", "days": 90, "amount": "790.00"},
    "pro_6m": {"title": "6 месяцев (180 дней)", "days": 180, "amount": "1390.00"},
}


def load_env(env_path: Path) -> None:
    """Загружает переменные из .env, если они ещё не заданы в окружении."""
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def generate_license_key(device_id: str, days: int, base_ts: int | None = None) -> tuple[str, int]:
    """Генерирует лицензионный ключ формата RFMPRO.<DEVICE_ID>.<EXPIRY_SEC>.<SIG>."""
    secret = os.environ.get("LICENSE_HMAC_SECRET", "RFM_SECRET_KEY_2026_MASTER_SIGNATURE").strip()
    clean_id = device_id.strip().upper()
    start_ts = base_ts if base_ts is not None else int(time.time())
    expiry_sec = start_ts + days * 86400
    payload = f"RFMPRO.{clean_id}.{expiry_sec}"
    sig = (
        hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        )
        .hexdigest()[:16]
        .upper()
    )
    return f"{payload}.{sig}", expiry_sec


def parse_iso_timestamp(iso_value: str | None) -> int:
    """Преобразует ISO-время ЮKassa в Unix timestamp (секунды)."""
    if not iso_value:
        return int(time.time())
    try:
        normalized = iso_value.strip().replace("Z", "+00:00")
        return int(datetime.fromisoformat(normalized).timestamp())
    except ValueError:
        return int(time.time())


class TelegramAPI:
    """Простой клиент Telegram Bot API на стандартной библиотеке Python."""

    def __init__(self, token: str) -> None:
        self.base_url = f"https://api.telegram.org/bot{token}"

    def call(self, method: str, payload: dict[str, Any] | None = None, timeout: int = 35) -> dict[str, Any]:
        data = json.dumps(payload or {}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/{method}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))


class YooKassaError(RuntimeError):
    """Ошибка взаимодействия с API ЮKassa."""


class YooKassaClient:
    """Клиент ЮKassa API v3 на стандартной библиотеке Python."""

    def __init__(self, shop_id: str, secret_key: str) -> None:
        self.shop_id = shop_id.strip()
        self.secret_key = secret_key.strip()

    def is_configured(self) -> bool:
        return bool(self.shop_id and self.secret_key)

    def _auth_header(self) -> str:
        raw = f"{self.shop_id}:{self.secret_key}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")

    def _request(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
        idempotence_key: str | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured():
            raise YooKassaError("Платёжный шлюз ещё не настроен (отсутствует YOOKASSA_SECRET_KEY).")

        headers = {
            "Authorization": self._auth_header(),
            "Accept": "application/json",
        }
        data: bytes | None = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if idempotence_key:
            headers["Idempotence-Key"] = idempotence_key

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise YooKassaError(f"Ошибка ЮKassa HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise YooKassaError(f"Сетевая ошибка ЮKassa: {exc}") from exc

    def create_payment(self, plan_id: str, device_id: str) -> tuple[str, dict[str, Any]]:
        plan = PLANS[plan_id]
        order_token = uuid.uuid4().hex
        return_url = f"{SITE_RETURN_URL}?order={order_token}"
        payload = {
            "amount": {"value": plan["amount"], "currency": "RUB"},
            "capture": True,
            "confirmation": {"type": "redirect", "return_url": return_url},
            "description": f"Лицензия RfmAnalytics PRO ({plan['title']}) для {device_id}",
            "metadata": {
                "order_token": order_token,
                "device_id": device_id,
                "plan_id": plan_id,
                "days": str(plan["days"]),
            },
        }
        payment = self._request("POST", YOOKASSA_API_URL, payload=payload, idempotence_key=str(uuid.uuid4()))
        return order_token, payment

    def get_payment(self, payment_id: str) -> dict[str, Any]:
        safe_id = urllib.parse.quote(payment_id, safe="")
        return self._request("GET", f"{YOOKASSA_API_URL}/{safe_id}")

    def find_payment_by_order_token(self, order_token: str) -> dict[str, Any] | None:
        resp = self._request("GET", f"{YOOKASSA_API_URL}?limit=50")
        for item in resp.get("items", []):
            meta = item.get("metadata") or {}
            if meta.get("order_token") == order_token:
                return item
        return None


class OrderCache:
    """Потокобезопасный in-memory кэш заказов и отправленных уведомлений."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._order_to_payment: OrderedDict[str, str] = OrderedDict()
        self._notified_payments: OrderedDict[str, bool] = OrderedDict()

    def remember_order(self, order_token: str, payment_id: str) -> None:
        with self._lock:
            self._order_to_payment[order_token] = payment_id
            self._order_to_payment.move_to_end(order_token)
            while len(self._order_to_payment) > MAX_CACHE_SIZE:
                self._order_to_payment.popitem(last=False)

    def get_payment_id(self, order_token: str) -> str | None:
        with self._lock:
            return self._order_to_payment.get(order_token)

    def mark_notified_once(self, payment_id: str) -> bool:
        """Возвращает True только при первом уведомлении по данному payment_id."""
        with self._lock:
            if payment_id in self._notified_payments:
                return False
            self._notified_payments[payment_id] = True
            self._notified_payments.move_to_end(payment_id)
            while len(self._notified_payments) > MAX_CACHE_SIZE:
                self._notified_payments.popitem(last=False)
            return True


def remember_mapping(cache: OrderedDict[int, int], forwarded_msg_id: int, user_chat_id: int) -> None:
    """Запоминает связь ID пересланного сообщения -> chat_id пользователя в памяти."""
    cache[forwarded_msg_id] = user_chat_id
    cache.move_to_end(forwarded_msg_id)
    while len(cache) > MAX_CACHE_SIZE:
        cache.popitem(last=False)


def resolve_target_chat_id(reply: dict[str, Any], cache: OrderedDict[int, int]) -> int | None:
    """Определяет chat_id пользователя по reply_to_message."""
    reply_msg_id = reply.get("message_id")
    if isinstance(reply_msg_id, int) and reply_msg_id in cache:
        return cache[reply_msg_id]

    forward_origin = reply.get("forward_origin")
    if isinstance(forward_origin, dict):
        sender_user = forward_origin.get("sender_user")
        if isinstance(sender_user, dict) and isinstance(sender_user.get("id"), int):
            return sender_user["id"]

    forward_from = reply.get("forward_from")
    if isinstance(forward_from, dict) and isinstance(forward_from.get("id"), int):
        return forward_from["id"]

    return None


def handle_user_message(
    api: TelegramAPI,
    msg: dict[str, Any],
    admin_chat_id: int | None,
    cache: OrderedDict[int, int],
) -> None:
    """Обрабатывает обращение пользователя и пересылает его оператору."""
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()

    if text == "/start" or text.startswith("/start "):
        api.call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "Здравствуйте! Это официальная техподдержка RFM Analytics (rfmpro.ru).\n\n"
                    "Напишите ваш вопрос или прикрепите скриншот — оператор ответит ежедневно "
                    "с 09:00 до 21:00 МСК.\n\n"
                    "Оформить PRO-лицензию с мгновенной выдачей ключа можно на сайте: https://rfmpro.ru/"
                ),
            },
        )
        return

    if text == "/myid":
        api.call(
            "sendMessage",
            {"chat_id": chat_id, "text": f"Ваш Telegram ID: {chat_id}"},
        )
        return

    if not admin_chat_id:
        api.call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": "Техподдержка сейчас настраивается. Пожалуйста, напишите позже или на почту maximkrabik96@gmail.com.",
            },
        )
        return

    forwarded = api.call(
        "forwardMessage",
        {
            "chat_id": admin_chat_id,
            "from_chat_id": chat_id,
            "message_id": msg["message_id"],
        },
    )
    fwd_id = forwarded.get("result", {}).get("message_id")
    if isinstance(fwd_id, int):
        remember_mapping(cache, fwd_id, chat_id)

    api.call(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": "Сообщение передано в техподдержку. Оператор ответит в ближайшее время.",
        },
    )


def handle_admin_genkey(api: TelegramAPI, admin_chat_id: int, text: str) -> None:
    """Генерирует лицензионные ключи для оператора по команде /genkey."""
    parts = text.split()
    if len(parts) < 2:
        api.call(
            "sendMessage",
            {
                "chat_id": admin_chat_id,
                "parse_mode": "HTML",
                "text": (
                    "🔑 <b>Генератор ключей RFM Analytics PRO</b>\n\n"
                    "Использование:\n"
                    "• <code>/genkey RFM-3C9E-8977 1</code> — ключ на 1 месяц\n"
                    "• <code>/genkey RFM-3C9E-8977 3</code> — ключ на 3 месяца\n"
                    "• <code>/genkey RFM-3C9E-8977 6</code> — ключ на 6 месяцев\n"
                    "• <code>/genkey RFM-3C9E-8977</code> — ключи на все 3 тарифа"
                ),
            },
        )
        return

    device_id = parts[1].strip().upper()
    if not DEVICE_ID_RE.match(device_id):
        api.call(
            "sendMessage",
            {
                "chat_id": admin_chat_id,
                "parse_mode": "HTML",
                "text": "⚠️ Неверный формат Device ID. Пример правильного ID: <code>RFM-3C9E-8977</code>",
            },
        )
        return

    if len(parts) >= 3:
        m_arg = parts[2].strip().lower()
        months_map = {
            "1": (30, "1 месяц (30 дней)"),
            "1m": (30, "1 месяц (30 дней)"),
            "3": (90, "3 месяца (90 дней)"),
            "3m": (90, "3 месяца (90 дней)"),
            "6": (180, "6 месяцев (180 дней)"),
            "6m": (180, "6 месяцев (180 дней)"),
        }
        days, label = months_map.get(m_arg, (30, "1 месяц (30 дней)"))
        key, _ = generate_license_key(device_id, days)
        api.call(
            "sendMessage",
            {
                "chat_id": admin_chat_id,
                "parse_mode": "HTML",
                "text": (
                    f"✅ <b>Ключ сформирован</b>\n\n"
                    f"📱 <b>Устройство:</b> <code>{device_id}</code>\n"
                    f"⏳ <b>Тариф:</b> {label}\n"
                    f"🔑 <b>Ключ:</b>\n<code>{key}</code>"
                ),
            },
        )
        return

    key_1m, _ = generate_license_key(device_id, 30)
    key_3m, _ = generate_license_key(device_id, 90)
    key_6m, _ = generate_license_key(device_id, 180)
    api.call(
        "sendMessage",
        {
            "chat_id": admin_chat_id,
            "parse_mode": "HTML",
            "text": (
                f"✅ <b>Ключи для <code>{device_id}</code>:</b>\n\n"
                f"1️⃣ <b>1 месяц (299 ₽):</b>\n<code>{key_1m}</code>\n\n"
                f"2️⃣ <b>3 месяца (790 ₽):</b>\n<code>{key_3m}</code>\n\n"
                f"3️⃣ <b>6 месяцев (1 390 ₽):</b>\n<code>{key_6m}</code>"
            ),
        },
    )


def handle_admin_message(
    api: TelegramAPI,
    msg: dict[str, Any],
    admin_chat_id: int,
    cache: OrderedDict[int, int],
) -> None:
    """Обрабатывает команды и ответы оператора (через Reply на пересланное сообщение)."""
    text = (msg.get("text") or "").strip()
    if text in {"/start", "/myid"}:
        api.call(
            "sendMessage",
            {
                "chat_id": admin_chat_id,
                "text": (
                    f"Режим оператора активен (ID: {admin_chat_id}).\n"
                    "Чтобы ответить пользователю, нажмите «Ответить» (Reply) на его пересланное сообщение.\n"
                    "Для ручной генерации ключа: /genkey RFM-XXXX-YYYY [1|3|6]"
                ),
            },
        )
        return

    if text == "/genkey" or text.startswith("/genkey ") or text == "/key" or text.startswith("/key "):
        handle_admin_genkey(api, admin_chat_id, text)
        return

    reply = msg.get("reply_to_message")
    if not isinstance(reply, dict):
        api.call(
            "sendMessage",
            {
                "chat_id": admin_chat_id,
                "text": "Чтобы ответить пользователю, сделайте Reply (Ответить) на его пересланное сообщение.",
            },
        )
        return

    target_chat_id = resolve_target_chat_id(reply, cache)
    if not target_chat_id:
        api.call(
            "sendMessage",
            {
                "chat_id": admin_chat_id,
                "text": "Не удалось определить получателя (возможно, у пользователя скрыта пересылка и бот был перезапущен).",
            },
        )
        return

    api.call(
        "copyMessage",
        {
            "chat_id": target_chat_id,
            "from_chat_id": admin_chat_id,
            "message_id": msg["message_id"],
        },
    )
    api.call(
        "sendMessage",
        {
            "chat_id": admin_chat_id,
            "text": "Ответ отправлен пользователю.",
            "reply_to_message_id": msg["message_id"],
        },
    )


def notify_admin_payment(
    api: TelegramAPI,
    admin_chat_id: int | None,
    device_id: str,
    plan_title: str,
    amount: str,
    payment_id: str,
    license_key: str,
) -> None:
    """Отправляет оператору уведомление об успешной оплате и выданном ключе."""
    if not admin_chat_id:
        return
    try:
        api.call(
            "sendMessage",
            {
                "chat_id": admin_chat_id,
                "parse_mode": "HTML",
                "text": (
                    f"💰 <b>Новая оплата через ЮKassa!</b>\n\n"
                    f"📦 <b>Тариф:</b> {escape(plan_title)}\n"
                    f"💵 <b>Сумма:</b> {escape(amount)} ₽\n"
                    f"📱 <b>Device ID:</b> <code>{escape(device_id)}</code>\n"
                    f"🧾 <b>Платёж:</b> <code>{escape(payment_id)}</code>\n\n"
                    f"🔑 <b>Выданный ключ:</b>\n<code>{escape(license_key)}</code>"
                ),
            },
        )
    except Exception as exc:
        print(f"Не удалось отправить уведомление оператору: {exc}")


def make_http_handler(
    yookassa: YooKassaClient,
    order_cache: OrderCache,
    tg_api: TelegramAPI,
    admin_chat_id: int | None,
) -> type[BaseHTTPRequestHandler]:
    """Создаёт класс HTTP-обработчика для health-check, создания платежа и выдачи ключа."""

    class _AppHTTPHandler(BaseHTTPRequestHandler):
        def _send_cors_headers(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Cache-Control", "no-store")

        def _send_json(self, status: int, data: dict[str, Any]) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_error_html(self, status: int, title: str, message: str) -> None:
            html_body = (
                "<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                f"<title>{escape(title)} — RFM Analytics PRO</title>"
                "<style>body{font-family:system-ui,-apple-system,sans-serif;background:#0b101b;color:#f3f6fc;"
                "display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:20px}"
                ".card{max-width:460px;background:#111827;border:1px solid #263149;border-radius:16px;padding:24px}"
                "h1{margin:0 0 12px;font-size:20px}p{margin:0 0 18px;color:#b4bfd6;line-height:1.5}"
                "a{display:inline-block;padding:10px 16px;border-radius:10px;background:#5248f0;color:#fff;"
                "text-decoration:none;font-weight:600;margin-right:8px;margin-bottom:8px}"
                "a.sec{background:#1e293b}</style></head><body><div class='card'>"
                f"<h1>{escape(title)}</h1><p>{escape(message)}</p>"
                f"<a href='{SITE_RETURN_URL}'>Вернуться на rfmpro.ru</a>"
                f"<a class='sec' href='{SUPPORT_BOT_URL}'>Написать в поддержку</a>"
                "</div></body></html>"
            ).encode("utf-8")
            self.send_response(status)
            self._send_cors_headers()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_body)))
            self.end_headers()
            self.wfile.write(html_body)

        def _create_order(self, plan_id: str, raw_device: str) -> tuple[int, dict[str, Any]]:
            plan_clean = plan_id.strip()
            device_clean = raw_device.strip().upper()
            if plan_clean not in PLANS:
                return 400, {"ok": False, "error": "Выбран неизвестный тариф."}
            if not DEVICE_ID_RE.match(device_clean):
                return 400, {
                    "ok": False,
                    "error": "Неверный формат Device ID. Укажите код вида RFM-3C9E-8977.",
                }
            try:
                order_token, payment = yookassa.create_payment(plan_clean, device_clean)
            except YooKassaError as exc:
                print(f"Ошибка создания платежа ЮKassa: {exc}")
                return 502, {"ok": False, "error": str(exc)}

            payment_id = payment.get("id")
            conf_url = (payment.get("confirmation") or {}).get("confirmation_url")
            if not payment_id or not conf_url:
                return 502, {"ok": False, "error": "ЮKassa не вернула ссылку на оплату."}

            order_cache.remember_order(order_token, payment_id)
            return 200, {
                "ok": True,
                "order_token": order_token,
                "payment_id": payment_id,
                "confirmation_url": conf_url,
            }

        def _handle_order_status(self, order_token: str) -> None:
            clean_token = order_token.strip().lower()
            if not ORDER_TOKEN_RE.match(clean_token):
                self._send_json(400, {"ok": False, "error": "Некорректный идентификатор заказа."})
                return

            try:
                payment_id = order_cache.get_payment_id(clean_token)
                if payment_id:
                    payment = yookassa.get_payment(payment_id)
                else:
                    payment = yookassa.find_payment_by_order_token(clean_token)
                    if payment and payment.get("id"):
                        order_cache.remember_order(clean_token, payment["id"])
            except YooKassaError as exc:
                print(f"Ошибка проверки заказа {clean_token}: {exc}")
                self._send_json(502, {"ok": False, "error": "Не удалось проверить статус платежа в ЮKassa."})
                return

            if not payment:
                self._send_json(404, {"ok": False, "error": "Заказ не найден. Если вы оплатили, обратитесь в поддержку."})
                return

            meta = payment.get("metadata") or {}
            plan_id = meta.get("plan_id", "pro_1m")
            plan = PLANS.get(plan_id, PLANS["pro_1m"])
            device_id = str(meta.get("device_id") or "").strip().upper()
            days_raw = meta.get("days")
            days = int(days_raw) if str(days_raw).isdigit() else int(plan["days"])
            status = payment.get("status", "pending")
            paid = bool(payment.get("paid", False))
            amount = str((payment.get("amount") or {}).get("value") or plan["amount"])
            conf_url = (payment.get("confirmation") or {}).get("confirmation_url")

            if status == "succeeded" and paid and DEVICE_ID_RE.match(device_id):
                base_ts = parse_iso_timestamp(payment.get("captured_at") or payment.get("created_at"))
                license_key, expiry_sec = generate_license_key(device_id, days, base_ts=base_ts)
                payment_id_str = str(payment.get("id") or "")
                if payment_id_str and order_cache.mark_notified_once(payment_id_str):
                    notify_admin_payment(
                        tg_api,
                        admin_chat_id,
                        device_id=device_id,
                        plan_title=plan["title"],
                        amount=amount,
                        payment_id=payment_id_str,
                        license_key=license_key,
                    )
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "status": "succeeded",
                        "paid": True,
                        "device_id": device_id,
                        "plan_id": plan_id,
                        "plan_title": plan["title"],
                        "amount": amount,
                        "license_key": license_key,
                        "expiry_sec": expiry_sec,
                    },
                )
                return

            self._send_json(
                200,
                {
                    "ok": True,
                    "status": status,
                    "paid": paid,
                    "device_id": device_id,
                    "plan_title": plan["title"],
                    "amount": amount,
                    "confirmation_url": conf_url,
                },
            )

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self._send_cors_headers()
            self.end_headers()

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            query = urllib.parse.parse_qs(parsed.query)

            if path in {"/", "/health"}:
                self.send_response(200)
                self._send_cors_headers()
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"OK")
                return

            if path == "/pay":
                plan_id = (query.get("plan") or [""])[0]
                device_id = (query.get("device") or [""])[0]
                code, result = self._create_order(plan_id, device_id)
                if code != 200:
                    self._send_error_html(
                        code,
                        "Не удалось создать платёж",
                        result.get("error", "Попробуйте снова или напишите в поддержку."),
                    )
                    return
                self.send_response(302)
                self._send_cors_headers()
                self.send_header("Location", result["confirmation_url"])
                self.end_headers()
                return

            if path == "/api/order":
                order_token = (query.get("order") or [""])[0]
                self._handle_order_status(order_token)
                return

            self._send_json(404, {"ok": False, "error": "Маршрут не найден."})

        def do_POST(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            if path != "/api/create-payment":
                self._send_json(404, {"ok": False, "error": "Маршрут не найден."})
                return

            raw_len = self.headers.get("Content-Length", "0")
            content_len = int(raw_len) if raw_len.isdigit() else 0
            if content_len <= 0 or content_len > 16384:
                self._send_json(400, {"ok": False, "error": "Некорректное тело запроса."})
                return

            try:
                body = json.loads(self.rfile.read(content_len).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._send_json(400, {"ok": False, "error": "Ожидался валидный JSON."})
                return

            code, result = self._create_order(
                str(body.get("plan") or ""),
                str(body.get("device") or ""),
            )
            self._send_json(code, result)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return _AppHTTPHandler


def start_http_server_if_needed(
    yookassa: YooKassaClient,
    order_cache: OrderCache,
    tg_api: TelegramAPI,
    admin_chat_id: int | None,
) -> None:
    """Поднимает многопоточный HTTP-сервер на PORT для Render Web Service и оплаты."""
    raw_port = os.environ.get("PORT", "").strip()
    if not raw_port.isdigit():
        return
    handler_cls = make_http_handler(yookassa, order_cache, tg_api, admin_chat_id)
    server = ThreadingHTTPServer(("0.0.0.0", int(raw_port)), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"HTTP-сервер запущен на порту {raw_port}")


def main() -> None:
    load_env(Path(__file__).resolve().parent / ".env")
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Не задана переменная окружения BOT_TOKEN")

    raw_admin_id = os.environ.get("ADMIN_CHAT_ID", "").strip()
    admin_chat_id = int(raw_admin_id) if raw_admin_id.lstrip("-").isdigit() else None

    shop_id = os.environ.get("YOOKASSA_SHOP_ID", "1533215").strip()
    secret_key = os.environ.get("YOOKASSA_SECRET_KEY", "").strip()

    api = TelegramAPI(token)
    yookassa = YooKassaClient(shop_id=shop_id, secret_key=secret_key)
    order_cache = OrderCache()

    start_http_server_if_needed(yookassa, order_cache, api, admin_chat_id)
    cache: OrderedDict[int, int] = OrderedDict()
    offset = 0

    print("Бот техподдержки и платежный шлюз RFM Pro запущены...")
    while True:
        try:
            resp = api.call("getUpdates", {"offset": offset, "timeout": 30}, timeout=40)
            for update in resp.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message")
                if not isinstance(msg, dict):
                    continue
                chat_id = msg["chat"]["id"]
                if admin_chat_id and chat_id == admin_chat_id:
                    handle_admin_message(api, msg, admin_chat_id, cache)
                else:
                    handle_user_message(api, msg, admin_chat_id, cache)
        except urllib.error.URLError as exc:
            print(f"Сетевая ошибка: {exc}")
            time.sleep(3)
        except Exception as exc:
            print(f"Ошибка обработки: {exc}")
            time.sleep(3)


if __name__ == "__main__":
    main()
