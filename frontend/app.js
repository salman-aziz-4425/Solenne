const state = {
  clients: [],
  route: { screen: "home" },
  width: "desktop",
  running: false,
};

const home = document.querySelector("#home");
const list = document.querySelector("#client-list");
const homeEmpty = document.querySelector("#home-empty");
const workspace = document.querySelector("#workspace");
const projectsScreen = document.querySelector("#projects");
const editor = document.querySelector("#editor");
const workspaceBody = document.querySelector("#workspace-body");
const title = document.querySelector("#client-title");
const pathLabel = document.querySelector("#client-path");
const messages = document.querySelector("#messages");
const preview = document.querySelector("#preview");
const previewUrl = document.querySelector("#preview-url");
const frameWrap = document.querySelector("#frame-wrap");
const error = document.querySelector("#client-error");
const projectList = document.querySelector("#project-list");
const projectError = document.querySelector("#project-error");
const projectsEmpty = document.querySelector("#projects-empty");
const renameError = document.querySelector("#rename-error");

const slug = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

document.querySelector("#new-client").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = document.querySelector("#client-name");
  error.hidden = true;
  const response = await fetch("/api/clients", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: input.value }),
  });
  const body = await response.json();
  if (!response.ok) {
    error.textContent = body.error || "Could not add that client.";
    error.hidden = false;
    return;
  }
  input.value = "";
  state.clients.push(body);
  go(`/clients/${body.id}`);
});

document.querySelector("#rename-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const client = selected();
  if (!client) return;
  renameError.hidden = true;
  const name = document.querySelector("#workspace-name").value;
  const response = await fetch(`/api/clients/${client.id}/rename`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const body = await response.json();
  if (!response.ok) {
    renameError.textContent = body.error || "Could not rename that workspace.";
    renameError.hidden = false;
    return;
  }
  replaceClient(body);
  render();
});

