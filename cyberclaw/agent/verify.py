"""Auto-verification: detect project type and run build/test after code changes."""

from pathlib import Path

from loguru import logger


# Map of project marker file → (project type, verify command)
PROJECT_TYPES: list[tuple[str, str, str]] = [
    # (marker file/dir, project type, verify command)
    ("go.mod", "go", "go build ./... 2>&1 | head -30"),
    ("Cargo.toml", "rust", "cargo check 2>&1 | head -30"),
    ("package.json", "node", "npx tsc --noEmit 2>&1 | head -30"),
    ("pyproject.toml", "python", "python -m py_compile {file} 2>&1"),
    ("setup.py", "python", "python -m py_compile {file} 2>&1"),
    ("requirements.txt", "python", "python -m py_compile {file} 2>&1"),
    ("Makefile", "make", "make -n 2>&1 | head -10"),  # Dry-run only
]

# File-modifying tool names that should trigger verification
FILE_MODIFY_TOOLS = {"write_file", "edit_file"}


def detect_project_type(workspace: Path) -> tuple[str, str] | None:
    """
    Detect project type from workspace marker files.
    
    Returns:
        Tuple of (project_type, verify_command) or None if unknown.
    """
    for marker, proj_type, command in PROJECT_TYPES:
        if (workspace / marker).exists():
            return (proj_type, command)
    return None


def get_verify_command(
    workspace: Path,
    custom_command: str = "",
    modified_file: str = "",
) -> str | None:
    """
    Get the verify command to run after file modification.
    
    Args:
        workspace: The project workspace path.
        custom_command: User-configured custom verify command (takes priority).
        modified_file: Path of the modified file (used in {file} placeholder).
    
    Returns:
        The command string to execute, or None if verification is not applicable.
    """
    if custom_command:
        return custom_command.replace("{file}", modified_file)
    
    detected = detect_project_type(workspace)
    if not detected:
        return None
    
    proj_type, command = detected
    
    # For Python, only py_compile the specific file
    if proj_type == "python" and modified_file:
        if modified_file.endswith(".py"):
            return command.replace("{file}", modified_file)
        return None  # Non-python file modified, skip
    
    # For other project types, strip {file} placeholder if present
    return command.replace("{file}", modified_file) if "{file}" in command else command


def should_verify(tool_names: list[str]) -> bool:
    """Check if any of the executed tools are file-modifying tools."""
    return bool(FILE_MODIFY_TOOLS & set(tool_names))
