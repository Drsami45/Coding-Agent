"""
Tools the agent can call. Every filesystem/code-execution tool is sandboxed
to WORKSPACE_DIR so the agent can never touch files outside the project's
workspace folder.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from langchain_core.tools import tool

from .config import WORKSPACE_DIR

RUN_TIMEOUT_SECONDS = 30


class WorkspaceError(Exception):
    pass


def _safe_path(relative_path: str) -> Path:
    """Resolve a user-supplied relative path and guarantee it stays inside
    the workspace directory. Raises WorkspaceError otherwise."""
    candidate = (WORKSPACE_DIR / relative_path).resolve()
    if WORKSPACE_DIR not in candidate.parents and candidate != WORKSPACE_DIR:
        raise WorkspaceError(
            f"Refused: '{relative_path}' resolves outside the sandboxed workspace."
        )
    return candidate


@tool
def list_files(directory: str = ".") -> str:
    """List files and folders inside the given directory of the workspace
    (relative path, defaults to the workspace root). Returns a tree-like
    listing of file names and sizes."""
    try:
        base = _safe_path(directory)
        if not base.exists():
            return f"Error: directory '{directory}' does not exist."
        lines = []
        for path in sorted(base.rglob("*")):
            if any(part.startswith((".git", "__pycache__", ".venv")) for part in path.parts):
                continue
            rel = path.relative_to(WORKSPACE_DIR)
            if path.is_dir():
                lines.append(f"[DIR]  {rel}/")
            else:
                lines.append(f"[FILE] {rel}  ({path.stat().st_size} bytes)")
        return "\n".join(lines) if lines else "(empty directory)"
    except WorkspaceError as e:
        return f"Error: {e}"


@tool
def read_file(path: str) -> str:
    """Read and return the full text contents of a file in the workspace.
    'path' is relative to the workspace root, e.g. 'src/main.py'."""
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"Error: file '{path}' does not exist."
        if not target.is_file():
            return f"Error: '{path}' is not a file."
        return target.read_text(encoding="utf-8", errors="replace")
    except WorkspaceError as e:
        return f"Error: {e}"


@tool
def write_file(path: str, content: str) -> str:
    """Create or overwrite a file in the workspace with the given text
    content. Creates parent directories automatically. 'path' is relative
    to the workspace root, e.g. 'src/main.py'."""
    try:
        target = _safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} characters to '{path}'."
    except WorkspaceError as e:
        return f"Error: {e}"


@tool
def delete_path(path: str) -> str:
    """Delete a file (or empty directory) in the workspace. 'path' is
    relative to the workspace root."""
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"Error: '{path}' does not exist."
        if target.is_dir():
            target.rmdir()
        else:
            target.unlink()
        return f"Deleted '{path}'."
    except WorkspaceError as e:
        return f"Error: {e}"
    except OSError as e:
        return f"Error deleting '{path}': {e}"


@tool
def run_python_file(path: str, cli_args: str = "") -> str:
    """Execute a Python file that already exists in the workspace and
    return its stdout/stderr. 'path' is relative to the workspace root.
    'cli_args' is an optional string of space-separated command-line
    arguments to pass to the script. Times out after 30 seconds."""
    try:
        target = _safe_path(path)
        if not target.exists():
            return f"Error: file '{path}' does not exist."
        cmd = [sys.executable, str(target), *cli_args.split()]
        return _run_subprocess(cmd)
    except WorkspaceError as e:
        return f"Error: {e}"


@tool
def run_shell_command(command: str) -> str:
    """Run a shell command inside the workspace directory (e.g. 'pytest',
    'pip install requests', 'python -m pyflakes main.py'). Use this to test
    code, install packages, or run linters. Times out after 30 seconds.
    Do not use for destructive or networked commands beyond package
    installation and running code."""
    return _run_subprocess(command, shell=True)


def _run_subprocess(cmd, shell: bool = False) -> str:
    try:
        result = subprocess.run(
            cmd,
            shell=shell,
            cwd=WORKSPACE_DIR,
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT_SECONDS,
        )
        output = ""
        if result.stdout:
            output += f"--- stdout ---\n{result.stdout}\n"
        if result.stderr:
            output += f"--- stderr ---\n{result.stderr}\n"
        output += f"--- exit code: {result.returncode} ---"
        return output.strip()
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {RUN_TIMEOUT_SECONDS} seconds."
    except Exception as e:
        return f"Error running command: {e}"


ALL_TOOLS = [
    list_files,
    read_file,
    write_file,
    delete_path,
    run_python_file,
    run_shell_command,
]