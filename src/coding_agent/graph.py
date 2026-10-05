from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# LangGraph loads this file by path, so the src folder must be importable.
_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from langchain.chat_models import init_chat_model
from langchain.messages import SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from coding_agent.config import resolve_model, resolve_workspace
from coding_agent.prompts import SYSTEM_PROMPT
from coding_agent.tools.filesystem import build_filesystem_tools
from coding_agent.tools.shell import build_shell_tool
from coding_agent.workspace import Workspace


class AgentState(MessagesState):
    """Conversation state for the coding agent."""


def model_kwargs(model_name: str) -> dict[str, Any]:
    """gpt-5 and gpt-6 tool calls must use the responses API, not chat completions."""
    bare = model_name.split(":", 1)[-1]
    kwargs: dict[str, Any] = {}
    if not bare.startswith("gpt-6"):
        kwargs["temperature"] = 0
    if bare.startswith(("gpt-5", "gpt-6")):
        kwargs["use_responses_api"] = True
    return kwargs


def compile_agent(
    workspace: str | Path | None = None,
    model: str | None = None,
    checkpointer: Any | None = None,
    system_prompt: str | None = None,
):
    ws = Workspace(resolve_workspace(workspace))
    tools = [*build_filesystem_tools(ws), build_shell_tool(ws)]
    model_name = model or resolve_model()
    bound_tools: list[Any] = [*tools]
    if model_kwargs(model_name).get("use_responses_api"):
        bound_tools.append({"type": "web_search"})
    llm = init_chat_model(model_name, **model_kwargs(model_name)).bind_tools(bound_tools)
    prompt = system_prompt or SYSTEM_PROMPT

    def agent(state: AgentState) -> dict:
        messages = [SystemMessage(content=prompt), *state["messages"]]
        return {"messages": [llm.invoke(messages)]}

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    saver = InMemorySaver() if checkpointer is None else checkpointer
    return builder.compile(checkpointer=saver)


def build_graph(config: dict):
    """LangGraph dev entry. The server calls this with one RunnableConfig."""
    configurable = config.get("configurable") if isinstance(config, dict) else None
    workspace = (configurable or {}).get("workspace")
    return compile_agent(workspace=workspace, checkpointer=False)


graph = build_graph
