from __future__ import annotations

import argparse
import sys
import uuid

from langchain.messages import AIMessage, HumanMessage, ToolMessage
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from coding_agent.config import recursion_limit, resolve_model, resolve_workspace
from coding_agent.graph import compile_agent

console = Console()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LangGraph coding agent")
    parser.add_argument("task", nargs="*", help="Coding task. Omit for an interactive session.")
    parser.add_argument("--workspace", help="Folder the agent can read, write, and run in.")
    parser.add_argument("--thread-id", default=str(uuid.uuid4())[:8], help="Conversation id for memory.")
    args = parser.parse_args(argv)

    workspace = resolve_workspace(args.workspace)
    graph = compile_agent(workspace=workspace)
    config = {
        "configurable": {"thread_id": args.thread_id},
        "recursion_limit": recursion_limit(),
    }

    console.print(
        Panel.fit(
            f"[bold]LangGraph coding agent[/bold]\nmodel: {resolve_model()}\nworkspace: {workspace}\nthread: {args.thread_id}",
            border_style="cyan",
        )
    )

    task = " ".join(args.task).strip()
    if task:
        _run_turn(graph, task, config)
        return 0

    console.print("Type a coding task. Use [bold]/exit[/bold] to quit.\n")
    while True:
        try:
            prompt = console.input("[bold cyan]you>[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nbye")
            return 0
        if not prompt:
            continue
        if prompt in {"/exit", "/quit", "exit", "quit"}:
            return 0
        _run_turn(graph, prompt, config)


def _run_turn(graph, prompt: str, config: dict) -> None:
    printed_ids: set[str] = set()
    try:
        for event in graph.stream(
            {"messages": [HumanMessage(content=prompt)]},
            config=config,
            stream_mode="values",
        ):
            message = event["messages"][-1]
            key = getattr(message, "id", None) or str(id(message))
            if key in printed_ids:
                continue
            printed_ids.add(key)
            _print_message(message)
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        return


def _print_message(message) -> None:
    if isinstance(message, HumanMessage):
        return
    if isinstance(message, ToolMessage):
        preview = (message.content or "").strip()
        if len(preview) > 500:
            preview = preview[:500] + " ..."
        console.print(f"[yellow]tool {message.name}[/yellow]\n{preview}\n")
        return
    if isinstance(message, AIMessage):
        if message.tool_calls:
            names = ", ".join(call["name"] for call in message.tool_calls)
            console.print(f"[magenta]agent → {names}[/magenta]")
            return
        content = message.content
        if isinstance(content, list):
            content = "".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        if content:
            console.print(Panel(Markdown(str(content)), title="agent", border_style="green"))


if __name__ == "__main__":
    sys.exit(main())