document.querySelector("#new-project").addEventListener("submit", async (event) => {
  event.preventDefault();
  const client = selected();
  const input = document.querySelector("#project-name");
  if (!client) return;
  projectError.hidden = true;
  const response = await fetch(`/api/clients/${client.id}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: input.value }),
  });
  const body = await response.json();
  if (!response.ok) {
    projectError.textContent = body.error || "Could not add that project.";
    projectError.hidden = false;
    return;
  }
  input.value = "";
  client.projects = [...(client.projects || []), body];
  render();
});

projectList.addEventListener("click", (event) => {
  const client = selected();
  if (!client) return;
  const open = event.target.closest("[data-open]");
  const rename = event.target.closest("[data-rename]");
  const remove = event.target.closest("[data-delete]");
  const save = event.target.closest("[data-save-name]");
  if (open) go(`/clients/${client.id}/projects/${open.dataset.open}`);
  if (rename) {
    const card = rename.closest(".project-card");
    card.querySelector(".card-rename").hidden = false;
    card.querySelector("input").focus();
  }
  if (save) saveProjectName(client, save.dataset.saveName);
  if (remove) removeProject(client, remove.dataset.delete);
});

document.querySelector("#composer").addEventListener("submit", (event) => {
  event.preventDefault();
  const prompt = document.querySelector("#prompt");
  const text = prompt.value.trim();
  const client = selected();
  const project = selectedProject();
  if (!text || !client || !project || state.running) return;
  prompt.value = "";
  runAgent(client, project, text);
});

document.querySelector("#prompt").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    document.querySelector("#composer").requestSubmit();
  }
});

document.querySelector("#reload").addEventListener("click", () => {
  const project = selectedProject();
  if (project) setPreview(project, true);
});

document.querySelector("#width-desktop").addEventListener("click", () => setWidth("desktop"));
document.querySelector("#width-mobile").addEventListener("click", () => setWidth("mobile"));

list.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-id]");
  if (!button) return;
  go(`/clients/${button.dataset.id}`);
});

document.addEventListener("click", (event) => {
  const link = event.target.closest("a[data-nav]");
  if (!link) return;
  event.preventDefault();
  go(link.getAttribute("href"));
});

window.addEventListener("popstate", () => render());

function readRoute() {
  const parts = location.pathname.split("/").filter(Boolean);
  if (parts[0] !== "clients" || !slug.test(parts[1] || "")) return { screen: "home" };
  if (parts.length === 2) return { screen: "workspace", clientId: parts[1] };
  if (parts.length === 3 && parts[2] === "projects") return { screen: "projects", clientId: parts[1] };
  if (parts.length === 4 && parts[2] === "projects" && slug.test(parts[3])) {
    return { screen: "editor", clientId: parts[1], projectId: parts[3] };
  }
  return { screen: "missing", clientId: parts[1] };
}

function go(path) {
  history.pushState({}, "", path);
  window.scrollTo(0, 0);
  render();
}

async function loadClients() {
  const response = await fetch("/api/clients");
  state.clients = await response.json();
  render();
}

function selected() {
  return state.clients.find((client) => client.id === state.route.clientId) || null;
}

function selectedProject() {
  const client = selected();
  if (!client || !state.route.projectId) return null;
  return (client.projects || []).find((project) => project.id === state.route.projectId) || null;
}

function replaceClient(client) {
  const index = state.clients.findIndex((item) => item.id === client.id);
  if (index >= 0) state.clients[index] = client;
}

function render() {
  state.route = readRoute();
  const screen = state.route.screen;
  home.hidden = screen !== "home";
  workspace.hidden = screen !== "workspace" && screen !== "missing";
  projectsScreen.hidden = screen !== "projects";
  editor.hidden = screen !== "editor";
  document.title = "Studio";

  list.replaceChildren();
  for (const client of state.clients) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.id = client.id;
    const name = document.createElement("span");
    name.textContent = client.name;
    const meta = document.createElement("small");
    meta.textContent = client.workspace;
    button.append(name, meta);
    item.append(button);
    list.append(item);
  }
  homeEmpty.hidden = state.clients.length > 0;

  if (screen === "home") return;
  const client = selected();
  if (screen === "missing") renderWorkspace(null);
  if (screen === "workspace") renderWorkspace(client);
  if (screen === "projects") renderProjectScreen(client);
  if (screen === "editor") renderEditor(client);
}

function renderWorkspace(client) {
  const found = Boolean(client);
  document.querySelector("#rename-form").hidden = !found;
  document.querySelector("#open-projects").hidden = !found;
  pathLabel.hidden = !found;
  document.querySelector("#workspace-missing").hidden = found;
  if (!client) {
    title.textContent = "Missing workspace";
    return;
  }
  document.title = client.name;
  title.textContent = client.name;
  pathLabel.textContent = client.workspace;
  document.querySelector("#workspace-name").value = client.name;
  document.querySelector("#open-projects").href = `/clients/${client.id}/projects`;
}

function renderProjectScreen(client) {
  const found = Boolean(client);
  document.querySelector("#new-project").hidden = !found;
  projectList.hidden = !found;
  projectsEmpty.hidden = !found;
  document.querySelector("#projects-title").hidden = !found;
  document.querySelector("#projects-missing").hidden = found;
  document.querySelector("#projects-back").href = client ? `/clients/${client.id}` : "/";
  if (!client) {
    document.querySelector("#projects-title").textContent = "Missing workspace";
    return;
  }
  document.title = client.name;
  document.querySelector("#projects-title").textContent = client.name;
  const projects = client.projects || [];
  projectsEmpty.hidden = projects.length > 0;
  projectList.replaceChildren();
  for (const project of projects) {
    projectList.append(projectCard(project));
  }
}

function projectCard(project) {
  const card = document.createElement("article");
  card.className = "project-card";
  const opener = document.createElement("button");
  opener.type = "button";
  opener.className = "card-open";
  opener.dataset.open = project.id;
  const frame = document.createElement("div");
  frame.className = "mini";
  const iframe = document.createElement("iframe");
  iframe.src = project.preview_url;
  iframe.title = `${project.name} preview`;
  iframe.tabIndex = -1;
  frame.append(iframe);
  const heading = document.createElement("h2");
  heading.textContent = project.name;
  opener.append(frame, heading);
  const actions = document.createElement("div");
  actions.className = "card-actions";
  actions.append(
    button("Rename", { "data-rename": project.id, class: "quiet" }),
    button("Delete", { "data-delete": project.id, class: "quiet" }),
  );
  const rename = document.createElement("form");
  rename.className = "card-rename";
  rename.hidden = true;
  rename.addEventListener("submit", (event) => event.preventDefault());
  const input = document.createElement("input");
  input.value = project.name;
  input.maxLength = 80;
  input.setAttribute("aria-label", `New name for ${project.name}`);
  const save = button("Save", { "data-save-name": project.id });
  rename.append(input, save);
  card.append(opener, actions, rename);
  return card;
}

function button(label, attrs) {
  const element = document.createElement("button");
  element.type = "button";
  element.textContent = label;
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") element.className = value;
    else element.setAttribute(key, value);
  }
  return element;
}

async function saveProjectName(client, projectId) {
  const card = projectList.querySelector(`[data-save-name="${CSS.escape(projectId)}"]`)?.closest(".project-card");
  const name = card?.querySelector("input")?.value || "";
  projectError.hidden = true;
  const response = await fetch(`/api/clients/${client.id}/projects/${projectId}/rename`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const body = await response.json();
  if (!response.ok) {
    projectError.textContent = body.error || "Could not rename that project.";
    projectError.hidden = false;
    return;
  }
  client.projects = (client.projects || []).map((project) => (project.id === projectId ? body : project));
  render();
}

async function removeProject(client, projectId) {
  const project = (client.projects || []).find((item) => item.id === projectId);
  if (!project || !window.confirm(`Delete ${project.name}?`)) return;
  projectError.hidden = true;
  const response = await fetch(`/api/clients/${client.id}/projects/${projectId}/delete`, { method: "POST" });
  const body = await response.json();
  if (!response.ok) {
    projectError.textContent = body.error || "Could not delete that project.";
    projectError.hidden = false;
    return;
  }
  replaceClient(body);
  render();
}

function renderEditor(client) {
  const project = selectedProject();
  const found = Boolean(client && project);
  document.querySelector("#editor-missing").hidden = found;
  workspaceBody.hidden = !found;
  document.querySelector("#editor-back").href = client ? `/clients/${client.id}/projects` : "/";
  document.querySelector("#editor-missing-back").href = client ? `/clients/${client.id}/projects` : "/";
  if (!found) {
    document.querySelector("#editor-title").textContent = "Missing project";
    document.querySelector("#editor-path").textContent = "";
    return;
  }
  document.title = project.name;
  document.querySelector("#editor-title").textContent = project.name;
  document.querySelector("#editor-path").textContent = `${client.name} / ${project.name}`;
  renderMessages(client.id, project.id);
  setPreview(project, false);
  setWidth(state.width);
}

function renderMessages(clientId, projectId) {
  const thread = loadThread(clientId, projectId);
  messages.replaceChildren();
  if (!thread.length) {
    const note = document.createElement("p");
    note.className = "placeholder";
    note.textContent = "Tell the agent what to build. It only changes this project.";
    messages.append(note);
    return;
  }
  for (const message of thread) {
    const bubble = document.createElement("p");
    bubble.className = `bubble ${message.role}`;
    bubble.textContent = message.text;
    messages.append(bubble);
  }
  messages.scrollTop = messages.scrollHeight;
}

function setPreview(project, reload) {
  const url = project.preview_url;
  previewUrl.textContent = url;
  preview.title = `${project.name} preview`;
  const next = reload ? `${url}?t=${Date.now()}` : url;
  if (preview.getAttribute("src") !== next) preview.src = next;
}

function setWidth(width) {
  state.width = width;
  frameWrap.classList.toggle("mobile", width === "mobile");
  document.querySelector("#width-desktop").setAttribute("aria-pressed", String(width === "desktop"));
  document.querySelector("#width-mobile").setAttribute("aria-pressed", String(width === "mobile"));
}

function loadThread(clientId, projectId) {
  try {
    return JSON.parse(localStorage.getItem(threadKey(clientId, projectId)) || "[]");
  } catch {
    return [];
  }
}

function saveThread(clientId, projectId, thread) {
  localStorage.setItem(threadKey(clientId, projectId), JSON.stringify(thread));
}

function threadKey(clientId, projectId) {
  return `studio-thread:${clientId}:${projectId}`;
}

async function runAgent(client, project, text) {
  const thread = loadThread(client.id, project.id);
  thread.push({ role: "user", text });
  saveThread(client.id, project.id, thread);
  if (selected()?.id === client.id && selectedProject()?.id === project.id) {
    renderMessages(client.id, project.id);
  }
  setBusy(true);
  try {
    const response = await fetch(`/api/clients/${client.id}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, project: project.id }),
    });
    if (!response.ok) {
      const body = await response.json();
      pushMessage(client.id, project.id, { role: "error", text: body.error || "The agent failed." });
      return;
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        const event = JSON.parse(line);
        if (event.type === "done") continue;
        const role = event.type === "assistant" ? "assistant" : event.type === "error" ? "error" : "status";
        pushMessage(client.id, project.id, { role, text: event.text || "" });
        if (
          event.type === "tool"
          && /write_file|edit_file/.test(event.text || "")
          && selected()?.id === client.id
          && selectedProject()?.id === project.id
        ) {
          setPreview(project, true);
        }
      }
    }
    if (selected()?.id === client.id && selectedProject()?.id === project.id) setPreview(project, true);
  } catch (err) {
    pushMessage(client.id, project.id, { role: "error", text: "The agent stopped before it finished." });
  } finally {
    setBusy(false);
  }
}

function pushMessage(clientId, projectId, message) {
  const thread = loadThread(clientId, projectId);
  thread.push(message);
  saveThread(clientId, projectId, thread);
  if (selected()?.id === clientId && selectedProject()?.id === projectId) renderMessages(clientId, projectId);
}

function setBusy(busy) {
  state.running = busy;
  document.querySelector("#prompt").disabled = busy;
  const button = document.querySelector("#composer button");
  button.disabled = busy;
  button.textContent = busy ? "Working" : "Send";
}

loadClients();
