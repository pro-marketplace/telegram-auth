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

import psycopg2
import requests


def handler(event: dict, context) -> dict:
    '''Telegram Bot Webhook — обработка команды /start web_auth для авторизации'''

    method = event.get('httpMethod', 'POST')

    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
            },
            'body': '',
        }

    body = json.loads(event.get('body', '{}'))

    message = body.get('message')
    if not message:
        return {'statusCode': 200, 'body': json.dumps({'ok': True})}

    text = message.get('text', '')
    user = message.get('from', {})
    chat_id = message.get('chat', {}).get('id')

    if not chat_id:
        return {'statusCode': 200, 'body': json.dumps({'ok': True})}

    if text.startswith('/start'):
        args = text.split(' ', 1)
        if len(args) > 1 and args[1] == 'web_auth':
            return handle_web_auth(chat_id, user)

        return send_message(chat_id, 'Привет! Используйте кнопку "Войти через Telegram" на сайте.')

    return {'statusCode': 200, 'body': json.dumps({'ok': True})}


def handle_web_auth(chat_id: int, user: dict) -> dict:
    '''Обработка команды /start web_auth — создание токена и отправка кнопки'''

    token = str(uuid.uuid4())
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    telegram_id = str(user.get('id', ''))
    username = user.get('username')
    first_name = user.get('first_name')
    last_name = user.get('last_name')

    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()

    cursor.execute('''
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
    ''')

    cursor.execute('''
        INSERT INTO telegram_auth_tokens
        (token_hash, telegram_id, telegram_username, telegram_first_name,
         telegram_last_name, telegram_photo_url, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    ''', (
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

    site_url = os.environ['SITE_URL']
    auth_url = f"{site_url}/auth/telegram/callback?token={token}"

    bot_token = os.environ['TELEGRAM_BOT_TOKEN']
    requests.post(
        f'https://api.telegram.org/bot{bot_token}/sendMessage',
        json={
            'chat_id': chat_id,
            'text': 'Авторизация готова!\n\nНажмите на кнопку ниже, чтобы войти на сайт 👇🏼\n\nСсылка действительна 5 минут',
            'reply_markup': {
                'inline_keyboard': [[
                    {'text': 'Войти на сайт', 'url': auth_url}
                ]]
            }
        },
        timeout=10
    )

    return {'statusCode': 200, 'body': json.dumps({'ok': True})}


def send_message(chat_id: int, text: str) -> dict:
    '''Отправка простого текстового сообщения'''

    bot_token = os.environ['TELEGRAM_BOT_TOKEN']
    requests.post(
        f'https://api.telegram.org/bot{bot_token}/sendMessage',
        json={'chat_id': chat_id, 'text': text},
        timeout=10
    )

    return {'statusCode': 200, 'body': json.dumps({'ok': True})}
