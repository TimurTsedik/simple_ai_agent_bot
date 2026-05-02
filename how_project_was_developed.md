# Как развивался проект simple_AI_agent_bot

Живой журнал разработки: цели, этапы, важные решения и отходы от первоначальных гипотез.  
**Соглашение:** после существенных изменений в коде или поведении системы этот файл нужно дополнять короткой записью в конце раздела «Журнал изменений» (дата + что сделано).

Исходная спецификация: [`specs.md`](specs.md). Краткий чеклист возможностей и запуска: [`README.md`](README.md).

---

## 1. Зачем проект

Собственный управляемый AI-агент с agentic loop: Telegram как основной транспорт, Python-tools, Markdown skills и память, OpenRouter с fallback, структурированные логи и read-only веб-интерфейс для наблюдаемости. Архитектура — **layered monolith**, MVP без vector DB, RAG и multi-agent.

---

## 2. Зафиксированный стек и ограничения MVP

| Область | Выбор |
|--------|--------|
| Язык | Python 3.12 |
| Зависимости | `pip` + `requirements.txt` |
| HTTP | FastAPI, синхронные обработчики на первом этапе; Uvicorn |
| LLM | OpenRouter, три модели (primary / secondary / tertiary), retry и fallback по политике |
| Хранение | Файлы: YAML config, Markdown skills/memory, JSON runs, JSONL logs |
| Telegram | Polling, только личные чаты, текст; allowlist по user id |
| Web | SSR HTML + минимальные internal JSON API; cookie-сессия после входа по admin token |

Секреты: через env и `.env` (пример `.env.example`), fail-fast при невалидном конфиге.

---

## 3. Этапы по плану из specs (1–7)

Развитие шло **пошагово**: сначала тесты и каркас, затем рабочий прогон.

1. **Skeleton** — структура каталогов, загрузка настроек, базовый FastAPI, health, зачатки Telegram и логирования.
2. **Agent loop MVP** — строгий JSON-контракт ответа модели (`tool_call` / `final` / `stop`), парсер, лимиты шагов/времени/tool calls, prompt builder с усечением.
3. **Tools** — реестр, JSON-схемы аргументов, coordinator с timeout и усечением вывода, единый envelope результата.
4. **OpenRouter** — HTTP-клиент, `LlmService` с повторами и fallback, логирование сырых ответов (в т.ч. с маскированием reasoning-полей для логов).
5. **Skills и memory** — Markdown-файлы, rule-based выбор skills (в т.ч. отдельное правило «нужен ли tool» для новостного дайджеста), память recent + session summary + long-term, политика по `memory_candidates`.
6. **Observability** — сохранение run в `data/runs/<runId>.json`, индекс `index.jsonl`, шаги с prompt / raw / parsed / tool / observation.
7. **Web UI** — логин по admin token, cookie TTL 12h, страницы runs/logs/git; позже вынесение HTML в [`app/presentation/web/adminPages.py`](app/presentation/web/adminPages.py) и обновление визуального стиля админки.

---

## 4. Важные продуктовые и технические решения

### 4.1. Telegram и новости

- Сообщения обрабатываются как текст; команды `/start`, `/reset`, `/health`; неавторизованным — отказ.
- Индикация «печатает…» через `sendChatAction` на время обработки личного сообщения.
- Инструмент **`digest_telegram_news`** изначально опирался на идею `channel_post` / локального стора и конфликтовал с polling (`getUpdates`). **Итог:** дайджест строится **скрапингом публичных страниц** `https://t.me/s/<channel>` без членства бота в канале.
- Параметры дайджеста (каналы, тикеры портфеля, семантические ключевые слова) задаются в конфиге; `sinceUnixTs: 0` трактуется как начало текущих суток (UTC).
- В ответах пользователю ожидаются **прямые ссылки** на посты; в skills усилены правила про один вызов tool на run и обязательность ссылок.

### 4.2. Управление loop и качеством ответов

- Лимиты `maxSteps`, `maxToolCalls`, `maxExecutionSeconds` в конфиге; защита от повторов одного и того же tool (в т.ч. по имени с разными args).
- **Gating tool calls:** если по сообщению не ожидается нужда в инструменте, в loop передаётся `in_allowToolCalls=False`, модель получает observation «tools disabled».
- **Память:** служебные ответы про лимиты/остановки не пишутся в recent/summary, чтобы не зацикливать следующие запросы.
- **Run snapshot:** в `effectiveConfigSnapshot` секция `telegram` опускается, если в run не было реальных tool calls (меньше шума в трассах «простых» диалогов).

### 4.3. Надёжность runtime (roadmap после этапа 7)

Реализовано в коде и тестах:

