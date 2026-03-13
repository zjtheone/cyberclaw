"""Text-to-Speech provider using Edge TTS."""

from pathlib import Path

from loguru import logger


class EdgeTTSProvider:
    """TTS provider using Microsoft Edge TTS (free, good Chinese support)."""

    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural"):
        self.voice = voice

    async def synthesize_to_file(self, text: str, output_path: Path) -> bool:
        """Synthesize text to an MP3 file.

        Args:
            text: Text to synthesize.
            output_path: Path to save the MP3 file.

        Returns:
            True if successful.
        """
        try:
            import edge_tts
        except ImportError:
            logger.error("edge-tts not installed. Run: pip install edge-tts")
            return False

        if not text.strip():
            logger.warning("Empty text for TTS synthesis")
            return False

        try:
            communicate = edge_tts.Communicate(text=text, voice=self.voice)
            await communicate.save(str(output_path))
            if output_path.exists() and output_path.stat().st_size > 0:
                logger.debug("TTS synthesized {} chars -> {}", len(text), output_path.name)
                return True
            logger.warning("TTS output file empty or missing: {}", output_path)
            return False
        except Exception as e:
            logger.error("Edge TTS synthesis error: {}", e)
            return False
