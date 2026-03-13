import asyncio
import json
import os
from typing import Any, Optional, Dict, List
from pathlib import Path
from loguru import logger

class LSPClient:
    """
    A lightweight JSON-RPC 2.0 client for Language Server Protocol (LSP).
    Communicates with language servers via stdio.
    """

    def __init__(self, name: str, command: List[str], root_uri: str):
        self.name = name
        self.command = command
        self.root_uri = root_uri
        self.process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self.capabilities: Dict[str, Any] = {}
        self._initialized = False

    async def start(self):
        """Start the language server subprocess."""
        if self.process:
            return

        logger.info(f"Starting LSP server '{self.name}': {' '.join(self.command)}")
        try:
            self.process = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, # Capture stderr for logging
                env=os.environ.copy() # Pass current env
            )
            self._reader_task = asyncio.create_task(self._read_stdout())
            self._stderr_task = asyncio.create_task(self._read_stderr())
            
            await self._initialize()
            
        except Exception as e:
            logger.error(f"Failed to start LSP server '{self.name}': {e}")
            raise

    async def stop(self):
        """Stop the language server."""
        if not self.process:
            return
            
        try:
            # Try graceful shutdown
            await self.send_request("shutdown")
            self.send_notification("exit")
        except:
            pass
            
        if self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                self.process.kill()
        
        if self._reader_task:
            self._reader_task.cancel()
        
        self.process = None

    async def _initialize(self):
        """Send initialize request."""
        params = {
            "processId": os.getpid(),
            "rootUri": self.root_uri,
            "capabilities": {
                "textDocument": {
                    "synchronization": {
                        "dynamicRegistration": False,
                        "willSave": False,
                        "willSaveWaitUntil": False,
                        "didSave": True,
                    },
                    "completion": {"dynamicRegistration": False},
                    "hover": {"dynamicRegistration": False},
                    "signatureHelp": {"dynamicRegistration": False},
                    "definition": {"dynamicRegistration": False},
                    "references": {"dynamicRegistration": False},
                    "documentHighlight": {"dynamicRegistration": False},
                    "documentSymbol": {"dynamicRegistration": False},
                    "codeAction": {"dynamicRegistration": False},
                    "formatting": {"dynamicRegistration": False},
                    "rangeFormatting": {"dynamicRegistration": False},
                    "onTypeFormatting": {"dynamicRegistration": False},
                    "rename": {"dynamicRegistration": False},
                },
                "workspace": {
                    "didChangeConfiguration": {"dynamicRegistration": False},
                }
            },
            "initializationOptions": {},
            "trace": "off"
        }
        
        response = await self.send_request("initialize", params)
        self.capabilities = response.get("capabilities", {})
        self.send_notification("initialized", {})
        self._initialized = True
        logger.info(f"LSP server '{self.name}' initialized. Capabilities: {list(self.capabilities.keys())}")

    async def send_request(self, method: str, params: Any = None) -> Any:
        """Send a JSON-RPC request and wait for the response."""
        if not self.process:
            raise RuntimeError("LSP server not running")

        self._request_id += 1
        request_id = self._request_id
        
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        future = asyncio.get_running_loop().create_future()
        self._pending_requests[request_id] = future
        
        await self._send_payload(request)
        
        try:
            return await future
        except Exception as e:
            logger.error(f"LSP request '{method}' failed: {e}")
            raise
        finally:
            self._pending_requests.pop(request_id, None)

    def send_notification(self, method: str, params: Any = None):
        """Send a JSON-RPC notification (no response expected)."""
        if not self.process:
            return

        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        asyncio.create_task(self._send_payload(notification))

    async def _send_payload(self, payload: Dict[str, Any]):
        """Encode and write payload to stdin."""
        if not self.process or not self.process.stdin:
            return

        body = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
        
        try:
            self.process.stdin.write(header + body)
            await self.process.stdin.drain()
        except Exception as e:
            logger.error(f"Failed to send LSP payload: {e}")

    async def _read_stdout(self):
        """Read and decode JSON-RPC messages from stdout."""
        if not self.process or not self.process.stdout:
            return

        buffer = b""
        
        try:
            while True:
                # Read headers
                content_length = 0
                while True:
                    line = await self.process.stdout.readline()
                    if not line:
                        break # EOF
                    
                    line = line.strip()
                    if not line:
                        # End of headers
                        break
                        
                    if line.startswith(b"Content-Length:"):
                        content_length = int(line.split(b":")[1].strip())

                if content_length == 0:
                     if self.process.returncode is not None:
                         break
                     continue

                # Read body
                body = await self.process.stdout.readexactly(content_length)
                
                try:
                    message = json.loads(body.decode("utf-8"))
                    self._handle_message(message)
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode LSP message: {body[:100]}")
                except Exception as e:
                    logger.error(f"Error handling LSP message: {e}")
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"LSP stdout reader crashed: {e}")

    async def _read_stderr(self):
        """Log stderr output from the language server."""
        if not self.process or not self.process.stderr:
            return
            
        try:
            while True:
                line = await self.process.stderr.readline()
                if not line:
                    break
                logger.debug(f"LSP [{self.name}] stderr: {line.decode().strip()}")
        except:
            pass

    def _handle_message(self, message: Dict[str, Any]):
        """Handle an incoming JSON-RPC message."""
        if "id" in message and "method" not in message:
            # Response
            request_id = message.get("id")
            if request_id in self._pending_requests:
                future = self._pending_requests[request_id]
                if "error" in message:
                    future.set_exception(RuntimeError(message["error"]))
                else:
                    future.set_result(message.get("result"))
        elif "method" in message:
            # Notification / Request from server
            method = message["method"]
            params = message.get("params")
            
            if method == "window/logMessage":
                self._handle_log_message(params)
            # Add other notifications as needed

    def _handle_log_message(self, params: Any):
        if not params:
            return
        msg_type = params.get("type", 4)
        message = params.get("message", "")
        
        if msg_type == 1: # Error
            logger.error(f"LSP [{self.name}]: {message}")
        elif msg_type == 2: # Warning
            logger.warning(f"LSP [{self.name}]: {message}")
        else:
            logger.debug(f"LSP [{self.name}]: {message}")

    # --- Convenience Methods ---

    async def did_open(self, file_path: str, text: str, language_id: str):
        """Notify that a document was opened."""
        params = {
            "textDocument": {
                "uri": Path(file_path).as_uri(),
                "languageId": language_id,
                "version": 1,
                "text": text
            }
        }
        self.send_notification("textDocument/didOpen", params)

    async def did_change(self, file_path: str, text: str, version: int):
        """Notify that a document changed."""
        # Full sync for simplicity
        params = {
            "textDocument": {
                "uri": Path(file_path).as_uri(),
                "version": version
            },
            "contentChanges": [{"text": text}]
        }
        self.send_notification("textDocument/didChange", params)

    async def definition(self, file_path: str, line: int, character: int) -> Any:
        """Find definition."""
        params = {
            "textDocument": {"uri": Path(file_path).as_uri()},
            "position": {"line": line, "character": character}
        }
        return await self.send_request("textDocument/definition", params)

    async def references(self, file_path: str, line: int, character: int) -> Any:
        """Find references."""
        params = {
            "textDocument": {"uri": Path(file_path).as_uri()},
            "position": {"line": line, "character": character},
            "context": {"includeDeclaration": True}
        }
        return await self.send_request("textDocument/references", params)

    async def hover(self, file_path: str, line: int, character: int) -> Any:
        """Get hover info."""
        params = {
            "textDocument": {"uri": Path(file_path).as_uri()},
            "position": {"line": line, "character": character}
        }
        return await self.send_request("textDocument/hover", params)


    async def rename(self, file_path: str, line: int, character: int, new_name: str) -> Any:
        """Rename a symbol."""
        params = {
            "textDocument": {"uri": Path(file_path).as_uri()},
            "position": {"line": line, "character": character},
            "newName": new_name
        }
        return await self.send_request("textDocument/rename", params)


