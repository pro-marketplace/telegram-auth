# Telegram Auth Extension

SSO авторизация через Telegram бота. **1 функция** с роутингом по action.

> **Как это работает:**
>
> 1. Пользователь нажимает "Войти через Telegram" → открывается бот
> 2. Бот генерирует токен, сохраняет в БД и показывает кнопку со ссылкой
> 3. Пользователь нажимает кнопку → callback страница обменивает токен на JWT
> 4. Готово!

---

# [AUTH] Общее для виджетов авторизации

## Логика привязки аккаунтов

Функция связывает аккаунты по telegram_id:

1. **Поиск по telegram_id** → если найден, логиним
2. **Новый пользователь** → создаём запись

> **Примечание:** Telegram не предоставляет email пользователя.

## Требования к базе данных

Функция работает с полями таблицы `users`:

| Поле | Тип | Требования |
|------|-----|------------|
| `telegram_id` | VARCHAR(50) | Может быть NULL |
| `email` | VARCHAR(255) | Может быть NULL |
| `name` | VARCHAR(255) | Может быть NULL |
| `avatar_url` | TEXT | Может быть NULL |
| `email_verified` | BOOLEAN | DEFAULT TRUE |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |
| `last_login_at` | TIMESTAMP | Может быть NULL |

**⚠️ Если столбец имеет `NOT NULL` без `DEFAULT` — функция упадёт при вставке!**

### Проверка структуры БД перед установкой

**ОБЯЗАТЕЛЬНО перед установкой расширения:**

1. Выполни `SELECT column_name, is_nullable, column_default FROM information_schema.columns WHERE table_name = 'users';`
2. Найди все столбцы с `is_nullable = 'NO'` и `column_default = NULL`
3. Такие столбцы вызовут ошибку при INSERT
4. **Типичные проблемы:**
   - `password_hash NOT NULL` — передай пустую строку `''`
   - `role NOT NULL` — передай дефолтное значение (например `'user'`)

**Если нашёл NOT NULL поля без DEFAULT — добавь их в INSERT с дефолтными значениями!**

## Добавление секретов

**ОБЯЗАТЕЛЬНО вызови тулу `put_secret` для КАЖДОГО секрета!**

```python
# Для auth и bot функций
put_secret("JWT_SECRET", "<сгенерируй: 64 hex символа>")
put_secret("TELEGRAM_BOT_TOKEN", "<токен бота от BotFather>")
put_secret("TELEGRAM_BOT_USERNAME", "<username бота без @>")
put_secret("SITE_URL", "https://{домен-пользователя}")
put_secret("TELEGRAM_WEBHOOK_SECRET", "<секретный токен для webhook>")
put_secret("MAIN_DB_SCHEMA", "<схема БД, например: public>")
```

- Вызывай `put_secret` для КАЖДОГО секрета отдельно
- **JWT_SECRET** — генерируй сам (64 hex символа)
- **TELEGRAM_BOT_TOKEN** — получи у пользователя (от BotFather)
- **TELEGRAM_WEBHOOK_SECRET** — сгенерируй случайную строку (1-256 символов)
- **MAIN_DB_SCHEMA** — схема БД проекта (обычно `public` или имя проекта)
- Покажи пользователю в чате каждый вызов тулы

## После установки

**ОБЯЗАТЕЛЬНО:** Последним шагом добавь кнопку входа на фронтенд, чтобы пользователь сразу видел результат!

Используй компоненты из `/frontend`:
- `TelegramLoginButton.tsx` — кнопка входа
- `useTelegramAuth.ts` — хук авторизации

**Скажи пользователю:**

> ✅ Расширение Telegram Auth установлено!
>
> Бот должен сохранять токен в таблицу `telegram_auth_tokens` и показывать пользователю ссылку на callback.

## API

```
POST ?action=callback   — фронтенд обменивает токен на JWT (body: { token })
POST ?action=refresh    — обновление токена (body: { refresh_token })
POST ?action=logout     — выход (body: { refresh_token })
```

## Безопасность

- JWT access tokens (15 мин)
- Refresh tokens хешируются (SHA256) перед сохранением
- Временные токены авторизации (5 мин)
- Автоочистка протухших токенов
- Параметризованные SQL-запросы
- CORS ограничение через `ALLOWED_ORIGINS`

