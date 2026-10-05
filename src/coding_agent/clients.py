from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from html import escape
from pathlib import Path

from coding_agent.config import PROJECT_ROOT

CLIENTS_ROOT = PROJECT_ROOT / "clients"
_SLUG = re.compile(r"[^a-z0-9]+")
_CLIENT_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class Project:
    id: str
    name: str

    def to_dict(self, client_id: str) -> dict[str, str]:
        return {
            "id": self.id,
            "name": self.name,
            "preview_url": f"/preview/{client_id}/{self.id}/",
        }


@dataclass(frozen=True)
class Client:
    id: str
    name: str
    projects: tuple[Project, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "preview_url": f"/preview/{self.id}/site/",
            "workspace": f"clients/{self.id}",
            "projects": [project.to_dict(self.id) for project in self.projects],
        }


def slugify(name: str) -> str:
    slug = _SLUG.sub("-", name.strip().lower()).strip("-")[:48].strip("-")
    if not slug or not _CLIENT_ID.match(slug):
        raise ValueError("Use a client name with letters or numbers.")
    return slug


def is_client_id(value: str) -> bool:
    return bool(_CLIENT_ID.match(value))


def list_clients(root: Path | None = None) -> list[Client]:
    base = root or CLIENTS_ROOT
    if not base.exists():
        return []
    clients: list[Client] = []
    for path in base.iterdir():
        meta = path / "client.json"
        if not path.is_dir() or not meta.is_file():
            continue
        data = json.loads(meta.read_text(encoding="utf-8"))
        clients.append(
            Client(
                id=str(data["id"]),
                name=str(data["name"]),
                projects=tuple(list_projects(path)),
            )
        )
    clients.sort(key=lambda client: client.name.lower())
    return clients


def create_client(name: str, root: Path | None = None) -> Client:
    base = root or CLIENTS_ROOT
    client_id = slugify(name)
    folder = base / client_id
    if folder.exists():
        raise FileExistsError(f"A client named {client_id} already exists.")
    display = name.strip()
    site = folder / "site"
    site.mkdir(parents=True)
    (folder / "client.json").write_text(
        json.dumps({"id": client_id, "name": display}, indent=2) + "\n",
        encoding="utf-8",
    )
    (folder / "brief.md").write_text(
        f"# {display}\n\nCampaign brief for this client. The live site is in `site/`.\n",
        encoding="utf-8",
    )
    (site / "index.html").write_text(_starter_page(display), encoding="utf-8")
    (site / "project.json").write_text(
        json.dumps({"id": "site", "name": "Main"}, indent=2) + "\n",
        encoding="utf-8",
    )
    return Client(id=client_id, name=display, projects=(Project(id="site", name="Main"),))


def rename_client(client_id: str, name: str, root: Path | None = None) -> Client:
    """Change the display name. The folder id stays so links keep working."""
    base = root or CLIENTS_ROOT
    display = name.strip()
    if not display:
        raise ValueError("Give the workspace a name.")
    if not is_client_id(client_id):
        raise FileNotFoundError("No client with that id.")
    meta_path = base / client_id / "client.json"
    if not meta_path.is_file():
        raise FileNotFoundError("No client with that id.")
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    data["name"] = display
    meta_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return Client(id=client_id, name=display, projects=tuple(list_projects(base / client_id)))


def create_project(client_id: str, name: str, root: Path | None = None) -> Project:
    base = root or CLIENTS_ROOT
    if not is_client_id(client_id) or not (base / client_id / "client.json").is_file():
        raise FileNotFoundError("No client with that id.")
    project_id = slugify(name)
    folder = project_dir(client_id, project_id, base)
    if folder.exists():
        raise FileExistsError(f"A project named {project_id} already exists.")
    display = name.strip()
    folder.mkdir(parents=True)
    (folder / "project.json").write_text(
        json.dumps({"id": project_id, "name": display}, indent=2) + "\n",
        encoding="utf-8",
    )
    (folder / "index.html").write_text(_starter_page(display), encoding="utf-8")
    return Project(id=project_id, name=display)


def rename_project(client_id: str, project_id: str, name: str, root: Path | None = None) -> Project:
    """Change the project title. The folder id stays so the preview link keeps working."""
    base = root or CLIENTS_ROOT
    display = name.strip()
    if not display:
        raise ValueError("Give the project a name.")
    folder = _existing_project(client_id, project_id, base)
    meta_path = folder / "project.json"
    data = {"id": project_id, "name": display}
    if meta_path.is_file():
        stored = json.loads(meta_path.read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            data = stored
    data["id"] = project_id
    data["name"] = display
    meta_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return Project(id=project_id, name=display)


def delete_project(client_id: str, project_id: str, root: Path | None = None) -> None:
    folder = _existing_project(client_id, project_id, root or CLIENTS_ROOT)
    shutil.rmtree(folder)


def _existing_project(client_id: str, project_id: str, root: Path) -> Path:
    if not is_client_id(client_id) or not is_client_id(project_id):
        raise FileNotFoundError("No project with that id.")
    client_root = (root / client_id).resolve()
    folder = project_dir(client_id, project_id, root).resolve()
    if client_root not in folder.parents or not folder.is_dir():
        raise FileNotFoundError("No project with that id.")
    return folder


def list_projects(folder: Path) -> list[Project]:
    projects: list[Project] = []
    site = folder / "site"
    if site.is_dir():
        projects.append(Project(id="site", name=_project_name(site, "Main")))
    extra = folder / "projects"
    if extra.is_dir():
        for path in sorted(extra.iterdir(), key=lambda item: item.name.lower()):
            if path.is_dir() and is_client_id(path.name) and path.name != "site":
                projects.append(Project(id=path.name, name=_project_name(path, path.name)))
    return projects


def project_dir(client_id: str, project_id: str, root: Path | None = None) -> Path:
    base = (root or CLIENTS_ROOT) / client_id
    if project_id == "site":
        return base / "site"
    return base / "projects" / project_id


def _project_name(folder: Path, fallback: str) -> str:
    meta = folder / "project.json"
    if not meta.is_file():
        return fallback
    data = json.loads(meta.read_text(encoding="utf-8"))
    name = str(data.get("name") or "").strip()
    return name or fallback


def _starter_page(name: str) -> str:
    safe = escape(name)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe}</title>
  <style>
    :root {{ color-scheme: light; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Georgia, "Iowan Old Style", serif;
      color: #1c1914;
      background:
        radial-gradient(900px 480px at 10% -10%, #fff7d6, transparent 60%),
        linear-gradient(165deg, #f7f3ea 0%, #d9ecff 48%, #e8ff8a 100%);
    }}
    main {{
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      justify-content: flex-end;
      padding: 56px 8vw 64px;
    }}
    .eyebrow {{
      margin: 0 0 16px;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-size: 13px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 0;
      max-width: 10ch;
      font-size: clamp(56px, 10vw, 112px);
      line-height: 0.9;
      letter-spacing: -0.045em;
    }}
    p {{
      max-width: 36rem;
      margin: 28px 0 0;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      font-size: 18px;
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <main>
    <p class="eyebrow">Campaign site</p>
    <h1>{safe}</h1>
    <p>This is {safe}'s workspace. The preview updates when new pages land in this folder.</p>
  </main>
</body>
</html>
"""
