"""Speech-to-Text provider using FunASR (local, offline)."""

import asyncio
from pathlib import Path

from loguru import logger

# Lazy-loaded globals
_model = None
_model_lock = asyncio.Lock()


async def _get_model():
    """Lazy-load the FunASR model (thread-safe singleton)."""
    global _model
    if _model is not None:
        return _model

    async with _model_lock:
        if _model is not None:
            return _model

        logger.info("Loading FunASR model (first-time download may take a while)...")
        loop = asyncio.get_event_loop()

        def _load():
            from funasr import AutoModel

            return AutoModel(
                model="paraformer-zh",
                vad_model="fsmn-vad",
                punc_model="ct-punc",
            )

        _model = await loop.run_in_executor(None, _load)
        logger.info("FunASR model loaded successfully")
        return _model


class FunASRProvider:
    """Local speech-to-text using FunASR Paraformer (Chinese + English)."""

    async def transcribe(self, file_path: str | Path) -> str:
        """Transcribe an audio file.

        Args:
            file_path: Path to audio file (wav, mp3, amr, etc.)

        Returns:
            Transcribed text, or empty string on failure.
        """
        path = Path(file_path)
        if not path.exists():
            logger.error("Audio file not found: {}", file_path)
            return ""

        try:
            model = await _get_model()
            loop = asyncio.get_event_loop()

            def _infer():
                res = model.generate(input=str(path))
                if res and len(res) > 0 and "text" in res[0]:
                    return res[0]["text"]
                return ""

            text = await loop.run_in_executor(None, _infer)
            if text:
                logger.debug("FunASR transcribed: {}...", text[:80])
            return text
        except Exception as e:
            logger.error("FunASR transcription error: {}", e)
            return ""