---

# [TELEGRAM] Специфичное для Telegram Auth

## Чеклист интеграции

### Шаг 1: Подготовка базы данных

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_id VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT;
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
```

### Шаг 2: Получить данные бота

**Спроси у пользователя:**

> Для авторизации через Telegram укажите **username вашего бота** (без @).
>
> Например: `myapp_bot`

### Шаг 3: Добавление секретов

```python
put_secret("TELEGRAM_BOT_USERNAME", "<username бота без @>")
put_secret("SITE_URL", "https://{домен-пользователя}")
put_secret("JWT_SECRET", "<сгенерируй: 64 hex символа>")
```

### Шаг 4: Создание бот-функции (Cloud Function)

Бот развёртывается как отдельная облачная функция с webhook.

**Создай функцию `/backend/telegram-bot/`:**

```python
# /backend/telegram-bot/index.py
import json
import os
import uuid
import hashlib
from datetime import datetime, timezone, timedelta

import psycopg2
import requests

def send_message(chat_id: int, text: str, reply_markup: dict = None) -> None:
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json=payload, timeout=10)

def handle_web_auth(chat_id: int, user: dict) -> None:
    token = str(uuid.uuid4())
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO telegram_auth_tokens
        (token_hash, telegram_id, telegram_username, telegram_first_name,
         telegram_last_name, telegram_photo_url, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (token_hash, str(user.get("id")), user.get("username"), user.get("first_name"),
          user.get("last_name"), None, datetime.now(timezone.utc) + timedelta(minutes=5)))
    conn.commit()
    conn.close()

    site_url = os.environ["SITE_URL"]
    auth_url = f"{site_url}/auth/telegram/callback?token={token}"
    send_message(chat_id, "Авторизация готова!\n\nНажмите кнопку ниже 👇🏼\n\nСсылка действительна 5 минут",
                 reply_markup={"inline_keyboard": [[{"text": "Войти на сайт", "url": auth_url}]]})

def handler(event: dict, context) -> dict:
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": {"Access-Control-Allow-Origin": "*"}, "body": ""}

    body = json.loads(event.get("body", "{}"))
    message = body.get("message")
    if not message:
        return {"statusCode": 200, "body": ""}

    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    user = message.get("from", {})

    if text.startswith("/start"):
        parts = text.split(" ", 1)
        if len(parts) > 1 and parts[1] == "web_auth":
            handle_web_auth(chat_id, user)
        else:
            send_message(chat_id, "Привет! Используйте кнопку \"Войти через Telegram\" на сайте.")

    return {"statusCode": 200, "body": ""}
```

**requirements.txt:**
```
psycopg2-binary
requests
```

### Шаг 5: Настройка Webhook

После деплоя функции нужно зарегистрировать webhook в Telegram с секретным токеном для безопасности.

**Скажи пользователю:**

> Функция бота задеплоена! Теперь нужно подключить webhook.
>
> **1. Сгенерируйте секретный токен** (любая строка 1-256 символов):
> ```
> Например: my_super_secret_webhook_token_12345
> ```
>
> **2. Зарегистрируйте webhook** (выполните в браузере):
> ```
> https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={URL_ФУНКЦИИ_БОТА}&secret_token={WEBHOOK_SECRET}
> ```
>
> Пример:
> ```
> https://api.telegram.org/bot123456:ABC.../setWebhook?url=https://functions.poehali.dev/xxx-telegram-bot&secret_token=my_super_secret_webhook_token_12345
> ```
>
> **3. Добавьте секрет в проект:**
> ```python
> put_secret("TELEGRAM_WEBHOOK_SECRET", "my_super_secret_webhook_token_12345")
> ```
>
> После этого бот начнёт получать сообщения, и только Telegram сможет вызывать webhook!

### Шаг 6: Добавление секретов для бота

```python
put_secret("TELEGRAM_BOT_TOKEN", "<токен бота от BotFather>")
put_secret("SITE_URL", "https://{домен-пользователя}")
```

### Шаг 7: Создание страниц

1. **Страница с кнопкой входа** — добавь `TelegramLoginButton`
2. **Страница callback** `/auth/telegram/callback` — обработка токена
3. **Страница профиля** — показать данные пользователя

---

## Frontend компоненты

| Файл | Описание |
|------|----------|
| `useTelegramAuth.ts` | Хук авторизации |
| `TelegramLoginButton.tsx` | Кнопка "Войти через Telegram" |
| `UserProfile.tsx` | Профиль пользователя |

### Пример использования

```tsx
const AUTH_URL = "https://functions.poehali.dev/xxx-telegram-auth";
const BOT_USERNAME = "myapp_auth_bot";

