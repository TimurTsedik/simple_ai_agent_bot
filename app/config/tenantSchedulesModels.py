"""Единая схема tenant schedules.yaml: internal_run и telegram_message в одном списке."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field

from app.config.settingsModels import (
    ReminderScheduleModel,
    SchedulerJobInternalRunAction,
    SchedulerJobSchedule,
)


class ScheduledTaskInternalRun(BaseModel):
    kind: Literal["internal_run"] = "internal_run"
    taskId: str = Field(min_length=1)
    enabled: bool = True
    schedule: SchedulerJobSchedule = Field(default_factory=SchedulerJobSchedule)
    internalRun: SchedulerJobInternalRunAction = Field(
        default_factory=SchedulerJobInternalRunAction
    )


class ScheduledTaskTelegramMessage(BaseModel):
    kind: Literal["telegram_message"] = "telegram_message"
    taskId: str = Field(min_length=1)
    enabled: bool = True
    message: str = Field(default="", max_length=4000)
    schedule: ReminderScheduleModel = Field(default_factory=ReminderScheduleModel)
    createdAtUnixTs: int | None = Field(default=None, ge=0)
    lastFiredAtUnixTs: int | None = Field(default=None, ge=0)
    nextFireAtUnixTs: int | None = Field(default=None, ge=0)


ScheduledTask = Annotated[
    Union[ScheduledTaskInternalRun, ScheduledTaskTelegramMessage],
    Field(discriminator="kind"),
]


class TenantSchedulesFile(BaseModel):
    """Содержимое schedules.yaml в каталоге sessions/telegramUser_<id>/."""

    scheduledTasks: list[ScheduledTask] = Field(default_factory=list)


def normalizeLegacySchedulesDict(in_data: dict[str, Any]) -> dict[str, Any]:
    """Сливает legacy keys jobs/reminders и scheduledTasks в один список scheduledTasks."""

    ret: dict[str, Any]
    out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    raw_tasks = in_data.get("scheduledTasks")
    if isinstance(raw_tasks, list):
        for item in raw_tasks:
            if isinstance(item, dict) is True:
                tid = str(item.get("taskId", "") or "").strip()
                if tid != "" and tid not in seen_ids:
                    seen_ids.add(tid)
                    out.append(dict(item))

    for job in in_data.get("jobs", []) or []:
        if isinstance(job, dict) is False:
            continue
        jid = str(job.get("jobId", "") or "").strip()
        if jid == "" or jid in seen_ids:
            continue
        seen_ids.add(jid)
        action_ir = job.get("actionInternalRun")
        if isinstance(action_ir, dict) is False:
            action_ir = job.get("internalRun")
        if isinstance(action_ir, dict) is False:
            action_ir = {}
        out.append(
            {
                "kind": "internal_run",
                "taskId": jid,
                "enabled": bool(job.get("enabled", True)),
                "schedule": job.get("schedule") or {},
                "internalRun": action_ir,
            }
        )

    for rem in in_data.get("reminders", []) or []:
        if isinstance(rem, dict) is False:
            continue
        rid = str(rem.get("reminderId", "") or rem.get("taskId", "") or "").strip()
        if rid == "" or rid in seen_ids:
            continue
        seen_ids.add(rid)
        out.append(
            {
                "kind": "telegram_message",
                "taskId": rid,
                "enabled": bool(rem.get("enabled", True)),
                "message": str(rem.get("message", "") or ""),
                "schedule": rem.get("schedule") or {},
                "createdAtUnixTs": rem.get("createdAtUnixTs"),
                "lastFiredAtUnixTs": rem.get("lastFiredAtUnixTs"),
                "nextFireAtUnixTs": rem.get("nextFireAtUnixTs"),
            }
        )

    ret = {"scheduledTasks": out}
    return ret
