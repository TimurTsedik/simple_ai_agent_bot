# Спецификация проекта: собственный AI agent-бот с agentic loop

## 1. Цель проекта

Разработать собственного AI agent-бота как управляемую, наблюдаемую и расширяемую систему, без платформенной перегруженности уровня OpenClaw.

Система должна быть ориентирована на один основной сценарий: безопасный и предсказуемый запуск агентного цикла по входящему сообщению из Telegram, с возможностью вызывать Python tools, использовать skills из Markdown, вести память, логирование, fallback по моделям OpenRouter и предоставлять защищённый web-интерфейс для наблюдения за работой системы.

Проект должен строиться как **монолитное приложение с layered architecture**, с возможностью дальнейшего роста без переписывания ядра.

---

## 2. Основные принципы проекта

1. Центр системы — **Agent Run**, а не Telegram-бот, не модель и не web UI.
2. Система строится как **управляемый execution runtime с LLM внутри**, а не как «магический AI-организм».
3. Поведение должно быть максимально воспроизводимым и наблюдаемым.
4. Все критические решения системы должны быть явными:

   * лимиты loop;
   * правила fallback;
   * правила memory persistence;
   * правила выбора skills;
   * контракты tools;
   * формат логирования.
5. На первом этапе проект реализуется как **один агент**, **один процесс**, **file-backed storage**, **без vector DB**, **без RAG**, **без multi-agent**.
6. Все внешние интеграции должны быть изолированы за интерфейсами/протоколами.
7. Модель не управляет инфраструктурой. Модель управляет только логикой tool calling и финальным ответом в пределах заданного контракта.

---

## 3. MVP scope

### Входит в MVP

* Telegram-бот с polling
* Agentic loop по схеме:

  * reason -> action -> observation -> reason -> ... -> final
* Ограничение количества шагов loop через конфиг
* Поддержка OpenRouter-моделей с fallback policy
* Tools как Python-код
* Skills как Markdown-файлы
* Текстовая память в Markdown-файлах
* Полное структурированное логирование agent runs
* Защищённый web UI для:

  * просмотра runs;
  * просмотра логов;
  * просмотра деталей loop;
  * просмотра tool calls;
  * просмотра текущего git status/diff;
  * просмотра health/status;
  * просмотра effective config snapshots.
* Контроль доступа:

  * Telegram — allowlist по Telegram user ID;
  * Web UI — вход по admin token, который хранится только в хэшированном виде.

### Не входит в MVP

* Vector DB
* RAG
* Multi-agent orchestration
* Webhook для Telegram
* Редактирование файлов через web UI
* Git write operations: commit/push/reset/checkout/merge
* Автоматический выбор skills моделью
* Сложные планировщики и meta-planning
* Полноценная RBAC-система
* Telegram-based web auth

---

## 4. Функциональные требования

### 4.1 Telegram transport

Система должна:

* принимать текстовые сообщения через Telegram Bot API;
* работать через polling;
* обрабатывать только сообщения от разрешённых Telegram user IDs;
* игнорировать или отклонять запросы от неавторизованных пользователей;
* сопоставлять один Telegram chat с одной session.

### 4.2 Agentic loop

Для каждого входящего сообщения должен создаваться отдельный `AgentRun`.

Agent loop должен работать по схеме:

1. подготовка context;
2. сбор prompt;
3. вызов модели;
4. разбор JSON-ответа модели;
5. если модель запросила tool — вызвать tool;
6. добавить observation в context;
7. повторить шаги в пределах лимитов;
8. завершить run финальным ответом или безопасной остановкой.

### 4.3 Skills

Skills должны храниться в `.md` файлах.

Skills используются как prompt assets и должны описывать:

* назначение skill;
* когда его использовать;
* когда его не использовать;
* инструкции модели;
* допустимые tools;
* ограничения;
* примеры.

Выбор skills для run должен выполняться **по rule-based policy**, а не самой моделью.

