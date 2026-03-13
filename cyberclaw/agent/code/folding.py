
import os
from pathlib import Path
from typing import NamedTuple

from loguru import logger

try:
    from tree_sitter import Parser, Node
    from tree_sitter_languages import get_language, get_parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    logger.warning("Tree-sitter not installed. Folding will be disabled.")

# Reuse language mappings from repomap partially, but we need expanded queries logic
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
}

class SymbolRange(NamedTuple):
    name: str
    type: str # 'function', 'class', etc.
    start_line: int # 1-indexed
    end_line: int   # 1-indexed

class FoldingEngine:
    """
    Analyzes code structure to support 'Smart Context'.
    Can extract symbol ranges and 'fold' non-focus code.
    """

    def __init__(self, root: Path):
        self.root = root
        self._parsers = {}
        self._languages = {}
    
    def is_available(self) -> bool:
        return TREE_SITTER_AVAILABLE

    def _get_parser(self, lang: str):
        if lang not in self._parsers:
            try:
                language = get_language(lang)
                self._languages[lang] = language
                parser = Parser()
                parser.set_language(language)
                self._parsers[lang] = parser
            except Exception as e:
                logger.warning(f"Failed to load language {lang}: {e}")
                return None
        return self._parsers.get(lang)

    def get_structure(self, fpath: Path) -> list[SymbolRange]:
        """
        Parse file and return a flat list of key symbols with their line ranges.
        """
        if not self.is_available():
            return []
            
        ext = fpath.suffix
        if ext not in EXTENSION_TO_LANG:
            return []
        
        lang = EXTENSION_TO_LANG[ext]
        parser = self._get_parser(lang)
        if not parser:
            return []
            
        try:
            content = fpath.read_bytes()
            tree = parser.parse(content)
            
            # recursive walk or query?
            # Walking is generic. Querying is precise but language-specific.
            # For "Structure", we generally want classes and functions.
            
            symbols = []
            cursor = tree.walk()
            
            def visit(node: Node):
                # Heuristic for determining "interesting" nodes
                kind = node.type
                is_interesting = False
                name = ""
                
                if kind in ("class_definition", "class_declaration"):
                    is_interesting = True
                    name = self._get_node_name(node, content) or "class"
                    
                elif kind in ("function_definition", "function_declaration", "method_definition", "method_declaration"):
                    is_interesting = True
                    name = self._get_node_name(node, content) or "func"
                    
                if is_interesting:
                    # Tree-sitter is 0-indexed, we return 1-indexed for tools
                    symbols.append(SymbolRange(
                        name=name,
                        type=kind,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1
                    ))
                
                # Check children
                for child in node.children:
                    visit(child)
            
            visit(tree.root_node)
            return symbols

        except Exception as e:
            logger.error(f"Error parsing structure for {fpath}: {e}")
            return []

    def _get_node_name(self, node: Node, content: bytes) -> str | None:
        """Extract name from a node (naive approach)."""
        # Look for a child field "name"
        child = node.child_by_field_name("name")
        if child:
            return child.text.decode("utf-8", errors="replace")
        return None

    def fold(self, fpath: Path, focus_lines: list[int] | None = None) -> str:
        """
        Read file and fold content.
        
        Strategy:
        1. Read full content.
        2. Identify 'blocks' (functions/classes).
        3. If a block overlaps with 'focus_lines', keep it fully.
        4. If a block does NOT overlap, keep only its signature (first few lines) and replace body with '...'.
        5. Keep top-level code (imports) mostly intact? 
           Actually, simpler: 
           - Identify top-level definitions.
           - If definition not in focus, collapse.
        """
        if not self.is_available():
            return fpath.read_text(errors="replace")
            
        # Simplistic folding:
        # 1. Get all symbols.
        # 2. Map lines to 'keep' or 'collapse'.
        # This is hard to do generically perfectly.
        # Let's delegate to a "skeleton" mode if focus_lines is empty?
        # User wants "Focus Mode".
        
        # For Phase 4 MVP, let's implement:
        # "Read file but collapse function bodies that are not in focus_lines"
        
        # If focus_lines is None, return full file? Or skeleton?
        # Expectation: read_file_focused(path, focus_lines=[10]) -> shows function at line 10, collapses others.
        
        content = fpath.read_text(errors="replace")
        lines = content.splitlines()
        total_lines = len(lines)
        
        if not focus_lines:
            # If no focus lines provided, maybe just return skeleton?
            # Or return full file (fallback).
            return content

        # Set of lines to forcefully keep (the focus)
        # expand focus to include the whole function if a line is touched?
        # For now, let's assume 'focus_lines' are the raw lines user requested.
        # We want to keep the containing block of any focus line.
        
        structure = self.get_structure(fpath)
        
        # Determine ranges to KEEP FULLY
        # 1. Any block that overlaps with focus_lines
        keep_ranges = set()
        
        # 2. Also keep the "signatures" of ALL blocks, so context is visible.
        signature_lines = set()

        # Helper: check overlap
        # focus_lines might be [10, 11, 12]
        # We convert to set for O(1)
        focus_set = set(focus_lines)
        
        for sym in structure:
            # Identify "signature" (approx first line)
            signature_lines.add(sym.start_line)
            
        # For each focused line, find the smallest containing symbol
        # This prevents expanding the whole class if we only focus a method
        for line in focus_lines:
             candidates = []
             for sym in structure:
                 if sym.start_line <= line <= sym.end_line:
                     candidates.append(sym)
             
             if candidates:
                 # Pick smallest by line count
                 best = min(candidates, key=lambda s: s.end_line - s.start_line)
                 for i in range(best.start_line, best.end_line + 1):
                     keep_ranges.add(i)
        
        # Also keep lines that are NOT part of any symbol? (Imports, constants)
        # This requires knowing which lines are "inside" a symbol.
        # Any line NOT in a symbol range -> Keep it (it's likely glue code/imports).
        
        # Map of line -> belongs_to_symbol_index
        line_to_symbol = {}
        for idx, sym in enumerate(structure):
            for i in range(sym.start_line, sym.end_line + 1):
                # If nested, inner wins? Or outer?
                # Usually we want top-level.
                # structure logic above does recursive visit.
                # Let's track "coverage".
                line_to_symbol[i] = idx
        
        final_lines = []
        last_line_idx = 0
        
        for i in range(1, total_lines + 1):
            should_keep = False
            
            # Rule 1: Always keep if input focused
            if i in focus_set:
                should_keep = True
            
            # Rule 2: Keep if in a focused block
            elif i in keep_ranges:
                should_keep = True
                
            # Rule 3: Keep if it's a signature
            elif i in signature_lines:
                should_keep = True
            
            # Rule 4: Keep if it's top-level (not in any symbol)
            elif i not in line_to_symbol:
                should_keep = True
            
            if should_keep:
                if i > last_line_idx + 1:
                    # We skipped lines
                    skipped_count = i - (last_line_idx + 1)
                    final_lines.append(f"... ({skipped_count} lines hidden) ...")
                final_lines.append(lines[i-1])
                last_line_idx = i
            else:
                # Line is hidden (inside a non-focused block, and not a signature)
                pass
                
        if last_line_idx < total_lines:
             skipped_count = total_lines - last_line_idx
             if skipped_count > 0:
                 final_lines.append(f"... ({skipped_count} lines hidden) ...")
             
        return "\n".join(final_lines)

    def resolve_symbols_to_lines(self, fpath: Path, symbols: list[str]) -> list[int]:
        """
        Convert symbol names to line numbers.
        Returns a list of all lines belonging to the matching symbols.
        """
        structure = self.get_structure(fpath)
        lines = set()
        
        # Simple name matching
        # If user asks for "AgentLoop", we match class AgentLoop
        # If user asks for "run", we match func run
        target_names = set(symbols)
        
        for sym in structure:
            if sym.name in target_names:
                for i in range(sym.start_line, sym.end_line + 1):
                    lines.add(i)
        
        return sorted(list(lines))
