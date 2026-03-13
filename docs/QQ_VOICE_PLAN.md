# QQ 语音交互 — 实施记录

## Context

cyberclaw QQ channel 原仅支持文本。目标：文字提问→文字回答，语音提问→语音回答。

**技术选型**：
- STT = Groq Whisper（优先） → FunASR Paraformer 本地模型（备选）
- TTS = Edge TTS（免费、中文好）
- 格式转换 = ffmpeg + pilk

---

## QQ 语音 API 实际行为

- **接收语音**: `C2CMessage.attachments[]` 中 `content_type="voice"`（非 `"audio"`），`filename="xxx.amr"`，`url` 为 HTTPS 下载链接
- **发送语音**: `post_c2c_file(openid, file_type=3, url=公网URL)` → 获得 `Media` 对象 → `post_c2c_message(msg_type=7, media=media)`
- **群组语音**: `post_group_file` / `post_group_message` 同理
- **语音格式**: QQ 要求 **silk** 格式，且必须带 `\x02` 字节前缀（腾讯特有要求，标准 silk 以 `#!SILK_V3` 开头）
- **限制**: `post_c2c_file` 的 `url` 参数**必须是公网可访问的 URL**，localhost 不可用

---

## 数据流（实际实现）

```
语音输入:
  QQ用户发语音 → attachments[].url → httpx 下载到 ~/.cyberclaw/media/qq/
  → silk/amr → AudioConverter.silk_to_wav (剥离\x02前缀 → pilk.decode → pcm → ffmpeg → wav)
  → Groq Whisper STT (如有 API key) → 失败则 FunASR 本地 STT
  → 转写文字 → AgentLoop 处理

语音输出:
  Agent 文字回复 → Edge TTS → mp3
  → AudioConverter.mp3_to_silk (ffmpeg → pcm 24000Hz → pilk.encode → silk → 添加\x02前缀)
  → tmpfiles.org 上传获得公网 URL
  → QQ post_c2c_file(file_type=3, url=公网URL) → 获得 Media
  → QQ post_c2c_message(msg_type=7, media=Media) → 用户收到语音

文字输入:
  正常文字处理，不触发 TTS，文字回复
```

---

## 新建文件

### 1. `cyberclaw/providers/tts.py` — Edge TTS Provider

```python
class EdgeTTSProvider:
    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural"):
        self.voice = voice

    async def synthesize_to_file(self, text: str, output_path: Path) -> bool:
        """文字 → MP3 文件"""
        import edge_tts
        communicate = edge_tts.Communicate(text=text, voice=self.voice)
        await communicate.save(str(output_path))
        return output_path.exists() and output_path.stat().st_size > 0
```

### 2. `cyberclaw/providers/audio_converter.py` — 音频格式转换

```python
class AudioConverter:
    @staticmethod
    async def silk_to_wav(silk_path, wav_path) -> bool:
        """silk → wav: 剥离\x02前缀 → pilk.decode → pcm → ffmpeg(24000Hz s16le) → wav"""

    @staticmethod
    async def mp3_to_silk(mp3_path, silk_path) -> bool:
        """mp3 → silk: ffmpeg → pcm(24000Hz mono s16le) → pilk.encode → 添加\x02前缀"""

    @staticmethod
    async def any_to_wav(input_path, wav_path) -> bool:
        """任意音频 → wav (ffmpeg, 16000Hz mono)"""

    @staticmethod
    def is_silk_file(file_path) -> bool:
        """检查文件头是否含 b'#!SILK'（含或不含\x02前缀）"""
```

关键细节：
- `mp3_to_silk` 编码后检查是否已有 `\x02` 前缀，没有则添加
- `silk_to_wav` 解码前检查是否有 `\x02` 前缀，有则剥离到临时 .clean.silk 文件
- pcm 采样率统一使用 24000Hz

### 3. `cyberclaw/providers/stt_funasr.py` — FunASR 本地 STT（原计划外新增）

```python
_model = None          # 全局单例
_model_lock = asyncio.Lock()  # 线程安全

async def _get_model():
    """懒加载 FunASR 模型（首次约 2GB 下载）"""
    # AutoModel(model="paraformer-zh", vad_model="fsmn-vad", punc_model="ct-punc")

class FunASRProvider:
    async def transcribe(self, file_path: str | Path) -> str:
        """音频文件 → 文字（支持中英文）"""
        model = await _get_model()
        # run_in_executor: model.generate(input=str(path)) → res[0]["text"]
```

