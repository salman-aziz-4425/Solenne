from __future__ import annotations

from pathlib import Path


class WorkspaceError(ValueError):
    """Raised when a tool tries to leave the sandbox."""


class Workspace:
    """Keep every file/shell action inside one project folder."""

    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, path: str | Path | None = None) -> Path:
        if path in (None, "", ".", "./"):
            return self.root
        candidate = Path(path)
        target = candidate.resolve() if candidate.is_absolute() else (self.root / candidate).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceError(f"Path is outside the workspace: {path}") from exc
        return target

    def rel(self, path: Path) -> str:
        return str(path.relative_to(self.root)) or "."