### 4.4 Tools

Tools должны быть реализованы исключительно как Python-код.

Для каждого tool должны существовать:

* стабильное имя;
* описание для модели;
* JSON schema аргументов;
* runtime implementation;
* timeout;
* ограничение на размер output;
* стандартный result envelope;
* стандартизованные error codes.

### 4.5 Memory

Memory на первом этапе должна быть file-based и храниться в Markdown.

Memory должна быть разделена минимум на:

* short-term session context;
* session summary;
* long-term memory.

Long-term memory не должна наполняться напрямую решением модели.

Подход должен быть гибридным:

* модель может **предлагать memory candidates**;
* runtime применяет policy и решает, что сохранять.

### 4.6 Logging and observability

Система должна вести полное логирование каждого run.

Для каждого run должны сохраняться:

* run metadata;
* session id;
* input message;
* selected skills;
* effective config snapshot;
* prompt snapshot;
* raw model response;
* parsed model response;
* tool calls;
* tool results;
* observations;
* fallback events;
* final answer;
* completion status;
* timing data.

### 4.7 Web UI

Web UI должен быть read-only admin surface на первом этапе.

Должны быть доступны:

* список runs;
* карточка отдельного run;
* просмотр логов;
* детали шагов loop;
* просмотр tool calls/results;
* git status;
* git diff;
* health/status;
* current config snapshot.

### 4.8 Git visibility

В web UI должны быть доступны только read-only операции:

* текущая ветка;
* git status;
* untracked files;
* staged / unstaged state;
* diff summary;
* diff по отдельным файлам.

Операции записи в git запрещены.

---

## 5. Нефункциональные требования

1. Архитектура должна быть layered.
2. Внутренний runtime не должен зависеть от Telegram/Falcon/OpenRouter напрямую.
3. Все важные контракты должны быть формализованы через схемы/модели.
4. Система должна быть пригодна для unit- и integration-тестирования.
5. Любой run должен быть максимально воспроизводимым.
6. Ошибки отдельных tools не должны неконтролируемо ломать весь loop.
7. Система должна gracefully degrade при частичных сбоях.
8. Должны существовать явные лимиты на размеры контекста.
9. Проект должен поддерживать локальную и серверную эксплуатацию.

---

## 6. Архитектурный стиль

Используется **layered monolith architecture**.

### 6.1 Layers

#### Layer 1. Entry Points

Внешние точки входа:

* Telegram polling
* Web API
* Internal HTTP API
* CLI/debug runner

Обязанности:

* принять внешний input;
* нормализовать его;
* передать в application layer.

Ограничения:

* не собирать prompt;
* не работать с памятью напрямую;
* не вызывать tools напрямую;
* не содержать agent loop.

#### Layer 2. Application Layer

Use cases и orchestration.

Основные use cases:

* runAgent
* handleIncomingTelegramMessage
* getRunDetails
* getRunList
* getLogs
* getGitStatus
* getGitDiff
* getHealthStatus

Обязанности:

* координация выполнения сценариев;
* вызов runtime;
* чтение/запись storage;
* организация ответов presentation layer.

#### Layer 3. Domain Layer

Ядро бизнес-логики.

Содержит:

* сущности;
* value objects;
* политики;
* доменные протоколы;
* инварианты.

Domain не должен зависеть от:

* Telegram;
* Falcon;
* файловой системы;
* OpenRouter API;
* Git CLI;
* UI.

#### Layer 4. Runtime Layer

Специализированный слой agent execution.

Содержит:

* agent loop;
* prompt builder;
* skill selector;
* memory injector;
* parser model output;
* tool execution coordinator;
* stop policy;
* fallback coordinator.

#### Layer 5. Infrastructure Layer

Реальные адаптеры и интеграции:

* OpenRouter client;
* file-based memory store;
* markdown skill loader;
* JSONL logger;
* Telegram API client;
* git readers;
* config loader;
* auth token repository.

