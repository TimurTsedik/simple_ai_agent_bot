from app.common.memoryPrincipal import formatTelegramUserMemoryPrincipal


def buildAdminRunsScopeHintPlainText(in_adminTelegramUserId: int) -> str:
    principal_text = formatTelegramUserMemoryPrincipal(
        in_telegramUserId=in_adminTelegramUserId,
    )
    ret = (
        "Ограничение: в админке показываются раны tenant администратора "
        f"({principal_text}) — включая под-сессии вроде scheduler "
        "(sessionId с префиксом `telegramUser:<id>:`). Раны других Telegram-пользователей не показываются."
    )
    return ret
