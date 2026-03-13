
import os
from pathlib import Path
from typing import NamedTuple, List

from loguru import logger
from cyberclaw.agent.code.repomap import RepoMap

class Location(NamedTuple):
    file: str
    line: int
    text: str

class SymbolIndex:
    """
    Indexer for semantic search (definitions and references).
    Uses RepoMap for definitions and text search for references.
    """

    def __init__(self, workspace: Path, repomap: RepoMap):
        self.workspace = workspace
        self.repomap = repomap
        self._definition_cache: dict[str, list[Location]] = {}
        self._cache_valid = False

    def _build_definition_index(self):
        """
        Build an in-memory index of definitions from RepoMap.
        RepoMap returns a string tree. We need to parse it or reuse its internal cache.
        RepoMap._cache maps path -> (mtime, [symbols]).
        Symbols are formatted like "func my_func" or "class MyClass".
        """
        if self._cache_valid:
            return

        self._definition_cache = {}
        
        # Access RepoMap's internal cache directly if populated
        # Ensure repomap is fresh
        if not self.repomap._cache:
             # Force a walk to populate cache
             self.repomap.get_map()
             
        for fpath, (_, symbols) in self.repomap._cache.items():
            rel_path = fpath.relative_to(self.workspace)
            
            for sym in symbols:
                # sym is "prefix name" e.g. "func run"
                parts = sym.split(" ", 1)
                if len(parts) == 2:
                    kind, name = parts
                    # Store mapping: name -> location
                    if name not in self._definition_cache:
                        self._definition_cache[name] = []
                    
                    # We don't have exact line number in RepoMap cache (it just stores names).
                    # To get line numbers, we'd need to re-parse or store them in RepoMap.
                    # RepoMap._extract_symbols currently returns formatted strings.
                    
                    # Optimization: For now, just store the file.
                    # We can find line number on demand?
                    # Or update RepoMap to store line numbers?
                    
                    # Let's use 0 for now and refine later, or grep the file for the definition.
                    self._definition_cache[name].append(Location(
                        file=str(rel_path),
                        line=0, # Placeholder
                        text=sym
                    ))
        
        self._cache_valid = True

    def find_definitions(self, symbol: str) -> List[Location]:
        """
        Find definition of a symbol.
        """
        self._build_definition_index()
        return self._definition_cache.get(symbol, [])
    
    async def find_references(self, symbol: str) -> List[Location]:
        """
        Find references to a symbol using grep (approximate).
        """
        import asyncio
        
        # Use grep -rnF to search recursively, with line numbers, fixed string
        # Exclude common ignore dirs
        ignore_args = []
        for d in [".git", "node_modules", ".venv", "__pycache__", "dist", "build"]:
             ignore_args.extend(["--exclude-dir", d])
             
        cmd_parts = ["grep", "-rnF"] + ignore_args + [symbol, "."]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd_parts,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.workspace)
        )
        stdout, _ = await proc.communicate()
        
        results = []
        if stdout:
            lines = stdout.decode("utf-8", errors="replace").splitlines()
            for line in lines:
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    fpath = parts[0]
                    if fpath.startswith("./"):
                        fpath = fpath[2:]
                        
                    try:
                        lineno = int(parts[1])
                    except ValueError:
                        lineno = 0
                        
                    text = parts[2].strip()
                    
                    # Limit text length
                    if len(text) > 100:
                        text = text[:97] + "..."
                        
                    results.append(Location(
                        file=fpath,
                        line=lineno,
                        text=text
                    ))
        
        # Limit results to top 50
        return results[:50]
