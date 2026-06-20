# Dev Landing API — бэкенд лендинга-презентации разработчика

Бэкенд-сервис для формы обратной связи лендинга с полноценным REST API и
AI-анализом обращений. Полный цикл одного запроса:

```
запрос → валидация → AI-анализ (Claude) → сохранение в БД → email-уведомления → ответ
```

Если AI недоступен — сервис продолжает работать на эвристическом fallback.

> Тестовое задание (backend-ориентированное). Стек: **Python 3.12 + FastAPI + PostgreSQL + Anthropic Claude**.

---

## Содержание

- [Демо и ссылки](#демо-и-ссылки)
- [Возможности](#возможности)
- [Стек технологий](#стек-технологий)
- [Быстрый старт](#быстрый-старт)
- [Архитектура](#архитектура)
- [API](#api)
- [AI-интеграция](#ai-интеграция)
- [Хранение данных](#хранение-данных)
- [Тесты](#тесты)
- [Что сделано с помощью AI](#что-сделано-с-помощью-ai)
- [Деплой](#деплой)

---

## Демо и ссылки

| Что | Ссылка |
|-----|--------|
| 🌐 Лендинг | http://37.233.86.126:8000/ |
| 📘 Swagger UI | http://37.233.86.126:8000/docs |
| 📗 ReDoc | http://37.233.86.126:8000/redoc |
| 🔌 OpenAPI JSON | http://37.233.86.126:8000/openapi.json |

> Сервис развёрнут в Docker на VPS (Ubuntu 22.04). AI работает на реальном Claude.
> Локально после запуска: http://localhost:8000/ (лендинг) и http://localhost:8000/docs (Swagger).

---

## Возможности

- ✅ `POST /api/contact` — приём обращения: валидация → AI → БД → почта
- ✅ Валидация имени, телефона, email и сообщения (Pydantic v2)
- ✅ Два email-уведомления: владельцу сайта и копия пользователю
- ✅ AI-анализ обращения: тональность, категория, приоритет, резюме, черновик ответа
- ✅ Graceful fallback: нет ключа/таймаут/ошибка → локальная эвристика, сервис жив
- ✅ Rate limiting (sliding window по IP) — защита от спама
- ✅ Логирование всех запросов в файл (с ротацией)
- ✅ Глобальный обработчик ошибок, единый формат ответа, корректные HTTP-статусы
- ✅ `GET /api/health` и `GET /api/metrics`
- ✅ CORS, Swagger/OpenAPI из коробки
- ✅ Слоистая архитектура: Controllers → Services → Repositories
- ✅ Тесты (pytest), Docker + docker-compose, фронтенд-лендинг

---

## Стек технологий

**Backend**
- Python 3.12, FastAPI, Uvicorn
- Pydantic v2 + pydantic-settings (валидация и конфигурация)
- SQLAlchemy 2.0 (async) + asyncpg (PostgreSQL) / aiosqlite (SQLite-fallback)
- aiosmtplib (асинхронная отправка почты)

**AI**
- Anthropic Claude (`anthropic` SDK), structured output через tool use

**Инфраструктура**
- Docker + docker-compose
- pytest + pytest-asyncio + httpx (тесты)

**Frontend**
- Чистые HTML / CSS / JS (без фреймворка), отдаётся тем же приложением

### Почему так

- **FastAPI** — асинхронный, строго типизированный, даёт Swagger/OpenAPI «бесплатно»
  (одно из требований ТЗ закрывается само собой). Pydantic делает валидацию
  декларативной.
- **PostgreSQL** как основное хранилище (показать навык работы с БД), но с
  прозрачным **SQLite-fallback** — проект заводится без внешней БД одной командой.
- **Claude** — выбран как основной AI-провайдер; structured output через tool use
  даёт гарантированно валидный JSON без хрупкого парсинга текста.
- **Свой rate limiter** вместо готового пакета — чтобы показать понимание алгоритма,
  а не «подключил библиотеку».

---

## Быстрый старт

### Вариант 1. Docker (рекомендуется)

Поднимает backend + PostgreSQL одной командой. Секреты не обязательны —
без ключа AI работает в fallback, без SMTP письма пишутся в лог.

```bash
docker compose up --build
```

- Лендинг: http://localhost:8000/
- Swagger: http://localhost:8000/docs

Чтобы включить реальный AI и почту — создай `.env` рядом с `docker-compose.yml`:

```env
ANTHROPIC_API_KEY=sk-ant-...
SMTP_HOST=sandbox.smtp.mailtrap.io
SMTP_PORT=2525
SMTP_USER=твой_mailtrap_user
SMTP_PASSWORD=твой_mailtrap_pass
OWNER_EMAIL=owner@example.com
```

### Вариант 2. Локально (без Docker)

Нужен Python 3.12+. БД по умолчанию — SQLite (файл `backend/data/app.db`).

```bash
cd backend

# 1. Виртуальное окружение
python -m venv .venv
source .venv/Scripts/activate      # Windows (Git Bash)
# source .venv/bin/activate        # Linux / macOS

# 2. Зависимости
pip install -r requirements.txt

# 3. Конфигурация (опционально — без неё работает на дефолтах)
cp .env.example .env

# 4. Запуск
uvicorn app.main:app --reload
```

### Переменные окружения

Полный список с комментариями — в [`backend/.env.example`](backend/.env.example).
Ключевые:

| Переменная | Назначение | По умолчанию |
|-----------|-----------|--------------|
| `DATABASE_URL` | Строка подключения. Пусто → SQLite | _(SQLite)_ |
| `ANTHROPIC_API_KEY` | Ключ Claude. Пусто → fallback | _(пусто)_ |
| `AI_MODEL` | Модель Claude | `claude-haiku-4-5` |
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` | SMTP. Пусто → письма в лог | Mailtrap |
| `OWNER_EMAIL` | Кому слать письмо владельцу | — |
| `RATE_LIMIT_MAX_REQUESTS` | Лимит запросов на IP за окно | `5` |
| `RATE_LIMIT_WINDOW_SECONDS` | Окно лимита, сек | `3600` |
| `CORS_ORIGINS` | Разрешённые источники (через запятую) | localhost |

---

## Архитектура

Слоистая структура — каждый слой знает только о соседе снизу:

```
       HTTP
        │
   ┌────▼─────────────────────────────────────────┐
   │ Middleware: CORS → request-id + логирование    │
   └────┬─────────────────────────────────────────┘
        │
   ┌────▼──────────┐   разбор/сборка HTTP, статус-коды
   │  Controllers  │   app/api/*.py
   └────┬──────────┘
        │
   ┌────▼──────────┐   бизнес-логика, оркестрация
   │   Services    │   app/services/*.py
   └────┬──────────┘
        │
   ┌────▼──────────┐   доступ к данным (SQL)
   │ Repositories  │   app/repositories/*.py
   └────┬──────────┘
        │
   ┌────▼──────────┐
   │   Database    │   app/db/*.py
   └───────────────┘

Сквозные: AI-сервис, Email-сервис, глобальный error handler.
```

### Структура проекта

```
labaratory-internet/
├── backend/
│   ├── app/
│   │   ├── main.py              # сборка приложения, lifespan, CORS, монтаж фронта
│   │   ├── config.py            # настройки (pydantic-settings)
│   │   ├── api/                 # КОНТРОЛЛЕРЫ
│   │   │   ├── contact.py       #   POST /api/contact
│   │   │   ├── health.py        #   GET  /api/health
│   │   │   └── metrics.py       #   GET  /api/metrics
│   │   ├── schemas/             # Pydantic-схемы (валидация I/O)
│   │   ├── services/            # СЕРВИСЫ (бизнес-логика)
│   │   │   ├── contact_service.py   # оркестрация полного цикла
│   │   │   ├── ai_service.py        # Claude + fallback
│   │   │   ├── email_service.py     # SMTP, два письма
│   │   │   └── metrics_service.py   # агрегация статистики
│   │   ├── repositories/        # РЕПОЗИТОРИИ (доступ к БД)
│   │   ├── db/                  # модели и подключение к БД
│   │   ├── middleware/          # request-context, rate-limit
│   │   └── core/                # логгер, исключения
│   ├── tests/                   # pytest
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/                    # лендинг (HTML/CSS/JS)
├── docker-compose.yml
├── postman_collection.json
└── README.md
```

### Паттерны проектирования

- **Layered architecture** — разделение ответственности по слоям.
- **Repository** — вся работа с таблицей `contact_requests` инкапсулирована в
  `ContactRepository`; сервисы не знают про SQL.
- **Service layer** — бизнес-логика отделена от транспорта (HTTP).
- **Dependency Injection** — сессии БД и rate-limit через `Depends(...)` FastAPI.
- **Strategy/Fallback** — `AIService` прозрачно подменяет Claude эвристикой.
- **Singleton** — клиент AI и rate limiter кешируются (`lru_cache`).

---

## API

Базовый префикс: `/api`. Полная интерактивная документация — в Swagger `/docs`.

### `POST /api/contact`

Принимает обращение, валидирует, анализирует AI, сохраняет, шлёт письма.

**Запрос:**
```json
{
  "name": "Илья Фарафонов",
  "phone": "+7 (999) 123-45-67",
  "email": "ilya@example.com",
  "message": "Здравствуйте! Хочу заказать лендинг под ключ, обсудим бюджет?"
}
```

**Успех — `201 Created`:**
```json
{
  "success": true,
  "request_id": "1f3c9a7e-2b6d-4e1a-9f0c-8d2b1a4c5e6f",
  "message": "Спасибо! Мы получили ваше обращение и скоро свяжемся с вами.",
  "analysis": {
    "sentiment": "positive",
    "category": "order",
    "priority": "high",
    "provider": "claude"
  }
}
```

**Пример (curl):**
```bash
curl -X POST http://localhost:8000/api/contact \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Илья Фарафонов",
    "phone": "+7 (999) 123-45-67",
    "email": "ilya@example.com",
    "message": "Здравствуйте! Хочу заказать лендинг под ключ, обсудим бюджет?"
  }'
```

### `GET /api/health`

```json
{
  "status": "ok",
  "version": "1.0.0",
  "uptime_seconds": 42.5,
  "checks": { "db": "up", "ai": "up", "email": "up" }
}
```

### `GET /api/metrics`

```json
{
  "total_requests": 12,
  "last_24h": 5,
  "by_sentiment": { "positive": 8, "neutral": 3, "negative": 1 },
  "by_category": { "order": 6, "question": 4, "spam": 2 },
  "by_priority": { "high": 6, "medium": 4, "low": 2 },
  "last_request_at": "2026-06-20T08:28:42"
}
```

### Валидация и обработка ошибок

Все ошибки — в едином формате с машинным кодом и `request_id`:

```json
{
  "success": false,
  "error": "validation_error",
  "message": "Проверьте корректность переданных данных",
  "request_id": "…",
  "details": { "email": "value is not a valid email address" }
}
```

| Статус | Когда | `error` |
|--------|-------|---------|
| `201` | Обращение принято | — |
| `422` | Невалидные данные формы | `validation_error` |
| `429` | Превышен лимит запросов (есть заголовок `Retry-After`) | `rate_limit_exceeded` |
| `500` | Непредвиденная ошибка (детали — только в логах) | `internal_error` |
| `503` | Критичная зависимость недоступна | `service_unavailable` |

**Правила валидации:** имя — 2–120 символов и содержит буквы; телефон — 7–15 цифр
в любом формате; email — корректный адрес; сообщение — 10–4000 символов.
Все строки автоматически очищаются от крайних пробелов; в письмах данные
экранируются (`html.escape`) — защита от инъекций.

---

## AI-интеграция

### Что делает

За **один** вызов Claude (structured output через tool use) обращение получает:

| Поле | Значения | Зачем |
|------|----------|-------|
| `sentiment` | positive / neutral / negative | Тональность |
| `category` | order / question / cooperation / complaint / spam / other | Тип обращения |
| `priority` | low / medium / high | Срочность для владельца |
| `summary` | строка | Резюме для письма владельцу |
| `reply` | строка | Черновик вежливого ответа клиенту |

Это сразу три из предложенных в ТЗ AI-функций (тональность + классификация +
генерация ответа) в одном запросе.

### Промпт

Системный промпт (сокращённо, полностью — в [`ai_service.py`](backend/app/services/ai_service.py)):

> «Ты — ассистент владельца сайта-портфолио веб-разработчика. К тебе приходят
> обращения из формы обратной связи. Классифицируй обращение и подготовь
> материалы для владельца. Отвечай строго через инструмент `submit_analysis`.
> Все тексты — на русском. Черновик ответа пиши вежливо, от первого лица,
> обращайся по имени, 2–4 предложения.»

Модель обязана вызвать инструмент `submit_analysis` со строгой JSON-схемой
(enum-поля), поэтому ответ всегда валиден.

### Fallback (graceful degradation)

Метод `AIService.analyze()` **никогда не бросает исключение**. Если ключа нет,
вышел таймаут или API ответил ошибкой — включается локальная эвристика:

- тональность — по словарям позитивных/негативных маркеров;
- категория — по ключевым словам (заказ, жалоба, спам, сотрудничество…);
- приоритет — производная от категории и тональности;
- резюме и черновик ответа — по шаблону с именем клиента.

В ответе при этом `provider: "fallback"`. Сервис продолжает принимать обращения.

---

## Хранение данных

### База данных

Обращения хранятся в таблице `contact_requests` (PostgreSQL или SQLite) вместе
с результатом AI-анализа. Схема — в [`models.py`](backend/app/db/models.py).
Таблицы создаются автоматически при старте (для прод-эволюции схемы в проект
легко добавляется Alembic).

### Логи

- Файл `backend/logs/app.log`, ротация (5 МБ × 5 файлов) + дублирование в консоль.
- Каждый запрос: `метод, путь, статус, длительность, IP, request_id`.
- Ошибки — со стектрейсом (только в лог, не наружу).

### Rate limiting

- Алгоритм: **sliding window** по IP (по умолчанию 5 запросов / час на `/api/contact`).
- Хранилище — in-memory (достаточно для одного инстанса; для горизонтального
  масштабирования меняется на Redis с TTL).
- Реализация: [`middleware/rate_limit.py`](backend/app/middleware/rate_limit.py).
- IP клиента берётся из `X-Forwarded-For` **только** при `TRUST_PROXY=true`
  (когда сервис стоит за доверенным nginx). Иначе заголовок игнорируется, чтобы
  его нельзя было подделать и обойти лимит. На проде за reverse-proxy ставим `true`.

> ⚠️ `GET /api/metrics` намеренно оставлен открытым (демо). Для продакшена сюда
> стоит добавить аутентификацию (API-ключ / Basic Auth).

### Статистика

`GET /api/metrics` агрегирует данные SQL-запросами прямо по таблице обращений
(всего, за 24 часа, разбивки по тональности/категории/приоритету).

---

## Тесты

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

Покрыто: health-check, успешный приём обращения, валидация (email, имя, телефон,
сообщение), эвристика fallback (тональность, категории, приоритет), rate limiting,
метрики. Тесты используют отдельную БД и принудительный fallback (реальный ключ
не дёргается).

---

## Что сделано с помощью AI

Разработка велась с активным использованием **Claude (Claude Code)** как
ассистента — это ускоряет рутину, но архитектурные решения и проверка за
разработчиком.

**Где помогал AI:**
- генерация шаблонного кода (Pydantic-схемы, CRUD-репозиторий, HTML/CSS лендинга);
- черновики email-шаблонов и текстов;
- подсказки по API FastAPI/SQLAlchemy и структуре проекта.

**Что делалось/проверялось вручную:**
- выбор стека и слоистой архитектуры, границы слоёв;
- дизайн AI-промпта и схемы `submit_analysis` (tool use), стратегия fallback;
- логика rate limiting, формат ошибок и набор HTTP-статусов;
- ревью сгенерированного кода, прогон тестов и ручная проверка эндпоинтов (curl + браузер).

**Примеры промптов** (по смыслу):
- «Спроектируй слоистую структуру FastAPI-сервиса для формы обратной связи с AI-анализом».
- «Напиши Pydantic-схему с валидацией телефона (7–15 цифр) и email».
- «Сделай эвристический fallback для анализа тональности и категории на русском».

---

## Деплой

Сервис упакован в Docker и разворачивается через `docker compose` на любом
сервере (VPS, Render, Railway). На целевом сервере:

```bash
git clone <repo-url> && cd labaratory-internet
# (опционально) положить .env с ANTHROPIC_API_KEY и SMTP
docker compose up -d --build
```

За reverse-proxy (nginx) пробрасывается порт `8000`; реальный IP клиента берётся
из заголовка `X-Forwarded-For` (учтено в middleware, включается `TRUST_PROXY=true`).

**Текущий деплой:** Docker на VPS Ubuntu 22.04, доступен по адресу
http://37.233.86.126:8000 (см. раздел [Демо и ссылки](#демо-и-ссылки)).