#### Layer 6. Presentation Layer

Представление данных наружу:

* Falcon routes;
* HTML pages;
* JSON responses;
* presenters/view models.

#### Layer 7. Cross-Cutting

Минимальный набор общих сервисов:

* id generation;
* clock;
* structured logging helpers;
* truncation utils;
* validation helpers.

---

## 7. Правила зависимостей

Разрешённые зависимости:

* Entry Points -> Application
* Presentation -> Application
* Application -> Domain
* Application -> Runtime
* Runtime -> Domain
* Infrastructure -> Domain/Application Protocols
* Presentation -> DTO/ViewModels

Запрещённые зависимости:

* Domain -> Infrastructure
* Domain -> Presentation
* Runtime -> Telegram/Falcon/OpenRouter directly
* Tools -> Web UI
* Telegram handlers -> Prompt Builder напрямую

Главные правила:

1. Domain не зависит ни от кого.
2. Runtime не знает про Telegram и Falcon.
3. Инфраструктура реализует интерфейсы, а не диктует поведение domain/runtime.

---

## 8. Подсистемы (bounded contexts)

### 8.1 Agent Core

Отвечает за:

* AgentRun;
* steps;
* loop;
* stop conditions;
* finalization.

### 8.2 Model Access

Отвечает за:

* OpenRouter integration;
* retries;
* timeouts;
* fallback;
* provider error mapping.

### 8.3 Tools

Отвечает за:

* registry;
* schemas;
* execution;
* metadata;
* result envelopes.

### 8.4 Memory

Отвечает за:

* session context;
* summaries;
* long-term memory;
* future seam for vector retrieval.

### 8.5 Observability

Отвечает за:

* run traces;
* logs;
* replay support;
* diagnostics.

### 8.6 Admin Surface

Отвечает за:

* web UI;
* auth;
* git visibility;
* config visibility;
* status pages.

---

## 9. Центральная сущность: Agent Run

Каждый запуск агента должен быть представлен сущностью `AgentRun`.

### 9.1 AgentRun включает

* уникальный run id;
* session id;
* source type;
* input message;
* timestamps;
* run status;
* selected skills;
* selected model;
* effective config snapshot;
* prompt snapshot;
* raw model outputs;
* parsed outputs;
* tool calls;
* tool results;
* observations;
* fallback events;
* final answer;
* memory candidates;
* completion reason.

### 9.2 Статусы run

Рекомендуемые статусы:

* created
* running
* completed
* stopped
* failed

### 9.3 Completion reason

Рекомендуемые варианты:

* final_answer
* stop_response
* max_steps_exceeded
* max_tool_calls_exceeded
* max_execution_time_exceeded
* fatal_runtime_error
* authorization_denied

---

## 10. Session model

### 10.1 Основное правило

Один Telegram chat = одна session.

### 10.2 Session id

Формат:

* `platform:chat_id`

Пример:

* `telegram:123456789`

### 10.3 Session metadata

Для каждой session сохраняются:

* session id;
* platform;
* chat id;
* createdAt;
* updatedAt;
* lastUserMessageAt;
* current summary reference.

### 10.4 Session reset

Session должна иметь явный reset-механизм:

* через Telegram command;
* либо через web UI action в будущем;
* либо через отдельный admin сценарий.

---

## 11. Agentic loop

### 11.1 Общая схема

1. Получить input.
2. Нормализовать input.
3. Загрузить session context.
4. Выбрать skills.
5. Загрузить memory.
6. Подготовить tools description.
7. Собрать prompt.
8. Вызвать модель.
9. Распарсить JSON.
10. Если `tool_call` -> исполнить tool.
11. Добавить observation.
12. Проверить лимиты.
13. Повторить.
14. Если `final` или `stop` -> завершить run.
15. Обновить memory.
16. Сохранить trace.
17. Отправить ответ в Telegram.

### 11.2 Лимиты loop

Через конфиг должны задаваться минимум:

