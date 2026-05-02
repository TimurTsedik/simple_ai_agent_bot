"""Сопоставление sessionId рана с tenant-ключом (включая под-сессии scheduler и др.)."""


def sessionIdMatchesTenantPrincipal(
    in_recordSessionId: str,
    in_tenantPrincipalId: str,
) -> bool:
    """True если ран относится к тому же tenant, что и in_tenantPrincipalId.

    Совпадение: точное равенство `telegramUser:<id>` или любой «дочерний» sessionId
    вида `telegramUser:<id>:...` (scheduler, вложенные namespace).
    """

    ret: bool
    record = str(in_recordSessionId or "").strip()
    principal = str(in_tenantPrincipalId or "").strip()
    if principal == "":
        ret = False
    elif record == principal:
        ret = True
    elif record.startswith(principal + ":"):
        ret = True
    else:
        ret = False
    return ret
