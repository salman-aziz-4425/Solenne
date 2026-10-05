from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKSPACE = PROJECT_ROOT / "workspace"


DEFAULT_MODEL = "openai:gpt-6-sol"


def resolve_model() -> str:
    if explicit := os.getenv("MODEL"):
        return explicit
    return DEFAULT_MODEL


def resolve_workspace(path: str | Path | None = None) -> Path:
    raw = path or os.getenv("WORKSPACE") or DEFAULT_WORKSPACE
    workspace = Path(raw).expanduser().resolve()
    if not workspace.is_dir():
        workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def recursion_limit() -> int:
    return int(os.getenv("RECURSION_LIMIT", "80"))
