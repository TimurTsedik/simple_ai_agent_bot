"""Поиск и разбор schedules.yaml по каталогам sessions/telegramUser_<id>/."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.common.memoryPrincipal import formatTelegramUserMemoryPrincipal
from app.config.tenantSchedulesModels import (
    ScheduledTaskInternalRun,
    ScheduledTaskTelegramMessage,
    TenantSchedulesFile,
    normalizeLegacySchedulesDict,
)

_TENANT_DIR = re.compile(r"^telegramUser_(\d+)$")


@dataclass(frozen=True)
class LoadedTenantSchedule:
    filePath: Path
    ownerMemoryPrincipalId: str
    ownerSanitizedSegment: str
    telegramUserId: int
    document: TenantSchedulesFile


def discoverTenantScheduleFiles(in_memoryRootPath: str) -> list[Path]:
    ret: list[Path]
    memory_root = Path(in_memoryRootPath)
    if memory_root.is_absolute() is False:
        memory_root = memory_root.resolve()
    sessions_root = memory_root / "sessions"
    paths: list[Path] = []
    if sessions_root.is_dir() is False:
        ret = paths
        return ret
    for child in sorted(sessions_root.iterdir()):
        if child.is_dir() is False:
            continue
        matched = _TENANT_DIR.fullmatch(child.name)
        if matched is None:
            continue
        schedule_path = child / "schedules.yaml"
        if schedule_path.is_file() is True:
            paths.append(schedule_path.resolve())
    ret = paths
    return ret


def loadTenantScheduleFile(in_path: Path) -> LoadedTenantSchedule | None:
    ret: LoadedTenantSchedule | None
    parent_name = in_path.parent.name
    matched = _TENANT_DIR.fullmatch(parent_name)
    if matched is None:
        ret = None
        return ret
    uid = int(matched.group(1))
    principal = formatTelegramUserMemoryPrincipal(in_telegramUserId=uid)
    try:
        raw = yaml.safe_load(in_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        ret = None
        return ret
    if isinstance(raw, dict) is False:
        raw = {}
    merged = normalizeLegacySchedulesDict(in_data=raw)
    try:
        doc = TenantSchedulesFile.model_validate(merged)
    except ValidationError:
        ret = None
        return ret
    ret = LoadedTenantSchedule(
        filePath=in_path.resolve(),
        ownerMemoryPrincipalId=principal,
        ownerSanitizedSegment=parent_name,
        telegramUserId=uid,
        document=doc,
    )
    return ret


def snapshotTenantFileMtimes(in_paths: list[Path]) -> dict[str, int]:
    ret: dict[str, int]
    out: dict[str, int] = {}
    for path in in_paths:
        try:
            out[str(path.resolve())] = int(path.stat().st_mtime_ns)
        except OSError:
            continue
    ret = out
    return ret


def tenantSnapshotChanged(
    in_previous: dict[str, int],
    in_current: dict[str, int],
) -> bool:
    ret: bool
    if in_previous.keys() != in_current.keys():
        ret = True
        return ret
    for key, value in in_current.items():
        if in_previous.get(key) != value:
            ret = True
            return ret
    ret = False
    return ret
