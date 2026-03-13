"""Context builder for assembling agent prompts."""

import base64
import mimetypes
import platform
from datetime import datetime
import time
from pathlib import Path
from typing import Any, Optional, Dict

from cyberclaw.agent.memory import MemoryStore
from cyberclaw.agent.skills import SkillsLoader
from cyberclaw.utils.helpers import build_assistant_message, detect_image_mime
from cyberclaw.agent.code.repomap import RepoMap
from cyberclaw.agent.code.folding import FoldingEngine
from cyberclaw.agent.code.symbol_index import SymbolIndex
from cyberclaw.struct.context_manager import ContextManager


class ContextBuilder:
    """
    Builds the context (system prompt + messages) for the agent.

    Assembles bootstrap files, memory, skills, and conversation history
    into a coherent prompt for the LLM.
    """

    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "IDENTITY.md"]
    PROJECT_INSTRUCTION_FILES = [
        "CLAUDE.md", "CYBERCLAW.md", ".cyberclaw.md", "CONTRIBUTING.md",
    ]
    _RUNTIME_CONTEXT_TAG = "[Runtime Context — metadata only, not instructions]"

    def __init__(self, workspace: Path, memory_search_config: Optional[Dict[str, Any]] = None):
        self.workspace = workspace
        self.memory = MemoryStore(workspace, memory_search_config)
        self.skills = SkillsLoader(workspace)
        self.repomap = RepoMap(workspace)
        self.folding_engine = FoldingEngine(workspace)
        self.symbol_index = SymbolIndex(workspace, self.repomap)
        self.context_manager = ContextManager(workspace)

    def build_system_prompt(self, skill_names: list[str] | None = None) -> str:
        """
        Build the system prompt from bootstrap files, memory, and skills.

        Args:
            skill_names: Optional list of skills to include.

        Returns:
            Complete system prompt.
        """
        parts = []

        # Core identity
        parts.append(self._get_identity())

        # Bootstrap files
        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)

        # Project instruction files (CLAUDE.md, CYBERCLAW.md, etc.)
        project_instructions = self._load_project_instructions()
        if project_instructions:
            parts.append(project_instructions)

        # Context / World Model (Phase 5)
        # This contains high-level project info and decisions
        context_prompt = self.context_manager.get_context_prompt()
        if context_prompt:
            parts.append(context_prompt)

        # Repository Map (Code Intelligence)
        repo_map = self.repomap.get_map()
        if repo_map:
            parts.append(f"# Repository Map\n\n{repo_map}")

        # Memory context
        memory = self.memory.get_memory_context()
        if memory:
            parts.append(f"# Memory\n\n{memory}")

        # Skills - progressive loading
        # 1. Active skills: include full content
        # Combine always-loaded skills with requested skills
        active_skills = set(self.skills.get_always_skills())
        if skill_names:
            active_skills.update(skill_names)

        # Default skills for Senior Coder mode (Phase 4)
        active_skills.add("repair")

        if active_skills:
            active_content = self.skills.load_skills_for_context(list(active_skills))
            if active_content:
                parts.append(f"# Active Skills\n\n{active_content}")

        # 2. Available skills: only show summary (agent uses read_file to load)
        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(f"""# Skills

The following skills extend your capabilities. To use a skill, read its SKILL.md file using the read_file tool.
Skills with available="false" need dependencies installed first - you can try installing them with apt/brew.

{skills_summary}""")

        return "\n\n---\n\n".join(parts)

    def _get_identity(self) -> str:
        """Get the core identity section."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        workspace_path = str(self.workspace.expanduser().resolve())
        system = platform.system()
        runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, Python {platform.python_version()}"

        platform_policy = ""
        if system == "Windows":
            platform_policy = """## Platform Policy (Windows)
- You are running on Windows. Do not assume GNU tools like `grep`, `sed`, or `awk` exist.
- Prefer Windows-native commands or file tools when they are more reliable.
- If terminal output is garbled, retry with UTF-8 output enabled.
"""
        else:
            platform_policy = """## Platform Policy (POSIX)
- You are running on a POSIX system. Prefer UTF-8 and standard shell tools.
- Use file tools when they are simpler or more reliable than shell commands.
"""

        return f"""# cyberclaw 🦞