新增原因：Groq API key 未配置时需要本地 STT 能力。

---

## 修改文件

### 4. `cyberclaw/config/schema.py` — QQConfig 新增字段

```python
class QQConfig(BaseModel):
    enabled: bool = False
    app_id: str = ""
    secret: str = ""
    allow_from: list[str] = Field(default_factory=list)
    voice_reply: bool = False                    # 对语音消息是否语音回复
    tts_voice: str = "zh-CN-XiaoxiaoNeural"      # TTS 语音角色
```

配置文件使用 **snake_case**（与其他 channel 配置一致）：
```json
{
  "qq": {
    "enabled": true,
    "app_id": "...",
    "secret": "...",
    "voice_reply": true,
    "tts_voice": "zh-CN-XiaoxiaoNeural"
  }
}
```

### 5. `cyberclaw/channels/manager.py` — 传入 groq_api_key

```python
self.channels["qq"] = QQChannel(
    self.config.channels.qq, self.bus,
    groq_api_key=self.config.providers.groq.api_key,
)
```

### 6. `cyberclaw/channels/qq.py` — 核心改造

#### 构造函数
```python
def __init__(self, config: QQConfig, bus: MessageBus, groq_api_key: str = ""):
    super().__init__(config, bus)
    self.groq_api_key = groq_api_key
    self._voice_chat_cache: dict[str, bool] = {}  # chat_id → 上条是否语音
    self._tts_provider = None  # lazy init
```

#### 语音检测（`_on_message` 中）
```python
# QQ 语音附件的 content_type 是 "voice"（不是 "audio"）
is_audio = (
    "audio" in content_type
    or content_type == "voice"
    or "silk" in content_type
    or url.endswith(".amr")
    or url.endswith(".silk")
    or filename.endswith(".amr")
    or filename.endswith(".silk")
)
```

#### 附件下载（`_download_attachment`）
- 优先从 `att.filename` 推断扩展名（QQ 的 url 通常是无后缀的通用下载链接）
- 使用 httpx 下载到 `~/.cyberclaw/media/qq/`

#### STT 转写（`_transcribe_voice`）
```python
async def _transcribe_voice(self, file_path: Path) -> str:
    # 1. 音频 → wav
    if AudioConverter.is_silk_file(file_path) or file_path.suffix == ".silk":
        AudioConverter.silk_to_wav(file_path, wav_path)
    else:
        AudioConverter.any_to_wav(file_path, wav_path)

    # 2. Groq Whisper STT（优先，需 API key）
    if self.groq_api_key:
        text = GroqTranscriptionProvider(api_key=self.groq_api_key).transcribe(wav_path)

    # 3. FunASR 本地 STT（备选）
    if not text:
        text = FunASRProvider().transcribe(wav_path)
```

#### 语音发送（`send` / `_send_voice_reply`）
```python
async def send(self, msg: OutboundMessage):
    if self.config.voice_reply and self._voice_chat_cache.get(msg.chat_id):
        if await self._send_voice_reply(msg):
            return
    await self._send_text(msg)

async def _send_voice_reply(self, msg: OutboundMessage) -> bool:
    # 1. Edge TTS → mp3
    # 2. AudioConverter.mp3_to_silk → silk（含\x02前缀）
    # 3. tmpfiles.org 上传 → 公网 URL
    # 4. QQ API post_c2c_file / post_group_file (file_type=3, url=公网URL) → Media
    # 5. QQ API post_c2c_message / post_group_message (msg_type=7, media=Media)
```

#### 公网 URL 获取（`_upload_for_public_url`）
```python
async def _upload_for_public_url(self, file_path: Path) -> str:
    """上传到 tmpfiles.org 获取公网直链"""
    # POST https://tmpfiles.org/api/v1/upload → page_url
    # 转换: tmpfiles.org/12345/file.silk → tmpfiles.org/dl/12345/file.silk
```

原计划使用 gateway `/media/` 端点，但该端点绑定 localhost 无法被 QQ 服务器访问。
先后尝试了 0x0.st（403 UA限制）、file.io（301重定向问题），最终使用 tmpfiles.org（免费、无需认证、文件约 1 小时过期）。

