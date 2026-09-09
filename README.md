# Transport Sharing

Сервис шеринга самокатов — тестовое задание на вакансию Agentic Developer.

Клиент-серверное приложение: отдельный бэкенд (REST API), отдельный фронтенд (SPA с картой),
реляционная база. Всё поднимается одной командой через Docker Compose.

## Стек

| Слой | Технологии |
| --- | --- |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (async, asyncpg), Alembic, pydantic-settings; uv, ruff, pytest |
| Frontend | React 19, Vite, TypeScript, react-leaflet + OpenStreetMap; oxlint |
| База | PostgreSQL 16 |
| Инфраструктура | Docker Compose, nginx (раздача фронтенда и прокси `/api`), GitHub Actions |

## Быстрый старт (Docker)

Нужен Docker с Compose v2.

```bash
cp .env.example .env        # необязательно: у всех переменных есть значения по умолчанию
docker compose up --build
```

После запуска:

| Что | Адрес |
| --- | --- |
| Карта (фронтенд) | http://localhost:3000 |
| Health бэкенда | http://localhost:8000/api/health → `{"status":"ok"}` (также http://localhost:3000/api/health через nginx) |
| Swagger UI | http://localhost:8000/api/docs |
| PostgreSQL | `localhost:5432`, пользователь/пароль/база — `scooter` |

При старте бэкенд применяет миграции (`alembic upgrade head`) и только потом поднимает API;
фронтенд стартует после того, как бэкенд стал `healthy`.

Остановить: `docker compose down` (вместе с данными базы — `docker compose down -v`).

## Режим разработки (hot reload)

Стек из «Быстрого старта» собирает фронтенд в статику, поэтому каждое изменение кода требует
пересборки образа. Для разработки есть overlay `docker-compose.dev.yml`:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

| Что | Как работает в dev-режиме |
| --- | --- |
| Фронтенд | Vite dev server на http://localhost:5173 с HMR; каталог `frontend/` примонтирован в контейнер, `/api` проксируется на бэкенд |
| Бэкенд | `uvicorn --reload` на http://localhost:8000; примонтированы `backend/app` и `backend/alembic` |
| База | та же, что в обычном режиме |

После изменения зависимостей (`package.json`, `pyproject.toml`) пересоберите образы: запустите ту же
команду с `--build -V` (`-V` обновляет `node_modules` внутри контейнера фронтенда).

Порт dev-сервера фиксирован (5173): HMR-клиент Vite подключается к порту страницы. Работать без Docker
можно так же удобно — см. раздел «Локальная разработка без Docker».

## Локальная разработка без Docker

### Backend

Нужен [uv](https://docs.astral.sh/uv/) — он сам поставит Python 3.12 из `backend/.python-version`.

```bash
cd backend
uv sync                                  # .venv + зависимости (включая dev)
uv run uvicorn app.main:app --reload     # http://localhost:8000/api/health
uv run pytest                            # тесты
uv run ruff check . && uv run ruff format --check .   # линт и формат
```

Настройки читаются из переменных окружения либо из `.env` в корне репозитория и/или в `backend/`
(см. `app/core/config.py`). Базу для локального запуска удобно взять из compose: `docker compose up db`.

### Frontend

Нужен Node.js 22+.

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173, запросы к /api проксируются на localhost:8000
npm run lint     # oxlint
npm run build    # tsc + vite build → dist/
```

Адрес бэкенда для dev-прокси можно переопределить переменной `VITE_API_PROXY_TARGET`.

## Миграции

```bash
cd backend
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

Alembic берёт URL базы из тех же переменных `POSTGRES_*`, что и приложение. Все модели должны
импортироваться в `app/models/__init__.py`, чтобы autogenerate их видел.

## Переменные окружения

Полный список с комментариями — в [`.env.example`](.env.example).

| Переменная | По умолчанию | Назначение |
| --- | --- | --- |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `scooter` | учётные данные и имя базы |
| `POSTGRES_HOST` | `localhost` | хост базы для запуска без Docker (в compose всегда `db`) |
| `POSTGRES_PORT` | `5432` | порт базы на хосте (в compose-сети всегда `5432`) |
| `BACKEND_PORT` | `8000` | порт бэкенда на хосте |
| `FRONTEND_PORT` | `3000` | порт фронтенда на хосте |
| `DEBUG` | `false` | SQL-логи SQLAlchemy |

## Структура репозитория

```
.
├── backend/                  FastAPI-приложение
│   ├── app/
│   │   ├── api/              роутеры и обработчики (сейчас: health)
│   │   ├── core/             настройки (pydantic-settings)
│   │   ├── db/               Base, async engine, сессии
│   │   ├── models/           ORM-модели
│   │   ├── schemas/          Pydantic-схемы
│   │   └── services/         бизнес-логика
│   ├── alembic/              миграции (async env)
│   ├── tests/                pytest
│   ├── Dockerfile
│   └── pyproject.toml        зависимости, ruff, pytest
├── frontend/                 React + Vite
│   ├── src/
│   │   ├── components/       CityMap — карта на react-leaflet
│   │   └── config/           константы карты (центр Бишкека, тайлы OSM)
│   ├── Dockerfile            стадии deps / dev / build → nginx
│   └── nginx.conf            статика + прокси /api → backend
├── .github/workflows/ci.yml  GitHub Actions
├── docker-compose.yml        postgres, backend, frontend
├── docker-compose.dev.yml    overlay для разработки: hot reload фронта и бэка
├── .env.example
├── DEVLOG.md                 журнал решений и допущений
└── PROMPTS.md                промпты владельца проекта
```

## CI

GitHub Actions запускается на push в `main` и на pull request'ах:

- **backend** — `uv sync --locked`, `ruff check`, `ruff format --check`, `pytest`;
- **frontend** — `npm ci`, `npm run lint`, `npm run build`.

## Процесс разработки

- В `main` попадают только смерженные pull request'ы. Работа ведётся в ветках `feature/*`,
  PR открывается через `gh pr create` с описанием «что сделано / как проверить / чеклист».
- Коммиты небольшие, перед каждым — тесты и линт.
- Решения с датой, временем и обоснованием — в [`DEVLOG.md`](DEVLOG.md), промпты — в [`PROMPTS.md`](PROMPTS.md).
