"""
Repository Map Generator using Tree-sitter.

Generates a concise map of the repository structure, including key symbols
(classes, functions) to help the agent understand the codebase without reading every file.
"""

import os
from pathlib import Path
from typing import Any

from loguru import logger
import warnings

# Suppress tree-sitter deprecation warning from tree_sitter_languages
warnings.filterwarnings("ignore", category=FutureWarning, module="tree_sitter")

try:
    from tree_sitter import Parser
    from tree_sitter_languages import get_language, get_parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    logger.warning("Tree-sitter not installed. RepoMap will be disabled.")


# Language mappings
EXTENSION_TO_LANG = {
    ".py": "python",
    ".go": "go",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "cpp",
}

# Queries to extract symbols
# We use simple queries to find definitions
QUERIES = {
    "python": """
    (function_definition
      name: (identifier) @name)
    (class_definition
      name: (identifier) @name)
    """,
    "go": """
    (function_declaration
      name: (identifier) @name)
    (method_declaration
      name: (field_identifier) @name)
    (type_declaration
      (type_spec
        name: (type_identifier_list (type_identifier) @name)))
    """,
    "javascript": """
    (function_declaration
      name: (identifier) @name)
    (class_declaration
      name: (identifier) @name)
    (method_definition
      name: (property_identifier) @name)
    """,
    "typescript": """
    (function_declaration
      name: (identifier) @name)
    (class_declaration
      name: (type_identifier) @name)
    (method_definition
      name: (property_identifier) @name)
    (interface_declaration
      name: (type_identifier) @name)
    """,
    "rust": """
    (function_item
      name: (identifier) @name)
    (struct_item
      name: (type_identifier) @name)
    (trait_item
      name: (type_identifier) @name)
    (impl_item
        type: (type_identifier) @name)
    """,
    "java": """
    (class_declaration
      name: (identifier) @name)
    (interface_declaration
      name: (identifier) @name)
    (method_declaration
      name: (identifier) @name)
    """,
}

# Directories to ignore
IGNORE_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".tox", "dist", "build", ".eggs",
    ".idea", ".vscode", ".DS_Store", "vendor",
}


class RepoMap:
    """Generates a map of the repository."""

    def __init__(self, root: Path):
        self.root = root
        self._languages = {}
        self._parsers = {}
        # Cache: path -> (mtime, [symbols])
        self._cache: dict[Path, tuple[float, list[str]]] = {}

    def get_map(self) -> str:
        """Generate the repository map string."""
        if not TREE_SITTER_AVAILABLE:
            return "RepoMap unavailable (tree-sitter not installed)"

        lines = []
        # Walk file tree
        for dirpath, dirnames, filenames in os.walk(self.root):
            # Skip ignored dirs
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
            
            rel_dir = Path(dirpath).relative_to(self.root)
            if str(rel_dir) == ".":
                depth = 0
            else:
                depth = len(rel_dir.parts)
                lines.append(f"{'  ' * (depth - 1)}{rel_dir.name}/")
            
            # Limit depth
            if depth > 5:
                continue

            for fname in sorted(filenames):
                # Skip hidden files
                if fname.startswith("."):
                    continue
                
                fpath = Path(dirpath) / fname
                ext = fpath.suffix
                
                if ext in EXTENSION_TO_LANG:
                    lang = EXTENSION_TO_LANG[ext]
                    
                    # Check cache
                    try:
                        mtime = fpath.stat().st_mtime
                        if fpath in self._cache and self._cache[fpath][0] == mtime:
                            symbols = self._cache[fpath][1]
                        else:
                            symbols = self._extract_symbols(fpath, lang)
                            self._cache[fpath] = (mtime, symbols)
                    except Exception:
                         # File might disappear or permission error
                         continue
                        
                    indent = '  ' * depth
                    if symbols:
                        lines.append(f"{indent}{fname}:")
                        for sym in symbols:
                            lines.append(f"{indent}  {sym}")
                    else:
                        lines.append(f"{indent}{fname}")
        
        return "\n".join(lines)

    def _extract_symbols(self, fpath: Path, lang: str) -> list[str]:
        """Parse file and extract symbols."""
        try:
            content = fpath.read_bytes()
            
            # Setup parser if needed
            if lang not in self._parsers:
                try:
                    language = get_language(lang)
                    self._languages[lang] = language
                    
                    parser = Parser()
                    # tree-sitter <0.22 uses set_language
                    parser.set_language(language)
                    self._parsers[lang] = parser
                except Exception as e:
                    logger.warning(f"Failed to load language {lang}: {e}")
                    return []
            
            parser = self._parsers[lang]
            tree = parser.parse(content)
            
            # Run query
            if lang not in QUERIES:
                return []
            
            query = self._languages[lang].query(QUERIES[lang])
            captures = query.captures(tree.root_node)
            
            symbols = []
            for node, name in captures:
                if name == "name":
                    text = node.text.decode("utf-8", errors="replace")
                    # Limit symbol length
                    if len(text) > 50:
                        text = text[:47] + "..."
                    
                    # Distinguish type based on parent (crudely)
                    kind = node.parent.type
                    prefix = ""
                    if "function" in kind or "method" in kind:
                        prefix = "func "
                    elif "class" in kind or "struct" in kind:
                        prefix = "class "
                    elif "job" in kind or "interface" in kind:
                        prefix = "interface "
                        
                    symbols.append(f"{prefix}{text}")
            
            # Limit symbols per file
            if len(symbols) > 20:
                return symbols[:20] + ["..."]
            return symbols

        except Exception as e:
            logger.warning(f"Error extracting symbols from {fpath}: {e}")
            return []