- Расширенные анти-циклы: скользящее окно сигнатур tool+args, лимит итераций `tool_call_blocked` → `tool_call_blocked_limit`.
- **Один repair-pass:** при невалидном JSON после основного ответа — отдельный repair-prompt; в trace поле `repairRawModelResponse`.
- **Метаданные LLM:** тип [`LlmCompletionResultModel`](app/domain/entities/llmCompletionResult.py) — `content`, фактическая `selectedModel`, `fallbackEvents`; события прокидываются в run-файл.
- **Observations после tool** — компактный JSON для модели вместо сырого `str(envelope)`.
- **Digest tool:** retries + backoff, `channelErrors` по каналам, дедуп постов, fallback-парсинг HTML при смене вёрстки.
- **Session summary** — инкрементальные блоки с timestamp, обрезка по лимиту.
- **JsonRunRepository:** атомарная запись JSON run (`tmp` + `replace`), устойчивое чтение индекса (пропуск битых строк), `fsync` на append индекса.
- **`/internal/*`** — те же проверки web-auth, что и у HTML-админки.

Новые поля `runtime` в конфиге (см. [`app/config/config.example.yaml`](app/config/config.example.yaml)): `toolCallHistoryWindowSize`, `maxSameToolSignatureInWindow`, `maxToolCallBlockedIterations`.

### 4.4. Web и безопасность

- Хэширование admin-токенов, валидация длины cookie secret и формата токенов.
- Единая навигация по админ-страницам; экранирование вывода git status/diff от XSS.
- Lifespan FastAPI вместо устаревших `on_event` для фона Telegram polling.

### 4.5. Тесты

- `pytest`, файлы `test_*.py`.
- Интеграционные проверки web (в т.ч. auth и `/internal/*`), unit-тесты на loop, parser, tools, settings, memory, git и т.д.

---

## 5. Известные операционные моменты

- Запуск тестов и приложения из **виртуального окружения** `.venv`; иначе возможны `ModuleNotFoundError: app` или конфликт версий Python.
- Для разработки удобен `.env` рядом с проектом; `app/config/config.yaml` с секретами не коммитить (см. `.gitignore`).

---

## 6. Журнал изменений (дополнять при каждой значимой доработке)

