

<div align="center">
  <img src="cyberclaw_logo.png" alt="cyberclaw" width="500">
  <h1>cyberclaw: Asistente de IA Personal Ultraligero</h1>
  <p>
    <a href="https://pypi.org/project/cyberclaw-ai/"><img src="https://img.shields.io/pypi/v/cyberclaw-ai" alt="PyPI"></a>
    <a href="https://pepy.tech/project/cyberclaw-ai"><img src="https://static.pepy.tech/badge/cyberclaw-ai" alt="Downloads"></a>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <a href="./COMMUNICATION.md"><img src="https://img.shields.io/badge/Feishu-Group-E9DBFC?style=flat&logo=feishu&logoColor=white" alt="Feishu"></a>
    <a href="./COMMUNICATION.md"><img src="https://img.shields.io/badge/WeChat-Group-C5EAB4?style=flat&logo=wechat&logoColor=white" alt="WeChat"></a>
    <a href="https://discord.gg/MnCvHqpUGB"><img src="https://img.shields.io/badge/Discord-Community-5865F2?style=flat&logo=discord&logoColor=white" alt="Discord"></a>
  </p>
</div>

🦞 **cyberclaw** es un asistente de IA personal **ultraligero**, bifurcado de [nanobot](https://github.com/HKUDS/nanobot) y profundamente personalizado.

⚡️ Ofrece la funcionalidad central del agente con un **99% menos de líneas de código** que los frameworks mainstream.

📏 Conteo de líneas en tiempo real: ejecuta `bash core_agent_lines.sh` para verificar en cualquier momento.

---

## 🆚 cyberclaw vs nanobot — ¿Qué hay de nuevo?

cyberclaw está bifurcado de [nanobot](https://github.com/HKUDS/nanobot) con capacidadesnuevas capacidades significativas. Esto es lo que hemos añadido:

| Categoría                     | nanobot (upstream)                       | cyberclaw (esta bifurcación)                                                          |
| ----------------------------- | ---------------------------------------- | -------------------------------------------------------------------------------------- |
| **Agente de Auto-mejora**     | —                                        | Motor de Reflexión + Repositorio de Experiencias + Analizador de Evolución de Habilidades |
| **Multi-Agente (A2A)**        | —                                        | Protocolo completo Agente-a-Agente con motor de políticas, diálogo PingPong, cadena de anuncios |
| **Consola Web**               | —                                        | Interfaz basada en Streamlit con chat en tiempo real, gestión de sesiones, monitoreo de subagentes |
| **Visualización de Pensamiento** | —                                     | Proceso de razonamiento/pensamiento de IA colapsable en el chat                        |
| **Evaluación de Confianza**   | —                                        | Puntuación de confianza de respuesta con umbral configurable                           |
| **Optimización de Herramientas** | —                                     | Selección inteligente de herramientas basada en tasas de éxito históricas              |
| **Monitoreo de Salud de Habilidades** | —                                  | Puntuación automática de salud (tasa de éxito, frecuencia, antigüedad, diversidad de fallos) |
| **Planificador de Tareas**    | —                                        | Módulo de descomposición y planificación de tareas                                     |
| **Reconocimiento de Imágenes de QQ** | Solo texto y voz                        | Descarga automática de imágenes, descripción mediante LLM multimodal                   |
| **Limpieza de Markdown para TTS en QQ** | Markdown sin procesar enviado a TTS                 | `_clean_for_tts()` elimina bloques de código, enlaces y tablas para un habla más natural          |
| **Corrección de Compresión de Contexto** | El límite de guardado puede derivar después de la compresión | `save_from` rastrea el límite correctamente a través de ciclos de recorte/compresión                 |
| **Cobertura de Pruebas**      | Básica                                   | 59 archivos de prueba con cobertura exhaustiva para todas las nuevas funciones         |
| **Documentación**             | Básica                                   | 28 documentos detallados que cubren A2A, auto-mejora, consola web, seguridad, etc.     |

### Nuevos Módulos Clave

```
cyberclaw/agent/
├── reflection.py       # 🪞 Reflexión post-tarea y análisis de causa raíz
├── experience.py       # 📚 Reutilización de soluciones y seguimiento de patrones de fallo
├── skill_evolution.py  # 📈 Puntuación de salud de habilidades e informes de evolución
├── confidence.py       # 🎯 Evaluación de confianza de respuesta
├── tool_optimizer.py   # ⚡ Optimización del rendimiento histórico de herramientas
├── policy_engine.py    # 🔒 AplicEjecución de lista blanca/negra/profundidad de A2A
├── pingpong_dialog.py  # 🏓 Conversaciones multiedad agenteagente-a-agente
├── announce_chain.py   # 📢 Agregación jerárquica de resultados
├── a2a_flow.py         # 🔄 Gestión de flujos de trabajo Agente-a-Agente
├── subagent.py         # 🤖 Orquestación de subagentes en segundo plano
├── planner.py          # 📋 Planificación y descomposición de tareas
└── tools/
    └── self_improvement.py  # 🛠️ ConsultaConsultar reflexiones, experiencias y métricas
web_console/                 # 🌐 Interfaz web Streamlit (10 archivos)
```

> Consulta [docs/SELF_IMPROVING_AGENT.md](docs/SELF_IMPROVING_AGENT.md) y [docs/A2A_COMPLETE_GUIDE.md](docs/A2A_COMPLETE_GUIDE.md) para más detalles.

---

## 📢 NoticiasNoticias

- **2026-03-13** 🖼️ El canal QQ ahora admite **reconocimiento de imágenes** y **limpieza de markdown para TTS** — las imágenes se descargan automáticamente y se describen, las respuestas por voz eliminan el markdown para un habla más natural. También se corrigió un error en la compresión de contexto que podía corromper los límites de guardado de la sesión.
- **2026-03-08** 🚀 Se lanzó **v0.1.4.post4** — una versión enfocada en la fiabilidad con valores predeterminados más seguros, mejor soporte para múltiples instancias, MCP más robusto y mejoras importantes en canales y proveedores. Consulta las [notas de la versión](https://github.com/HKUDS/cyberclaw/releases/tag/v0.1.4.post4) para más detalles.
- **2026-03-07** 🚀 Proveedor de Azure OpenAI, multimedia de WhatsApp, chats grupales de QQ y más pulido para Telegram/Feishu.
- **2026-03-06** 🪄 Proveedores más ligeros, manejo inteligente de multimedia y memoria/compatibilidad CLI más robustas.
- **2026-03-05** ⚡️ Streaming de borradores en Telegram, soporte MCP SSE y correcciones de fiabilidad más amplias en canales.
- **2026-03-04** 🛠️ Limpieza de dependencias, lecturalecturas de archivos más seguras y otra ronda de correcciones en pruebas y Cron.
- **2026-03-03** 🧠 Fusión de mensajes de usuario más limpia, guardados multimodales más seguros y protecciones Cron más fuertes.
- **2026-03-02** 🛡️ Control de acceso predeterminado más seguro, recargas Cron más robustas y manejo de multimedia en Matrix más limpio.
- **2026-03-01** 🌐 Soporte de proxy web, recordatorios Cron más inteligentes y mejoras en el análisis de texto enriquecido de Feishu.
- **2026-02-28** 🚀 Se lanzó **v0.1.4.post3** — contexto más limpio, historial de sesiones endurecido y agente más inteligente. Consulta las [notas de la versión](https://github.com/HKUDS/cyberclaw/releases/tag/v0.1.4.post3) para más detalles.
- **2026-02-27** 🧠 Soporte experimental de modo de pensamiento, mensajes multimedia de DingTalk y correcciones en canales de Feishu y QQ.
- **2026-02-26** 🛡️ Corrección de envenenamiento de sesionessecciones, deduplicación de WhatsApp, protección de rutas en Windows y compatibilidad con Mistral.

<details>
<summary>Noticias anteriores</summary>

- **2026-02-25** 🧹 Nuevo canal Matrix, contexto de sesión más limpio, sincronización automática de plantillas de workspace.
- **2026-02-24** 🚀 Se lanzó **v0.1.4.post2** — una versión enfocada en la fiabilidad con un latido rediseñado, optimización de caché de prompts y mayor estabilidad de proveedores y canales. Consulta las [notas de la versión](https://github.com/HKUDS/cyberclaw/releases/tag/v0.1.4.post2) para más detalles.
- **2026-02-23** 🔧 Latido de llamada a herramienta virtuales, optimización de caché de prompts, correcciones en Slack mrkdwn.
- **2026-02-22** 🛡️ Aislamiento de hilos en Slack, corrección de tipe en Discord y mejoras de fiabilidad del agente.
- **2026-02-21** 🎉 Se lanzó **v0.1.4.post1** — nuevos proveedores, soporte multimedia en canales y mejoras de estabilidad importantes. Consulta las [notas de la versión](https://github.com/HKUDS/cyberclaw/releases/tag/v0.1.4.post1) para más detalles.
- **2026-02-20** 🐦 Feishu ahora recibe archivos multimodales de los usuarios. Memoria más fiable bajo el capó.
- **2026-02-19** ✨ Slack ahora envía archivos, Discord divide mensajes largos y los subagentes funcionan en modo CLI.
- **2026-02-18** ⚡️ cyberclaw ahora soporta VolcEngine, cabeceras de autenticación personalizadas para MCP y caché de prompts de Anthropic.
- **2026-02-17** 🎉 Se lanzó **v0.1.4** — So para MCP, streaming de progreso, nuevos proveedores y múltiples mejoras en canales. Consulta las [notas de la versión](https://github.com/HKUDS/cyberclaw/releases/tag/v0.1.4) para más detalles.
- **2026-02-16** 🦞 cyberclaw ahora integra una habilidad de [ClawHub](https://clawhub.ai) — busca e instala habilidades de agentes públicas.
- **2026-02-15** 🔑 cyberclaw ahora soporta el proveedor OpenAI Codex con soporte de inicio de sesión OAuth.
- **2026-02-14** 🔌 cyberclaw ahora soporta MCP! Consulta la [sección MCP](#mcp-model-context-protocol) para más detalles.
- **2026-02-13** 🎉 Se lanzó **v0.1.3.post7** — incluye endurecimiento de seguridad y múltiples mejoras. **Actualiza a la última versión para solucionar problemas de seguridad**. Consulta las [notas de la versión](https://github.com/HKUDS/cyberclaw/releases/tag/v0.1.3.post7) para más detalles.
- **2026-02-12** 🧠 Sistema de memoria rediseñado — Menos código, más fiable. ¡Únete a la [discusión](https://github.com/HKUDS/cyberclaw/discussions/566) al respecto!
- **2026-02-11** ✨ Experiencia CLI mejorada y añadido soporte para MiniMax!
- **2026-02-10** 🎉 Se lanzó **v0.1.3.post6** con mejoras! Consulta las [notas](https://github.com/HKUDS/cyberclaw/releases/tag/v0.1.3.post6) y nuestro [roadmap](https://github.com/HKUDS/cyberclaw/discussions/431).
- **2026-02-09** 💬 Añadido soporte para Slack, Email y QQ — ¡cyberclaw ahora soporta múltiples plataformas de chat!
- **2026-02-08** 🔧 Proveedores refactorizados — ¡añadir un nuevo proveedor LLM ahora toma solo 2 pasos simples! Consulta [aquí](#providers).
- **2026-02-07** 🚀 Se lanzó **v0.1.3.post5** con soporte para Qwen y varias mejoras clave! Consulta [aquí](https://github.com/HKUDS/cyberclaw/releases/tag/v0.1.3.post5) para más detalles.
- **2026-02-06** ✨ Añadido proveedor Moonshot/Kimi, integración con Discord y mayor endurecimiento de seguridad!
- **2026-02-05** ✨ Añadido canal Feishu, proveedor DeepSeek y soporte mejorado para tareas programadas!
- **2026-02-04** 🚀 Se lanzó **v0.1.3.post4** con soporte multi-proveedor y Docker! Consulta [aquí](https://github.com/HKUDS/cyberclaw/releases/tag/v0.1.3.post4) para más detalles.
- **2026-02-03** ⚡ Integrado vLLM para soporte de LLM local y mejorada la programación de tareas en lenguaje natural!
- **2026-02-02** 🎉 ¡cyberclaw se lanzó oficialmente! ¡Da la bienvenida a probar 🦞 cyberclaw!

</details>

## Características Clave de cyberclaw:

🪶 **Ultraligero**: Solo ~4,000 líneas de código del agente principal — un 99% más pequeño que Clawdbot.

🔬 **Preparado para InvestigaciónInvestigación**: Código limpio y legible que es fácil de entender, modificar y extender para investigación.

⚡️ **Ultra Rápido**: Una huella mínima significa un inicio más rápido, menor uso de recursos e iteraciones más rápidas.

💎 **Fácil de Usar**: Implementación con un solo clic y listo para usar.

## 🏗️ Arquitectura

<p align="center">
  <img src="cyberclaw_arch.png" alt="cyberclaw architecture" width="800">
</p>

## ✨ Funciones

<table align="center">
  <tr align="center">
    <th><p align="center">📈 Análisis de Mercado en Tiempo Real 24/7</p></th>
    <th><p align="center">🚀 Ingeniero de Software Full-Stack</p></th>
    <th><p align="center">📅 Administrador Inteligente de Rutinas Diarias</p></th>
    <th><p align="center">📚 Asistente Personal de Conocimiento</p></th>
  </tr>
  <tr>
    <td align="center"><p align="center"><img src="case/search.gif" width="180" height="400"></p></td>
    <td align="center"><p align="center"><img src="case/code.gif" width="180" height="400"></p></td>
    <td align="center"><p align="center"><img src="case/scedule.gif" width="180" height="400"></p></td>
    <td align="center"><p align="center"><img src="case/memory.gif" width="180" height="400"></p></td>
  </tr>
  <tr>
    <td align="center">Descubrimiento • Perspectivas • Tendencias</td>
    <td align="center">Desarrollar • Implementar • Escalar</td>
    <td align="center">Programar • Automatizar • Organizar</td>
    <td align="center">Aprender • Memoria • Razonamiento</td>
  </tr>
</table>

## 📦 Instalar

**Instalar desde el código fuente** (últimas funciones, recomendado para desarrollo)

```bash
git clone https://github.com/zjtheone/cyberclaw.git
cd cyberclaw
pip install -e .
```

**Instalar con [uv](https://github.com/astral-sh/uv)** (estable, rápido)

```bash
uv tool install cyberclaw-ai
```

**Instalar desde PyPI** (estable)

```bash
pip install cyberclaw-ai
```

### Actualizar a la última versión

**PyPI / pip**

```bash
pip install -U cyberclaw-ai
cyberclaw --version
```

**uv**

```bash
uv tool upgrade cyberclaw-ai
cyberclaw --version
```

**¿Usas WhatsApp?** Reconstruye el puente local después de actualizar:

```bash
rm -rf ~/.cyberclaw/bridge
cyberclaw channels login
```

## 🚀 Inicio Rápido

> [!TIP]
> Configura tu clave API en `~/.cyberclaw/config.json`.
> Obtén claves API: [OpenRouter](https://openrouter.ai/keys) (Global) · [Brave Search](https://brave.com/search/api/) (opcional, para búsqueda web)

**1. Inicializar**

```bash
cyberclaw onboard
```

**2. Configurar** (`~/.cyberclaw/config.json`)

Agrega o fusiona estas **dos partes** en tu configuración (las demás opciones tienen valores predeterminados).

*Configura tu clave API* (ej. OpenRouter, recomendado para usuarios globales):
```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-xxx"
    }
  }
}
```

*Configura tu modelo* (opcionalmente fija un proveedor — predeterminado a detección automática):
```json
{
  "agents": {
    "defaults": {
      "model": "anthropic/claude-opus-4-5",
      "provider": "openrouter"
    }
  }
}
```

**3. Chatear**

```bash
cyberclaw agent
```

¡Eso es todo! Tienes un asistente de IA funcionando en 2 minutos.

## 💬 Apps de Chat

Conecta cyberclaw a tu plataforma de chat favorita.

| Canal        | Qué necesitas                      |
| ------------ | ---------------------------------- |
| **Telegram** | Token de bot desde @BotFather      |
| **Discord**  | Token de bot + Intento de Contenido de Mensaje |
| **WhatsApp** | Escaneo de código QR               |
| **Feishu**   | ID de aplicación + Secreto de aplicación |
| **Mochat**   | Token de Claw (configuración automática disponible)  |
| **DingTalk** | Clave de aplicación + Secreto de aplicación |
| **Slack**    | Token de bot + Token a nivel de aplicación |
| **Email**    | Credenciales IMAP/SMTP             |
| **QQ**       | ID de aplicación + Secreto de aplicación |

<details>
<summary><b>Telegram</b> (Recomendado)</summary>

**1. Crear un bot**
- Abre Telegram, busca `@BotFather`
- Envía `/newbot`, sigue las instrucciones
- Copia el token

**2. Configurar**

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "TU_TOKEN_DE_BOT",
      "allowFrom": ["TU_ID_DE_USUARIO"]
    }
  }
}
```

> Puedes encontrar tu **ID de usuario** en los ajustes de Telegram. Se muestra como `@yourUserId`.
> Copia este valor **sin el símbolo `@`** y pégalo en el archivo de configuración.


**3. Ejecutar**

```bash
cyberclaw gateway
```

</details>

<details>
<summary><b>Mochat (Claw IM)</b></summary>

Usa **Socket.IO WebSocket** por defecto, con fallback a polling HTTP.

**1. Pídele a cyberclaw que configure Mochat por ti**

Simplemente envía este mensaje a cyberclaw (reemplaza `xxx@xxx` con tu correo real):

```
Read https://raw.githubusercontent.com/HKUDS/MoChat/refs/heads/main/skills/cyberclaw/skill.md and register on MoChat. My Email account is xxx@xxx Bind me as your owner and DM me on MoChat.
```

cyberclaw registrará automáticamente, configurará `~/.cyberclaw/config.json` y se conectará a Mochat.

**2. Reiniciar gateway**

```bash
cyberclaw gateway
```

¡Eso es todo! cyberclaw se encarga del resto.

<br>

<details>
<summary>Configuración manual (avanzado)</summary>

Si prefieres configurar manualmente, agrega lo siguiente en `~/.cyberclaw/config.json`:

> Mantén `claw_token` privado. Solo debe enviarse en la cabecera `X-Claw-Token` a tu endpoint de API de Mochat.

```json
{
  "channels": {
    "mochat": {
      "enabled": true,
      "base_url": "https://mochat.io",
      "socket_url": "https://mochat.io",
      "socket_path": "/socket.io",
      "claw_token": "claw_xxx",
      "agent_user_id": "6982abcdef",
      "sessions": ["*"],
      "panels": ["*"],
      "reply_delay_mode": "non-mention",
      "reply_delay_ms": 120000
    }
  }
}
```



</details>

</details>

<details>
<summary><b>Discord</b></summary>

**1. Crear un bot**
- Ve a https://discord.com/developers/applications
- Crea una aplicación → Bot → AñadirAgregar Bot
- Copia el token del bot

**2. Habilitar intents**
- En los ajustes del Bot, habilita **MESSAGE CONTENT INTENT**
- (Opcional) Habilita **SERVER MEMBERS INTENT** si planeas usar listas de permitidos basadas en datos de miembros

**3. Obtener tu ID de usuario**
- Ajustes de Discord → Avanzados → habilita **Developer Mode**
- Haz clic derecho en tu avatar → **Copiar ID de usuario**

**4. Configurar**

```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "token": "TU_TOKEN_DE_BOT",
      "allowFrom": ["TU_ID_DE_USUARIO"],
      "groupPolicy": "mention"
    }
  }
}
```

> `groupPolicy` controla cómo responde el bot en canales grupales:
> - `"mention"` (predeterminado) — Solo responde cuando @mencionado
> - `"open"` — Responde a todos los mensajes
> Los DMs siempre responden cuando el remitente está en `allowFrom`.

**5. Invitar al bot**
- OAuth2 → URL Generator
- Scopes: `bot`
- Bot Permissions: `Send Messages`, `Read Message History`
- Abre la URL de invitación generada y añade el bot a tu servidor

**6. Ejecutar**

```bash
cyberclaw gateway
```

</details>

<details>
<summary><b>Matrix (Element)</b></summary>

Instala las dependencias de Matrix primero:

```bash
pip install cyberclaw-ai[matrix]
```

**1. Crear/escoger una cuenta de Matrix**

- Crea o reutiliza una cuenta de Matrix en tu homeserver (por ejemplo `matrix.org`).
- Confirma que puedes iniciar sesión con Element.

**2. Obtener credenciales**

- Necesitas:
  - `userId` (ejemplo: `@cyberclaw:matrix.org`)
  - `accessToken`
  - `deviceId` (recomendado para que los tokens de sincronización se puedan restaurar entre reinicios)
- Puedes obtenerlos desde la API de inicio de sesión de tu homeserver (`/_matrix/client/v3/login`) o desde los ajustes avanzados de sesión de tu cliente.

**3. Configurar**

```json
{
  "channels": {
    "matrix": {
      "enabled": true,
      "homeserver": "https://matrix.org",
      "userId": "@cyberclaw:matrix.org",
      "accessToken": "syt_xxx",
      "deviceId": "CYBERCLAW01",
      "e2eeEnabled": true,
      "allowFrom": ["@tu_usuario:matrix.org"],
      "groupPolicy": "open",
      "groupAllowFrom": [],
      "allowRoomMentions": false,
      "maxMediaBytes": 20971520
    }
  }
}
```

> Mantén un `matrix-store` persistente y un `deviceId` estable — el estado de la sesión encriptada se pierde si estos cambian entre reinicios.

| Opción              | Descripción                                                                    |
| ------------------- | ------------------------------------------------------------------------------ |
| `allowFrom`         | IDs de usuario autorizados para interactuar. Vacío deniega todos; usa `["*"]` para permitir a todos. |
| `groupPolicy`       | `open` (predeterminado), `mention`, o `allowlist`.                             |
| `groupAllowFrom`    | Lista blanca de salas (usado cuando la política es `allowlist`).               |
| `allowRoomMentions` | Aceptar menciones `@room` en modo mención.                                     |
| `e2eeEnabled`       | Soporte E2EE (predeterminado `true`). Establece `false` solo para texto plano. |
| `maxMediaBytes`     | Tamaño máximo de adjuntos (predeterminado `20MB`). Establece `0` para bloquear toda la multimedia. |




**4. Ejecutar**

```bash
cyberclaw gateway
```

</details>

<details>
<summary><b>WhatsApp</b></summary>

Requiere **Node.js ≥18**.

**1. Vincular dispositivo**

```bash
cyberclaw channels login
# Escaneaear QR con WhatsApp → Ajustes → Dispositivos vincululados
```

**2. Configurar**

```json
{
  "channels": {
    "whatsapp": {
      "enabled": true,
      "allowFrom": ["+1234567890"]
    }
  }
}
```

**3. Ejecutar** (dos terminales)

```bash
# Terminal 1
cyberclaw channels login

# Terminal 2
cyberclaw gateway
```

> Las actualizaciones del puente de WhatsApp no se aplican automáticamente en instalaciones existentes.
> Después de actualizar cyberclaw, reconstruye el puente local con:
> `rm -rf ~/.cyberclaw/bridge && cyberclaw channels login`

</details>

<details>
<summary><b>Feishu (飞书)</b></summary>

Usa **WebSocket** de conexión prolongada — no se requiere IP pública.

**1. Crear un bot de Feishu**
- Visita [Plataforma Abierta de Feishu](https://open.feishu.cn/app)
- Crea una nueva aplicación → Habilita la capacidad de **Bot**
- **Permisos**: Añade `im:message` (enviar mensajes) y `im:message.p2p_msg:readonly` (recibir mensajes)
- **Eventos**: Añade `im.message.receive_v1` (recibir mensajes)
  - Selecciona el modo de **Conexión Prolongada** (requiere ejecutar cyberclaw primero para establecer la conexión)
- Obtén el **App ID** y **App Secret** en "Credenciales y A Básica"
- Publica la aplicación

**2. Configurar**

```json
{
  "channels": {
    "feishu": {
      "enabled": true,
      "appId": "cli_xxx",
      "appSecret": "xxx",
      "encryptKey": "",
      "verificationToken": "",
      "allowFrom": ["ou_TU_OPEN_ID"]
    }
  }
}
```

> `encryptKey` y `verificationToken` son opcionales en el modo de Conexión Prolongada.
> `allowFrom`: Añade tu open_id (encuéntralo en los registros de cyberclaw cuando envíes un mensaje al bot). Usa `["*"]` para permitir a todos los usuarios.

**3. Ejecutar**

```bash
cyberclaw gateway
```

> [!TIP]
> ¡Feishu usa WebSocket para recibir mensajes — no se requiereebhook ni IP pública necesaria!

</details>

<details>
<summary><b>QQ (Chat Privado QQ)</b></summary>

Usa la **SDK botpy** con WebSocket — no se requiere IP pública. Actualmente solo soporta **mensajes privados**.

**1. Registrarse y crear bot**
- Visita [Plataforma Abierta de QQ](https://q.qq.com) → Registrarse como desarrollador (personal o empresarial)
- Crear una nueva aplicación de bot
- Ve a **Ajustes de Desarrollo** → copiar **AppID** y **AppSecret**

**2. Configurar sandbox para pruebas**
- En la consola de gestión de bots, encuentra **Configuración de Sandbox**
- Bajoajo **Configurar en la lista de mensajes**, haz clic en **Añadir miembro** y añade tu propio número de QQ
- Una vez añadido, escanea el código QR del bot con QQ móvil → abre el perfil del bot → toca "Enviar mensaje" para comenzar a chatear

**3. Configurar**

> - `allowFrom`: Añade tu openid (encuéntralo en los registros de cyberclaw cuando envíes un mensaje al bot). Usa `["*"]` para acceso público.
> - Para producción: envía una revisión en la consola de bots y publicaícala. Consulta [Documentación de QQ Bot](https://bot.q.qq.com/wiki) para el flujo completo de publicación.

```json
{
  "channels": {
    "qq": {
      "enabled": true,
      "appId": "TU_APP_ID",
      "secret": "TU_APP_SECRET",
      "allowFrom": ["TU_OPENID"]
    }
  }
}
```

**4. Ejecutar**

```bash
cyberclaw gateway
```

¡Ahora envía un mensaje al bot desde QQ — debería responder!

</details>

<details>
<summary><b>DingTalk (钉钉)</b></summary>

Usa el **Modo Stream** — no se requiere IP pública.

**1. Crear un bot de DingTalk**
- Visita [Plataforma Abierta de DingTalk](https://open-dev.dingtalk.com/)
- Crear una nueva aplicación -> Añadir capacidad de **Robot**
- **Configuración**:
  - Alternar **Modo Stream** a ON
- **Permisos**: AñadirAddir los permisos necesarios para enviar mensajes
- Obtén **AppKey** (Client ID) y **AppSecret** (Client Secret) desde "Credenciales"
- Publica la aplicación

**2. Configurar**

```json
{
  "channels": {
    "dingtalk": {
      "enabled": true,
      "clientId": "TU_APP_KEY",
      "clientSecret": "TU_APP_SECRET",
      "allowFrom": ["TU_STAFF_ID"]
    }
  }
}
```

> `allowFrom`: Añade tu ID de personal. Usa `["*"]` para permitir a todos los usuarios.

**3. Ejecutar**

```bash
cyberclaw gateway
```

</details>

<details>
<summary><b>Slack</b></summary>

Usa el **Modo Socket** — no se requiere URL pública.

**1. Crear una aplicación de Slack**
- Ve a [API de Slack](https://api.slack.com/apps) → **Crear Nueva Aplicación** → "Desde cero"
- Elige un nombre y selecciona tu espacio de trabajo

**2. Configurar la aplicación**
- **Modo Socket**: Alternar ON → Generar un **Token a Nivel de Aplicación** con alcancescope `connections:write` → copiarlo (`xapp-...`)
- **OAuth & Permisos**: Añadir scopes de bot: `chat:write`, `reactions:write`, `app_mentions:read`
- **Suscripciones a Eventos**: Alternar ON → SuscribirseSuscribirse a eventos de bot: `message.im`, `message.channels`, `app_mention` → Guardar Cambios
- **Inicio de la Aplicación**: Desplázate a **Mostrar Pestañas** → Habilitar **Pestaña de Mensajes** → Marcar **"Permitir a los usuarios enviar comandcommandes Slash y mensajes desde la pestaña de mensajes"**
- **Instalar Aplicación**: Haz clic en **Instalar en el Espacio de Trabajo** → Autorizar → copiar el **Token de Bot** (`xoxb-...`)

**3. Configurar cyberclaw**

```json
{
  "channels": {
    "slack": {
      "enabled": true,
      "botToken": "xoxb-...",
      "appToken": "xapp-...",
      "allowFrom": ["TU_ID_DE_USUARIO_DE_SLACK"],
      "groupPolicy": "mention"
    }
  }
}
```

**4. Ejecutar**

```bash
cyberclaw gateway
```

¡Manda un DM al bot directamente o @menciónalo en un canal — debería responder!

> [!TIP]
> - `groupPolicy`: `"mention"` (predeterminado — solo responde cuando @mencionado), `"open"` (responde a todos los mensajes del canal) o `"allowlist"` (restringir a canales específicos).
> - La política de DMs es abierta por defecto. Establece `"dm": {"enabled": false}` para deshabilitar DMs.

</details>

<details>
<summary><b>Email</b></summary>

Dale a cyberclaw su propia cuenta de correo electrónico. Consultapolling **IMAP** para recibir correos y responde víavía **SMTP** — como un asistente de correo personal.

**1. Obtener credenciales (ejemplo Gmail)**
- Crear una cuenta de Gmail dedicada para tu bot (ej. `my-cyberclaw@gmail.com`)
- Habilitar Verificación en 2 Pasos → Crear una [Contraseña de Aplicación](https://myaccount.google.com/apppasswords)
- Usar esta contraseña de aplicación tanto para IMAP como para SMTP

**2. Configurar**

> - `consentGranted` debe ser `true` para permitir el acceso al buzón. Esta es una barrera de seguridad — establece `false` para deshabilitar completamente.
> - `allowFrom`: Añade tu dirección de correo electrónico. Usa `["*"]` para aceptar correos de cualquieraqualquiera.
> - `smtpUseTls` y `smtpUseSsl` son `true` / `false` por defecto, lo cual es correcto para Gmail (puerto 587 + STARTTLS). No es necesario establecerlos explícitamente.
> - Establece `"autoReplyEnabled": false` si solo quieres leer/analizar correos sin enviar respuestas automáticas.

```json
{
  "channels": {
    "email": {
      "enabled": true,
      "consentGranted": true,
      "imapHost": "imap.gmail.com",
      "imapPort": 993,
      "imapUsername": "my-cyberclaw@gmail.com",
      "imapPassword": "tu-contraseña-de-aplicación",
      "smtpHost": "smtp.gmail.com",
      "smtpPort": 587,
      "smtpUsername": "my-cyberclaw@gmail.com",
      "smtpPassword": "tu-contraseña-de-aplicación",
      "fromAddress": "my-cyberclaw@gmail.com",
      "allowFrom": ["tu-correo-real@gmail.com"]
    }
  }
}
```


**3. Ejecutar**

```bash
cyberclaw gateway
```

</details>

## 🌐 Red Social de Agentes

🦞 cyberclaw es capaz de conectarse a la red social de agentes (comunidad de agentes). **¡Solo envía un mensaje y tu cyberclaw se unirá automáticamente!**

| Plataforma                                 | Cómo unirse (envía este mensaje a tu bot)                                        |
| ------------------------------------------ | ---------------------------------------------------------------------------------- |
| [**Moltbook**](https://www.moltbook.com/)  | `Read https://moltbook.com/skill.md and follow the instructions to join Moltbook`  |
| [**ClawdChat**](https://clawdchat.ai/)     | `Read https://clawdchat.ai/skill.md and follow the instructions to join ClawdChat` |

Simplemente envía el comando anterior a tu cyberclaw (vía CLI o cualquier canal de chat), y se encargará del resto.

## ⚙️ Configuración

Archivo de configuración: `~/.cyberclaw/config.json`

### Proveedores

> [!TIP]
> - **Groq** proporciona transcripción de voz gratuita mediante Whisper. Si está configurado, los mensajes de voz de Telegram se transcribirán automáticamente.
> - **Plan de Codificación de Zhipu**: Si estás en el plan de codificación de Zhipu, establece `"apiBase": "https://open.bigmodel.cn/api/coding/paas/v4"` en la configuración de tu proveedor zhipu.
> - **MiniMax (China Continental)**: Si tu clave API es de la plataforma de China Continental de MiniMax (minimaxi.com), establece `"apiBase": "https://api.minimaxi.com/v1"` en la configuración de tu proveedor minimax.
> - **Plan de Codificación de VolcEngine**: Si estás en el plan de codificación de VolcEngine, establece `"apiBase": "https://ark.cn-beijing.volces.com/api/coding/v3"` en la configuración de tu proveedor volcengine.
> - **Plan de Codificación de Alibaba Cloud**: Si estás en el Plan de Codificación de Alibaba Cloud (BaiLian), establece `"apiBase": "https://coding.dashscope.aliyuncs.com/v1"` en la configuración de tu proveedor dashscope.

| Proveedor      | Propósito                                             | Obtener Clave API                                                          |
| ----------------- | --------------------------------------------------- | -------------------------------------------------------------------- |
| `custom`         | Cualquier endpoint compatible con OpenAI (directo, sin LiteLLM) | —                                                                    |
| `openrouter`     | LLM (recomendado, acceso a todos los modelos)             | [openrouter.ai](https://openrouter.ai)                               |
| `anthropic`      | LLM (Claude directo)                                 | [console.anthropic.com](https://console.anthropic.com)               |
| `azure_openai`   | LLM (Azure OpenAI)                                  | [portal.azure.com](https://portal.azure.com)                         |
| `openai`         | LLM (GPT directo)                                    | [platform.openai.com](https://platform.openai.com)                   |
| `deepseek`       | LLM (DeepSeek directo)                               | [platform.deepseek.com](https://platform.deepseek.com)               |
| `groq`           | LLM + **Transcripción de Voz** (Whisper)             | [console.groq.com](https://console.groq.com)                         |
| `gemini`         | LLM (Gemini directo)                                 | [aistudio.google.com](https://aistudio.google.com)                   |
| `minimax`        | LLM (MiniMax directo)                                | [platform.minimaxi.com](https://platform.minimaxi.com)               |
| `aihubmix`       | LLM (Gateway de API, acceso a todos los modelos)             | [aihubmix.com](https://aihubmix.com)                                 |
| `siliconflow`    | LLM (SiliconFlow)                          | [siliconflow.cn](https://siliconflow.cn)                             |
| `volcengine`     | LLM (VolcEngine)                           | [volcengine.com](https://www.volcengine.com)                         |
| `dashscope`      | LLM (Qwen)                                          | [dashscope.console.aliyun.com](https://dashscope.console.aliyun.com) |
| `moonshot`       | LLM (Moonshot/Kimi)                                 | [platform.moonshot.cn](https://platform.moonshot.cn)                 |
| `zhipu`          | LLM (Zhipu GLM)                                     | [open.bigmodel.cn](https://open.bigmodel.cn)                         |
| `vllm`           | LLM (local, cualquier servidor compatible con OpenAI)           | —                                                                    |
| `openai_codex`   | LLM (Codex, OAuth)                                  | `cyberclaw provider login openai-codex`                              |
| `github_copilot` | LLM (GitHub Copilot, OAuth)                         | `cyberclaw provider login github-copilot`                            |

<details>
<summary><b>OpenAI Codex (OAuth)</b></summary>

Codex usa OAuth en lugar de claves API. Requiere una cuenta ChatGPT Plus o Pro.

**1. Iniciar sesión:**
```bash
cyberclaw provider login openai-codex
```

**2. Configurar modelo** (fusionar en `~/.cyberclaw/config.json`):
```json
{
  "agents": {
    "defaults": {
      "model": "openai-codex/gpt-5.1-codex"
    }
  }
}
```

**3. Chatear:**
```bash
cyberclaw agent -m "¡Hola!"

# Dirigirse a un espacio de trabajo/config específico localmente
cyberclaw agent -c ~/.cyberclaw-telegram/config.json -m "¡Hola!"

# Anulación de espacio de trabajo único sobre esa configuración
cyberclaw agent -c ~/.cyberclaw-telegram/config.json -w /tmp/cyberclaw-telegram-test -m "¡Hola!"
```

> Usuarios de Docker: usa `docker run -it` para inicio de sesión OAuth interactivo.

</details>

<details>
<summary><b>Proveedor Personalizado (Cualquier API compatible con OpenAI)</b></summary>

Se conecta directamente a cualquier endpoint compatible con OpenAI — LM Studio, llama.cpp, Together AI, Fireworks, Azure OpenAI, o cualquier servidor autoalojado. Elude a LiteLLM; el nombre del modelo se pasa tal cual.

```json
{
  "providers": {
    "custom": {
      "apiKey": "tu-clave-api",
      "apiBase": "https://api.tu-proveedor.com/v1"
    }
  },
  "agents": {
    "defaults": {
      "model": "nombre-de-tu-modelo"
    }
  }
}
```

> Para servidores locales que no requieren clave, establece `apiKey` en cualquier cadena no vacía (ej. `"no-key"`).

</details>

<details>
<summary><b>vLLM (local / compatible con OpenAI)</b></summary>

Ejecuta tu propio modelo con vLLM o cualquier servidor compatible con OpenAI, luego añadeaade a la configuración:

**1. Iniciar el servidor** (ejemplo):
```bash
vllm serve meta-llama/Llama-3.1-8B-Instruct --port 8000
```

**2. Añadiraade a la configuración** (parcial — fusionar en `~/.cyberclaw/config.json`):

*Proveedor (la clave puede ser cualquier cadena no vacía para local):*
```json
{
  "providers": {
    "vllm": {
      "apiKey": "dummy",
      "apiBase": "http://localhost:8000/v1"
    }
  }
}
```

*Modelo:*
```json
{
  "agents": {
    "defaults": {
      "model": "meta-llama/Llama-3.1-8B-Instruct"
    }
  }
}
```

</details>

<details>
<summary><b>Añadir un Nuevo Proveedor (Guía para Desarrolladores)</b></summary>

cyberclaw utiliza un **Registro de Proveedores** (`cyberclaw/providers/registry.py`) como la única fuente de verdad.
Añadir un nuevo proveedor solo toma **2 pasos** — sin cadenas `if-elif` que modificar.

**Paso 1.** Añade una entrada `ProviderSpec` a `PROVIDERS` en `cyberclaw/providers/registry.py`:

```python
ProviderSpec(
    name="myprovider",                   # nombre del campo de configuración
    keywords=("myprovider", "mymodel"),  # palabras clave del nombre del modelo para aut coincidmpareo
    env_key="MYPROVIDER_API_KEY",        # variable de entorno para LiteLLM
    display_name="My Provider",          # mostrado en `cyberclaw status`
    litellm_prefix="myprovider",         # autoprefijo: model → myprovider/model
    skip_prefixes=("myprovider/",),      # no autoprefijar
)
```

**Paso 2.** Añade un campo a `ProvidersConfig` en `cyberclaw/config/schema.py`:

```python
class ProvidersConfig(BaseModel):
    ...
    myprovider: ProviderConfig = ProviderConfig()
```

¡Eso es todo! Las variables de entorno, el autoprefijo de modelos, el  mpareo de configuración y la visualización de `cyberclaw status` funcionarán automáticamente.

**Opciones comunes de `ProviderSpec`:**

| Campo                    | Descripción                                     | Ejemplo                                  |
| ------------------------ | ----------------------------------------------- | ---------------------------------------- |
| `litellm_prefix`         | Autoprefijo de nombres de modelo para LiteLLM             | `"dashscope"` → `dashscope/qwen-max`     |
| `skip_prefixes`          | No prefijar si el modelo ya comienza con estas | `("dashscope/", "openrouter/")`          |
| `env_extras`             | Variables de entorno adicionales para establecer                      | `(("ZHIPUAI_API_KEY", "{api_key}"),)`    |
| `model_overrides`        | Anulaciones de parámetros por modelo                   | `(("kimi-k2.5", {"temperature": 1.0}),)` |
| `is_gateway`             | Puede enrutar cualquier modelo (como OpenRouter)           | `True`                                   |
| `detect_by_key_prefix`   | Detectar gateway por prefijo de API key                | `"sk-or-"`                               |
| `detect_by_base_keyword` | Detectar gateway por URL base de API                  | `"openrouter"`                           |
| `strip_model_prefix`     | Eliminar prefijo existente antes de autoprefijar       | `True` (para AiHubMix)                    |

</details>


### MCP (Model Context Protocol)

> [!TIP]
> El formato de configuración es compatible con Claude Desktop / Cursor. Puedes copiar configuraciones de servidores MCP directamente desde el README de cualquier servidor MCP.

cyberclaw soporta [MCP](https://modelcontextprotocol.io/) — conectar servidores de herramientas externos y usarlos como herramientas nativas del agente.

Añade servidores MCP a tu `config.json`:

```json
{
  "tools": {
    "mcpServers": {
      "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/ruta/al/dir"]
      },
      "mi-mcp-remoto": {
        "url": "https://ejemplo.com/mcp/",
        "headers": {
          "Authorization": "Bearer xxxxx"
        }
      }
    }
  }
}
```

Se soportan dos modos de transporte:

| Modo      | Configuración                       | Ejemplo                                         |
| --------- | ---------------------------- | ----------------------------------------------- |
| **Stdio** | `command` + `args`           | Proceso local vía `npx` / `uvx`                 |
| **HTTP**  | `url` + `headers` (opcional) | Endpoint remoto (`https://mcp.ejemplo.com/sse`) |

Usa `toolTimeout` para anular el tiempo de espera predeterminado de 30s por llamada para servidores lentos:

```json
{
  "tools": {
    "mcpServers": {
      "mi-servidor-lento": {
        "url": "https://ejemplo.com/mcp/",
        "toolTimeout": 120
      }
    }
  }
}
```

Las herramientas MCP se descubren y registran automáticamente al inicio. El LLM puede usarlas junto con las herramientas integradas — sin configuración adicional.





### Seguridad

> [!TIP]
> Para implementaciones en producción, establece `"restrictToWorkspace": true` en tu configuración para arener el agente.
> En `v0.1.4.post3` y anteriores, un `allowFrom` vacío permitía a todos los remitentes. Desde `v0.1.4.post4`, un `allowFrom` vacío deniega el acceso a todos por defecto. Para permitir a todos los remitentes, establece `"allowFrom": ["*"]`.

| Opción                      | Predeterminado | Descripción                                                                                                                                                 |
| --------------------------- | --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tools.restrictToWorkspace` | `false`         | Cuando `true`, restringe **todas** las herramientas del agente (shell, lectura/escritura/edición de archivos, listar) al directorio del espacio de trabajo. Previene travesías de ruta y acceso fuera del alcance. |
| `tools.exec.pathAppend`     | `""`            | Directorios adicionales para agregar a `PATH` al ejecutar comandos de shell (ej. `/usr/sbin` para `ufw`).                                                             |
| `channels.*.allowFrom`      | `[]` (deniega todos) | Lista blanca de IDs de usuario. Vacío deniega todos; usa `["*"]` para permitir a todos.                                                                                     |


## 🧩 Múltiples Instancias

Ejecuta múltiples instancias de cyberclaw simultáneamente con configuraciones y datos de ejecución separados. Usa `--config` como punto de entrada principal, y opcionalmente usa `--workspace` para anular el espacio de trabajo para una ejecución específica.

### Inicio Rápido

```bash
# Instancia A - Bot de Telegram
cyberclaw gateway --config ~/.cyberclaw-telegram/config.json

# Instancia B - Bot de Discord  
cyberclaw gateway --config ~/.cyberclaw-discord/config.json

# Instancia C - Bot de Feishu con puerto personalizado
cyberclaw gateway --config ~/.cyberclaw-feishu/config.json --port 18792
```

### Resolución de Rutas

Al usar `--config`, cyberclaw deriva su directorio de datos de ejecución desde la ubicación del archivo de configuración. El espacio de trabajo aún proviene de `agents.defaults.workspace` a menos que lo anules con `--workspace`.

Para abrir una sesión CLI contra una de estas instancias localmente:

```bash
cyberclaw agent -c ~/.cyberclaw-telegram/config.json -m "Hola desde la instancia de Telegram"
cyberclaw agent -c ~/.cyberclaw-discord/config.json -m "Hola desde la instancia de Discord"

# Anulación única opcional de espacio de trabajo
cyberclaw agent -c ~/.cyberclaw-telegram/config.json -w /tmp/cyberclaw-telegram-test
```

> `cyberclaw agent` inicia un agente CLI local usando el espacio de trabajo/config seleccionado. No se conecta ni proxy a través de un proceso `cyberclaw gateway` ya en ejecución.

| Componente                 | Resuelto Desde           | Ejemplo                      |
| ------------------------- | ----------------------- | ---------------------------- |
| **Configuración**         | `--config` path         | `~/.cyberclaw-A/config.json` |
| **Espacio de Trabajo**    | `--workspace` o config  | `~/.cyberclaw-A/workspace/`  |
| **Tareas Cron**           | directorio de config    | `~/.cyberclaw-A/cron/`       |
| **Multimedia / estado de ejecución** | directorio de config    | `~/.cyberclaw-A/media/`      |

### Cómo Funciona

- `--config` selecciona qué archivo de configuración cargar
- Por defecto, el espacio de trabajo proviene de `agents.defaults.workspace` en esa configuración
- Si pasas `--workspace`, anula el espacio de trabajo del archivo de configuración

### Configuración Mínima

1. Copia tu configuración base en un nuevo directorio de instancia.
2. Establece un `agents.defaults.workspace` diferente para esa instancia.
3. Inicia la instancia con `--config`.

Ejemplo de configuración:

```json
{
  "agents": {
    "defaults": {
      "workspace": "~/.cyberclaw-telegram/workspace",
      "model": "anthropic/claude-sonnet-4-6"
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "TU_TOKEN_DE_BOT_DE_TELEGRAM"
    }
  },
  "gateway": {
    "port": 18790
  }
}
```

Inicia instancias separadas:

```bash
cyberclaw gateway --config ~/.cyberclaw-telegram/config.json
cyberclaw gateway --config ~/.cyberclaw-discord/config.json
```

Anula el espacio de trabajo para ejecuciones únicas cuando sea necesario:

```bash
cyberclaw gateway --config ~/.cyberclaw-telegram/config.json --workspace /tmp/cyberclaw-telegram-test
```

### Casos de Uso Comunes

- Ejecutar bots separados para Telegram, Discord, Feishu y otras plataformas
- Mantener instancias de prueba y producción aisladas
- Usar diferentes modelos o proveedores para diferentes equipos
- Atender múltiplesqualquiera de inquilinos con configuraciones y datos de ejecución separados

### Notas

- Cada instancia debe usar un puerto diferente si se ejecutan simultáneamente
- Usa un espacio de trabajo diferente por instancia si quieres memoria, sesiones y habilidades aisladas
- `--workspace` anula el espacio de trabajo definido en el archivo de configuración
- Las tareas Cron y la multimedia/estado de ejecución se derivan del directorio de configuración

## 💻 Referencia CLI

| Comando                                      | Descripción                              |
| -------------------------------------------- | ---------------------------------------- |
| `cyberclaw onboard`                          | Inicializar configuración y espacio de trabajo            |
| `cyberclaw agent -m "..."`                   | Chatear con el agente                      |
| `cyberclaw agent -w <workspace>`             | Chatear contra un espacio de trabajo específico        |
| `cyberclaw agent -w <workspace> -c <config>` | Chatear contra un espacio de trabajo/config específico |
| `cyberclaw agent`                            | Modo de chat interactivo                    |
| `cyberclaw agent --no-markdown`              | Mostrar respuestas en texto sin formato                  |
| `cyberclaw agent --logs`                     | Mostrar registros en tiempo real durante el chat            |
| `cyberclaw gateway`                          | Iniciar el gateway                        |
| `cyberclaw status`                           | Mostrar estado                              |
| `cyberclaw provider login openai-codex`      | Inicio de sesión OAuth para proveedores                |
| `cyberclaw channels login`                   | Vincular WhatsApp (escanear QR)                  |
| `cyberclaw channels status`                  | Mostrar estado del canal                      |

El modo interactivo sale con: `exit`, `quit`, `/exit`, `/quit`, `:q`, o `Ctrl+D`.

<details>
<summary><b>Latido (Tareas Periódicas)</b></summary>

El gateway se despierta cada 30 minutos y  `HEARTBEAT.md` en tu espacio de trabajo (`~/.cyberclaw/workspace/HEARTBEAT.md`). Si el archivo tiene tareas, el agente las ejecuta y entrega los resultados a tu canal de chat más recientemente activo.

**Configuración:** edita `~/.cyberclaw/workspace/HEARTBEAT.md` (creado automáticamente por `cyberclaw onboard`):

```markdown
## Tareas Periódicas

- [ ] Comprobar el pronóstico del tiempo y enviar un resumen
- [ ] Buscarscanear la bandeja de entrada por correos urgentes
```

El agente también puede gestionar este archivo por sí mismo — pídele "añadir una tarea periódica" y actualizará `HEARTBEAT.md` por ti.

> **Nota:** El gateway debe estar en ejecución (`cyberclaw gateway`) y debes haber chateado con el bot al menos una vez para que sepa por qué canal entregar.

</details>

## 🐳 Docker

> [!TIP]
> El flag `-v ~/.cyberclaw:/root/.cyberclaw` monta tu directorio de configuración local dentro del contenedor, por lo que tu configuración y espacio de trabajo persisten entre reinicios del contenedor.

### Docker Compose

```bash
docker compose run --rm cyberclaw-cli onboard   # configuración inicial
vim ~/.cyberclaw/config.json                     # añadiraadir claves API
docker compose up -d cyberclaw-gateway           # iniciar gateway
```

```bash
docker compose run --rm cyberclaw-cli agent -m "¡Hola!"   # ejecutar CLI
docker compose logs -f cyberclaw-gateway                   # ver registros
docker compose down                                      # detener
```

### Docker

```bash
# Construir la imagen
docker build -t cyberclaw .

# Inicializar configuración (solo la primera vez)
docker run -v ~/.cyberclaw:/root/.cyberclaw --rm cyberclaw onboard

# Editar configuración en el host para  ́ir claves API
vim ~/.cyberclaw/config.json

# Ejecutar gateway (se conecta a canales habilitados, ej. Telegram/Discord/Mochat)
docker run -v ~/.cyberclaw:/root/.cyberclaw -p 18790:18790 cyberclaw gateway

# O ejecutar un  ́nico comando
docker run -v ~/.cyberclaw:/root/.cyberclaw --rm cyberclaw agent -m "¡Hola!"
docker run -v ~/.cyberclaw:/root/.cyberclaw --rm cyberclaw status
```

## 🐧 Servicio Linux

Ejecuta el gateway como un servicio de usuario de systemd para que se inicie automáticamente y se reinicie en caso de fallo.

**1. Encontrar la ruta del binario de cyberclaw:**

```bash
which cyberclaw   # ej. /home/user/.local/bin/cyberclaw
```

**2. Crear el archivo de servicio** en `~/.config/systemd/user/cyberclaw-gateway.service` (reemplaza la ruta de `ExecStart` si es necesario):

```ini
[Unit]
Description=Cyberclaw Gateway
After=network.target

[Service]
Type=simple
ExecStart=%h/.local/bin/cyberclaw gateway
Restart=always
RestartSec=10
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=%h

[Install]
WantedBy=default.target
```

**3. Habilitar e iniciar:**

```bash
systemctl --user daemon-reload
systemctl --user enable --now cyberclaw-gateway
```

**Operaciones comunes:**

```bash
systemctl --user status cyberclaw-gateway        # comprobar estado
systemctl --user restart cyberclaw-gateway       # reiniciar después de cambios en la configuración
journalctl --user -u cyberclaw-gateway -f        # seguir registros
```

Si editas el archivo `.service` en sí, ejecuta `systemctl --user daemon-reload` antes de reiniciar.

> **Nota:** Los servicios de usuario solo se ejecutan mientras has iniciado sesión. Para mantener el gateway en ejecución después de cerrar sesión, habilita la persistencia:
>
> ```bash
> loginctl enable-linger $USER
> ```

## 📁 Estructura del Proyecto

```
cyberclaw/
├── agent/          # 🧠 Lógica principal del agente
│   ├── loop.py     #    Bucle del agente (LLM ↔ ejecución de herramientas)
│   ├── context.py  #    Constructor de prompts
│   ├── memory.py   #    Memoria persistente
│   ├── skills.py   #    Cargador de habilidades
│   ├── subagent.py #    Ejecución de tareas en segundo plano
│   └── tools/      #    Herramientas integradas (incl. spawn)
├── skills/         # 🎯 Habilidades integradas (github, weather, tmux...)
├── channels/       # 📱 Integraciones de canales de chat
├── bus/            # 🚌 Enrutamiento de mensajes
├── cron/           # ⏰ Tareas programadas
├── heartbeat/      # 💓 Despertar proactivo
├── providers/      # 🤖 Proveedores LLM (OpenRouter, etc.)
├── session/        # 💬 Sesiones de conversación
├── config/         # ⚙️ Configuración
└── cli/            # 🖥️ Comandos
```

## 🤝 Contribuir y Hoja de Ruta

¡Las PRs son bienvenidas! La base de código es intencionalmente pequeña y legible. 🤗

**Hoja de Ruta** — ige un elemento y [abre una PR](https://github.com/HKUDS/cyberclaw/pulls)!

- [ ] **Multimodal** — Ver y oír (imágenes, voz, video)
- [ ] **Memoria a largo plazo** — Nuncaolvidar nunca el contexto importante
- [ ] **Mejor razonamiento** — Planificación y reflexión multietapa
- [ ] **Más integraciones** — Calendario y más
- [x] **Auto-mejora** — Aprender de feedback y errores (✅ Implementado 2026-03-09 ~ 2026-03-10)

### 🧠 Funciones de Auto-mejora (P0/P1/P2)

cyberclaw ahora incluye un sistema integral de auto-mejora que aprende de la experiencia:

#### ✅ P0 - Funciones Core (2026-03-09)
- **Motor de Reflexión** 🪞 — Genera automáticamente informes de reflexión después de completar tareas
  - Analiza patrones de éxito/fallo, uso de herramientas y causas raíz
  - Almacenado en `workspace/.cyberclaw/reflections/`
- **Repositorio de Experiencias** 📚 — Almacena soluciones exitosas y patrones de fallo
  - Recupera experiencias similares para tareas actuales
  - Deduplicación automática y seguimiento de reutilización
  - Almacenado en `workspace/.cyberclaw/experience/`
- **Seguimiento de Patrones de Fallo** 📊 — Identifica errores recurrentes con conteo de frecuencia
- **Herramientas de Auto-mejora** 🛠️ — Consultar perspectivasnsights vía herramientas integradas:
  - `get_reflections` — Ver reflexiones recientes y patrones de fallo
  - `get_experience` — Buscar soluciones y advertencias pasadas
  - `get_improvement_metrics` — Dashboard integral de mejora

#### ✅ P1 - Funciones Mejoradas (2026-03-09)
- **Inyección de Confianza** — Evalúa la confianza de la respuesta antes de responder
  - La baja confianza activa rompts de verificación
  - Umbral configurable (predeterminado: 0.7)
- **Optimización de Selección de Herramientas** — Recomienda herramientas óptimas basadas en el rendimiento histórico
  - Rastrea tasas de éxito, tiempos de ejecución, patrones de fallo
  - Puntuación compuesta: 40% éxito + 30% velocidad + 20% experiencia + 10% antigüedad

#### ✅ P2 - Funciones Avanzadas (2026-03-10)
- **Sugerencias de Evolución de Habilidades** — Analiza el uso de habilidades y genera recomendaciones de mejora
  - Rastrea puntuaciones de salud de habilidades (0-1) basadas en tasa de éxito, frecuencia, antigüedad y diversidad de fallos
  - Identifica lagunas de habilidades (habilidades faltantes o infrarrendadas)
  - Genera informes de evolución con sugerencias ccionables
- **Monitoreo de Salud de Habilidades** — Seguimiento en tiempo real del uso de habilidades durante la ejecución de tareas
  - Análisis automático después de cada reflexión
  - Puntuación de salud: ≥0.7 excelente, 0.5-0.7 moderado, <0.5 necesita mejora

**Ejemplos de Uso**:
```bash
# Ver reflexiones recientes
cyberclaw agent -m "Muéstrame mis reflexiones recientes"

# Obtener métricas de mejora
cyberclaw agent -m "¿Cómo estoy mejorando?"

# Buscar experiencias pasadas
cyberclaw agent -m "¿He creado endpoints de API antes?"

# Generar informe de evolución de habilidades
cyberclaw agent -m "Genera un informe de evolución de habilidades"
```

**Documentación**: Consulta [`docs/SELF_IMPROVING_AGENT.md`](docs/SELF_IMPROVING_AGENT.md) y [`docs/features/skill-evolution-integration.md`](docs/features/skill-evolution-integration.md) para una implementación detallada.

### Colaboradores

<a href="https://github.com/HKUDS/cyberclaw/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=HKUDS/cyberclaw&max=100&columns=12&updated=20260210" alt="Contributors" />
</a>


## ⭐ Historial de Estrellas

<div align="center">
  <a href="https://star-history.com/#HKUDS/cyberclaw&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=HKUDS/cyberclaw&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=HKUDS/cyberclaw&type=Date" />
      <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=HKUDS/cyberclaw&type=Date" style="border-radius: 15px; box-shadow: 0 0 30px rgba(0, 217, 255, 0.3);" />
    </picture>
  </a>
</div>

<p align="center">
  <em> ¡Gracias por visitarnos ✨ cyberclaw!</em><br><br>
  <img src="https://visitor-badge.laobi.icu/badge?page_id=HKUDS.cyberclaw&style=for-the-badge&color=00d4ff" alt="Views">
</p>


## 📜 Agradecimientos

Este proyecto está bifurcado de [nanobot](https://github.com/HKUDS/nanobot) (Licencia MIT, Copyright (c) 2025 colaboradores de nanobot). Agradecemos a los autores y colaboradores originales del proyecto nanobot.

## 📄 Licencia

Este proyecto está licenciado bajo la [Licencia MIT](./LICENSE). Consulta el archivo [NOTICE](./NOTICE) para atribuciones de terceros.

<p align="center">
  <sub>cyberclaw es solo para fines educativos, de investigación e intercambio técnico</sub>
</p>
