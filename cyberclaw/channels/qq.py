"""QQ channel implementation using botpy SDK."""

import asyncio
import re
import uuid
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from loguru import logger

from cyberclaw.bus.events import OutboundMessage
from cyberclaw.bus.queue import MessageBus
from cyberclaw.channels.base import BaseChannel
from cyberclaw.config.paths import get_media_dir
from cyberclaw.config.schema import QQConfig

try:
    import botpy
    from botpy.message import C2CMessage, GroupMessage

    QQ_AVAILABLE = True
except ImportError:
    QQ_AVAILABLE = False
    botpy = None
    C2CMessage = None
    GroupMessage = None

if TYPE_CHECKING:
    from botpy.message import C2CMessage, GroupMessage


def _make_bot_class(channel: "QQChannel") -> "type[botpy.Client]":
    """Create a botpy Client subclass bound to the given channel."""
    intents = botpy.Intents(public_messages=True, direct_message=True)

    class _Bot(botpy.Client):
        def __init__(self):
            # Disable botpy's file log — cyberclaw uses loguru; default "botpy.log" fails on read-only fs
            super().__init__(intents=intents, ext_handlers=False)

        async def on_ready(self):
            logger.info("QQ bot ready: {}", self.robot.name)

        async def on_c2c_message_create(self, message: "C2CMessage"):
            await channel._on_message(message, is_group=False)

        async def on_group_at_message_create(self, message: "GroupMessage"):
            await channel._on_message(message, is_group=True)

        async def on_direct_message_create(self, message):
            await channel._on_message(message, is_group=False)

    return _Bot


