"""Минимальный Telegram-бот техподдержки на русском языке без хранения данных на диске."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

MAX_CACHE_SIZE = 5000


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

    if text == "/start":
        api.call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "Здравствуйте! Это официальная техподдержка RFM Analytics (rfmpro.ru).\n\n"
                    "Напишите ваш вопрос или прикрепите скриншот — оператор ответит ежедневно "
                    "с 09:00 до 21:00 МСК."
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


def handle_admin_message(
    api: TelegramAPI,
    msg: dict[str, Any],
    admin_chat_id: int,
    cache: OrderedDict[int, int],
) -> None:
    """Обрабатывает ответ оператора (через Reply на пересланное сообщение)."""
    text = (msg.get("text") or "").strip()
    if text in {"/start", "/myid"}:
        api.call(
            "sendMessage",
            {
                "chat_id": admin_chat_id,
                "text": (
                    f"Режим оператора активен (ID: {admin_chat_id}).\n"
                    "Чтобы ответить пользователю, нажмите «Ответить» (Reply) на его пересланное сообщение."
                ),
            },
        )
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


class _HealthHandler(BaseHTTPRequestHandler):
    """Отвечает 200 OK на health-check запросы Render."""

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format: str, *args: Any) -> None:
        return


def start_health_server_if_needed() -> None:
    """Поднимает HTTP-сервер на PORT, если сервис запущен на Render Web Service."""
    raw_port = os.environ.get("PORT", "").strip()
    if not raw_port.isdigit():
        return
    server = HTTPServer(("0.0.0.0", int(raw_port)), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Health-сервер запущен на порту {raw_port}")


def main() -> None:
    load_env(Path(__file__).resolve().parent / ".env")
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Не задана переменная окружения BOT_TOKEN")

    raw_admin_id = os.environ.get("ADMIN_CHAT_ID", "").strip()
    admin_chat_id = int(raw_admin_id) if raw_admin_id.lstrip("-").isdigit() else None

    start_health_server_if_needed()
    api = TelegramAPI(token)
    cache: OrderedDict[int, int] = OrderedDict()
    offset = 0

    print("Бот техподдержки RFM Pro запущен...")
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
