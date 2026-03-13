"""Audio format converter using ffmpeg and pilk (for silk codec)."""

import asyncio
import struct
import tempfile
from pathlib import Path

from loguru import logger


class AudioConverter:
    """Convert between audio formats, with special support for QQ's silk format."""

    @staticmethod
    async def silk_to_wav(silk_path: Path, wav_path: Path) -> bool:
        """Convert silk audio to wav.

        silk -> pcm (pilk.decode) -> wav (ffmpeg)
        """
        try:
            import pilk
        except ImportError:
            logger.error("pilk not installed. Run: pip install pilk")
            return False

        try:
            with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as tmp:
                pcm_path = Path(tmp.name)

            # Strip \x02 prefix if present (Tencent/QQ silk format)
            data = silk_path.read_bytes()
            if data.startswith(b"\x02"):
                clean_silk = silk_path.with_suffix(".clean.silk")
                clean_silk.write_bytes(data[1:])
            else:
                clean_silk = silk_path

            # silk -> pcm
            duration = await asyncio.get_event_loop().run_in_executor(
                None, pilk.decode, str(clean_silk), str(pcm_path)
            )
            if clean_silk != silk_path:
                clean_silk.unlink(missing_ok=True)
            logger.debug("Decoded silk -> pcm ({:.1f}s)", duration / 1000)

            # pcm -> wav via ffmpeg
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1",
                "-i", str(pcm_path), str(wav_path),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()

            # cleanup
            pcm_path.unlink(missing_ok=True)

            if wav_path.exists() and wav_path.stat().st_size > 0:
                return True
            logger.warning("silk_to_wav: output file empty or missing")
            return False
        except Exception as e:
            logger.error("silk_to_wav error: {}", e)
            return False

    @staticmethod
    async def mp3_to_silk(mp3_path: Path, silk_path: Path) -> bool:
        """Convert mp3 audio to silk.

        mp3 -> pcm (ffmpeg, 24000Hz mono s16le) -> silk (pilk.encode)
        """
        try:
            import pilk
        except ImportError:
            logger.error("pilk not installed. Run: pip install pilk")
            return False

        try:
            with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as tmp:
                pcm_path = Path(tmp.name)

            # mp3 -> pcm via ffmpeg
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-i", str(mp3_path),
                "-f", "s16le", "-ar", "24000", "-ac", "1",
                str(pcm_path),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()

            if not pcm_path.exists() or pcm_path.stat().st_size == 0:
                logger.warning("mp3_to_silk: ffmpeg produced no pcm output")
                pcm_path.unlink(missing_ok=True)
                return False

            # pcm -> silk
            duration = await asyncio.get_event_loop().run_in_executor(
                None, pilk.encode, str(pcm_path), str(silk_path), 24000
            )
            logger.debug("Encoded pcm -> silk ({:.1f}s)", duration / 1000)

            # Add \x02 prefix required by Tencent/QQ silk format
            if silk_path.exists():
                data = silk_path.read_bytes()
                if not data.startswith(b"\x02"):
                    silk_path.write_bytes(b"\x02" + data)

            # cleanup
            pcm_path.unlink(missing_ok=True)

            if silk_path.exists() and silk_path.stat().st_size > 0:
                return True
            logger.warning("mp3_to_silk: output file empty or missing")
            return False
        except Exception as e:
            logger.error("mp3_to_silk error: {}", e)
            return False

    @staticmethod
    async def any_to_wav(input_path: Path, wav_path: Path) -> bool:
        """Convert any audio format to wav using ffmpeg."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-i", str(input_path),
                "-ar", "16000", "-ac", "1", str(wav_path),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()

            if wav_path.exists() and wav_path.stat().st_size > 0:
                return True
            logger.warning("any_to_wav: output file empty or missing")
            return False
        except FileNotFoundError:
            logger.error("ffmpeg not found. Install with: brew install ffmpeg")
            return False
        except Exception as e:
            logger.error("any_to_wav error: {}", e)
            return False

    @staticmethod
    def is_silk_file(file_path: Path) -> bool:
        """Check if a file is in silk format by examining the header."""
        try:
            with open(file_path, "rb") as f:
                header = f.read(10)
                # Silk files start with b'#!SILK_V3' or b'\x02#!SILK_V3'
                return b"#!SILK" in header
        except Exception:
            return False