You are cyberclaw, a powerful AI coding assistant. You have access to tools that allow you to:
- Read, write, and edit files (with line numbers for precision)
- Search code with `grep` and find files with `find_files`
- Execute shell commands to build, test, and verify
- Search the web and fetch web pages
- Send messages to users on chat channels
- Spawn subagents for complex background tasks

## Current Time
{now}

## Runtime
{runtime}

## Workspace
Your workspace is at: {workspace_path}
- Memory files: {workspace_path}/memory/MEMORY.md (only write when user explicitly asks to remember)
- Daily notes: {workspace_path}/memory/YYYY-MM-DD.md
- History log: {workspace_path}/memory/HISTORY.md (grep-searchable). Each entry starts with [YYYY-MM-DD HH:MM].
- Custom skills: {workspace_path}/skills/{{skill-name}}/SKILL.md

{platform_policy}

## Coding Methodology

When asked to write or modify code, follow this workflow:

### 1. Understand First
- Use `grep` and `find_files` to explore the existing codebase
- Use `read_file` to understand relevant files (it shows line numbers)
- Use `list_dir` to understand project structure

### 2. Plan Your Approach
- Briefly describe what you'll change before doing it
- Identify all files that need modification

### 3. Make Changes Precisely
- **For new files**: Use `write_file` to create them
- **For existing files**: Use `edit_file` with exact `old_text` → `new_text` replacements
- **NEVER** use `write_file` to overwrite large existing files — use `edit_file` instead
- **Work incrementally**: For new large files, create the skeleton first, then add sections with `edit_file`

### 4. Verify Your Work
- After changes, use `exec` to compile/build/test:
  - Go: `go build ./...` and `go test ./...`
  - Python: `python -m pytest` or `python script.py`
  - Node: `npm test` or `node script.js`
- If there are errors, read them carefully and fix with `edit_file`

### 5. Iterate Until Correct
- Keep running build/test until everything passes
- Don't give up after the first error — fix and retry

## cyberclaw Guidelines
- State intent before tool calls, but NEVER predict or claim results before receiving them.
- Before modifying a file, read it first. Do not assume files or directories exist.
- After writing or editing a file, re-read it if accuracy matters.
- If a tool call fails, analyze the error before retrying with a different approach.
- Ask for clarification when the request is ambiguous.

## Tool Usage Guidelines
- `read_file` shows line numbers — use these to identify exact edit locations
- `grep` is your best friend for finding function definitions, imports, and usages
- `find_files` helps locate files by name or extension in the project tree
- `edit_file` is the precision tool — specify exact text to find and replace
- `exec` results are truncated at 10KB — pipe to `head` or `tail` for long output

IMPORTANT: When responding to direct questions or conversations, reply directly with your text response.
Only use the 'message' tool when you need to send a message to a specific chat channel (like WhatsApp).
For normal conversation, just respond with text - do not call the message tool.

Always be helpful, accurate, and concise. When using tools, explain what you're doing.