* `maxSteps`
* `maxToolCalls`
* `maxExecutionSeconds`

### 11.3 Поведение при превышении лимитов

Система должна завершать run безопасно, через controlled stop, а не через неконтролируемое падение.

---

## 12. Model output contract

Модель должна отвечать **только валидным JSON**, без текста вне JSON.

### 12.1 Допустимые типы ответа

#### Tool call

```json
{
  "type": "tool_call",
  "reason": "short internal reason",
  "action": "tool_name",
  "args": {}
}
```

#### Final

```json
{
  "type": "final",
  "reason": "short internal reason",
  "final_answer": "text"
}
```

#### Stop

```json
{
  "type": "stop",
  "reason": "short internal reason",
  "final_answer": "safe stop message"
}
```

### 12.2 Правила

* один ответ модели = один JSON object;
* без markdown fences;
* без текста до/после JSON;
* `reason` должен быть коротким;
* `action` должен быть одним из разрешённых tools;
* `args` должны соответствовать схеме выбранного tool.

### 12.3 Обработка невалидного ответа модели

При невалидном JSON или нарушении схемы runtime должен:

1. зафиксировать raw response;
2. зафиксировать parse failure;
3. при необходимости выполнить retry/fallback;
4. либо завершить run controlled stop.

---

## 13. Skills

### 13.1 Формат хранения

Skills хранятся в Markdown.

### 13.2 Назначение

Skills — это prompt-facing assets, а не executable code.

### 13.3 Рекомендуемая структура skill файла

Каждый skill должен содержать:

* title
* purpose
* when_to_use
* when_not_to_use
* instructions
* allowed_tools
* limitations
* examples

### 13.4 Политика выбора skills

Для MVP используется **rule-based skill selection**.

Модель не выбирает skills самостоятельно.

### 13.5 Ограничение

В один run должны подмешиваться только релевантные skills, а не весь набор.

---

## 14. Tools

### 14.1 Общие требования

Каждый tool должен иметь:

* стабильное имя;
* описание для LLM;
* input schema;
* runtime implementation;
* timeout;
* output size limit;
* standardized result envelope.

### 14.2 Tool metadata

Для модели у каждого tool должны быть доступны:

* `name`
* `description`
* JSON schema аргументов

### 14.3 Tool execution model

Tool execution должен происходить через coordinator/executor, который:

* валидирует args;
* исполняет tool;
* измеряет duration;
* оборачивает результат в standardized envelope;
* ловит exceptions;
* преобразует ошибки в standardized error result.

### 14.4 Standard tool result envelope

#### Успех

```json
{
  "ok": true,
  "tool_name": "search_logs",
  "data": {},
  "error": null,
  "meta": {
    "duration_ms": 42
  }
}
```

#### Ошибка

```json
{
  "ok": false,
  "tool_name": "search_logs",
  "data": null,
  "error": {
    "code": "TIMEOUT",
    "message": "Tool execution timed out"
  },
  "meta": {
    "duration_ms": 5000
  }
}
```

### 14.5 Standard error codes

Стартовый набор:

* `VALIDATION_ERROR`
* `TIMEOUT`
* `NOT_FOUND`
* `ACCESS_DENIED`
* `UNAVAILABLE`
* `EXECUTION_ERROR`

### 14.6 Правила обработки ошибок

Tool не должен выбрасывать raw exception наружу loop.

Exception должен быть:

* залогирован;
* преобразован в standardized error result;
* возвращён runtime как контролируемый результат.

### 14.7 Ограничение результата tool

Результат каждого tool должен проходить policy ограничения размера. При необходимости результат должен быть усечён с пометкой в meta.

---

## 15. Memory

### 15.1 Виды памяти

Для MVP память разделяется на:

* recent messages;
* session summary;
* long-term memory.

### 15.2 Формат хранения

На первом этапе память хранится в Markdown и file-backed storage.

### 15.3 Политика long-term memory

