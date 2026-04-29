# simple_AI_agent_bot

Монолитный MVP AI-агент с управляемым agentic loop, Telegram-ботом, fallback по OpenRouter и веб-админкой для наблюдаемости.

![Admin dashboard](image.png)

## Быстрый старт (локально)

1) Создать venv и поставить зависимости:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Подготовить конфиг и `.env`:

```bash
cp app/config/config.example.yaml app/config/config.yaml
cp .env.example .env
```

3) Заполнить `.env`:

```env
TELEGRAM_BOT_TOKEN=...
OPENROUTER_API_KEY=...
SESSION_COOKIE_SECRET=your-long-secret-at-least-32-chars
ADMIN_RAW_TOKENS=admin_token_123456,admin_token_654321
EMAIL_APP_PASSWORD=your_gmail_app_password
```

4) Запустить приложение:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Переменные из окружения терминала имеют приоритет над значениями из `.env`.

## Что это умеет (коротко)

- **Telegram**: личные чаты, allowlist по user id, команды `/start`, `/health`, `/reset`, `/context`.
- **Agent runtime**: strict JSON-выход, agentic loop, лимиты по шагам/времени/tool calls, repair-pass для JSON.
- **OpenRouter**: primary/secondary/tertiary модели, retry и fallback с логированием.
- **Инструменты (tools)**: `digest_telegram_news`, `save_digest_preference`, `web_search`, `read_memory_file`, `read_email`.
- **Skills & memory**: Markdown skills, rule-based selection, память recent/summary/long-term.
- **Observability**: runs в `data/runs/<runId>.json` + `index.jsonl`, JSONL-логи, web UI (`/`, `/runs`, `/logs`, `/tools`, `/skills`, `/git/*`).
- **Scheduler (variant B)**: встроенные запуски внутренних run-ов по расписанию.

## Веб-админка

- **Логин**: `GET /login` + `POST /login` (admin token из `ADMIN_RAW_TOKENS`), cookie TTL 12h.
- **Основные страницы**: `/`, `/runs`, `/logs`, `/tools`, `/skills`, `/config/tools`, `/git/status`, `/git/diff`.
- **Read-only / writes enabled**:
  - по умолчанию админка в режиме read-only;
  - чтобы включить редактирование skills и `tools.yaml`, выставь `security.adminWritesEnabled: true` в `app/config/config.yaml` и перезапусти сервис.

## Конфиги и секреты

- **Основной конфиг**: `app/config/config.yaml` (без секретов).
- **Секреты только через env**: `TELEGRAM_BOT_TOKEN`, `OPENROUTER_API_KEY`, `SESSION_COOKIE_SECRET`, `ADMIN_RAW_TOKENS`, `EMAIL_APP_PASSWORD`.

Требования к web-auth:
- `SESSION_COOKIE_SECRET` — минимум 32 символа
- `ADMIN_RAW_TOKENS` — CSV, 1..`security.maxAdminTokens` токенов
- каждый admin token — минимум 16 символов, только `A-Z a-z 0-9 . _ -`, без дублей

## Инструменты и их настройки (`tools.yaml`)

Часть настроек инструментов вынесена в `app/config/tools.yaml`.

Рекомендуемый подход:
- держать в git файл-пример `app/config/tools.example.yaml`
- локально копировать его в `app/config/tools.yaml` (он добавлен в `.gitignore`)

Что там настраивается:
- **`digest_telegram_news`**: `telegramNewsDigest.digestChannelUsernames`, `telegramNewsDigest.portfolioTickers`, `telegramNewsDigest.digestSemanticKeywords`; в вызове доступны args `channels`, `topics`, `keywords`, `sinceHours`, `sinceUnixTs`, `maxItems`
- **`save_digest_preference`**: пишет строку предпочтений в долгосрочную память (`digest_pref_json` в `long_term.md`); вызывать после уточнения у пользователя
- **`read_email`**: `emailReader.*` (host/port/ssl/email и т.д.), пароль — только в env: `EMAIL_APP_PASSWORD`

Путь к `tools.yaml` задаётся в `app/config/config.yaml`:

```yaml
tools:
  toolsConfigPath: "./app/config/tools.yaml"
```

