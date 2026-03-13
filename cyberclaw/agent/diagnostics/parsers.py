
import re
from typing import NamedTuple, List, Protocol

class Diagnostic(NamedTuple):
    file: str
    line: int
    message: str
    severity: str = "error" # error, warning

class OutputParser(Protocol):
    def parse(self, stdout: str, stderr: str) -> List[Diagnostic]:
        ...

class PytestParser:
    """Parses pytest output for failures."""
    
    # Regex to capture: file:line: error_message
    # Standard pytest failure line:
    # tests/test_foo.py:10: AssertionError: assert False
    # Or sometimes:
    # E   AssertionError: assert False
    # with file/line above it.
    
    # Reliable way: look for "FAILED tests/test_foo.py::test_bar - AssertionError: ..."
    # Or look for file:line pattern in the failure summary section?
    # Pytest output is complex.
    
    # Simple approach for now:
    # Look for lines starting with "tests/..." and containing "FAILED" or similar?
    # Or rely on `--tb=short` format which is usually path:line:in func: error.
    
    def parse(self, stdout: str, stderr: str) -> List[Diagnostic]:
        diagnostics = []
        
        # Merge stdout/stderr? Pytest usually puts output in stdout.
        lines = stdout.splitlines()
        
        # Parse standard file:line: message format
        # tests/test_example.py:5: AssertionError
        # Also handles --tb=line format: path:line: Ex: msg
        pattern = re.compile(r"^([^:\s]+):(\d+): (.+)$")
        
        current_error_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Capture "E   ..." lines (standard pytest traceback)
            if line.startswith("E   "):
                current_error_lines.append(line[4:]) # Strip "E   "
                continue
            
            match = pattern.match(line)
            if match:
                fpath, lineno, tail = match.groups()
                
                # Filter out suspicious paths
                if fpath.endswith(".py"):
                    # Use accumulated E lines as message if available, else tail
                    if current_error_lines:
                        # Sometimes E lines are verbose, just take the first one or join?
                        # Usually the first E line is the main error.
                        msg = current_error_lines[0]
                        # If multiple error lines, maybe join them?
                        if len(current_error_lines) > 1:
                             msg += " " + current_error_lines[1]
                    else:
                        msg = tail
                        
                    diagnostics.append(Diagnostic(
                        file=fpath,
                        line=int(lineno),
                        message=msg
                    ))
                    current_error_lines = [] # Reset after consuming
            
            # Reset error lines if we hit a new test block or something?
            # "def test_..."
            if line.startswith("def test_") or line.startswith("class Test"):
                 current_error_lines = []
        
        return diagnostics

class GoTestParser:
    """Parses go test output."""
    # check_test.go:20: some error
    
    def parse(self, stdout: str, stderr: str) -> List[Diagnostic]:
        diagnostics = []
        lines = stdout.splitlines()
        
        pattern = re.compile(r"\s*([^:\s]+\.go):(\d+): (.+)$")
        
        for line in lines:
            match = pattern.search(line)
            if match:
                fpath, lineno, msg = match.groups()
                diagnostics.append(Diagnostic(
                    file=fpath,
                    line=int(lineno),
                    message=msg
                ))
        return diagnostics