| Дата | Изменения |
|------|-----------|
| 2026-04-26 | Добавлен файл `how_project_was_developed.md`: сводка этапов 1–7, ключевых решений (Telegram digest, gating tools, память, web), блока «Надёжность Agent Runtime» (repair-pass, LlmCompletionResultModel/fallbackEvents, anti-loop, digest hardening, atomic runs, защита `/internal/*`, тесты). Договорённость: после будущих изменений дописывать сюда строку в таблицу. |
| 2026-04-27 | Добавлена команда Telegram `/context`: возвращает размер текущего session memory block (chars) и лимит `runtime.maxPromptChars` (контекстное окно). Добавлен unit-тест `testAuthorizedUserContextCommandShowsContextAndWindow`. |
| 2026-04-27 | Исправлен тест `testDigestToolRecordsChannelFetchErrors`: стабилизирован порог «сегодня» через `todayStartUnixTsProvider=lambda: 0`, чтобы тест не зависел от текущей даты. |
| 2026-04-27 | Расширен tool `digest_telegram_news`: добавлен аргумент `sinceHours` (0..168) и вычисление `sinceUnixTs` как `now - sinceHours*3600` внутри `DigestTelegramNewsTool` (через `nowUnixTsProvider`). Добавлен unit-тест `testDigestToolUsesSinceHoursWhenProvided`. |
| 2026-04-27 | Добавлен tool `web_search` (DuckDuckGo HTML + скачивание top-5 страниц, извлечение plain text, safety-checks URL) и skill `web_research` с rule-based выбором. Добавлены тесты `test_web_search_tool.py` и расширен `test_skill_service.py`. |
| 2026-04-27 | Сделан более гибкий лимит времени run: `StopPolicy` теперь учитывает число LLM-ошибок (`model_error`) и увеличивает эффективный `maxExecutionSeconds` на `extraSecondsPerLlmError` (с потолком `maxExtraSecondsTotal`). |
| 2026-04-27 | Исправлена сериализация tool-result: `ToolExecutionCoordinator` теперь сериализует `dict/list` в валидный JSON (а не `str(dict)`), чтобы модель могла надёжно читать structured tool outputs и не зацикливаться на повторных tool calls. Добавлен тест `testToolCoordinatorSerializesDictAsJsonString`. |
| 2026-04-27 | Усилен anti-loop на уровне runtime: после успешного вызова инструмента повторный `tool_call` того же инструмента в рамках одного run блокируется (`tool_call_blocked`), чтобы вынудить модель перейти к `final` вместо бессмысленных повторов. Одновременно observation после tool сделано «LLM-friendly»: вместо потенциально обрезанного `data_excerpt` используется структурный `data_preview` (первые элементы + ссылки), чтобы не провоцировать повтор из-за «полу-JSON» в prompt. Добавлен тест `testAgentLoopBlocksRepeatToolCallAfterSuccess`. |
| 2026-04-27 | Улучшена наблюдаемость в web-админке: на странице шагов run (`/runs/<runId>/steps`) теперь видно `status` каждого шага в виде badge, а для `tool_call_blocked` выводится причина guard (reason/message) из observation. Это позволяет быстро понять, почему loop остановился/заблокировался, не читая JSON run-файл вручную. |
| 2026-04-27 | Разделены глобальные настройки и tool-specific: добавлен `app/config/tools.yaml` и настройка пути `tools.toolsConfigPath` в `config.yaml`. Для `digest_telegram_news` сделан live reload через провайдеры настроек (читаются из `tools.yaml`). В админке добавлены страницы `/tools`, `/skills`, `/skills/{skillId}`, `/config/tools` и флаг `security.adminWritesEnabled` для включения/выключения write-операций (редактирование skills и tools.yaml). Добавлены тесты на web-auth и запрет/разрешение POST при writes disabled/enabled. |
| 2026-04-27 | Улучшен `web_search`: tool теперь не падает целиком из-за одной запрещённой ссылки — собирает `blockedUrls`/`fetchErrors` и продолжает. Дополнительно добавлена нормализация ссылок DuckDuckGo редиректа (`//duckduckgo.com/l/?uddg=...`) с распаковкой `uddg` в конечный `https://...`, чтобы реально скачивать страницы в `fetchedPages`. Добавлен unit-тест `testWebSearchToolUnwrapsDdgRedirectUrls`. |
| 2026-04-27 | Устранено «отравление памяти» ошибками web поиска: ответы вида `ACCESS_DENIED` / «Не удалось выполнить поиск в интернете…» теперь считаются служебными и не сохраняются в `recent`/`session summary`. В `web_research` skill добавлено правило: даже при наличии прошлых ошибок всё равно делать одну попытку `web_search` в run. Добавлен тест `testMemoryServiceSkipsWebSearchAccessDeniedInRecentAndSummary`. |
| 2026-04-27 | Сделан “hardening” для больших ответов инструментов: `ToolExecutionCoordinator` больше не возвращает обрезанный невалидный JSON для `dict/list`. Если результат превышает `runtime.maxToolOutputChars`, он возвращает валидный JSON-preview (например для `web_search`: counts + sample URLs). Это устраняет ситуацию, когда модель видит `non_json_tool_payload` и считает, что данных нет. Добавлен тест `testToolCoordinatorKeepsValidJsonWhenTruncated`. |
| 2026-04-27 | `web_search` сделан устойчивее к таймаутам: внутри tool введён общий deadline (тайм-бюджет) и адаптивные таймауты на запросы. При нехватке времени tool возвращает частичный результат (`results` + что успели в `fetchedPages` + `fetchErrors`) вместо падения по TIMEOUT на уровне coordinator. Добавлен тест `testWebSearchToolStopsFetchingOnDeadline`. |
| 2026-04-27 | Добавлен tool `read_email` (IMAP) для чтения писем (по умолчанию: последние непрочитанные, с фильтром по `sinceHours`, с коротким snippet). Настройки подключения добавлены в `tools.yaml` (`emailReader.*`), пароль хранится только в env (`EMAIL_APP_PASSWORD`) и маскируется в `effectiveConfigSnapshot`. Добавлены unit-тесты `test_read_email_tool.py`. |
| 2026-04-27 | Улучшен `read_email`: если `text/plain` отсутствует, snippet извлекается из `text/html` (очистка от тегов + unescape). В observation после tool добавлен `email_preview` с `from/subject/date/snippet`, чтобы модель могла делать нормальный дайджест без повторных запросов. Добавлен тест `testReadEmailToolExtractsSnippetFromHtml`. |
| 2026-04-27 | Добавлен skill `compose_digest`: стандартный формат дайджеста (пункты с разделителем `---`, источник, краткое резюме, короткая цитата; перевод на русский для не-русских фрагментов). Правило выбора skills расширено: по фразам "составь/сделай дайджест" добавляется `compose_digest`. |
| 2026-04-27 | Hardening email→дайджест: `read_email` теперь извлекает текст через `get_content()` (лучше для кодировок), очищает snippet от URL/CSS-шаблонов и добавляет `langHint`. Skill `compose_digest` закреплён с двухшаговой стратегией UNSEEN→ALL (если писем < N). В observation расширен `email_preview` (uid/date/langHint). Добавлены/обновлены тесты на очистку snippets. |
| 2026-04-27 | Добавлен встроенный scheduler (variant B): конфиг `scheduler.*` в `config.yaml` + файл расписаний у tenant админа рядом с `tools.yaml` (минимальный шаблон при первом создании — см. `app/config/defaultTenantSessionYaml.py`; явная миграция со старого `./app/config/schedules.yaml` через `scheduler.schedulesConfigPath`). Реализован `SchedulerRunner` (фоновый thread в FastAPI lifespan), который запускает internal-run через `RunAgentUseCase.execute(sessionId, message)` и пишет состояние в `data/scheduler/jobs_state.json`. Добавлены unit-тесты `tests/test_scheduler_runner.py`. |
| 2026-04-29 | Обновлён favicon-пайплайн в web-админке: `/favicon.ico` теперь отдаёт реальный `favicon.ico` с `image/x-icon` (вместо PNG), добавлены anti-cache заголовки (`no-store/no-cache`), а в HTML ссылка переключена на версионируемый URL `/favicon.ico?v=1` для надёжного cache-bust в браузерах. |
| 2026-04-30 | Добавлены reminders в unified scheduler: tools `schedule_reminder/list_reminders/delete_reminder`, skill `schedule_reminder` (schema-first JSON), runtime guard на `VALIDATION_ERROR`, авто-удаление отработавших reminders из `schedules.yaml`, observability в web. |
| 2026-04-30 | Добавлена поддержка Telegram voice/audio → text через `faster-whisper` (CPU). Добавлены события `voice_transcription_started/succeeded/failed`, лимиты по длительности/размеру, docker dependency `ffmpeg`, кэш моделей направлен в `/app/data/models`. |
| 2026-05-02 | **Tenant-only конфиги:** из runtime-контракта убраны override-пути `tools.toolsConfigPath` и `scheduler.schedulesConfigPath`. Единственный источник `tools.yaml` / `schedules.yaml` — каталог `sessions/telegramUser_<ADMIN_TELEGRAM_USER_ID>/` под `memory.memoryRootPath`; при загрузке выставляются `adminTenantToolsYamlPath` / `adminTenantSchedulesYamlPath`. Попытка указать legacy-ключи в YAML → ошибка валидации (`extra=forbid` на секциях). Записи 2026-04-27 про глобальный `app/config/tools.yaml` и `schedulesConfigPath` ниже — **исторические**, актуальная схема в `README.md` (раздел «Миграция…»). |

