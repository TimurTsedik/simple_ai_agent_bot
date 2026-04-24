# simple_AI_agent_bot

Монолитный MVP AI-агент с управляемым agentic loop, Telegram transport, fallback по OpenRouter и read-only admin surface.

## Что уже сделано (Этапы 1-2)

- каркас layered-архитектуры;
- typed-конфиг с fail-fast загрузкой;
- базовый FastAPI app и health endpoint;
- базовый Telegram polling skeleton с allowlist-проверкой;
- базовые доменные модели и протоколы;
- strict JSON output parser (`tool_call` / `final` / `stop`);
- базовый agent loop с лимитами шагов/времени/tool calls и controlled stop;
- skeleton prompt builder с ограничением размера;
- внутренний endpoint для отладки запуска loop: `POST /internal/run`;
- unit-тесты на конфиг, Telegram authorization behavior, parser и loop.

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
