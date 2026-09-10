# Transport Sharing

Сервис шеринга самокатов — тестовое задание на вакансию Agentic Developer.

Клиент-серверное приложение: отдельный бэкенд (REST API + WebSocket), отдельный фронтенд (SPA
с картой), реляционная база и симулятор телеметрии. Всё поднимается одной командой через Docker
Compose.

## Стек

| Слой | Технологии |
| --- | --- |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (async, asyncpg), Alembic, pydantic-settings; uv, ruff, pytest |
| Frontend | React 19, Vite, TypeScript, react-leaflet + OpenStreetMap; oxlint, vitest |
| Simulator | Python 3.12, httpx; uv, ruff, pytest |
| База | PostgreSQL 16 |
| Инфраструктура | Docker Compose, nginx (раздача фронтенда и прокси `/api`, включая WebSocket), GitHub Actions |

## Быстрый старт (Docker)

Нужен Docker с Compose v2.

```bash
cp .env.example .env        # необязательно: у всех переменных есть значения по умолчанию
docker compose up --build
```

Поднимаются четыре сервиса: `db`, `backend` (применяет миграции и сидит 18 самокатов), `frontend`
и `simulator`, который двигает самокаты по Бишкеку и шлёт телеметрию. Через несколько секунд после
старта на карте появляются маркеры, и часть из них едет.

| Что | Адрес |
| --- | --- |
| Карта (фронтенд) | http://localhost:3000 |
| Список самокатов | http://localhost:3000/api/scooters (и http://localhost:8000/api/scooters напрямую) |
| WebSocket с обновлениями | `ws://localhost:3000/api/ws` |
| Health / readiness бэкенда | http://localhost:8000/api/health → `{"status":"ok"}`, http://localhost:8000/api/health/db |
| Swagger UI | http://localhost:8000/api/docs |
| PostgreSQL | `localhost:5432` (или `POSTGRES_PORT` из `.env`), пользователь/пароль/база — `scooter` |

Остановить: `docker compose down` (вместе с данными базы — `docker compose down -v`).

### Что проверить на карте

- Маркеры окрашены по статусу (легенда в шапке): свободен, забронирован, в поездке, недоступен.
  В попапе — код, заряд и статус.
- Откройте две вкладки: обе получают одни и те же обновления по WebSocket, маркеры двигаются
  синхронно, без перезагрузки страницы. Индикатор в шапке показывает состояние соединения.
- Самокат с зарядом ниже `LOW_BATTERY_THRESHOLD` (15 %) становится недоступным и показывается серым.
  В сиде таких два (`KG-006`, `KG-012`); симулятор «заряжает» недоступные самокаты через
  `SIM_RECHARGE_SECONDS` (3 минуты), а у едущих заряд падает, так что серые маркеры появляются и
  позже. Правило можно вызвать вручную:

```bash
curl -X POST http://localhost:8000/api/telemetry -H "Content-Type: application/json" \
  -d '{"code": "KG-001", "lat": 42.8756, "lon": 74.6036, "battery": 5}'
```

## API

| Метод и путь | Назначение |
| --- | --- |
| `GET /api/health` | liveness, без обращения к базе |
| `GET /api/health/db` | readiness: `SELECT 1`, при недоступной базе — 503 |
| `GET /api/scooters` | все самокаты: `code`, `lat`, `lon`, `battery`, `status`, `updated_at` |
| `POST /api/telemetry` | `{code, lat, lon, battery}` от самоката; отвечает актуальным состоянием, 404 для неизвестного кода |
| `WS /api/ws` | сервер шлёт `{"type": "scooter.updated", "scooter": {...}}` после каждой телеметрии |

Правило заряда: если `battery` строго ниже порога, самокат получает статус `unavailable`; когда
телеметрия приносит заряд не ниже порога, недоступный самокат снова становится `available`.
Статусы `reserved` и `riding` телеметрия не меняет.

## Режим разработки (hot reload)

Стек из «Быстрого старта» собирает фронтенд в статику, поэтому каждое изменение кода требует
пересборки образа. Для разработки есть overlay `docker-compose.dev.yml`:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