Модель не должна напрямую писать в long-term memory.

Правильный процесс:

1. модель может предложить `memory_candidates`;
2. runtime применяет policy;
3. прошедшие policy записи сохраняются.

### 15.4 Что сохранять в long-term memory

Только устойчивую информацию, полезную в будущем:

* предпочтения пользователя;
* постоянные ограничения;
* договорённости;
* важные результаты длительных задач;
* устойчивые рабочие параметры.

### 15.5 Что не сохранять

* сырые диалоги;
* случайные детали;
* временные состояния;
* промежуточные observations;
* длинные tool outputs.

### 15.6 Session summary update

Session summary обновляется после завершения run.

---

## 16. Prompt assembly

### 16.1 Prompt должен включать

* system instructions;
* relevant skills;
* memory block;
* tools description;
* session context;
* execution instructions;
* strict output format instructions.

### 16.2 Prompt snapshot

Для каждого run должен сохраняться финальный rendered prompt snapshot.

Это необходимо для воспроизводимости и диагностики.

### 16.3 Контроль размера

Prompt builder должен иметь policy ограничения размера контекста:

* global prompt size limit;
* skill block limit;
* memory block limit;
* observation block limit.

При необходимости данные должны:

* усекаться;
* суммаризоваться;
* маркироваться как truncated.

---

## 17. OpenRouter integration и fallback

### 17.1 Model access

Система должна поддерживать работу с моделями OpenRouter.

### 17.2 Конфигурация моделей

Через конфиг должны задаваться:

* primary model;
* secondary model;
* tertiary model при необходимости.

### 17.3 Fallback policy

Fallback должен быть формализован и не должен быть «магическим».

Должны быть отдельные правила fallback минимум по:

* timeout;
* provider error;
* rate limit;
* invalid response;
* malformed JSON.

### 17.4 Что не должна решать модель

Модель не должна решать:

* когда включать fallback;
* какую модель выбрать;
* как обрабатывать provider errors.

Этим управляет runtime.

---

## 18. Logging and observability

### 18.1 Форматы логов

Необходимо два слоя логирования:

* structured logs (JSONL);
* human-readable logs.

Приоритет — за structured logs.

### 18.2 Идентификаторы

Каждый run и все связанные сущности должны быть снабжены идентификаторами:

* traceId
* runId
* sessionId
* messageId
* toolCallId при необходимости

### 18.3 Что логировать

Минимальный набор:

* incoming event;
* normalized input;
* selected skills;
* selected model;
* prompt snapshot;
* raw model response;
* parsed model response;
* tool calls;
* tool results;
* fallback events;
* memory updates;
* final output;
* error events;
* durations.

### 18.4 Replay support

Архитектура должна предусматривать возможность дальнейшего replay конкретного run на основе сохранённого trace.

---

## 19. Run persistence model

### 19.1 Для каждого run сохраняются

* metadata;
* effective config snapshot;
* prompt snapshot;
* raw model response(s);
* parsed response(s);
* tool chain;
* observations;
* final answer;
* completion reason.

### 19.2 Зачем это хранить

Это требуется для:

* диагностики;
* сравнения run behavior;
* воспроизводимости;
* анализа fallback;
* анализа влияния memory/skills;
* последующего replay.

---

## 20. Web UI

### 20.1 Назначение

Web UI — это admin/read-only control surface для наблюдения за системой.

### 20.2 Обязательные разделы

* run list;
* run details;
* logs;
* tool execution details;
* git status;
* git diff;
* config snapshot;
* health page.

### 20.3 Ограничения MVP

Web UI не должен:

* редактировать файлы;
* коммитить в git;
* менять настройки напрямую;
* выполнять произвольные shell-команды.

---

## 21. Авторизация

### 21.1 Telegram auth

Telegram-бот должен обслуживать только пользователей из allowlist по Telegram user ID.

### 21.2 Web auth

Web UI должен быть защищён:

1. сетью — через SSH tunnel;
2. приложением — через admin token login.

