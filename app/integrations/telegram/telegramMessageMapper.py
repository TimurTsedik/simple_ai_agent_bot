from app.application.dto.incomingTelegramMessageDto import IncomingTelegramMessageDto


def mapUpdateToDto(in_updateData: dict) -> IncomingTelegramMessageDto | None:
    ret: IncomingTelegramMessageDto | None
    messageData = in_updateData.get("message")
    if not isinstance(messageData, dict):
        ret = None
    else:
        textValue = messageData.get("text")
        fromData = messageData.get("from")
        chatData = messageData.get("chat")
        hasValidParts = (
            isinstance(textValue, str)
            and isinstance(fromData, dict)
            and isinstance(chatData, dict)
            and isinstance(fromData.get("id"), int)
            and isinstance(chatData.get("id"), int)
            and isinstance(in_updateData.get("update_id"), int)
        )
        if hasValidParts:
            ret = IncomingTelegramMessageDto(
                updateId=in_updateData["update_id"],
                telegramUserId=fromData["id"],
                chatId=chatData["id"],
                text=textValue,
            )
        else:
            ret = None
    return ret