Изменения в `tools.yaml` применяются **без перезапуска**.

## Scheduler (variant B): автоматические запуски по расписанию

Встроенный планировщик запускает **внутренние run-ы агента** по расписанию (каждый job — своё расписание).

Как включить:

1) В `app/config/config.yaml`:

```yaml
scheduler:
  enabled: true
  schedulesConfigPath: "./app/config/schedules.yaml"
  tickSeconds: 30
```

2) Создать файл расписаний:

```bash
cp app/config/schedules.example.yaml app/config/schedules.yaml
```

Формат `app/config/schedules.yaml`:
- `jobs[]`:
  - `jobId` — уникальный ID job-а
  - `enabled` — включён/выключен
  - `schedule.intervalSeconds` — интервал в секундах (минимум 5)
  - `schedule.allowedHourStart / allowedHourEnd` — окно часов (например 8..23), локальное время сервера
  - `actionInternalRun.sessionId` — sessionId для этих run-ов (удобно выделять `scheduler:*`)
  - `actionInternalRun.message` — текст, который будет отправлен агенту как пользовательское сообщение

Важно: `scheduler.tickSeconds` задаётся только в `app/config/config.yaml`.

State jobs сохраняется в: `data/scheduler/jobs_state.json` (lastRunAt/lastStatus/lastRunId).

## Запуск тестов

Запускай из venv:

```bash
pytest
```

## Частые проблемы

- **`No module named pytest`**: проверь, что активировал venv (`source .venv/bin/activate`) или запускай `./.venv/bin/python -m pytest -q`.
- **Ошибка валидации settings при старте**: проверь `.env` (секреты обязательны) и формат `ADMIN_RAW_TOKENS`.

---

## Примечание (история)

- каркас layered-архитектуры;
- typed-конфиг с fail-fast загрузкой;
- базовый FastAPI app и health endpoint;
- базовый Telegram polling skeleton с allowlist-проверкой;
- базовые доменные модели и протоколы;
- strict JSON output parser (`tool_call` / `final` / `stop`);
- базовый agent loop с лимитами шагов/времени/tool calls и controlled stop;
- skeleton prompt builder с ограничением размера;
- tools subsystem: registry, schemas, metadata renderer, execution coordinator;
- standardized tool result envelope и стандартные error-codes;
- read-only tools:
  - `digest_telegram_news`
  - `web_search`
  - `read_memory_file`
  - `read_email`;
- OpenRouter client integration;
- retries + fallback policy по primary/secondary/tertiary;
- raw provider response logging и fallback events в JSONL;
- markdown skills store и rule-based skill selection;
- markdown memory store:
  - recent messages
  - session summary
  - long-term memory;
- memory policy для отбора `memory_candidates`;
- обновление summary/long-term после завершения run;
- внутренний endpoint для отладки запуска loop: `POST /internal/run`;
- web просмотр логов:
  - `GET /logs`
  - `GET /internal/logs`;
- Telegram polling подключен в lifecycle FastAPI (`startup/shutdown`);
- Telegram команды:
  - `/start`
  - `/health`
  - `/reset`;
- run persistence model:
  - `data/runs/<runId>.json`
  - `data/runs/index.jsonl`;
- в run trace сохраняются:
  - prompt snapshot
  - raw/parsed model responses
  - tool calls/results
  - observations
  - effective config snapshot (masked);
- run read API:
  - `GET /internal/runs`
  - `GET /internal/runs/{runId}`
  - `GET /internal/runs/{runId}/steps`;
- web страницы runs:
  - `GET /runs`
  - `GET /runs/{runId}`
  - `GET /runs/{runId}/steps`;
- web auth для admin surface:
  - `GET /login`
  - `POST /login` (вход по admin token из env)
  - `POST /logout`
  - `/logs`, `/runs`, `/runs/{runId}`, `/runs/{runId}/steps` защищены cookie-сессией;
- git admin pages:
  - `GET /git/status`
  - `GET /git/diff`
  - внутренние API: `GET /internal/git/status`, `GET /internal/git/diff`;
- unit-тесты на конфиг, Telegram authorization behavior, parser, loop, tool executor, llm fallback, skills и memory.
