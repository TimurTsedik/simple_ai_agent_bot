# Schedule recurring agent run

purpose: настроить регулярный запуск агента (дайджест новостей, почты и т.п.) через tool `schedule_recurring_agent_run`.
when_to_use: пользователь просит «каждый час/день присылать дайджест», «регулярно проверять почту», «по расписанию собирать новости по теме» — не путать с простым напоминанием текста в Telegram (`schedule_reminder`).
when_not_to_use: одноразовый запрос без расписания; напоминание фиксированной фразы в заданное время суток — тогда `schedule_reminder`.
instructions:
- финальный ответ на русском;
- для дайджестов и почты поле `message` — это инструкция агенту при каждом запуске (как сообщение в чат), например: «Сделай краткий дайджест экономических новостей за последний час» или «Прочитай непрочитанные письма и выдели важное»;
- `intervalSeconds` — интервал между запусками (минимум 60), по умолчанию 3600; для «раз в сутки» используй **86400**;
- опционально `allowedHourStart` / `allowedHourEnd` (0–23) — окно локального времени, вне которого задача не стартует; для «каждый день в 10:00» задай, например, `allowedHourStart: 10`, `allowedHourEnd: 10` вместе с `intervalSeconds: 86400`;
- `taskId` пустой = создать новую задачу; указан = обновить существующую;
- `sessionSlug` опционально — короткий суффикс для сессии планировщика; можно не задавать;
- список задач: `list_reminders` (возвращает и напоминания, и recurring internal_run);
- удаление: `delete_reminder` с `reminderId` = `taskId` задачи internal_run;
- не вызывай `schedule_reminder` для сценариев «каждый час дайджест» — используй `schedule_recurring_agent_run`.
allowed_tools:
- schedule_recurring_agent_run
- list_reminders
- delete_reminder
limitations:
- не придумывай поля вне schema;
- не используй `schedule_reminder` для периодических дайджестов с интервалом.
json_examples:
- hourly news digest during day:
  {
    "message": "Покажи краткий дайджест новостей по экономике РФ за последний час (Telegram).",
    "intervalSeconds": 3600,
    "allowedHourStart": 8,
    "allowedHourEnd": 23,
    "taskId": "",
    "sessionSlug": "",
    "enabled": true
  }
- email check every 2 hours:
  {
    "message": "Прочитай непрочитанные письма и сделай краткий дайджест важного.",
    "intervalSeconds": 7200,
    "allowedHourStart": null,
    "allowedHourEnd": null,
    "taskId": "",
    "sessionSlug": "email_digest",
    "enabled": true
  }
- daily Telegram topic digest at ~10:00 local:
  {
    "message": "Собери дайджест постов в Telegram по теме AI (user_topic_telegram_digest, topic AI, fetchUnread=true).",
    "intervalSeconds": 86400,
    "allowedHourStart": 10,
    "allowedHourEnd": 10,
    "taskId": "",
    "sessionSlug": "ai_digest_daily",
    "enabled": true
  }
examples:
- «каждый час присылай дайджест новостей по рынку»
- «раз в день в 9 утра по Москве обзор почты» — уточни интервал/окно часов и вызови tool