class QQChannel(BaseChannel):
    """QQ channel using botpy SDK with WebSocket connection."""

    name = "qq"

    def __init__(self, config: QQConfig, bus: MessageBus, groq_api_key: str = ""):
        super().__init__(config, bus)
        self.config: QQConfig = config
        self.groq_api_key = groq_api_key
        self._client: "botpy.Client | None" = None
        self._processed_ids: deque = deque(maxlen=1000)
        self._msg_seq: int = 1  # 消息序列号，避免被 QQ API 去重
        self._chat_type_cache: dict[str, str] = {}
        self._voice_chat_cache: dict[str, bool] = {}  # chat_id -> was last msg voice
        self._tts_provider = None  # lazy init

    async def start(self) -> None:
        """Start the QQ bot."""
        if not QQ_AVAILABLE:
            logger.error("QQ SDK not installed. Run: pip install qq-botpy")
            return

        if not self.config.app_id or not self.config.secret:
            logger.error("QQ app_id and secret not configured")
            return

        self._running = True
        BotClass = _make_bot_class(self)
        self._client = BotClass()
        logger.info("QQ bot started (C2C & Group supported, voice_reply={})", self.config.voice_reply)
        await self._run_bot()

    async def _run_bot(self) -> None:
        """Run the bot connection with auto-reconnect."""
        while self._running:
            try:
                await self._client.start(appid=self.config.app_id, secret=self.config.secret)
            except Exception as e:
                logger.warning("QQ bot error: {}", e)
            if self._running:
                logger.info("Reconnecting QQ bot in 5 seconds...")
                await asyncio.sleep(5)

    async def stop(self) -> None:
        """Stop the QQ bot."""
        self._running = False
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
        logger.info("QQ bot stopped")

    # ---- Send ----

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through QQ (voice or text)."""
        if not self._client:
            logger.warning("QQ client not initialized")
            return

        # If voice_reply is enabled and the last inbound was voice, try voice reply
        if self.config.voice_reply and self._voice_chat_cache.get(msg.chat_id):
            sent = await self._send_voice_reply(msg)
            if sent:
                return

        await self._send_text(msg)

    async def _send_text(self, msg: OutboundMessage) -> None:
        """Send a text message."""
        try:
            msg_id = msg.metadata.get("message_id")
            self._msg_seq += 1
            msg_type = self._chat_type_cache.get(msg.chat_id, "c2c")
            if msg_type == "group":
                await self._client.api.post_group_message(
                    group_openid=msg.chat_id,
                    msg_type=2,
                    markdown={"content": msg.content},
                    msg_id=msg_id,
                    msg_seq=self._msg_seq,
                )
            else:
                await self._client.api.post_c2c_message(
                    openid=msg.chat_id,
                    msg_type=2,
                    markdown={"content": msg.content},
                    msg_id=msg_id,
                    msg_seq=self._msg_seq,
                )
        except Exception as e:
            logger.error("Error sending QQ text message: {}", e)

    @staticmethod
    def _clean_for_tts(text: str) -> str:
        """Convert markdown text into natural spoken language for TTS."""
        # Remove code blocks — spoken context doesn't need raw code
        text = re.sub(r"```[\s\S]*?```", "", text)
        # Inline code: keep content, drop backticks
        text = re.sub(r"`([^`]*)`", r"\1", text)
        # Markdown links [text](url) -> just text
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
        # Bare URLs — replace with nothing
        text = re.sub(r"https?://\S+", "", text)
        # Headings: strip # markers, add pause (period) if missing
        text = re.sub(r"^#{1,6}\s*(.+)$", r"\1。", text, flags=re.MULTILINE)
        # Bold/italic markers
        text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
        text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
        # Bullet lists: convert to natural sentence flow with pauses
        text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
        # Numbered lists: keep number for spoken context (e.g. "1、xxx")
        text = re.sub(r"^\s*(\d+)[.)]\s+", r"\1、", text, flags=re.MULTILINE)
        # Table dividers and pipes
        text = re.sub(r"^\s*\|?[-:]+\|[-:|\s]+$", "", text, flags=re.MULTILINE)
        text = re.sub(r"\|", "，", text)
        # Blockquotes
        text = re.sub(r"^\s*>\s*", "", text, flags=re.MULTILINE)
        # Remaining noisy symbols
        text = re.sub(r"[~`]", "", text)
        # Collapse whitespace
        text = re.sub(r"\n{3,}", "\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()

    async def _send_voice_reply(self, msg: OutboundMessage) -> bool:
        """TTS + format conversion + QQ API voice send.

        Returns True if voice was sent successfully, False to fall back to text.
        """
        try:
            from cyberclaw.providers.audio_converter import AudioConverter
            from cyberclaw.providers.tts import EdgeTTSProvider

            if self._tts_provider is None:
                self._tts_provider = EdgeTTSProvider(voice=self.config.tts_voice)

            media_dir = get_media_dir("qq")
            file_id = uuid.uuid4().hex[:12]

            # 1. Strip markdown symbols and clean text for TTS
            tts_text = self._clean_for_tts(msg.content)

            # 2. Edge TTS -> mp3
            mp3_path = media_dir / f"tts_{file_id}.mp3"
            ok = await self._tts_provider.synthesize_to_file(tts_text, mp3_path)
            if not ok:
                logger.warning("TTS synthesis failed, falling back to text")
                return False

            # 2. mp3 -> silk
            silk_path = media_dir / f"tts_{file_id}.silk"
            ok = await AudioConverter.mp3_to_silk(mp3_path, silk_path)
            if not ok:
                logger.warning("mp3->silk conversion failed, falling back to text")
                mp3_path.unlink(missing_ok=True)
                return False

            # 3. Upload silk to get a public URL
            media_url = await self._upload_for_public_url(silk_path)
            msg_type_cache = self._chat_type_cache.get(msg.chat_id, "c2c")
            msg_id = msg.metadata.get("message_id")
            self._msg_seq += 1

            if msg_type_cache == "group":
                # Group voice: post_group_file -> post_group_message
                file_info = await self._client.api.post_group_file(
                    group_openid=msg.chat_id,
                    file_type=3,  # 3 = voice/silk
                    url=media_url,
                )
                await self._client.api.post_group_message(
                    group_openid=msg.chat_id,
                    msg_type=7,  # 7 = media
                    media=file_info,
                    msg_id=msg_id,
                    msg_seq=self._msg_seq,
                )
            else:
                # C2C voice: post_c2c_file -> post_c2c_message
                file_info = await self._client.api.post_c2c_file(
                    openid=msg.chat_id,
                    file_type=3,  # 3 = voice/silk
                    url=media_url,
                )
                await self._client.api.post_c2c_message(
                    openid=msg.chat_id,
                    msg_type=7,  # 7 = media
                    media=file_info,
                    msg_id=msg_id,
                    msg_seq=self._msg_seq,
                )

            logger.info("QQ voice reply sent to {}", msg.chat_id)

            # Cleanup temp files
            mp3_path.unlink(missing_ok=True)
            # Keep silk for a while in case QQ needs to re-fetch
            return True

        except Exception as e:
            logger.error("QQ voice reply failed: {}, falling back to text", e)
            return False

    async def _upload_for_public_url(self, file_path: Path) -> str:
        """Upload a file to a temporary public hosting service and return the direct URL.

        Uses tmpfiles.org (free, no auth required, files expire after ~1 hour).
        """
        # tmpfiles.org
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                with open(file_path, "rb") as f:
                    resp = await client.post(
                        "https://tmpfiles.org/api/v1/upload",
                        files={"file": (file_path.name, f, "application/octet-stream")},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("status") == "success":
                            # Convert page URL to direct download URL
                            # http://tmpfiles.org/12345/file.silk -> http://tmpfiles.org/dl/12345/file.silk
                            page_url = data["data"]["url"]
                            dl_url = page_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                            logger.debug("Uploaded to tmpfiles.org: {}", dl_url)
                            return dl_url
        except Exception as e:
            logger.warning("tmpfiles.org upload failed: {}", e)

        raise RuntimeError("Failed to upload file to public hosting service")

    # ---- Receive ----

    async def _on_message(self, data: "C2CMessage | GroupMessage", is_group: bool = False) -> None:
        """Handle incoming message from QQ."""
        try:
            # Dedup by message ID
            if data.id in self._processed_ids:
                return
            self._processed_ids.append(data.id)

            # Debug: dump full message for diagnostics
            logger.info("QQ raw message: {}", repr(data))

            content = (data.content or "").strip()
            media_files = []
            is_voice = False

            # Debug: log raw message structure
            attachments = getattr(data, "attachments", None) or []
            logger.info(
                "QQ msg: content={!r}, attachments_count={}, attachments={}",
                content[:100] if content else content,
                len(attachments),
                [repr(a) for a in attachments],
            )

            # Check attachments for voice
            for att in attachments:
                content_type = getattr(att, "content_type", "") or ""
                url = getattr(att, "url", "") or ""
                filename = getattr(att, "filename", "") or ""
                logger.info(
                    "QQ attachment: content_type={}, url={}, filename={}",
                    content_type, url[:100] if url else url, filename,
                )
                if not url:
                    continue
                # Detect voice: by content_type, url suffix, or filename
                is_audio = (
                    "audio" in content_type
                    or content_type == "voice"
                    or "silk" in content_type
                    or url.endswith(".amr")
                    or url.endswith(".silk")
                    or filename.endswith(".amr")
                    or filename.endswith(".silk")
                )
                if is_audio:
                    file_path = await self._download_attachment(url, att)
                    if file_path:
                        media_files.append(str(file_path))
                        is_voice = True
                        # STT transcription (Groq or FunASR)
                        text = await self._transcribe_voice(file_path)
                        if text:
                            content = text
                            logger.info("QQ voice transcribed: {}...", text[:50])
                    continue

                # Detect image: by content_type, url suffix, or filename
                is_image = (
                    content_type.startswith("image/")
                    or any(url.lower().endswith(e) for e in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"))
                    or any(filename.lower().endswith(e) for e in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"))
                )
                if is_image:
                    file_path = await self._download_attachment(url, att)
                    if file_path:
                        media_files.append(str(file_path))
                        logger.info("QQ image downloaded: {}", file_path.name)

            if is_group:
                chat_id = data.group_openid
                user_id = data.author.member_openid
                self._chat_type_cache[chat_id] = "group"
            else:
                chat_id = str(
                    getattr(data.author, "id", None)
                    or getattr(data.author, "user_openid", "unknown")
                )
                user_id = chat_id
                self._chat_type_cache[chat_id] = "c2c"

            self._voice_chat_cache[chat_id] = is_voice

            if not content:
                if is_voice:
                    content = "[voice message: transcription unavailable]"
                elif media_files:
                    content = "请描述这张图片"
                else:
                    return

            await self._handle_message(
                sender_id=user_id,
                chat_id=chat_id,
                content=content,
                media=media_files,
                metadata={"message_id": data.id},
            )
        except Exception:
            logger.exception("Error handling QQ message")

    async def _download_attachment(self, url: str, att) -> Path | None:
        """Download an attachment to the local media directory."""
        try:
            media_dir = get_media_dir("qq")
            # Determine file extension from filename, URL, or content_type
            att_filename = getattr(att, "filename", "") or ""
            content_type = getattr(att, "content_type", "") or ""

            # Image MIME -> extension mapping
            _IMAGE_EXT_MAP = {
                "image/jpeg": ".jpg", "image/png": ".png",
                "image/gif": ".gif", "image/webp": ".webp", "image/bmp": ".bmp",
            }

            if att_filename.endswith(".silk") or ".silk" in url or "silk" in content_type:
                ext = ".silk"
                prefix = "voice"
            elif att_filename.endswith(".amr") or ".amr" in url or "amr" in content_type:
                ext = ".amr"
                prefix = "voice"
            elif content_type in _IMAGE_EXT_MAP:
                ext = _IMAGE_EXT_MAP[content_type]
                prefix = "image"
            elif any(att_filename.lower().endswith(e) for e in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")):
                ext = Path(att_filename).suffix.lower()
                prefix = "image"
            else:
                ext = ".dat"
                prefix = "file"

            filename = f"{prefix}_{uuid.uuid4().hex[:12]}{ext}"
            file_path = media_dir / filename

            # Ensure url has scheme
            if url.startswith("//"):
                url = "https:" + url

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                file_path.write_bytes(resp.content)

            logger.debug("Downloaded QQ attachment: {} ({} bytes)", filename, file_path.stat().st_size)
            return file_path
        except Exception as e:
            logger.error("Failed to download QQ attachment: {}", e)
            return None

    async def _transcribe_voice(self, file_path: Path) -> str:
        """Transcribe a voice file: convert -> STT (Groq or FunASR fallback)."""
        try:
            from cyberclaw.providers.audio_converter import AudioConverter

            wav_path = file_path.with_suffix(".wav")

            # Convert to wav based on format
            if AudioConverter.is_silk_file(file_path) or file_path.suffix == ".silk":
                ok = await AudioConverter.silk_to_wav(file_path, wav_path)
            else:
                ok = await AudioConverter.any_to_wav(file_path, wav_path)

            if not ok:
                logger.warning("Audio conversion to wav failed for {}", file_path.name)
                return ""

            text = ""

            # Try Groq first if API key is available
            if self.groq_api_key:
                try:
                    from cyberclaw.providers.transcription import GroqTranscriptionProvider

                    transcriber = GroqTranscriptionProvider(api_key=self.groq_api_key)
                    text = await transcriber.transcribe(wav_path)
                    if text:
                        logger.debug("Transcribed via Groq Whisper")
                except Exception as e:
                    logger.warning("Groq transcription failed: {}, trying FunASR", e)

            # Fallback to FunASR (local model)
            if not text:
                try:
                    from cyberclaw.providers.stt_funasr import FunASRProvider

                    transcriber = FunASRProvider()
                    text = await transcriber.transcribe(wav_path)
                    if text:
                        logger.debug("Transcribed via FunASR (local)")
                except Exception as e:
                    logger.error("FunASR transcription failed: {}", e)

            # Cleanup wav
            wav_path.unlink(missing_ok=True)

            return text
        except Exception as e:
            logger.error("Voice transcription failed: {}", e)
            return ""
