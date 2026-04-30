from app.application.useCases.handleIncomingTelegramMessageUseCase import (
    HandleIncomingTelegramMessageUseCase,
)
from app.application.dto.incomingTelegramMessageDto import IncomingTelegramMessageDto
from app.common.structuredLogger import writeJsonlEvent
from app.config.settingsModels import SettingsModel
from app.domain.protocols.loggerProtocol import LoggerProtocol
from app.integrations.telegram.telegramMessageMapper import mapUpdateToDto
from app.integrations.telegram.telegramFileDownloaderProtocol import (
    TelegramFileDownloaderProtocol,
)
from app.integrations.speech.voiceTranscriberProtocol import VoiceTranscriberProtocol

import tempfile
from pathlib import Path
from typing import Any


class TelegramUpdateHandler:
    def __init__(
        self,
        *,
        in_handleIncomingTelegramMessageUseCase: HandleIncomingTelegramMessageUseCase,
        in_settings: SettingsModel,
        in_logger: LoggerProtocol,
        in_telegramFileDownloader: TelegramFileDownloaderProtocol | None,
        in_voiceTranscriber: VoiceTranscriberProtocol | None,
    ) -> None:
        self._handleIncomingTelegramMessageUseCase = in_handleIncomingTelegramMessageUseCase
        self._settings = in_settings
        self._logger = in_logger
        self._telegramFileDownloader = in_telegramFileDownloader
        self._voiceTranscriber = in_voiceTranscriber

    def handleUpdate(self, in_updateData: dict) -> tuple[int | None, str | None]:
        ret: tuple[int | None, str | None]
        messageDto = mapUpdateToDto(in_updateData=in_updateData)
        if messageDto is None:
            ret = self._handleVoiceOrAudioUpdate(in_updateData=in_updateData)
        else:
            useCaseResult = self._handleIncomingTelegramMessageUseCase.execute(
                in_messageDto=messageDto
            )
            ret = (messageDto.chatId, useCaseResult.outgoingText)
        return ret

    def _handleVoiceOrAudioUpdate(
        self,
        *,
        in_updateData: dict[str, Any],
    ) -> tuple[int | None, str | None]:
        ret: tuple[int | None, str | None]
        extracted = self._extractVoiceOrAudioMeta(in_updateData=in_updateData)
        if extracted is None:
            ret = (None, None)
        else:
            chatId, userId, updateId, fileId, durationSeconds = extracted
            if self._telegramFileDownloader is None or self._voiceTranscriber is None:
                ret = (chatId, "Голосовые сообщения пока не поддерживаются в этой конфигурации.")
            else:
                maxSeconds = int(getattr(self._settings.telegram, "voiceMaxSeconds", 60))
                maxBytes = int(getattr(self._settings.telegram, "voiceMaxBytes", 5_000_000))
                if durationSeconds is not None and durationSeconds > maxSeconds:
                    ret = (
                        chatId,
                        f"Голосовое слишком длинное ({durationSeconds}s). Максимум: {maxSeconds}s. "
                        "Попробуй короче или отправь текст.",
                    )
                else:
                    writeJsonlEvent(
                        in_loggingSettings=self._settings.logging,
                        in_eventType="voice_transcription_started",
                        in_payload={
                            "chatId": chatId,
                            "telegramUserId": userId,
                            "updateId": updateId,
                            "fileId": fileId,
                            "durationSeconds": durationSeconds,
                        },
                    )
                    try:
                        transcribedText = self._transcribeTelegramFile(
                            in_fileId=fileId,
                            in_maxBytes=maxBytes,
                            in_maxSeconds=maxSeconds,
                        )
                        if transcribedText.strip() == "":
                            outgoingText = (
                                "Не удалось распознать речь (пустой результат). "
                                "Попробуй сказать чётче или отправь текст."
                            )
                            ret = (chatId, outgoingText)
                        else:
                            writeJsonlEvent(
                                in_loggingSettings=self._settings.logging,
                                in_eventType="voice_transcription_succeeded",
                                in_payload={
                                    "chatId": chatId,
                                    "telegramUserId": userId,
                                    "updateId": updateId,
                                    "chars": len(transcribedText),
                                },
                            )
                            dto = IncomingTelegramMessageDto(
                                updateId=updateId,
                                telegramUserId=userId,
                                chatId=chatId,
                                text=transcribedText,
                                messageType="voice",
                                telegramFileId=fileId,
                            )
                            useCaseResult = self._handleIncomingTelegramMessageUseCase.execute(
                                in_messageDto=dto
                            )
                            ret = (chatId, useCaseResult.outgoingText)
                    except Exception as in_exc:
                        self._logger.error(f"voice_transcription_failed {in_exc}")
                        writeJsonlEvent(
                            in_loggingSettings=self._settings.logging,
                            in_eventType="voice_transcription_failed",
                            in_payload={
                                "chatId": chatId,
                                "telegramUserId": userId,
                                "updateId": updateId,
                                "error": str(in_exc),
                            },
                        )
                        ret = (
                            chatId,
                            "Не удалось распознать голосовое сообщение. Попробуй ещё раз или отправь текст.",
                        )
        return ret

    def _extractVoiceOrAudioMeta(
        self,
        *,
        in_updateData: dict[str, Any],
    ) -> tuple[int, int, int, str, int | None] | None:
        ret: tuple[int, int, int, str, int | None] | None
        messageData = in_updateData.get("message")
        if not isinstance(messageData, dict):
            ret = None
        else:
            fromData = messageData.get("from")
            chatData = messageData.get("chat")
            updateIdValue = in_updateData.get("update_id")
            if not (
                isinstance(fromData, dict)
                and isinstance(chatData, dict)
                and isinstance(fromData.get("id"), int)
                and isinstance(chatData.get("id"), int)
                and isinstance(updateIdValue, int)
            ):
                ret = None
            else:
                voiceData = messageData.get("voice")
                audioData = messageData.get("audio")
                targetData = voiceData if isinstance(voiceData, dict) else audioData
                if not isinstance(targetData, dict):
                    ret = None
                else:
                    fileIdValue = targetData.get("file_id")
                    durationValue = targetData.get("duration")
                    if not isinstance(fileIdValue, str) or fileIdValue.strip() == "":
                        ret = None
                    else:
                        durationSeconds: int | None
                        if isinstance(durationValue, int):
                            durationSeconds = max(0, durationValue)
                        else:
                            durationSeconds = None
                        ret = (
                            int(chatData["id"]),
                            int(fromData["id"]),
                            int(updateIdValue),
                            fileIdValue.strip(),
                            durationSeconds,
                        )
        return ret

    def _transcribeTelegramFile(
        self,
        *,
        in_fileId: str,
        in_maxBytes: int,
        in_maxSeconds: int,
    ) -> str:
        ret: str
        if self._telegramFileDownloader is None or self._voiceTranscriber is None:
            raise RuntimeError("voice_transcription_dependencies_missing")
        tmpDir = Path(self._settings.app.dataRootPath).resolve() / "tmp"
        tmpDir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".ogg",
            delete=False,
            dir=str(tmpDir),
        ) as handle:
            tmpPath = handle.name
        try:
            self._telegramFileDownloader.downloadTelegramFileToPath(
                in_fileId=in_fileId,
                in_outPath=tmpPath,
                in_maxBytes=in_maxBytes,
                in_timeoutSeconds=30.0,
            )
            ret = self._voiceTranscriber.transcribeToText(
                in_audioPath=tmpPath,
                in_language=str(getattr(self._settings.telegram, "voiceLanguage", "") or ""),
                in_maxSeconds=in_maxSeconds,
            )
        finally:
            try:
                Path(tmpPath).unlink(missing_ok=True)
            except Exception:
                pass
        return ret
