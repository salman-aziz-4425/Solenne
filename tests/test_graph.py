from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from coding_agent.config import resolve_model
from coding_agent.graph import compile_agent as build_graph, model_kwargs


def test_gpt5_tools_use_the_responses_api():
    assert model_kwargs("openai:gpt-6-sol")["use_responses_api"] is True
    assert "temperature" not in model_kwargs("openai:gpt-6-sol")
    assert model_kwargs("openai:gpt-5.6-luna")["use_responses_api"] is True
    assert "use_responses_api" not in model_kwargs("openai:gpt-4.1")


def test_ollama_keeps_a_page_sized_context():
    kwargs = model_kwargs("ollama:qwen3.5:9b")
    assert kwargs["reasoning"] is False
    assert kwargs["num_ctx"] == 32768
    assert kwargs["num_predict"] == -1
    assert "num_ctx" not in model_kwargs("openai:gpt-4.1")


def test_resolve_model_defaults_to_openai(monkeypatch):
    monkeypatch.delenv("MODEL", raising=False)
    assert resolve_model() == "openai:gpt-6-sol"


def test_resolve_model_uses_env_override(monkeypatch):
    monkeypatch.setenv("MODEL", "ollama:llama3.2")
    assert resolve_model() == "ollama:llama3.2"


def test_graph_compiles_and_answers_without_tools(tmp_path):
    bound = MagicMock()
    bound.invoke.return_value = AIMessage(content="Done.")
    model = MagicMock()
    model.bind_tools.return_value = bound

    with patch("coding_agent.graph.init_chat_model", return_value=model):
        graph = build_graph(
            workspace=tmp_path,
            model="openai:gpt-4.1",
            checkpointer=InMemorySaver(),
        )

    result = graph.invoke(
        {"messages": [{"role": "user", "content": "hello"}]},
        {"configurable": {"thread_id": "test"}},
    )
    assert result["messages"][-1].content == "Done."
    assert bound.invoke.called
    assert {"type": "web_search"} not in model.bind_tools.call_args.args[0]
    assert graph.get_graph().nodes.keys() >= {"agent", "tools"}


def test_gpt6_can_search_the_web(tmp_path):
    bound = MagicMock()
    bound.invoke.return_value = AIMessage(content="Done.")
    model = MagicMock()
    model.bind_tools.return_value = bound

    with patch("coding_agent.graph.init_chat_model", return_value=model):
        build_graph(
            workspace=tmp_path,
            model="openai:gpt-6-sol",
            checkpointer=InMemorySaver(),
        )

    assert {"type": "web_search"} in model.bind_tools.call_args.args[0]
