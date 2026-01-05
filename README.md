# Telegram Auth Extension

SSO авторизация через Telegram бота. **1 функция** с роутингом по action.

> **Как это работает:**
>
> 1. Пользователь нажимает "Войти через Telegram" → открывается бот
> 2. Бот создаёт токен и отправляет пользователю ссылку авторизации
> 3. Пользователь переходит по ссылке → callback страница обменивает токен на JWT
> 4. Готово! Пользователь авторизован

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
put_secret("TELEGRAM_BOT_SECRET", "<сгенерируй: 64 hex символа>")
put_secret("SITE_URL", "https://{домен-пользователя}")
put_secret("JWT_SECRET", "<сгенерируй: 64 hex символа>")
```

- Вызывай `put_secret` для КАЖДОГО секрета отдельно
- **JWT_SECRET и TELEGRAM_BOT_SECRET генерируй сам** (64 hex символа)
- Покажи пользователю в чате каждый вызов тулы
- **TELEGRAM_BOT_SECRET** — этот же секрет нужно добавить в бота для авторизации запросов к API

## После установки скажи пользователю

> ✅ Расширение Telegram Auth установлено!
>
> **Осталось настроить бота:**
>
> Ваш бот должен обрабатывать команду `/start web_auth` и вызывать API расширения.
>
> При получении `/start web_auth`:
> 1. Отправьте POST запрос на `{API_URL}?action=init-auth`
> 2. В заголовке `X-Bot-Secret` передайте: `{TELEGRAM_BOT_SECRET}`
> 3. В body передайте данные пользователя: `telegram_id`, `username`, `first_name`, `last_name`
> 4. Отправьте пользователю ссылку `auth_url` из ответа
>
> После настройки бота авторизация заработает!

## API

```
POST ?action=init-auth  — бот создаёт токен + сохраняет данные пользователя (требует X-Bot-Secret)
POST ?action=callback   — фронтенд обменивает токен на JWT (body: { token })
POST ?action=refresh    — обновление токена (body: { refresh_token })
POST ?action=logout     — выход (body: { refresh_token })
```

## Безопасность

- JWT access tokens (15 мин)
- Refresh tokens хешируются (SHA256) перед сохранением
- Временные токены авторизации (10 мин)
- Автоочистка протухших токенов
- Верификация запросов бота через секретный ключ
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

Пользователь должен указать username уже существующего бота.

### Шаг 3: Добавление секретов

Когда пользователь пришлёт username бота:

```python
put_secret("TELEGRAM_BOT_USERNAME", "<username бота без @>")
put_secret("TELEGRAM_BOT_SECRET", "<сгенерируй: 64 hex символа>")
put_secret("SITE_URL", "https://{домен-пользователя}")
put_secret("JWT_SECRET", "<сгенерируй: 64 hex символа>")
```

### Шаг 4: Настройка Webhook бота

**ВАЖНО:** Бот должен обрабатывать команду `/start web_auth`.

**Скажи пользователю:**

> Для работы авторизации нужно настроить бота на обработку команды `/start web_auth`.
>
> **Что должен делать бот при получении `/start web_auth`:**
> 1. Получить данные пользователя (telegram_id, username, first_name, last_name)
> 2. Вызвать API: `POST {API_URL}?action=init-auth` с этими данными
> 3. Отправить пользователю ссылку `auth_url` из ответа API
>
> **Пример запроса к API:**
> ```
> POST /telegram-auth?action=init-auth
> Headers: X-Bot-Secret: {TELEGRAM_BOT_SECRET}
> Body: {
>   "telegram_id": "123456789",
>   "username": "user_name",
>   "first_name": "Имя",
>   "last_name": "Фамилия"
> }
> ```
>
> **Ответ API:**
> ```json
> {
>   "success": true,
>   "token": "xxx",
>   "auth_url": "https://site.com/auth/telegram/callback?token=xxx"
> }
> ```
>
> Бот должен отправить пользователю `auth_url` как кликабельную ссылку.

**Пример кода для бота (Python):**

```python
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args and context.args[0] == "web_auth":
        user = update.effective_user

        response = requests.post(
            f"{API_URL}?action=init-auth",
            json={
                "telegram_id": str(user.id),
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
            headers={"X-Bot-Secret": BOT_SECRET},
        )

        if response.ok:
            data = response.json()
            await update.message.reply_text(
                f"✅ Нажмите для авторизации:\n{data['auth_url']}"
            )
        else:
            await update.message.reply_text("❌ Ошибка. Попробуйте снова.")
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
3. Бот получает /start web_auth
4. Бот → POST ?action=init-auth { telegram_id, ... }
5. API создаёт токен, возвращает auth_url
6. Бот отправляет пользователю ссылку
7. Пользователь переходит по ссылке
8. Callback страница → POST ?action=callback { token }
9. API возвращает JWT + user data
10. Готово!
```

---

## Формат параметров бота

Бот парсит параметры из `/start` по правилам:
- `__` разделяет key и value: `key__value`
- `___` разделяет пары: `key1__value1___key2__value2`

Пример: `/start action__web_auth___ref__12345`
Результат: `{ action: "web_auth", ref: "12345" }`

Для простой авторизации достаточно: `/start web_auth`
