import http.client
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

from langchain_core.messages import AIMessage, ToolMessage

from coding_agent.clients import create_client, create_project, delete_project, list_clients, rename_client, rename_project
from coding_agent.prompts import STUDIO_PROMPT
from coding_agent.studio import SiteAgents, message_event, page_from_reply
from coding_agent.web import make_handler


def test_create_client_makes_a_private_site(tmp_path: Path):
    client = create_client("Acme Co", tmp_path)
    assert client.id == "acme-co"
    assert (tmp_path / "acme-co" / "site" / "index.html").is_file()
    assert (tmp_path / "acme-co" / "brief.md").is_file()
    assert list_clients(tmp_path)[0].name == "Acme Co"


def test_preview_stays_inside_the_client_site(tmp_path: Path):
    frontend = Path(__file__).resolve().parents[1] / "frontend"
    create_client("Acme", tmp_path)
    (tmp_path / "secret.txt").write_text("nope", encoding="utf-8")
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(tmp_path, frontend))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        with urlopen(f"http://127.0.0.1:{port}/api/clients") as response:
            body = json.loads(response.read().decode("utf-8"))
        assert body[0]["projects"][0]["id"] == "site"
        assert body[0]["projects"][0]["preview_url"] == "/preview/acme/site/"

        with urlopen(f"http://127.0.0.1:{port}/clients/acme") as response:
            page = response.read().decode("utf-8")
        assert response.status == 200
        assert "<title>Studio</title>" in page
        with urlopen(f"http://127.0.0.1:{port}/clients/acme/projects") as response:
            assert b'id="projects"' in response.read()
        with urlopen(f"http://127.0.0.1:{port}/clients/acme/projects/site") as response:
            assert b'id="editor"' in response.read()

        with urlopen(f"http://127.0.0.1:{port}/preview/acme/") as response:
            html = response.read().decode("utf-8")
        assert "Acme" in html

        connection = http.client.HTTPConnection("127.0.0.1", port)
        connection.request("GET", "/preview/acme/%2e%2e/%2e%2e/secret.txt")
        denied = connection.getresponse()
        body = denied.read()
        assert denied.status == 404
        assert b"nope" not in body
    finally:
        server.shutdown()
        server.server_close()


def test_studio_answers_questions_without_tools():
    assert "Do not call any tool" in STUDIO_PROMPT


def test_a_finished_page_in_the_reply_is_saved(tmp_path: Path, monkeypatch):
    body = "<p>" + ("Los Santos operations. " * 40) + "</p>"
    page = f"<!DOCTYPE html><html><head><title>Solenne</title></head><body>{body}</body></html>"
    reply = f"Here is the complete page:\n```html\n{page}\n```"

    class _Graph:
        def stream(self, *_args, **_kwargs):
            yield {"messages": [AIMessage(content=reply)]}

    monkeypatch.setattr("coding_agent.studio.compile_agent", lambda **_kwargs: _Graph())
    events = list(SiteAgents().stream("acme", "Acme", tmp_path, "rebuild the landing page"))
    saved = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert saved.startswith("<!DOCTYPE html>")
    assert "Los Santos operations." in saved
    assert any(event["type"] == "tool" and "index.html" in event["text"] for event in events)
    assert "<!DOCTYPE html>" not in next(event["text"] for event in events if event["type"] == "assistant")


def test_a_short_html_example_stays_in_the_chat():
    snippet = "<!DOCTYPE html><html><body>hi</body></html>"
    assert page_from_reply(f"A tiny example is {snippet}. " + ("word " * 40)) is None


def test_message_event_reports_tools_and_the_answer():
    tool = message_event(AIMessage(content="", tool_calls=[{"name": "write_file", "args": {}, "id": "1"}]))
    assert tool == {"type": "status", "text": "write_file"}
    answer = message_event(AIMessage(content="The page is updated."))
    assert answer == {"type": "assistant", "text": "The page is updated."}
    result = message_event(ToolMessage(content="Wrote index.html", tool_call_id="1", name="write_file"))
    assert result["type"] == "tool"
    assert "index.html" in result["text"]


def test_workspace_can_hold_another_project_and_a_new_name(tmp_path: Path):
    client = create_client("Acme", tmp_path)
    renamed = rename_client(client.id, "Acme Studio", tmp_path)
    assert renamed.id == "acme"
    assert renamed.name == "Acme Studio"
    assert (tmp_path / "acme").is_dir()

    poster = create_project("acme", "Spring poster", tmp_path)
    assert poster.id == "spring-poster"
    renamed_project = rename_project("acme", poster.id, "Launch poster", tmp_path)
    assert renamed_project.id == "spring-poster"
    assert renamed_project.name == "Launch poster"
    delete_project("acme", "spring-poster", tmp_path)
    assert not (tmp_path / "acme" / "projects" / "spring-poster").exists()
    poster = create_project("acme", "Spring poster", tmp_path)
    listed = list_clients(tmp_path)[0]
    assert [project.id for project in listed.projects] == ["site", "spring-poster"]

    frontend = Path(__file__).resolve().parents[1] / "frontend"
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(tmp_path, frontend))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        with urlopen(f"http://127.0.0.1:{port}/preview/acme/spring-poster/") as response:
            html = response.read().decode("utf-8")
        assert "Spring poster" in html
        with urlopen(f"http://127.0.0.1:{port}/preview/acme/") as response:
            main = response.read().decode("utf-8")
        assert "Acme" in main
    finally:
        server.shutdown()
        server.server_close()


class _FakeAgents:
    def stream(self, client_id, client_name, site, text, project_id="site", project_name=""):
        assert client_id == "acme"
        assert "pink" in text
        assert site.name == "site"
        yield {"type": "status", "text": "write_file"}
        yield {"type": "assistant", "text": "Updated the page."}
        yield {"type": "done"}


def test_chat_runs_the_agent_for_that_client(tmp_path: Path):
    frontend = Path(__file__).resolve().parents[1] / "frontend"
    create_client("Acme", tmp_path)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(tmp_path, frontend, _FakeAgents()))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        connection = http.client.HTTPConnection("127.0.0.1", port)
        payload = json.dumps({"message": "make the hero pink"}).encode("utf-8")
        connection.request(
            "POST",
            "/api/clients/acme/run",
            body=payload,
            headers={"Content-Type": "application/json", "Content-Length": str(len(payload))},
        )
        response = connection.getresponse()
        lines = [json.loads(line) for line in response.read().decode("utf-8").splitlines() if line]
        assert response.status == 200
        assert lines[-1]["type"] == "done"
        assert any(line["type"] == "assistant" for line in lines)
    finally:
        server.shutdown()
        server.server_close()
