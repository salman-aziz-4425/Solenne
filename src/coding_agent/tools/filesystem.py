from __future__ import annotations

from pathlib import Path

from langchain.tools import tool

from coding_agent.workspace import Workspace, WorkspaceError

MAX_READ_CHARS = 80_000
MAX_GREP_HITS = 80
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache"}


def build_filesystem_tools(workspace: Workspace):
    @tool
    def list_dir(path: str = ".") -> str:
        """List files and folders in a workspace path.

        Args:
            path: Directory relative to the workspace root. Defaults to the root.
        """
        try:
            target = workspace.resolve(path)
        except WorkspaceError as exc:
            return str(exc)
        if not target.exists():
            return f"Not found: {path}"
        if not target.is_dir():
            return f"Not a directory: {workspace.rel(target)}"

        entries = []
        for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if child.name in SKIP_DIRS:
                continue
            kind = "dir" if child.is_dir() else "file"
            entries.append(f"{kind}\t{workspace.rel(child)}")
        if not entries:
            return f"Empty directory: {workspace.rel(target)}"
        return "\n".join(entries)

    @tool
    def read_file(path: str, offset: int = 1, limit: int = 400) -> str:
        """Read a text file from the workspace.

        Args:
            path: File path relative to the workspace.
            offset: 1-based line to start from.
            limit: Maximum number of lines to return.
        """
        try:
            target = workspace.resolve(path)
        except WorkspaceError as exc:
            return str(exc)
        if not target.is_file():
            return f"Not a file: {path}"
        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"Cannot read binary file: {path}"

        lines = text.splitlines()
        start = max(offset, 1)
        end = min(start + max(limit, 1) - 1, len(lines))
        numbered = [f"{i:>4}|{lines[i - 1]}" for i in range(start, end + 1)]
        body = "\n".join(numbered)
        if len(body) > MAX_READ_CHARS:
            body = body[:MAX_READ_CHARS] + "\n... truncated ..."
        return f"{workspace.rel(target)} lines {start}-{end} of {len(lines)}\n{body}"

    @tool
    def write_file(path: str, content: str) -> str:
        """Create or overwrite a text file in the workspace.

        Args:
            path: File path relative to the workspace.
            content: Full file contents.
        """
        try:
            target = workspace.resolve(path)
        except WorkspaceError as exc:
            return str(exc)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {workspace.rel(target)} ({len(content.splitlines())} lines)"

    @tool
    def edit_file(path: str, old_text: str, new_text: str) -> str:
        try:
            target = workspace.resolve(path)
        except WorkspaceError as exc:
            return str(exc)
        if not target.is_file():
            return f"Not a file: {path}"
        text = target.read_text(encoding="utf-8")
        count = text.count(old_text)
        if count == 0:
            return f"old_text not found in {path}"
        if count > 1:
            return f"old_text found {count} times in {path}. Make it unique."
        target.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
        return f"Edited {workspace.rel(target)}"

    @tool
    def grep(pattern: str, path: str = ".") -> str:
        """Search workspace files for a substring (case-insensitive).

        Args:
            pattern: Text to search for.
            path: File or directory to search. Defaults to the workspace root.
        """
        try:
            target = workspace.resolve(path)
        except WorkspaceError as exc:
            return str(exc)
        if not target.exists():
            return f"Not found: {path}"

        hits: list[str] = []
        files = [target] if target.is_file() else _iter_files(target)
        needle = pattern.lower()
        for file in files:
            try:
                lines = file.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for index, line in enumerate(lines, start=1):
                if needle in line.lower():
                    hits.append(f"{workspace.rel(file)}:{index}:{line.strip()}")
                    if len(hits) >= MAX_GREP_HITS:
                        hits.append("... more matches truncated ...")
                        return "\n".join(hits)
        return "\n".join(hits) if hits else f"No matches for {pattern!r}"

    return [list_dir, read_file, write_file, edit_file, grep]


def _iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path
