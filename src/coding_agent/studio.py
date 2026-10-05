from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from langchain.messages import AIMessage, HumanMessage, ToolMessage

from coding_agent.config import recursion_limit
from coding_agent.graph import compile_agent
from coding_agent.prompts import STUDIO_PROMPT


def message_text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block) for block in content
        )
    return str(content or "")


def message_event(message: Any) -> dict[str, str] | None:
    if isinstance(message, HumanMessage):
        return None
    if isinstance(message, ToolMessage):
        preview = message_text(message).strip()
        if len(preview) > 400:
            preview = preview[:400] + " ..."
        name = getattr(message, "name", None) or "tool"
        return {"type": "tool", "text": f"{name}\n{preview}" if preview else name}
    if isinstance(message, AIMessage):
        if message.tool_calls:
            names = ", ".join(call["name"] for call in message.tool_calls)
            return {"type": "status", "text": names}
        text = message_text(message).strip()
        if text:
            return {"type": "assistant", "text": text}
    return None


class SiteAgents:
    """One compiled agent per client, kept for the life of the server."""

    def __init__(self) -> None:
        self._graphs: dict[str, Any] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def stream(
        self,
        client_id: str,
        client_name: str,
        site: Path,
        text: str,
        project_id: str = "site",
        project_name: str = "",
    ) -> Iterator[dict[str, str]]:
        key = f"{client_id}:{project_id}"
        label = project_name or project_id
        try:
            with self._guard:
                lock = self._locks.setdefault(key, threading.Lock())
                graph = self._graphs.get(key)
                if graph is None:
                    graph = compile_agent(workspace=site, system_prompt=STUDIO_PROMPT)
                    self._graphs[key] = graph
        except Exception as exc:
            yield {"type": "error", "text": str(exc)}
            return
        prompt = (
            f"Client: {client_name}. Project: {label}. The preview shows this project's index.html.\n"
            "Edit only this project folder.\n"
            "If this is a question or casual talk, answer in text and do not call tools. "
            "Call tools only when they ask you to change this project.\n\n"
            f"{text}"
        )
        config = {
            "configurable": {"thread_id": key},
            "recursion_limit": recursion_limit(),
        }
        with lock:
            seen: set[str] = set()
            try:
                for event in graph.stream(
                    {"messages": [HumanMessage(content=prompt)]},
                    config=config,
                    stream_mode="values",
                ):
                    message = event["messages"][-1]
                    key = getattr(message, "id", None) or str(id(message))
                    if key in seen:
                        continue
                    seen.add(key)
                    payload = message_event(message)
                    if payload:
                        yield payload
            except Exception as exc:
                yield {"type": "error", "text": str(exc)}
                return
        yield {"type": "done"}