| Что | Как работает в dev-режиме |
| --- | --- |
| Фронтенд | Vite dev server на http://localhost:5173 с HMR; каталог `frontend/` примонтирован в контейнер, `/api` и WebSocket проксируются на бэкенд |
| Бэкенд | `uvicorn --reload` на http://localhost:8000; примонтированы `backend/app` и `backend/alembic` |
| База и симулятор | те же, что в обычном режиме |

После изменения зависимостей (`package.json`, `pyproject.toml`) пересоберите образы: запустите ту же
команду с `--build -V` (`-V` обновляет `node_modules` внутри контейнера фронтенда).

Порт dev-сервера фиксирован (5173): HMR-клиент Vite подключается к порту страницы. Работать без Docker
можно так же удобно — см. раздел «Локальная разработка без Docker».

## Локальная разработка без Docker

### Backend

Нужен [uv](https://docs.astral.sh/uv/) — он сам поставит Python 3.12 из `backend/.python-version`.
Для интеграционных тестов и запуска нужна база: `docker compose up -d db`.

```bash
cd backend
uv sync                                  # .venv + зависимости (включая dev)
uv run alembic upgrade head              # миграции
uv run python -m app.seed                # демо-парк (только в пустую таблицу)
uv run uvicorn app.main:app --reload     # http://localhost:8000/api/health
uv run pytest                            # все тесты, включая интеграционные с базой
uv run pytest -m "not db"                # только быстрые тесты без базы
uv run ruff check . && uv run ruff format --check .
```

Настройки читаются из переменных окружения либо из `.env` в корне репозитория и/или в `backend/`
(см. `app/core/config.py`). Интеграционные тесты сами создают базу `<POSTGRES_DB>_test`, прогоняют
в ней миграции и удаляют её после прогона; каждый тест выполняется в транзакции с откатом.

Если порт 5432 на хосте занят (например, локально установленным PostgreSQL), задайте в `.env`
другой `POSTGRES_PORT` (скажем, `15432`): compose опубликует базу на нём, а бэкенд и тесты подхватят
значение из того же `.env`.

### Frontend

Нужен Node.js 22+.

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173, /api и WebSocket проксируются на localhost:8000
npm run lint     # oxlint
npm test         # vitest
npm run build    # tsc + vite build → dist/
```

Адрес бэкенда для dev-прокси можно переопределить переменной `VITE_API_PROXY_TARGET`.

### Simulator

```bash
cd simulator
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
BACKEND_URL=http://localhost:8000 uv run python -m scootersim
```

## Симулятор

Отдельный сервис `simulator` (пакет `scootersim`): берёт список самокатов у бэкенда, часть из них
отправляет в поездки к случайным точкам центра Бишкека, у едущих падает заряд, и раз в
`SIM_INTERVAL_SECONDS` шлёт телеметрию по HTTP. Самокат, который бэкенд пометил недоступным,
«заряжает техник» через `SIM_RECHARGE_SECONDS`. Недоступность бэкенда симулятор переживает: пишет
предупреждение, ждёт с экспоненциальной паузой (до 30 с) и пробует снова, процесс не завершается.

| Переменная | По умолчанию | Назначение |
| --- | --- | --- |
| `BACKEND_URL` | `http://localhost:8000` (в compose — `http://backend:8000`) | адрес API |
| `SIM_ACTIVE_SCOOTERS` | `6` | сколько самокатов едут одновременно |
| `SIM_INTERVAL_SECONDS` | `1.5` | период тика и отправки телеметрии |
| `SIM_SPEED_KMH` | `40` | скорость (завышена, чтобы движение было заметно) |
| `SIM_DRAIN_PER_KM` | `4` | расход заряда в процентах на километр (завышен для демо) |
| `SIM_RECHARGE_SECONDS` | `180` | через сколько «техник» заряжает недоступный самокат |
| `SIM_MIN_RIDE_BATTERY` | `20` | ниже этого заряда самокат не начинает поездку |
| `SIM_HEARTBEAT_TICKS` | `20` | как часто стоящие самокаты шлют телеметрию |

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
| `LOW_BATTERY_THRESHOLD` | `15` | порог заряда, ниже которого самокат недоступен |
| `SIM_ACTIVE_SCOOTERS` / `SIM_INTERVAL_SECONDS` | `6` / `1.5` | параметры симулятора (остальные — в разделе «Симулятор») |

## Структура репозитория

```
.
├── backend/                  FastAPI-приложение
│   ├── app/
│   │   ├── api/              роутеры: health, scooters (telemetry, list), ws
│   │   ├── core/             настройки (pydantic-settings)
│   │   ├── db/               Base, async engine, сессии
│   │   ├── models/           ORM-модели (Scooter, ScooterStatus)
│   │   ├── realtime/         хаб WebSocket-соединений и события
│   │   ├── schemas/          Pydantic-схемы
│   │   ├── services/         бизнес-логика (телеметрия, правило заряда)
│   │   └── seed.py           демо-парк самокатов
│   ├── alembic/              миграции (async env)
│   ├── tests/                pytest: юнит + интеграционные с PostgreSQL
│   ├── Dockerfile
│   └── pyproject.toml        зависимости, ruff, pytest
├── frontend/                 React + Vite
│   ├── src/
│   │   ├── api/              типы и HTTP-клиент
│   │   ├── components/       CityMap, ScooterMarkers
│   │   ├── config/           константы карты и статусов
│   │   └── realtime/         стор самокатов и хук WebSocket
│   ├── Dockerfile            стадии deps / dev / build → nginx
│   └── nginx.conf            статика + прокси /api и /api/ws → backend
├── simulator/                симулятор телеметрии (пакет scootersim)
│   ├── scootersim/           config, geo, fleet, client, runner
│   ├── tests/
│   └── Dockerfile
├── .github/workflows/ci.yml  GitHub Actions
├── docker-compose.yml        postgres, backend, frontend, simulator
├── docker-compose.dev.yml    overlay для разработки: hot reload фронта и бэка
├── .env.example
├── DEVLOG.md                 журнал решений и допущений
└── PROMPTS.md                промпты владельца проекта
```

## CI

GitHub Actions запускается на push в `main` и на pull request'ах:

- **backend** — сервис `postgres:16`, `uv sync --locked`, `ruff check`, `ruff format --check`, `pytest`
  (включая интеграционные тесты с базой);
- **simulator** — `uv sync --locked`, `ruff check`, `ruff format --check`, `pytest`;
- **frontend** — `npm ci`, `npm run lint`, `npm test`, `npm run build`.

## Что дальше

Осознанные упрощения этого этапа и то, что сделали бы следующим заходом:

- **Движение по улицам.** Симулятор ведёт самокаты по прямой между случайными точками и проходит
  сквозь дома. Следующий шаг — маршруты по дорогам: OSRM (готовый роутер поверх данных OSM, есть
  публичный демо-сервер и Docker-образ) либо собственный граф дорог из выгрузки OSM (osmnx).
- **Разрядка во время поездки.** Сейчас заряд ниже порога делает самокат недоступным при любом
  статусе. С появлением поездок такой самокат должен сначала завершить поездку со счётом и
  письмом пользователю (TODO в `app/services/scooters.py`).
- **Бронирование и поездки.** Статусы `reserved` и `riding` пока никем не выставляются; они
  появятся вместе с API бронирования, старта и завершения поездки.
- **Реалтайм на несколько воркеров.** Хаб WebSocket живёт в одном процессе; при масштабировании
  бэкенда потребуется общий брокер (Redis pub/sub).

## Процесс разработки

- В `main` попадают только смерженные pull request'ы. Работа ведётся в ветках `feature/*`,
  PR открывается через `gh pr create` с описанием «что сделано / как проверить / чеклист».
- Коммиты небольшие, перед каждым — тесты и линт.
- Решения с датой, временем и обоснованием — в [`DEVLOG.md`](DEVLOG.md), промпты — в [`PROMPTS.md`](PROMPTS.md).