### 21.3 Token model

В системе должны храниться только:

* token id;
* token hash;
* createdAt;
* optional description;
* optional revoked flag.

Сами raw tokens не должны храниться.

### 21.4 Web session

После успешного входа по токену UI должен выдавать session cookie.

### 21.5 Telegram-based web auth

Не входит в MVP.

---

## 22. Git visibility

### 22.1 Доступные функции

* текущая ветка;
* git status;
* untracked files;
* staged / unstaged changes;
* diff summary;
* file diff view.

### 22.2 Запрещённые функции

* commit;
* push;
* pull;
* checkout;
* reset;
* merge;
* rebase.

---

## 23. Storage layout

Для MVP рекомендуется следующий storage style:

* config: YAML
* skills: Markdown files
* memory: Markdown files
* runs: JSON files and/or JSONL indexed storage
* logs: JSONL
* UI session storage: file or lightweight local storage

База данных на первом этапе не требуется.

---

## 24. Рекомендуемая структура каталогов

```text
app/
  main.py

  config/
    settingsModels.py
    settingsLoader.py
    defaults.py

  application/
    useCases/
      runAgentUseCase.py
      handleIncomingTelegramMessageUseCase.py
      getRunListUseCase.py
      getRunDetailsUseCase.py
      getLogsUseCase.py
      getGitStatusUseCase.py
      getGitDiffUseCase.py
      getHealthStatusUseCase.py
    dto/
    services/

  domain/
    entities/
      agentRun.py
      agentStep.py
      toolCall.py
      toolResult.py
      sessionContext.py
      memorySnapshot.py
    valueObjects/
    policies/
      stopPolicy.py
      fallbackPolicy.py
      memoryPolicy.py
    protocols/
      llmClientProtocol.py
      toolProtocol.py
      toolRegistryProtocol.py
      memoryStoreProtocol.py
      skillStoreProtocol.py
      runRepositoryProtocol.py
      gitReaderProtocol.py
      loggerProtocol.py

  runtime/
    agentLoop.py
    promptBuilder.py
    outputParser.py
    toolExecutionCoordinator.py
    skillSelector.py
    memoryInjector.py
    fallbackCoordinator.py

  tools/
    registry/
      toolRegistry.py
      toolSchemas.py
      toolMetadataRenderer.py
    implementations/
    services/

  memory/
    services/
      memoryService.py
      sessionSummaryService.py
      longTermMemoryService.py
    stores/
      markdownMemoryStore.py

  skills/
    services/
      skillService.py
      skillSelectorRules.py
    stores/
      markdownSkillStore.py

  models/
    services/
      llmService.py
    providers/
      openRouterClient.py
    parsing/

  observability/
    services/
      auditLogService.py
      runTraceService.py
      replayService.py
    stores/
      jsonlRunRepository.py
      fileSnapshotStore.py

  integrations/
    telegram/
      telegramPollingRunner.py
      telegramUpdateHandler.py
      telegramMessageMapper.py
    git/
      gitStatusReader.py
      gitDiffReader.py

  web/
    api/
    pages/
    auth/
    presenters/

  common/
    ids.py
    timeProvider.py
    jsonUtils.py
    truncation.py
```

---

## 25. Тестируемость

### 25.1 Обязательные типы тестов

* unit tests для domain policies;
* unit tests для parser model output;
* unit tests для tool executor;
* unit tests для memory policy;
* unit tests для fallback policy;
* integration tests для full agent loop;
* integration tests для Telegram message handling;
* integration tests для web read-only endpoints.

### 25.2 Mock LLM client

Должен существовать mock/fake LLM client, который умеет сценарно возвращать:

* valid tool_call;
* valid final;
* valid stop;
* malformed JSON;
* provider error;
* timeout-like behavior.

### 25.3 Tool stubs

Должны существовать stub/fake tools для тестирования loop без внешних зависимостей.

---

