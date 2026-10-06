from __future__ import annotations

import re
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


_PAGE = re.compile(r"(<!DOCTYPE html\b.*?</html>)", re.IGNORECASE | re.DOTALL)


def page_from_reply(text: str) -> str | None:
    """A reply that is mostly a finished HTML document, which should be the site."""
    match = _PAGE.search(text)
    if match is None:
        return None
    html = match.group(1).strip()
    if len(html) < 400 or len(html) < len(text) * 0.5:
        return None
    return html


def _saved_index(message: Any) -> bool:
    return (
        isinstance(message, ToolMessage)
        and getattr(message, "name", "") in {"write_file", "edit_file"}
        and "index.html" in message_text(message)
    )


def _events_for(site: Path, message: Any, wrote_page: bool) -> tuple[bool, list[dict[str, str]]]:
    """Turn one model message into the events the page should show."""
    if _saved_index(message):
        wrote_page = True
    payload = message_event(message)
    if payload is None:
        return wrote_page, []
    html = None
    if payload["type"] == "assistant" and not wrote_page:
        html = page_from_reply(payload["text"])
    if html is None:
        return wrote_page, [payload]
    (site / "index.html").write_text(html + "\n", encoding="utf-8")
    lines = html.count("\n") + 1
    return True, [
        {"type": "tool", "text": f"write_file\nWrote index.html ({lines} lines)"},
        {"type": "assistant", "text": "Saved the page to index.html. The preview is updated."},
    ]


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
            "When they ask you to change this project, save index.html with write_file or edit_file. "
            "Do not paste the page into the reply.\n\n"
            f"{text}"
        )
        config = {
            "configurable": {"thread_id": key},
            "recursion_limit": recursion_limit(),
        }
        with lock:
            seen: set[str] = set()
            wrote_page = False
            try:
                for event in graph.stream(
                    {"messages": [HumanMessage(content=prompt)]},
                    config=config,
                    stream_mode="values",
                ):
                    message = event["messages"][-1]
                    marker = getattr(message, "id", None) or str(id(message))
                    if marker in seen:
                        continue
                    seen.add(marker)
                    wrote_page, payloads = _events_for(site, message, wrote_page)
                    yield from payloads
            except Exception as exc:
                yield {"type": "error", "text": str(exc)}
                return
        yield {"type": "done"}
