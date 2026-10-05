from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from coding_agent.clients import (
    CLIENTS_ROOT,
    create_client,
    create_project,
    delete_project,
    is_client_id,
    list_clients,
    project_dir,
    rename_client,
    rename_project,
)
from coding_agent.config import PROJECT_ROOT
from coding_agent.studio import SiteAgents
from coding_agent.workspace import Workspace, WorkspaceError

FRONTEND_ROOT = PROJECT_ROOT / "frontend"


def _client_page(path: str) -> bool:
    parts = [unquote(part) for part in path.split("/") if part]
    if not parts or parts[0] != "clients" or not is_client_id(parts[1] if len(parts) > 1 else ""):
        return False
    if len(parts) == 2:
        return True
    if len(parts) == 3 and parts[2] == "projects":
        return True
    return len(parts) == 4 and parts[2] == "projects" and is_client_id(parts[3])


def make_handler(clients_root: Path, frontend_root: Path, agents: SiteAgents | None = None):
    agents = agents or SiteAgents()
    static = {
        "/": frontend_root / "index.html",
        "/index.html": frontend_root / "index.html",
        "/styles.css": frontend_root / "styles.css",
        "/app.js": frontend_root / "app.js",
    }

    class Handler(BaseHTTPRequestHandler):
        server_version = "Studio/0.1"

        def log_message(self, fmt: str, *args) -> None:
            return

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/clients":
                payload = [client.to_dict() for client in list_clients(clients_root)]
                self._json(200, payload)
                return
            if path in static or _client_page(path):
                self._file(static.get(path, frontend_root / "index.html"))
                return
            if path.startswith("/preview/"):
                self._preview(path)
                return
            self._json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            parts = [unquote(part) for part in path.split("/") if part]
            if path == "/api/clients":
                self._create_client()
                return
            if len(parts) == 4 and parts[:2] == ["api", "clients"] and is_client_id(parts[2]):
                if parts[3] == "run":
                    self._run_agent(parts[2])
                    return
                if parts[3] == "rename":
                    self._rename_client(parts[2])
                    return
                if parts[3] == "projects":
                    self._create_project(parts[2])
                    return
            if (
                len(parts) == 6
                and parts[:2] == ["api", "clients"]
                and parts[3] == "projects"
                and is_client_id(parts[2])
                and is_client_id(parts[4])
            ):
                if parts[5] == "rename":
                    self._rename_project(parts[2], parts[4])
                    return
                if parts[5] == "delete":
                    self._delete_project(parts[2], parts[4])
                    return
            self._json(404, {"error": "Not found"})

        def _create_client(self) -> None:
            body = self._body(20_000)
            if body is None:
                return
            try:
                client = create_client(str(body.get("name", "")), clients_root)
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
                return
            except FileExistsError as exc:
                self._json(409, {"error": str(exc)})
                return
            self._json(201, client.to_dict())

        def _rename_client(self, client_id: str) -> None:
            body = self._body(20_000)
            if body is None:
                return
            try:
                client = rename_client(client_id, str(body.get("name", "")), clients_root)
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
                return
            except FileNotFoundError as exc:
                self._json(404, {"error": str(exc)})
                return
            self._json(200, client.to_dict())

        def _create_project(self, client_id: str) -> None:
            body = self._body(20_000)
            if body is None:
                return
            try:
                project = create_project(client_id, str(body.get("name", "")), clients_root)
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
                return
            except FileNotFoundError as exc:
                self._json(404, {"error": str(exc)})
                return
            except FileExistsError as exc:
                self._json(409, {"error": str(exc)})
                return
            self._json(201, project.to_dict(client_id))

        def _rename_project(self, client_id: str, project_id: str) -> None:
            body = self._body(20_000)
            if body is None:
                return
            try:
                project = rename_project(client_id, project_id, str(body.get("name", "")), clients_root)
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
                return
            except FileNotFoundError as exc:
                self._json(404, {"error": str(exc)})
                return
            self._json(200, project.to_dict(client_id))

        def _delete_project(self, client_id: str, project_id: str) -> None:
            try:
                delete_project(client_id, project_id, clients_root)
            except FileNotFoundError as exc:
                self._json(404, {"error": str(exc)})
                return
            client = next((item for item in list_clients(clients_root) if item.id == client_id), None)
            if client is None:
                self._json(404, {"error": "No client with that id."})
                return
            self._json(200, client.to_dict())

        def _run_agent(self, client_id: str) -> None:
            body = self._body(80_000)
            if body is None:
                return
            text = str(body.get("message", "")).strip()
            if not text:
                self._json(400, {"error": "Tell the agent what to make."})
                return
            client = next((item for item in list_clients(clients_root) if item.id == client_id), None)
            if client is None:
                self._json(404, {"error": "No client with that id."})
                return
            project_id = str(body.get("project") or "site").strip()
            if not is_client_id(project_id):
                self._json(400, {"error": "Unknown project."})
                return
            site = project_dir(client_id, project_id, clients_root)
            project = next((item for item in client.projects if item.id == project_id), None)
            if project is None or not site.is_dir():
                self._json(404, {"error": "That project is not in this workspace."})
                return
            self._events(
                agents.stream(
                    client_id,
                    client.name,
                    site,
                    text,
                    project_id=project.id,
                    project_name=project.name,
                )
            )

        def _body(self, limit: int) -> dict | None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._json(400, {"error": "Invalid request"})
                return None
            if length > limit:
                self._json(400, {"error": "Request is too large"})
                return None
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._json(400, {"error": "Invalid JSON"})
                return None
            if not isinstance(body, dict):
                self._json(400, {"error": "Invalid JSON"})
                return None
            return body

        def _events(self, events) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                for event in events:
                    self.wfile.write((json.dumps(event) + "\n").encode("utf-8"))
                    self.wfile.flush()
            except BrokenPipeError:
                return

        def _preview(self, path: str) -> None:
            parts = [unquote(part) for part in path.split("/") if part]
            if len(parts) < 2 or parts[0] != "preview" or not is_client_id(parts[1]):
                self._json(404, {"error": "Not found"})
                return
            client_id, *rest = parts[1:]
            project_id = "site"
            relative_parts = rest
            if rest and is_client_id(rest[0]):
                candidate = project_dir(client_id, rest[0], clients_root)
                if candidate.is_dir():
                    project_id = rest[0]
                    relative_parts = rest[1:]
            site = project_dir(client_id, project_id, clients_root)
            if not site.is_dir():
                self._json(404, {"error": "This client has no site yet"})
                return
            relative = "/".join(relative_parts) if relative_parts else "index.html"
            try:
                target = Workspace(site).resolve(relative)
            except WorkspaceError:
                self._json(404, {"error": "Not found"})
                return
            if target.is_dir():
                target = target / "index.html"
            if not target.is_file():
                self._json(404, {"error": "Not found"})
                return
            self._file(target)

        def _file(self, path: Path) -> None:
            if not path.is_file():
                self._json(404, {"error": "Not found"})
                return
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _json(self, status: int, payload: object) -> None:
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8765, clients_root: Path | None = None) -> None:
    root = clients_root or CLIENTS_ROOT
    root.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, port), make_handler(root, FRONTEND_ROOT))
    print(f"Studio http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        server.server_close()


def main() -> None:
    serve()


if __name__ == "__main__":
    main()