## 26. Ошибки и graceful degradation

Система должна ломаться контролируемо.

### 26.1 Примеры ожидаемого поведения

* primary model недоступна -> fallback;
* fallback недоступна -> controlled stop;
* tool упал -> standardized error result;
* memory store недоступен -> run продолжается без memory, если возможно;
* git unavailable -> только соответствующий UI блок показывает ошибку;
* parse failure -> retry/fallback/stop по policy.

---

## 27. Конфигурирование

### 27.1 Конфиг должен задавать минимум

* Telegram bot token;
* allowed Telegram user IDs;
* OpenRouter credentials;
* model list and fallback order;
* maxSteps;
* maxToolCalls;
* maxExecutionSeconds;
* storage paths;
* logging options;
* web auth token hashes;
* feature flags.

### 27.2 Требования к конфигу

* typed settings models;
* schema validation;
* defaults;
* effective config snapshot per run.

---

## 28. Этапы реализации

### Этап 1. Core skeleton

* структура проекта;
* config loading;
* domain entities;
* runtime interfaces;
* basic logging;
* basic Telegram transport.

### Этап 2. Agent loop MVP

* strict JSON output parser;
* loop;
* stop policy;
* step limits;
* prompt builder skeleton.

### Этап 3. Tools system

* tool registry;
* tool schemas;
* execution coordinator;
* standardized result envelope;
* error handling.

### Этап 4. OpenRouter integration

* provider client;
* retries;
* fallback policy;
* raw response logging.

### Этап 5. Skills and memory

* markdown skill store;
* rule-based skill selection;
* markdown memory store;
* session summary;
* memory candidate filtering.

### Этап 6. Observability

* JSONL run traces;
* run repository;
* log viewer backend;
* replay seam.

### Этап 7. Web UI

* auth;
* run list/details;
* logs;
* health;
* git status/diff.

### Этап 8. Hardening

* tests;
* failure handling;
* output truncation;
* config hardening;
* documentation.

---

## 29. Архитектурные запреты

В проекте запрещается:

* смешивать domain logic и transport logic;
* давать модели управлять fallback policy;
* давать модели напрямую писать long-term memory;
* давать tool raw exceptions ломать loop;
* строить multi-agent в MVP;
* строить vector DB/RAG до стабилизации core;
* делать web UI write-capable в MVP;
* использовать неявные источники состояния вне контролируемого storage.

---

## 30. Definition of Done для MVP

MVP считается завершённым, если:

1. Telegram-бот принимает сообщение от разрешённого пользователя.
2. Создаётся `AgentRun`.
3. Загружаются session, skills, memory.
4. Собирается prompt.
5. OpenRouter вызывается по configured primary model.
6. Loop корректно обрабатывает `tool_call`, `final`, `stop`.
7. Tools выполняются через standardized executor.
8. Ошибки tools оборачиваются в standardized error results.
9. Работают loop limits.
10. Работает fallback policy.
11. Ведётся structured logging.
12. Сохраняются prompt snapshot, raw model response и trace.
13. Web UI показывает runs, logs, git status/diff.
14. Telegram auth по allowlist работает.
15. Web UI auth по hashed token работает.
16. Система выдерживает базовые integration tests.

---

## 31. Дальнейшее развитие после MVP

После стабилизации MVP можно развивать:

* более сложную memory policy;
* memory search;
* vector DB;
* retrieval layer;
* richer admin UI;
* safe file editing;
* advanced replay tooling;
* comparative run analysis;
* multiple transports;
* additional skill selection strategies.

Но только после стабилизации core runtime и observability.

---

## 32. Итоговая позиция

Проект должен быть реализован не как «ещё одна агентная платформа», а как **компактный, строго управляемый, полностью наблюдаемый agent runtime**, ориентированный на конкретные сценарии эксплуатации и постепенное наращивание возможностей.

Главный приоритет проекта:
**контролируемость, воспроизводимость, явность правил и удобство развития.**