---

## 8. Сводка “что уже сделано” (перенесено из README)

Ранее в `README.md` поддерживался список выполненных шагов/компонентов. Чтобы README оставался чистой эксплуатационной документацией, эта сводка живёт здесь.

- layered-архитектура монолита;
- typed-конфиг с fail-fast загрузкой;
- базовый FastAPI app + `/health`;
- Telegram polling skeleton с allowlist и typing-индикатором;
- strict YAML/JSON контракт runtime (`tool_call` / `final` / `stop`), repair-pass;
- agent loop с лимитами шагов/времени/tool calls и anti-loop guards;
- prompt builder с усечением prompt и time-context (UTC + business timezone);
- tools subsystem: registry, schemas, metadata renderer, execution coordinator;
- стандартизированный tool-result envelope + error codes;
- read-only tools: `digest_telegram_news`, `web_search`, `read_memory_file`, `read_email`;
- OpenRouter интеграция: retries + fallback policy primary/secondary/tertiary;
- Markdown skills store + rule-based skill selection;
- Markdown memory store: recent, session summary, long-term memory;
- обновление summary/long-term после завершения run;
- внутренний endpoint для отладки: `POST /internal/run`;
- web UI (runs/logs/tools/skills/git) + web auth;
- run persistence model: `data/runs/<runId>.json` + `data/runs/index.jsonl`, trace prompt/raw/parsed/tool/observations/config snapshot;
- run read API: `GET /internal/runs`, `GET /internal/runs/{runId}`, `GET /internal/runs/{runId}/steps`;
- git admin pages: `/git/status`, `/git/diff` (+ internal API);
- unit/integration тесты на config, loop, tools, fallback, skills, memory, web auth.

---

## 7. Что логично делать дальше (не обязательно в backlog)

- Этап **hardening** из specs: расширить негативные сценарии, документацию под деплой (Docker), при необходимости — лёгкая асинхронность без переписывания домена.
- Отдельный internal token vs общая cookie-сессия — если появятся не-browser клиенты к `/internal/*`.
- Постраничный обход истории `t.me/s/...` для digest при необходимости глубже «за сегодня».
