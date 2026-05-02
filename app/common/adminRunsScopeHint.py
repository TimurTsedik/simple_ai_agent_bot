from app.common.memoryPrincipal import formatTelegramUserMemoryPrincipal


def buildAdminRunsScopeHintPlainText(in_adminTelegramUserId: int) -> str:
    principal_text = formatTelegramUserMemoryPrincipal(
        in_telegramUserId=in_adminTelegramUserId,
    )
    ret = (
        "Ограничение: в админке учитываются только раны с sessionId, совпадающим с tenant админа "
        f"({principal_text}). Раны scheduler и других Telegram-пользователей здесь не показываются."
    )
    return ret
