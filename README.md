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
put_secret("TELEGRAM_BOT_USERNAME", "<username бота от пользователя, без @>")
put_secret("SITE_URL", "https://{домен-пользователя}")
put_secret("JWT_SECRET", "<сгенерируй: 64 hex символа>")
```

- Вызывай `put_secret` для КАЖДОГО секрета отдельно
- **JWT_SECRET генерируй сам** (64 hex символа)
- Покажи пользователю в чате каждый вызов тулы

## После установки скажи пользователю

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

### Шаг 4: Настройка бота

Бот должен обрабатывать команду `/start web_auth`:

1. Сгенерировать UUID токен
2. Сохранить токен в таблицу `telegram_auth_tokens` с данными пользователя
3. Показать сообщение с кнопкой-ссылкой

**SQL для сохранения токена (бот выполняет напрямую):**

```sql
INSERT INTO telegram_auth_tokens
(token_hash, telegram_id, telegram_username, telegram_first_name,
 telegram_last_name, telegram_photo_url, expires_at)
VALUES (
  SHA256('uuid-токен'),
  '123456789',
  'username',
  'Имя',
  'Фамилия',
  NULL,
  NOW() + INTERVAL '5 minutes'
);
```

**Пример сообщения бота:**

```
Авторизация готова!

Нажмите на кнопку ниже, чтобы войти на сайт 👇🏼

[Войти на сайт] ← кнопка со ссылкой

Ссылка действительна 5 минут
```

**Ссылка в кнопке:**
```
https://{SITE_URL}/auth/telegram/callback?token={uuid-токен}
```

### Шаг 5: Создание страниц

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
3. Бот генерирует UUID токен
4. Бот сохраняет токен в telegram_auth_tokens
5. Бот показывает кнопку со ссылкой
6. Пользователь нажимает кнопку
7. Callback страница → POST ?action=callback { token }
8. API возвращает JWT + user
9. Готово!
```

---

## Таблица telegram_auth_tokens

Расширение автоматически создаёт таблицу при первом запросе:

```sql
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
);
```

**Важно:** `token_hash` — это SHA256 хеш токена, а не сам токен!
