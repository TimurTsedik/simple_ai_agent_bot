# Schedule Reminder

purpose: поставить/изменить напоминание через tool `schedule_reminder` по строго структурированному JSON.
when_to_use: когда пользователь просит поставить напоминание, изменить расписание напоминания, ограничить число повторов, удалить/посмотреть напоминания.
when_not_to_use: когда пользователь не просит работать с напоминаниями.
instructions:
- финальный ответ всегда на русском языке;
- никакого разбора естественного языка внутри tool: не делать NLP-парсинг фраз вида "во вторник", "через час", окончаний слов и т.п.;
- относительное время ("через N минут/часов") преобразуй в `timeLocal` на стороне модели, используя текущее время и `Configured business timezone` из prompt;
- сначала уточни недостающие поля для JSON (если они неочевидны): `message`, `scheduleType`, `timeLocal`, `timeZone`, `weekdays`, `remainingRuns`;
- минимальные обязательные поля перед вызовом `schedule_reminder`: `message`, `scheduleType`, `timeLocal`;
- если `scheduleType=weekly`, то `weekdays` обязателен и должен быть массивом 0..6;
- если `scheduleType=daily`, то `weekdays` должен быть пустым массивом;
- не задавай лишний уточняющий вопрос для "через N минут/часов", если N однозначен и timezone уже задан в prompt;
- уточнение нужно только если:
  - N не удалось однозначно извлечь;
  - timezone не задан/противоречив;
  - пользователь дал конфликтующие условия;
- для создания/обновления используй только `schedule_reminder` с аргументами:
  - `reminderId` (опционально; пусто = создать новое),
  - `enabled` (bool),
  - `message` (string),
  - `scheduleType` (`daily` или `weekly`),
  - `weekdays` (массив 0..6; только для weekly),
  - `timeLocal` (`HH:MM`),
  - `timeZone` (IANA, например `Europe/Moscow`; пусто = дефолт приложения),
  - `remainingRuns` (int|null);
- безопасная развилка:
  - create: `schedule_reminder` с `reminderId=""`;
  - update: `schedule_reminder` с конкретным `reminderId`;
  - list: `list_reminders`;
  - delete: `delete_reminder` с `reminderId`;
- если пользователь просит список напоминаний — вызови `list_reminders`;
- если пользователь просит удалить напоминание — вызови `delete_reminder` с `reminderId`;
- после успешного tool-вызова верни короткое подтверждение и ключевые поля расписания.
allowed_tools:
- schedule_reminder
- list_reminders
- delete_reminder
limitations:
- не выдумывать поля, которых нет в schema;
- не использовать `schedule_reminder`, пока не собраны минимально необходимые поля.
- anti-patterns:
  - нельзя передавать свободный текст расписания в одном поле (`"каждый вторник в 17:00"`) вместо структурных полей;
  - нельзя заполнять `weekdays` для `daily`;
  - нельзя оставлять `weekdays` пустым для `weekly`;
  - нельзя отправлять частично заполненный payload, если обязательные поля неизвестны.
  - нельзя переспрашивать время, если пользователь дал "через N минут/часов" и в prompt есть текущее время + timezone.
json_examples:
- daily unlimited:
  {
    "reminderId": "",
    "enabled": true,
    "message": "Пей воду",
    "scheduleType": "daily",
    "weekdays": [],
    "timeLocal": "09:30",
    "timeZone": "",
    "remainingRuns": null
  }
- weekly multiple days:
  {
    "reminderId": "",
    "enabled": true,
    "message": "Статус по задачам",
    "scheduleType": "weekly",
    "weekdays": [1, 3],
    "timeLocal": "17:00",
    "timeZone": "",
    "remainingRuns": null
  }
- limited runs:
  {
    "reminderId": "",
    "enabled": true,
    "message": "Курс антибиотика",
    "scheduleType": "daily",
    "weekdays": [],
    "timeLocal": "08:00",
    "timeZone": "",
    "remainingRuns": 5
  }
- relative time (5 minutes from now):
  {
    "reminderId": "",
    "enabled": true,
    "message": "Выпить воды",
    "scheduleType": "daily",
    "weekdays": [],
    "timeLocal": "<now+5min in HH:MM by configured timezone>",
    "timeZone": "",
    "remainingRuns": 1
  }
examples:
- "напомни каждый день в 09:30 пить воду"
- "поставь напоминание по вторникам и четвергам в 17:00"
- "удали напоминание reminder-abc123"