def apply_workspace_edit(workspace_path: Path, edit: Dict[str, Any]) -> List[str]:
    """
    Apply a WorkspaceEdit to the file system.
    Returns a list of modified file paths.
    """
    modified_files = []
    
    # helper to apply changes to a single file content
    def apply_text_edits(content: str, changes: List[Dict[str, Any]]) -> str:
        lines = content.splitlines(keepends=True)
        # Sort edits in reverse order to avoid offsetting
        changes.sort(key=lambda c: (c["range"]["start"]["line"], c["range"]["start"]["character"]), reverse=True)
        
        for change in changes:
            start = change["range"]["start"]
            end = change["range"]["end"]
            new_text = change["newText"]
            
            # Simple handling for now - assuming line-based edits mostly
            # Ideally we need robust character-level splicing
            
            # Convert to character offsets? Or utilize splice directly?
            # Let's do a character-level reconstruction for correctness
            
            # 1. Flatten lines to single string? 
            # Or operate on lines? Operating on lines is safer for memory but harder for multi-line edits
            pass # logic below
            
        # Re-implement using full string replacement for safety
        full_text = "".join(lines)
        
        # Sort changes reverse
        changes.sort(key=lambda c: (c["range"]["start"]["line"], c["range"]["start"]["character"]), reverse=True)
        
        for change in changes:
            start_line = change["range"]["start"]["line"]
            start_char = change["range"]["start"]["character"]
            end_line = change["range"]["end"]["line"]
            end_char = change["range"]["end"]["character"]
            new_text = change["newText"]

            # Calculate offsets
            # This is expensive but accurate. 
            # Optimization: could calculate offsets once.
            
            current_line = 0
            current_char = 0
            start_offset = 0
            end_offset = 0
            found_start = False
            found_end = False
            
            offset = 0
            for i, line in enumerate(lines):
                line_len = len(line)
                
                if not found_start:
                    if i == start_line:
                        start_offset = offset + start_char
                        found_start = True
                
                if not found_end:
                    if i == end_line:
                        end_offset = offset + end_char
                        found_end = True
                        break
                
                offset += line_len
            
            if found_start and found_end:
                full_text = full_text[:start_offset] + new_text + full_text[end_offset:]
                # Re-split needed for next iteration if we were doing line-based, but we are doing full text
                # IMPORTANT: Since we sort reverse, the offsets of previous (earlier in file) edits are not affected!
                # But wait, we are modifying `full_text` in place.
                # If we modify the end, the start offsets are unchanged. 
                # So yes, reverse sort works for single-string replacement too.
                pass
        
        return full_text

    changes = edit.get("changes", {})
    document_changes = edit.get("documentChanges", [])
    
    # Normalize to changes dict
    if document_changes:
        for doc_edit in document_changes:
            # textDocumentEdit
            if "textDocument" in doc_edit:
                uri = doc_edit["textDocument"]["uri"]
                edits = doc_edit["edits"]
                if uri not in changes:
                    changes[uri] = []
                changes[uri].extend(edits)
            # createFile, renameFile, deleteFile support could be added here
            
    for uri, file_changes in changes.items():
        if not uri.startswith("file://"):
            continue
            
        path_str = uri.replace("file://", "")
        # unquote?
        from urllib.parse import unquote, urlparse
        path_str = unquote(urlparse(uri).path)
        
        file_path = Path(path_str)
        if not file_path.exists():
            continue
            
        try:
            content = file_path.read_text(encoding="utf-8")
            new_content = apply_text_edits(content, file_changes)
            file_path.write_text(new_content, encoding="utf-8")
            modified_files.append(str(file_path))
            logger.info(f"Applied LSP edits to {file_path}")
        except Exception as e:
            logger.error(f"Failed to apply edits to {file_path}: {e}")

    return modified_files

