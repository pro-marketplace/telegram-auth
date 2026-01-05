"""
Telegram Bot Webhook Function

Обрабатывает webhook от Telegram для авторизации через /start web_auth.
Генерирует токен, сохраняет в БД и отправляет пользователю кнопку для входа.

Использует aiogram 3.x для обработки updates.
"""

import asyncio
import json
import os
import uuid
import hashlib
from datetime import datetime, timezone, timedelta

import psycopg2
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Update, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, CommandObject

router = Router()


@router.message(CommandStart(deep_link=True))
async def handle_start_with_args(message: Message, command: CommandObject) -> None:
    """Обработка /start с аргументами (deep link)."""
    if command.args == "web_auth":
        await handle_web_auth(message)
    else:
        await message.answer("Привет! Используйте кнопку \"Войти через Telegram\" на сайте.")


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    """Обработка /start без аргументов."""
    await message.answer("Привет! Используйте кнопку \"Войти через Telegram\" на сайте.")


async def handle_web_auth(message: Message) -> None:
    """Создание токена авторизации и отправка кнопки."""
    user = message.from_user

    token = str(uuid.uuid4())
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    telegram_id = str(user.id)
    username = user.username
    first_name = user.first_name
    last_name = user.last_name

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telegram_auth_tokens (
            id SERIAL PRIMARY KEY,
            token_hash VARCHAR(64) UNIQUE NOT NULL,
            telegram_id VARCHAR(50),
            telegram_username VARCHAR(255),
            telegram_first_name VARCHAR(255),
            telegram_last_name VARCHAR(255),
            telegram_photo_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT FALSE
        )
    """)

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

    site_url = os.environ["SITE_URL"]
    auth_url = f"{site_url}/auth/telegram/callback?token={token}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Войти на сайт", url=auth_url)]
    ])

    await message.answer(
        "Авторизация готова!\n\n"
        "Нажмите на кнопку ниже, чтобы войти на сайт 👇🏼\n\n"
        "Ссылка действительна 5 минут",
        reply_markup=keyboard
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

    body = event.get("body", "{}")
    update_data = json.loads(body)

    # Создаём bot и dispatcher
    bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
    dp = Dispatcher()
    dp.include_router(router)

    # Обрабатываем update
    async def process():
        update = Update.model_validate(update_data, context={"bot": bot})
        await dp.feed_update(bot, update)
        await bot.session.close()

    asyncio.run(process())

    return {"statusCode": 200, "body": json.dumps({"ok": True})}