### 7. `cyberclaw/gateway/http_server.py` — /media/ 路由

```python
# 新增路由: GET /media/{filename}
# 从 ~/.cyberclaw/media/qq/ 提供文件下载
# 支持 .silk, .mp3, .wav, .amr 等格式
# 含路径遍历防护（禁止 /, \, ..）
```

> 注意：此端点保留为通用工具，但**不用于 QQ 语音上传**（QQ 需要公网 URL）。

---

## 涉及文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `cyberclaw/providers/tts.py` | 新建 | Edge TTS Provider |
| `cyberclaw/providers/audio_converter.py` | 新建 | 音频格式转换（ffmpeg+pilk，含\x02前缀处理） |
| `cyberclaw/providers/stt_funasr.py` | 新建 | FunASR 本地 STT（计划外新增） |
| `cyberclaw/config/schema.py` | 修改 | QQConfig 新增 voice_reply, tts_voice |
| `cyberclaw/channels/qq.py` | 修改 | 语音接收、STT、TTS、语音发送、tmpfiles.org 上传 |
| `cyberclaw/channels/manager.py` | 修改 | 传入 groq_api_key |
| `cyberclaw/gateway/http_server.py` | 修改 | 新增 /media/ 路由（通用工具） |

---

## 依赖安装

```bash
pip install edge-tts pilk funasr modelscope
# 系统级 (macOS):
brew install ffmpeg
```

- `edge-tts`: TTS 合成
- `pilk`: silk 编解码
- `funasr` + `modelscope`: 本地 STT（FunASR Paraformer 模型，首次运行下载约 2GB）
- `ffmpeg`: 音频格式转换

---

## 验证步骤

1. 安装依赖: `pip install edge-tts pilk funasr modelscope`
2. 确认 `ffmpeg -version` 可用
3. 配置 `~/.cyberclaw/config.json` 中 qq 字段: `"voice_reply": true, "tts_voice": "zh-CN-XiaoxiaoNeural"`
4. 启动: `cyberclaw gateway -m -w /path/to/workspace`
5. QQ 发**文字**消息 → 应收到**文字**回复
6. QQ 发**语音**消息 → 日志应显示：下载 → silk→wav → STT转写 → Agent处理 → TTS→mp3 → mp3→silk → tmpfiles.org上传 → QQ语音回复
7. 运行测试: `pytest tests/ -x --ignore=tests/test_matrix_channel.py`

---

## 实施中遇到的问题与解决

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 语音消息检测不到 | QQ 语音的 `content_type` 是 `"voice"` 而非 `"audio"` | 增加 `content_type == "voice"` 检测条件 |
| 下载文件扩展名为 `.audio` | QQ 的 URL 是通用下载链接，无后缀 | 优先从 `att.filename` 推断扩展名 |
| Groq STT 无输出 | 未配置 Groq API key | 新增 FunASR 本地 STT 作为备选方案 |
| `post_c2c_file` 报 "请求参数url无效" | gateway `/media/` 绑定 localhost，QQ 服务器无法访问 | 改用 tmpfiles.org 上传获取公网 URL |
| 0x0.st 上传 403 | "User agent not allowed" | 弃用，改用 tmpfiles.org |
| QQ 服务器报 "to pcm err: exit status 183" | silk 文件缺少 `\x02` 字节前缀（腾讯/QQ 特有要求） | `mp3_to_silk` 编码后添加 `\x02` 前缀 |
| config.json 字段不生效 | 最初用 camelCase（`voiceReply`），但其他 channel 用 snake_case | 改为 snake_case（`voice_reply`） |

---

## 待验证

- [ ] `\x02` silk 前缀修复后，QQ 服务器是否能正确解码并发送语音消息给用户
- [ ] 群组语音收发是否正常（`post_group_file` / `post_group_message`）
- [ ] 长文本 TTS 是否有时长限制或需要分段

---

## 风险与备选

| 风险 | 备选方案 |
|------|---------|
| tmpfiles.org 不可用/限速 | 换用其他文件托管服务，或部署公网可访问的文件服务器 |
| pilk 在某些平台编译失败 | 用 ffmpeg silk 编解码器（需特殊编译） |
| edge-tts 网络不通 | 自动降级为文字回复（已实现） |
| FunASR 模型下载慢 | 首次加载需耐心等待，后续使用本地缓存 |
