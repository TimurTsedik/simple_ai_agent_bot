from pathlib import Path
from typing import Any
import os

from app.integrations.speech.voiceTranscriberProtocol import VoiceTranscriberProtocol


class FasterWhisperTranscriber(VoiceTranscriberProtocol):
    def __init__(
        self,
        *,
        in_modelName: str,
        in_device: str,
        in_computeType: str,
        in_downloadRoot: str,
    ) -> None:
        self._modelName = str(in_modelName or "small").strip() or "small"
        self._device = str(in_device or "cpu").strip() or "cpu"
        self._computeType = str(in_computeType or "int8").strip() or "int8"
        self._downloadRoot = str(in_downloadRoot or "").strip()
        self._model: Any | None = None

    def transcribeToText(
        self,
        *,
        in_audioPath: str,
        in_language: str,
        in_maxSeconds: int,
    ) -> str:
        ret: str
        audioPathValue = str(in_audioPath or "").strip()
        languageValue = str(in_language or "").strip()
        maxSecondsValue = max(1, int(in_maxSeconds))
        if audioPathValue == "":
            raise ValueError("audioPath is required")
        _ = Path(audioPathValue).resolve()  # normalize

        model = self._getModel()
        segments, info = model.transcribe(
            audioPathValue,
            language=languageValue if languageValue != "" else None,
            vad_filter=True,
        )
        # NOTE: faster-whisper doesn't provide hard cut by seconds at API level reliably;
        # enforce a conservative limit by stopping after N seconds worth of segments.
        collected: list[str] = []
        elapsedSeconds = 0.0
        for segment in segments:
            collected.append(str(segment.text or "").strip())
            try:
                elapsedSeconds = float(segment.end)
            except Exception:
                elapsedSeconds = elapsedSeconds
            if elapsedSeconds >= float(maxSecondsValue):
                break
        transcript = " ".join(item for item in collected if item != "").strip()
        if transcript == "":
            # `info` exists to help debug, but we keep returned text empty and let caller decide.
            ret = ""
        else:
            ret = transcript
        _ = info
        return ret

    def _getModel(self) -> Any:
        ret: Any
        if self._model is None:
            from faster_whisper import WhisperModel

            downloadRootValue = self._downloadRoot if self._downloadRoot != "" else None
            if downloadRootValue is not None:
                downloadRootPath = Path(downloadRootValue).resolve()
                downloadRootPath.mkdir(parents=True, exist_ok=True)
                # Make sure HF/transformers/onnxruntime caches are writable in containers.
                # Prefer explicit env overrides to avoid writing under /home/appuser/.cache or similar.
                os.environ.setdefault("HF_HOME", str(downloadRootPath))
                os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(downloadRootPath / "huggingface"))
                os.environ.setdefault("XDG_CACHE_HOME", str(downloadRootPath / "xdg_cache"))
                os.environ.setdefault("TORCH_HOME", str(downloadRootPath / "torch"))
            self._model = WhisperModel(
                self._modelName,
                device=self._device,
                compute_type=self._computeType,
                download_root=downloadRootValue,
            )
        ret = self._model
        return ret