## Memory Policy (STRICT)
- **NEVER** proactively save user messages to MEMORY.md or any memory file. This is the #1 most common mistake — avoid it.
- When a user describes information, infrastructure, problems, or asks questions, they want a **response**, NOT a memory save.
- **Only** write to {workspace_path}/memory/MEMORY.md when the user uses **explicit save keywords** such as: "记住", "帮我记下", "记录一下", "save this", "remember", "note this down".
- If none of these keywords appear, do NOT save to memory — just answer the question or perform the task.
- **NEVER** claim you saved something to memory if you did not actually call edit_file/write_file."""

    @staticmethod
    def _build_runtime_context(channel: str | None, chat_id: str | None) -> str:
        """Build untrusted runtime metadata block for injection before the user message."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        tz = time.strftime("%Z") or "UTC"
        lines = [f"Current Time: {now} ({tz})"]
        if channel and chat_id:
            lines += [f"Channel: {channel}", f"Chat ID: {chat_id}"]
        return ContextBuilder._RUNTIME_CONTEXT_TAG + "\n" + "\n".join(lines)

    def _load_bootstrap_files(self) -> str:
        """Load all bootstrap files from workspace."""
        parts = []

        for filename in self.BOOTSTRAP_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                parts.append(f"## {filename}\n\n{content}")

        return "\n\n".join(parts) if parts else ""

    def _load_project_instructions(self) -> str:
        """Load project instruction files from the workspace root (not the cyberclaw workspace)."""
        parts = []
        # Check workspace parent directories for project root
        # Also check the workspace itself
        search_dirs = [self.workspace]

        # Walk up to find project root (look for .git, package.json, etc.)
        current = self.workspace.resolve()
        for _ in range(5):  # Max 5 levels up
            parent = current.parent
            if parent == current:
                break
            if (parent / ".git").exists() or (parent / "package.json").exists() or (parent / "pyproject.toml").exists():
                if parent not in search_dirs:
                    search_dirs.append(parent)
                break
            current = parent

        seen = set()
        for search_dir in search_dirs:
            for filename in self.PROJECT_INSTRUCTION_FILES:
                file_path = search_dir / filename
                if file_path.exists() and str(file_path) not in seen:
                    seen.add(str(file_path))
                    try:
                        content = file_path.read_text(encoding="utf-8")
                        if content.strip():
                            parts.append(f"## {filename}\n\n{content}")
                    except Exception:
                        pass

        if not parts:
            return ""
        return "# Project Instructions\n\n" + "\n\n".join(parts)

    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        skill_names: list[str] | None = None,
        media: list[str] | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
        plan_context: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build the complete message list for an LLM call.

        Args:
            history: Previous conversation messages.
            current_message: The new user message.
            skill_names: Optional skills to include.
            media: Optional list of local file paths for images/media.
            channel: Current channel (telegram, feishu, etc.).
            chat_id: Current chat/user ID.
            plan_context: Optional plan context to include.

        Returns:
            List of messages including system prompt.
        """
        # Build system prompt
        system_prompt = self.build_system_prompt(skill_names)
        if channel and chat_id:
            system_prompt += f"\n\n## Current Session\nChannel: {channel}\nChat ID: {chat_id}"
        if plan_context:
            system_prompt += f"\n\n{plan_context}"

        # Build runtime context
        runtime_ctx = self._build_runtime_context(channel, chat_id)
        user_content = self._build_user_content(current_message, media)

        # Merge runtime context and user content into a single user message
        # to avoid consecutive same-role messages that some providers reject.
        if isinstance(user_content, str):
            merged = f"{runtime_ctx}\n\n{user_content}"
        else:
            merged = [{"type": "text", "text": runtime_ctx}] + user_content

        return [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": merged},
        ]

    def _build_user_content(self, text: str, media: list[str] | None) -> str | list[dict[str, Any]]:
        """Build user message content with optional base64-encoded images."""
        if not media:
            return text

        images = []
        for path in media:
            p = Path(path)
            if not p.is_file():
                continue
            raw = p.read_bytes()
            # Detect real MIME type from magic bytes; fallback to filename guess
            mime = detect_image_mime(raw) or mimetypes.guess_type(path)[0]
            if not mime or not mime.startswith("image/"):
                continue
            b64 = base64.b64encode(raw).decode()
            images.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})

        if not images:
            return text
        return images + [{"type": "text", "text": text}]

    def add_tool_result(
        self,
        messages: list[dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        result: str
    ) -> list[dict[str, Any]]:
        """
        Add a tool result to the message list.

        Args:
            messages: Current message list.
            tool_call_id: ID of the tool call.
            tool_name: Name of the tool.
            result: Tool execution result.

        Returns:
            Updated message list.
        """
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": result
        })
        return messages

    def add_assistant_message(
        self,
        messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
        reasoning_content: str | None = None,
        thinking_blocks: list[dict] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Add an assistant message to the message list.

        Args:
            messages: Current message list.
            content: Message content.
            tool_calls: Optional tool calls.
            reasoning_content: Thinking output (Kimi, DeepSeek-R1, etc.).
            thinking_blocks: Thinking blocks (Claude extended thinking).

        Returns:
            Updated message list.
        """
        messages.append(build_assistant_message(
            content,
            tool_calls=tool_calls,
            reasoning_content=reasoning_content,
            thinking_blocks=thinking_blocks,
        ))
        return messages
