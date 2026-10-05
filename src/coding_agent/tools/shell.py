from __future__ import annotations

import os
import subprocess

from langchain.tools import tool

from coding_agent.workspace import Workspace

MAX_OUTPUT_CHARS = 40_000
DEFAULT_TIMEOUT = 60


def build_shell_tool(workspace: Workspace):
    @tool
    def run_command(command: str, timeout_seconds: int = DEFAULT_TIMEOUT) -> str:
        """Run a shell command in the workspace. Use this to execute code and tests.

        Args:
            command: Shell command to run. The working directory is the workspace.
            timeout_seconds: Kill the process after this many seconds. Default 60.
        """
        timeout = min(max(timeout_seconds, 1), 180)
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=workspace.root,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return f"Timed out after {timeout}s: {command}"

        stdout = _clip(completed.stdout)
        stderr = _clip(completed.stderr)
        parts = [f"exit_code={completed.returncode}"]
        if stdout:
            parts.append(f"stdout:\n{stdout}")
        if stderr:
            parts.append(f"stderr:\n{stderr}")
        if len(parts) == 1:
            parts.append("(no output)")
        return "\n".join(parts)

    return run_command


def _clip(text: str) -> str:
    text = text.strip()
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n... truncated ..."
