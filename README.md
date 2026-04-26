# simple_AI_agent_bot

Монолитный MVP AI-агент с управляемым agentic loop, Telegram transport, fallback по OpenRouter и read-only admin surface.

## Что уже сделано (Этапы 1-7)

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
  - `read_memory_file`;
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

## Локальный запуск

1. Установить зависимости:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Скопировать пример конфига:

```bash
cp app/config/config.example.yaml app/config/config.yaml
```

3. Создать `.env`:

```bash
cp .env.example .env
```

4. Заполнить `.env`:

```env
TELEGRAM_BOT_TOKEN=...
OPENROUTER_API_KEY=...
SESSION_COOKIE_SECRET=...
ADMIN_RAW_TOKENS=token1,token2
```

5. Запустить приложение:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Переменные из окружения терминала имеют приоритет над значениями из `.env`.

## Запуск тестов

```bash
pytest
```
