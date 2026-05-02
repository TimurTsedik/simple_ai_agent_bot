# simple_AI_agent_bot

![simple_AI_agent_bot logo](logo.png)

Монолитный AI‑агент, которого действительно хочется “потрогать руками”: Telegram‑бот с голосом→текст, управляемым agentic loop, набором tools, Markdown skills/памятью и web‑админкой для наблюдаемости.  
Если ты любишь системы, где можно **видеть каждый шаг**, **воспроизводить run**, **контролировать tool‑вызовы** и **не ловить магию “оно само что-то сделало”** — тебе сюда.

![Admin dashboard](image.png)

## Оглавление

- [Почему интересно попробовать](#почему-интересно-попробовать)
- [Что умеет](#что-умеет-главные-фичи)
- [Use cases (сценарии)](#use-cases-сценарии)
- [Быстрый старт (локально)](#быстрый-старт-локально)
- [Веб-админка](#веб-админка)
- [Конфигурация](#конфигурация)
- [Voice-to-text (Telegram голосовые → текст)](#voice-to-text-telegram-голосовые--текст)
- [Инструменты и их настройки (`tools.yaml`)](#инструменты-и-их-настройки-toolsyaml)
- [Scheduler и reminders](#scheduler-и-reminders)
- [Запуск тестов](#запуск-тестов)
- [Production deploy (VPS + GitHub Actions + Docker Compose)](#production-deploy-vps--github-actions--docker-compose)
- [Частые проблемы](#частые-проблемы)
- [История развития](#история-развития)

### Почему интересно попробовать
- **Живой агент в Telegram**: пиши текстом или голосом — дальше всё идёт по одному пайплайну.
- **Управляемость**: строгий runtime‑контракт (`tool_call`/`final`/`stop`), лимиты, repair‑pass, анти‑циклы.
- **Наблюдаемость “из коробки”**: каждый run сохраняется на диск вместе с prompt snapshot, raw/parsed ответами модели, tool calls/results и observations.
- **Skills как продуктовая логика**: поведение/форматы живут в Markdown‑skills (можно читать и править), а не “в коде где-то глубоко”.
- **Scheduler + reminders**: планировщик внутренних run‑ов + напоминания, которые хранятся в `schedules.yaml` и автоматически чистятся после отработки.

### Что умеет (главные фичи)
- **Telegram‑бот**: allowlist по user id, команды `/start`, `/health`, `/reset`, `/context`.
- **Voice‑to‑text**: `message.voice` и `message.audio` → `faster-whisper` → транскрипт → обычный агентский пайплайн.
- **Agent runtime**: шаги, лимиты времени/инструментов, repair‑pass на формат, anti‑loop guards; **до цикла** отдельный LLM‑шаг **LLM‑first routing** (`route_plan` в YAML): выбор активных skills, `allow_tool_calls`, `required_first_successful_tool_name`, `memory_mode`; при битом/пустом ответе включается **rule‑based fallback** (`routingSource=fallback` в run‑логе).
- **OpenRouter**: primary/secondary/tertiary модель + retry/fallback с логированием выбранной модели.
- **Tools**: `digest_telegram_news`, `user_topic_telegram_digest`, `read_email`, `web_search`, `read_memory_file`, `schedule_reminder`, `list_reminders`, `delete_reminder`, и др.
- **Skills & memory**: Markdown skills; релевантные skills задаёт роутер (см. выше), память recent/summary/long‑term; в сохранённом run доступны поля `routingPlan`, `routingSource`, `routingPromptSnapshot`, `routingDiagnostics`.
- **Web‑админка**: runs/logs/tools/skills/git, internal JSON API `/internal/*` под той же auth‑схемой.
- **Scheduler (variant B)**: periodic internal runs + reminders, state в `data/scheduler/jobs_state.json`.

## Use cases (сценарии)

Ниже — сценарии, ради которых этот проект реально удобно запускать и развивать.

1) **Личный Telegram‑агент “на каждый день”**  
   Пишешь в чат: “составь список дел”, “помоги сформулировать сообщение”, “объясни код”. Агент работает как обычный бот, но все шаги сохраняются в runs.

2) **Голосовые команды → действия**  
   Отправляешь voice: “напомни через минуту выпить воды” → voice→text → skill `schedule_reminder` → reminder попадает в `schedules.yaml` и отработает.

3) **Дайджест новостей из Telegram‑каналов**  
   “Сделай дайджест экономических новостей за последний час” → tool `digest_telegram_news` → аккуратный формат дайджеста (через skills).

4) **Email‑дайджест непрочитанных писем**  
   “Сделай дайджест непрочитанных писем” → tool `read_email` → агент собирает 3 категории и выдаёт компактный итог.

5) **Проверка качества prompt/skills на воспроизводимых run‑ах**  
   Меняешь skill‑файл, повторяешь запрос, смотришь “что изменилось” в `/runs/<runId>/steps` (prompt snapshot + tool results).

6) **Наблюдаемость и разбор ошибок без гадания**  
   Если “что-то не сработало” — в `data/runs/<runId>.json` видно: какой prompt ушёл в LLM, что модель ответила, какие tool calls были, какие ошибки вернулись, плюс **маршрутизация**: `routingPlan`, `routingSource` (`llm` или `fallback`), снимок промпта роутера и `routingFallbackReason` при падении до fallback.

7) **Scheduler для регулярных внутренних запусков**  
   Настраиваешь `schedules.yaml` — сервис сам запускает internal runs по расписанию (и пишет state в `data/scheduler/jobs_state.json`).

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

Дальше:
- web‑админка: `GET /login` → вставить admin token → `GET /runs`
- Telegram: напиши боту `/start`, затем любой запрос

## Конфигурация

- **Основной конфиг**: `app/config/config.yaml` (без секретов).
- **Секреты только через env**: `TELEGRAM_BOT_TOKEN`, `OPENROUTER_API_KEY`, `SESSION_COOKIE_SECRET`, `ADMIN_RAW_TOKENS`, `EMAIL_APP_PASSWORD`, опционально `ADMIN_TELEGRAM_USER_ID` (см. ниже).

**Multi-user (Telegram):** единый белый список — файл **`app.usersRegistryPath`** (по умолчанию `data/users/registry.yaml`): все `telegramUserId` оттуда могут общаться с ботом; рассылки scheduler/reminder уходят тем же списком. Добавление через веб **`/users`** (нужно `security.adminWritesEnabled: true`) или правка YAML реестра; при создании выделяется `sessions/telegramUser_<id>/` с автосгенерированными `tools.yaml` / `schedules.yaml` (минимальный каркас из кода, см. `app/config/defaultTenantSessionYaml.py`) и пустым контекстом (`long_term.md`, `summary.md`, `recent.md`). Поле `telegram.allowedUserIds` в конфиге больше не используется — список только в реестре. Каждый разрешённый пользователь получает tenant-ключ сессии `telegramUser:<id>`: краткосрочная память (`recent.md`, `summary.md`), долгосрочная (`long_term.md`), state digest и напоминания с `ownerMemoryPrincipalId` изолированы между пользователями. Веб-админка и список runs по умолчанию ограничены администратором: `adminTelegramUserId` в конфиге или **`ADMIN_TELEGRAM_USER_ID` в `.env`**. Перенос старых файлов памяти из общего корня в каталог tenant выполняется вручную при необходимости.

Требования к web-auth:
- `SESSION_COOKIE_SECRET` — минимум 32 символа
- `ADMIN_RAW_TOKENS` — CSV, 1..`security.maxAdminTokens` токенов
- каждый admin token — минимум 16 символов, только `A-Z a-z 0-9 . _ -`, без дублей

### Session id в текущем коде

- Входящие сообщения Telegram обрабатываются с **`sessionId` = `telegramUser:<telegramUserId>`** (см. `formatTelegramUserMemoryPrincipal`).
- Фильтр админки и дашборда по runs сравнивает **`sessionId` в индексе строго** с tenant админа. Если в **`data/runs/index.jsonl`** остались старые строки с **`telegram:<id>`**, их нужно нормализовать (см. **`scripts/normalize_runs_index_session_ids.py`**), иначе такие раны не попадут в выдачу админа.
- Scheduler и internal-run используют свои схемы session id (`scheduler:…`, нормализация через `normalizeScheduledInternalSessionId`); **новый** произвольный код не должен вводить **`telegram:`** как основной формат для Telegram-user tenant.

### Что выполняется при старте процесса

1. **`loadSettings`**: чтение YAML + env; **`tools.yaml`** и **`schedules.yaml`** администратора всегда в каталоге **`${memory.memoryRootPath}/sessions/telegramUser_<ADMIN_TELEGRAM_USER_ID>/`** (имена файлов фиксированы). Override путей в `config.yaml` **не поддерживается** (поля `tools.toolsConfigPath` / `scheduler.schedulesConfigPath` удалены — конфиг с ними не загрузится). При отсутствии файлов — запись минимальных шаблонов из **`defaultTenantSessionYaml.py`**. После загрузки в runtime доступны абсолютные пути: **`adminTenantToolsYamlPath`**, **`adminTenantSchedulesYamlPath`** (в т.ч. в `effectiveConfigSnapshot` ранов).
2. **`buildApplicationContainer`**: сбор зависимостей и use case без автоматических миграций дисковых данных.

### Миграция с legacy (`tools.toolsConfigPath` / `scheduler.schedulesConfigPath`)

- Удали из `app/config/config.yaml` строки **`tools.toolsConfigPath`** и **`scheduler.schedulesConfigPath`** (если остались).
- Перенеси содержимое старых глобальных `app/config/tools.yaml` / `app/config/schedules.yaml` в tenant-каталог администратора:
  - **`${memory.memoryRootPath}/sessions/telegramUser_<ADMIN_TELEGRAM_USER_ID>/tools.yaml`**
  - тот же каталог **`schedules.yaml`**
- Проверка: в логе рана или в `effectiveConfigSnapshot` должны быть **`adminTenantToolsYamlPath`** / **`adminTenantSchedulesYamlPath`** с путями внутри `data/memory/sessions/...`, а не в `app/config/`.
- Если конфиг всё ещё содержит legacy-ключи, **`loadSettings` упадёт** (запрещены лишние поля в секциях `tools` и `scheduler`).

## Веб-админка

- **Логин**: `GET /login` + `POST /login` (admin token из `ADMIN_RAW_TOKENS`), cookie TTL 12h.
- **Основные страницы**: `/`, `/runs`, `/logs`, `/tools`, `/skills`, `/config/tools`, `/git/status`, `/git/diff`.
- **Favicon/branding**:
  - используется `GET /favicon.ico` (файл `favicon.ico` в корне репозитория);
  - для favicon выставлены anti-cache заголовки (`Cache-Control: no-store`, `Pragma: no-cache`, `Expires: 0`);
  - в HTML используется версионирование URL (`/favicon.ico?v=1`) для стабильного cache-bust после замены иконки.
- **JSON API** (`/internal/*`): без сессии возвращают **401** (без редиректа на `/login`).
- **Read-only / writes enabled**:
  - по умолчанию админка в режиме read-only;
  - чтобы включить редактирование skills и `tools.yaml`, выставь `security.adminWritesEnabled: true` в `app/config/config.yaml` и перезапусти сервис.
  - важно: для редактирования skills в production `skills.skillsDirPath` должен указывать на writable директорию (рекомендуется `./data/skills`, см. `app/config/config.example.yaml`); иначе будет 500 из-за `PermissionError`.

## Time zone

- **Отображение времени в web-админке** настраивается через `app.displayTimeZone` в `app/config/config.yaml` (IANA zone, например `Europe/Moscow` или `Asia/Jerusalem`).
- Если `app.displayTimeZone` пустой или некорректный, отображение автоматически fallback в `UTC`.
- **Scheduler** (`schedule.allowedHourStart / allowedHourEnd` в tenant `schedules.yaml`) работает в **локальном времени сервера**.
- Для стабильности логики в tools/runtime часть вычислений ведётся в `UTC` (например, `sinceUnixTs: 0` для news digest трактуется как начало текущих суток UTC).

## Voice-to-text (Telegram голосовые → текст)

Поддерживается обработка `message.voice` и `message.audio` в Telegram: бот скачивает файл, распознаёт речь через `faster-whisper` и передаёт полученный текст в обычный пайплайн (`RunAgentUseCase`).

Настройки в `app/config/config.yaml` (см. `app/config/config.example.yaml`):
- `telegram.voiceLanguage`: подсказка языка (`ru`, `en`), пусто = авто
- `telegram.voiceModelName`: `tiny|base|small|medium|large-v3` (для VPS обычно старт с `small`)
- `telegram.voiceComputeType`: для CPU обычно `int8`
- `telegram.voiceMaxSeconds`: лимит длительности голосового для синхронной обработки
- `telegram.voiceMaxBytes`: лимит размера файла

Наблюдаемость:
- в `data/logs/run.jsonl` пишутся события:
  - `voice_transcription_started`
  - `voice_transcription_succeeded`
  - `voice_transcription_failed`

Troubleshooting:
- если распознавание падает на проде, проверь, что в образ добавлен `ffmpeg` (в `Dockerfile`) и что хватает CPU/RAM.

## Инструменты и их настройки (`tools.yaml`)

Часть настроек инструментов живёт в отдельном YAML-файле в **namespace памяти администратора** (тот же tenant, что и `long_term.md`):

`${memory.memoryRootPath}/sessions/telegramUser_<ADMIN_TELEGRAM_USER_ID>/tools.yaml`

(значение `ADMIN_TELEGRAM_USER_ID` — в `.env`, по умолчанию совпадает с владельцем админки.)

Рекомендуемый подход:
- при первом старте без файла приложение записывает в каталог сессии админа минимальный **`tools.yaml`** (тот же каркас, что при провижинге пользователя в `defaultTenantSessionYaml.py`); дальше правь уже файл в `sessions/telegramUser_<id>/tools.yaml`.

Что там настраивается:
- **`digest_telegram_news`**: необязательные дефолты `telegramNewsDigest.*` только для общего дайджеста (skill `telegram_news_digest`), когда в args не переданы каналы/фильтры; дайджесты **по теме** (`user_topic_telegram_digest`) эти списки не используют. В вызове доступны args `channels`, `topics`, `keywords`, `sinceHours`, `sinceUnixTs`, `maxItems`
- **`user_topic_telegram_digest`**: пользовательские тематические дайджесты; хранит каналы и ключевые слова в долгосрочной памяти (`digest_topic_config_json` в `long_term.md`), state непрочитанных — `data/state/telegram_digest_read_state.json` (рядом с `dataRootPath`); args `topic`, `channels`, `keywords`, `fetchUnread`, `deleteTopic`; сценарий и формат — skill `user_topic_telegram_digest`
- **`save_digest_preference`**: пишет строку предпочтений в долгосрочную память (`digest_pref_json` в `long_term.md`); вызывать после уточнения у пользователя
- **`save_email_preference`**: пишет строку email-предпочтений (`email_pref_json` в `long_term.md`) с полями `preferredSenders` (email/домены) и `preferredKeywords`; используется skill-ом `email_preference_feedback`
- **`read_email`**: `emailReader.*` (host/port/ssl/email/password и т.д.) в tenant `tools.yaml` конкретного пользователя

Путь к файлу **не настраивается**: используется только tenant-путь выше (см. `adminTelegramUserId` / `ADMIN_TELEGRAM_USER_ID`).

Изменения в `tools.yaml` применяются **без перезапуска**.

## Email-дайджест и категории

Email-дайджест строится агентом по skill-инструкциям `compose_digest` + `read_and_analyze_email` и всегда содержит ровно 3 категории (даже если какая-то пустая):

1. `Требуют ответа/действия или предпочтительные отправители` — письма, требующие действий (вопросы/просьбы/верификации/доставки/банковские/корпоративные действия), а также письма от **предпочтительных отправителей** из long-term памяти.
2. `Важные` — содержательные письма без явного действия (аналитика, профильные дайджесты, работа, личное); промо/реклама сюда не попадает.
3. `Остальное/мусор` — промо/реклама/рассылки/маркетинг/низкоценностные авто-уведомления соцсетей.

### Предпочтительные отправители (preferred senders)

- хранятся в `data/memory/long_term.md` строкой вида `- email_pref_json: {...}` (`kind=email_user_preference`);
- ключевые поля: `preferredSenders` (список email-адресов или доменов в нижнем регистре, например `research@aton.ru`, `alfabank.ru`), `preferredKeywords`, `userNote`;
- в run-prompt подставляются как блок **`## Email preference hints`** (только в long-term-only режиме памяти, см. ниже);
- сохраняются через tool `save_email_preference` (вызывается skill-ом `email_preference_feedback` после уточнения у пользователя).

Пример пользовательского сценария:
- "запомни, что письма от research@aton.ru важные и должны попадать в первую категорию" → `email_preference_feedback` → `save_email_preference`.

### Изоляция памяти для email-дайджеста

Если в **routing plan** задано `memory_mode: long_term_only` (обычно при сочетании `compose_digest + read_and_analyze_email`, например scheduler-job `email_digest_hourly`), `RunAgentUseCase` подаёт в prompt **только** блок Long-Term Memory (без Session Summary и Recent Messages), чтобы каждый периодический запуск дайджеста заново читал почту, не отвечая "уже было выше". При LLM‑fallback это же поведение включается, если rule‑based выбор skills совпал с этим сочетанием.

## Scheduler и reminders

Два режима:

- **Scheduler jobs**: регулярные внутренние run‑ы агента по интервалу и часовому окну.
- **Reminders**: напоминания, которые записываются в `schedules.yaml`, имеют `remainingRuns` и автоматически удаляются после завершения (если включена соответствующая логика).

Ниже описан общий формат файла расписаний (`schedules.yaml`) и как включить планировщик.

## Scheduler (variant B): автоматические запуски по расписанию

Встроенный планировщик запускает **внутренние run-ы агента** по расписанию (каждый job — своё расписание).

Файл расписаний по умолчанию живёт рядом с `tools.yaml` в namespace памяти администратора:

`${memory.memoryRootPath}/sessions/telegramUser_<ADMIN_TELEGRAM_USER_ID>/schedules.yaml`

Как включить:

1) В `app/config/config.yaml`:

```yaml
scheduler:
  enabled: true
  tickSeconds: 30
```

2) Если файла ещё нет, при старте создаётся минимальный `schedules.yaml` (`jobs: []` / `reminders: []`) в том же каталоге, что и `tools.yaml` админа; полный пример структуры — в разделе «Формат schedules.yaml» ниже (или скопируй существующий tenant-файл, например из `data/memory/sessions/telegramUser_<id>/schedules.yaml`).

Формат `schedules.yaml`:
- `jobs[]`:
  - `jobId` — уникальный ID job-а
  - `enabled` — включён/выключен
  - `schedule.intervalSeconds` — интервал в секундах (минимум 5)
  - `schedule.allowedHourStart / allowedHourEnd` — окно часов (например 8..23), локальное время сервера
  - `actionInternalRun.sessionId` — см. ниже (`scheduler:*` привязывается к tenant админа автоматически)
  - `actionInternalRun.message` — короткий intent-текст, который будет отправлен агенту как пользовательское сообщение
- `reminders[]`:
  - `reminderId`, `enabled`, `message`
  - `schedule.kind` (`daily|weekly`), `schedule.weekdays` (для `weekly`), `schedule.timeLocal`, `schedule.timeZone`, `schedule.remainingRuns`

Рекомендация:
- держи `actionInternalRun.message` максимально коротким (без длинных шаблонов формата ответа);
- правила формата/структуры ответа должны жить в skills (например `compose_digest`, `read_and_analyze_email`, `telegram_news_digest`).
- для напоминаний используй skill `schedule_reminder`: модель формирует JSON строго по schema tool-а, без NLP-парсинга текста пользователя внутри tool.

Важно: `scheduler.tickSeconds` задаётся только в `app/config/config.yaml`.

State jobs/reminders сохраняется в: `data/scheduler/jobs_state.json` (`jobsState` + `remindersState`).

Особенности reminder-функционала:
- фразы вида `через N минут/часов` конвертируются моделью в абсолютное `HH:MM` по `app.displayTimeZone` и сразу отправляются в `schedule_reminder` (без лишнего уточнения времени);
- для записи напоминаний файл расписаний в контейнере должен быть **writable** (не `:ro`); в `docker-compose.prod.yml` он монтируется в подкаталог `data/memory/sessions/...`;
- при ограничениях на создание `schedules.yaml.tmp` используется fallback-запись напрямую в целевой `schedules.yaml`.

**Фактический sessionId scheduler-job-ов.** Значение `scheduler:something` в YAML превращается внутри процесса в  
`telegramUser:<ADMIN_TELEGRAM_USER_ID>:scheduler:something` (соответствующая директория под `sessions/`, см. память Markdown store). Так весь контекст планировщика относится к tenant администратора; долгая память (long‑term) при этих запусках читается из того же профиля, что и основной пользователь‑админ.

## Запуск тестов

Запускай из venv из **корня репозитория** (чтобы пакет `app` находился на `PYTHONPATH`):

```bash
PYTHONPATH=. pytest
```

## Production deploy (VPS + GitHub Actions + Docker Compose)

Ниже — рекомендуемый production-процесс: GitHub Actions собирает Docker image и публикует в GHCR, а VPS делает `docker compose pull && up -d`.

### Что уже настроено для деплоя (чеклист операций)

1) В репозитории добавлен ручной workflow GitHub Actions:
- файл: `.github/workflows/deploy_vps_manual.yml`
- триггер: `workflow_dispatch` (ручной запуск)
- входной параметр: `ref` (ветка / tag / commit SHA)

2) В workflow настроены права и пайплайн сборки:
- `permissions`: `contents: read`, `packages: write`
- checkout выбранного `ref`
- установка Python 3.12 и зависимостей
- прогон unit-тестов: `PYTHONPATH=. pytest -q`
- сборка Docker image и push в GHCR
- теги image: `ghcr.io/<owner>/<repo>:sha-<shortSha>` и `manual-latest`

3) В workflow настроен отдельный deploy job на VPS:
- environment: `production`
- установка SSH-ключа из GitHub Secret
- добавление VPS в `known_hosts`
- загрузка на VPS файлов деплоя:
  - `docker-compose.prod.yml`
  - `scripts/deploy_prod.sh`
- выставление executable-права на `scripts/deploy_prod.sh`
- запуск деплоя по SSH с передачей `APP_IMAGE`, `GHCR_USERNAME`, `GHCR_TOKEN`

4) На VPS подготовлена структура для деплоя:
- директория приложения (по умолчанию: `/opt/simple_ai_agent_bot`)
- подкаталоги: `scripts`, `config`, `data`
- персистентные данные вынесены в `data/` (runs/logs/memory/scheduler)