const auth = useTelegramAuth({
  botUsername: BOT_USERNAME,
  apiUrls: {
    callback: `${AUTH_URL}?action=callback`,
    refresh: `${AUTH_URL}?action=refresh`,
    logout: `${AUTH_URL}?action=logout`,
  },
});

// Кнопка входа - просто открывает бота
<TelegramLoginButton onClick={auth.login} isLoading={auth.isLoading} />

// После авторизации
if (auth.isAuthenticated && auth.user) {
  return <UserProfile user={auth.user} onLogout={auth.logout} />;
}
```

### Страница callback

```tsx
// app/auth/telegram/callback/page.tsx
"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTelegramAuth } from "@/hooks/useTelegramAuth";

const AUTH_URL = "https://functions.poehali.dev/xxx-telegram-auth";
const BOT_USERNAME = "myapp_auth_bot";

export default function TelegramCallbackPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const auth = useTelegramAuth({
    botUsername: BOT_USERNAME,
    apiUrls: {
      callback: `${AUTH_URL}?action=callback`,
      refresh: `${AUTH_URL}?action=refresh`,
      logout: `${AUTH_URL}?action=logout`,
    },
  });

  useEffect(() => {
    if (!token) {
      router.push("/login?error=no_token");
      return;
    }

    auth.handleCallback(token).then((success) => {
      if (success) {
        router.push("/profile");
      } else {
        router.push("/login?error=auth_failed");
      }
    });
  }, [token]);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <p>Авторизация...</p>
    </div>
  );
}
```

---

## Поток авторизации

```
1. Пользователь нажимает "Войти через Telegram"
2. Открывается t.me/botname?start=web_auth
3. Telegram отправляет webhook на бот-функцию
4. Бот-функция генерирует UUID токен
5. Бот-функция сохраняет токен в telegram_auth_tokens
6. Бот-функция отправляет сообщение с кнопкой через Telegram API
7. Пользователь нажимает кнопку в Telegram
8. Callback страница → POST ?action=callback { token }
9. Auth API возвращает JWT + user
10. Готово!
```

## Архитектура

```
┌─────────────┐    ┌─────────────┐    ┌─────────────────┐
│  Frontend   │───▶│  Telegram   │───▶│  telegram-bot   │
│  (Button)   │    │   (App)     │    │ (Cloud Function)│
└─────────────┘    └─────────────┘    └────────┬────────┘
                                               │
                         ┌─────────────────────┘
                         │ INSERT token
                         ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────────┐
│  Frontend   │───▶│telegram-auth│◀───│    Database     │
│ (Callback)  │    │(Cloud Func) │    │   (PostgreSQL)  │
└─────────────┘    └─────────────┘    └─────────────────┘
```

---

## Таблица telegram_auth_tokens

**ВАЖНО:** Таблица должна быть создана заранее (расширение НЕ создаёт таблицы автоматически).

### Проверка структуры перед установкой

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'telegram_auth_tokens'
ORDER BY ordinal_position;
```

### Требуемая структура

```sql
CREATE TABLE telegram_auth_tokens (
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
);
```

### Если структура отличается

Код использует следующие поля:
- `token_hash` — SHA256 хеш токена (НЕ `token`!)
- `telegram_id`, `telegram_username`, `telegram_first_name`, `telegram_last_name`
- `telegram_photo_url`, `expires_at`, `used`, `created_at`

**Если в БД другие названия столбцов — нужно либо изменить таблицу, либо адаптировать код!**

**Важно:** `token_hash` — это SHA256 хеш токена, а не сам токен!
