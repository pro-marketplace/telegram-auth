"""
Telegram Bot Webhook Function

Обрабатывает webhook от Telegram для авторизации через /start web_auth.
Генерирует токен, сохраняет в БД и отправляет пользователю кнопку для входа.
"""

import json
import os
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional

import psycopg2
import requests


def send_message(chat_id: int, text: str, reply_markup: Optional[dict] = None) -> None:
    """Отправка сообщения через Telegram API."""
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json=payload,
        timeout=10
    )


def save_auth_token(
    telegram_id: str,
    username: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str]
) -> str:
    """Сохраняет токен авторизации в БД и возвращает его."""
    token = str(uuid.uuid4())
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO telegram_auth_tokens
        (token_hash, telegram_id, telegram_username, telegram_first_name,
         telegram_last_name, telegram_photo_url, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        token_hash,
        telegram_id,
        username,
        first_name,
        last_name,
        None,
        datetime.now(timezone.utc) + timedelta(minutes=5)
    ))

    conn.commit()
    conn.close()

    return token


def handle_web_auth(chat_id: int, user: dict) -> None:
    """Обработка команды /start web_auth."""
    telegram_id = str(user.get("id", ""))
    username = user.get("username")
    first_name = user.get("first_name")
    last_name = user.get("last_name")

    token = save_auth_token(telegram_id, username, first_name, last_name)

    site_url = os.environ["SITE_URL"]
    auth_url = f"{site_url}/auth/telegram/callback?token={token}"

    send_message(
        chat_id,
        "Авторизация готова!\n\nНажмите на кнопку ниже, чтобы войти на сайт 👇🏼\n\nСсылка действительна 5 минут",
        reply_markup={
            "inline_keyboard": [[{"text": "Войти на сайт", "url": auth_url}]]
        }
    )


def handler(event: dict, context) -> dict:
    """Точка входа для serverless функции."""
    method = event.get("httpMethod", "POST")

    if method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, X-Telegram-Bot-Api-Secret-Token",
            },
            "body": "",
        }

    # Верификация webhook secret
    headers = event.get("headers", {})
    headers_lower = {k.lower(): v for k, v in headers.items()}
    webhook_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET")

    if webhook_secret:
        request_secret = headers_lower.get("x-telegram-bot-api-secret-token", "")
        if request_secret != webhook_secret:
            return {"statusCode": 401, "body": json.dumps({"error": "Unauthorized"})}

    # Парсим update
    body = json.loads(event.get("body", "{}"))
    message = body.get("message")

    if not message:
        return {"statusCode": 200, "body": json.dumps({"ok": True})}

    text = message.get("text", "")
    user = message.get("from", {})
    chat_id = message.get("chat", {}).get("id")

    if not chat_id:
        return {"statusCode": 200, "body": json.dumps({"ok": True})}

    # Обработка команды /start
    if text.startswith("/start"):
        parts = text.split(" ", 1)
        if len(parts) > 1 and parts[1] == "web_auth":
            handle_web_auth(chat_id, user)
        else:
            send_message(chat_id, "Привет! Используйте кнопку \"Войти через Telegram\" на сайте.")

    return {"statusCode": 200, "body": json.dumps({"ok": True})}