class LSPManager:
    """
    Manages multiple LSP clients for different languages.
    """
    
    # Default server commands
    SERVER_COMMANDS = {
        "python": ["pyright-langserver", "--stdio"],
        "go": ["gopls"],
        "typescript": ["typescript-language-server", "--stdio"],
        "javascript": ["typescript-language-server", "--stdio"],
        "rust": ["rust-analyzer"],
    }
    
    # Extension mapping
    EXTENSIONS = {
        ".py": "python",
        ".go": "go",
        ".ts": "typescript",
        ".js": "javascript",
        ".rs": "rust",
    }

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.clients: Dict[str, LSPClient] = {}
        self.root_uri = workspace.as_uri()

    async def get_client(self, file_path: str) -> Optional[LSPClient]:
        """Get or start a client for the given file."""
        ext = Path(file_path).suffix
        lang = self.EXTENSIONS.get(ext)
        
        if not lang:
            return None
            
        if lang in self.clients:
            return self.clients[lang]
        
        # Check if server binary exists
        cmd = self.SERVER_COMMANDS.get(lang)
        if not cmd:
            return None
            
        import shutil
        if not shutil.which(cmd[0]):
            logger.warning(f"LSP server for {lang} ({cmd[0]}) not found in PATH.")
            return None
            
        # Start new client
        try:
            client = LSPClient(lang, cmd, self.root_uri)
            await client.start()
            self.clients[lang] = client
            return client
        except Exception as e:
            logger.error(f"Failed to start {lang} LSP: {e}")
            return None

    async def shutdown(self):
        """Stop all clients."""
        for client in self.clients.values():
            await client.stop()
        self.clients.clear()

