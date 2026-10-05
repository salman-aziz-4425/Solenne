from pathlib import Path

from coding_agent.tools.filesystem import build_filesystem_tools
from coding_agent.tools.shell import build_shell_tool
from coding_agent.workspace import Workspace, WorkspaceError


def test_workspace_blocks_escape(tmp_path: Path):
    ws = Workspace(tmp_path)
    try:
        ws.resolve("../secret.txt")
        raised = False
    except WorkspaceError:
        raised = True
    assert raised


def test_write_read_edit_and_grep(tmp_path: Path):
    ws = Workspace(tmp_path)
    tools = {tool.name: tool for tool in build_filesystem_tools(ws)}

    written = tools["write_file"].invoke({"path": "app.py", "content": "print('hello')\n"})
    assert "Wrote app.py" in written

    listing = tools["list_dir"].invoke({"path": "."})
    assert "app.py" in listing

    contents = tools["read_file"].invoke({"path": "app.py"})
    assert "print('hello')" in contents

    edited = tools["edit_file"].invoke(
        {"path": "app.py", "old_text": "hello", "new_text": "world"}
    )
    assert "Edited app.py" in edited

    matches = tools["grep"].invoke({"pattern": "world", "path": "."})
    assert "app.py:1" in matches


def test_run_command_uses_workspace(tmp_path: Path):
    ws = Workspace(tmp_path)
    (tmp_path / "hello.py").write_text("print('ok')\n", encoding="utf-8")
    run_command = build_shell_tool(ws)
    result = run_command.invoke({"command": "python hello.py"})
    assert "exit_code=0" in result
    assert "ok" in result