5) Для GitHub Environment `production` используются секреты:
- `VPS_HOST`, `VPS_PORT`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_APP_DIR`
- `GHCR_USERNAME`, `GHCR_TOKEN`

6) Подготовлена эксплуатационная схема выката:
- деплой запускается вручную через Actions (`Deploy to VPS (manual)`)
- health-check выполняется на этапе deploy job
- rollback выполняется повторным запуском workflow на нужный предыдущий commit/ref

### 1) Одноразовая подготовка VPS

На VPS нужно:
- Docker Engine + Docker Compose plugin
- пользователь для деплоя (например `deploy`) с доступом к Docker
- открыть входящий порт `8000/tcp` (пока доступ по IP; HTTPS позже)

### 2) Каталог приложения на VPS

На VPS создаём директорию (пример: `/opt/simple_ai_agent_bot`) со структурой:

```text
/opt/simple_ai_agent_bot/
  docker-compose.prod.yml
  .env
  config/
    config.yaml
    schedules.yaml         # только если scheduler.enabled=true
  config/tools.yaml        # опционально: монтируется в tenant-файл под data/memory/... (см. docker-compose.prod.yml)
  data/                    # персистентные данные
    runs/
    logs/
    memory/
    scheduler/             # если включён scheduler
```

Важно:
- `config/config.yaml` обязателен: приложение стартует из `app/config/config.yaml`, а в контейнере он монтируется из `./config`.
- `data/` обязательно монтировать, иначе потеряешь runs/logs/memory при пересоздании контейнера.
- Не монтируй `./config` целиком поверх `/app/app/config`: это перекроет python-модули (`settingsModels.py` и т.д.). Монтируются только YAML-файлы.
- `config/schedules.yaml` должен монтироваться без `:ro`, иначе `schedule_reminder` не сможет сохранять/обновлять напоминания.
- Права на `data/`: контейнер должен иметь право писать в `./data` (логи/память/runs). В `docker-compose.prod.yml` используется `user: "1001:1001"` (UID/GID пользователя `deploy` на VPS). Если UID/GID на сервере другой — обнови значение.

### Скачать текущие `run`-файлы, логи и конфиги с VPS

Из корня репозитория:

```bash
scripts/fetch_server_snapshot.sh \
  --host 187.124.165.192 \
  --user deploy \
  --key ~/.ssh/simple_ai_agent_bot_vps_deploy \
  --port 22 \
  --remote-app-dir /opt/simple_ai_agent_bot \
  --local-project-root .```

### 3) Секреты и конфиги на VPS

Файл `.env` (в директории приложения на VPS) должен содержать минимум:

```env
TELEGRAM_BOT_TOKEN=...
OPENROUTER_API_KEY=...
SESSION_COOKIE_SECRET=your-long-secret-at-least-32-chars
ADMIN_RAW_TOKENS=admin_token_123456,admin_token_654321
EMAIL_APP_PASSWORD=...
```

Файл `config/config.yaml` — по образцу `app/config/config.example.yaml` (обрати внимание на `app.displayTimeZone` и `scheduler.*`).

### 4) Проверка локально на VPS (ручной запуск один раз)

В директории приложения на VPS:

```bash
APP_IMAGE=ghcr.io/<owner>/<repo>:sha-<shortSha> ./scripts/deploy_prod.sh
curl -fsS http://127.0.0.1:8000/health
```

### 5) GitHub Actions: ручной деплой

Рекомендуемый режим на старте — **только вручную** (`workflow_dispatch`), чтобы не выкатывать случайно каждый push в `main`.

Workflow делает:
- build + push Docker image в `ghcr.io`
- ssh на VPS, обновление compose-файлов и перезапуск через `scripts/deploy_prod.sh`

#### GitHub Secrets (Environment: production)

Workflow ожидает следующие секреты (Settings → Environments → `production` → Secrets):

- **`VPS_HOST`**: `187.124.165.192`
- **`VPS_PORT`**: `22` (или ваш SSH-порт)
- **`VPS_USER`**: например `deploy`
- **`VPS_SSH_KEY`**: приватный ключ (ed25519/rsa) для SSH-доступа на VPS
- **`VPS_APP_DIR`**: директория приложения на VPS, например `/opt/simple_ai_agent_bot` (если не задано, workflow использует этот путь по умолчанию)
- **`GHCR_USERNAME`**: username для `docker login ghcr.io` (часто owner/аккаунт)
- **`GHCR_TOKEN`**: токен для чтения образов из GHCR на VPS (минимум `read:packages`; если репозиторий/пакет приватный — обязателен)

#### Как запустить деплой

1) Открой Actions → workflow `Deploy to VPS (manual)`.\n
2) Нажми **Run workflow** и оставь `ref=main` (или укажи нужный tag/commit).\n
3) Дожидайся зелёного `Deploy` job — он заканчивается health-check’ом `/health` на VPS.\n
### Rollback

Откат — это повторный запуск workflow с более старым `sha` (образ тегируется по коммиту).

## Бэкапы `data/` на VPS (tar + cron)

В `data/` хранятся `runs/logs/memory` (и состояние scheduler при включении), поэтому имеет смысл делать регулярные бэкапы.

### Скрипт бэкапа

В репозитории есть скрипт [`scripts/backup_data.sh`](scripts/backup_data.sh). На VPS его можно запускать вручную или по cron.\n

Параметры через env (все опциональны):
- `BASE_DIR` (default: `/opt/simple_ai_agent_bot`)
- `SRC_DIR` (default: `${BASE_DIR}/data`)
- `DST_DIR` (default: `${BASE_DIR}/backups`)
- `RETENTION_DAYS` (default: `14`)

### Пример cron (ежедневно)

На VPS под пользователем `deploy`:

```bash
crontab -e
```

Добавь:

```cron
15 3 * * * /opt/simple_ai_agent_bot/scripts/backup_data.sh >> /opt/simple_ai_agent_bot/backups/backup.log 2>&1
```

## Частые проблемы

- **`No module named pytest`**: проверь, что активировал venv (`source .venv/bin/activate`) или запускай `./.venv/bin/python -m pytest -q`.
- **Ошибка валидации settings при старте**: проверь `.env` (секреты обязательны) и формат `ADMIN_RAW_TOKENS`.

---

## История развития

История развития, этапы и важные решения ведутся отдельно: [`how_project_was_developed.md`](how_project_was_developed.md).
