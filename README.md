# Solenne

<img width="2300" height="1470" alt="image" src="https://github.com/user-attachments/assets/0fb17540-b324-41b9-92c0-5cac0ac38502" />


A private studio for client work. Each client gets a workspace. Each workspace holds as many projects as you need. Open a project, and a coding agent edits only that folder while you watch the page update beside the chat.

```
Clients  →  Workspace  →  Projects  →  Editor
                                              │
                                         START → agent ⇄ tools → END
```

The agent is a LangGraph loop. It reads the project, changes files, searches the web when a fact has to be current, and runs commands until the task is done. The preview is not a second app. It is `index.html` from the project you have open.

## The rooms

**Clients.** The front door. Add a client and you land in their workspace.

**Workspace.** The title of the account. Rename it here. The folder id stays put, so links you already shared keep working.

**Projects.** A gallery of the work. Every card shows the name, a live miniature of the page, and rename or delete. Add another project when the same client needs a second page, poster, or campaign.

**Editor.** Chat on the left, the site on the right. A question stays in the chat. A request to build or change the page is the only thing that writes files. When a file lands, the iframe reloads.

The sample workspace is **Solenne**, a Los Santos campaign page, at `clients/autobot/`.

## The loop

```
START → agent ⇄ tools → END
```

`agent` sends the thread to the model. If the model calls a file or shell tool, LangGraph runs it and comes back. Web search happens inside the model call and returns with its sources. The loop ends when the model answers without asking for a tool. That last message is the summary you see in the chat.

One compiled graph belongs to one project folder. The tools cannot step outside it. Chat memory for that project stays on its own thread.

## Setup

```bash
cd langgraph-coding-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Put an OpenAI key in `.env`. The default model is `gpt-6-sol`.

```
OPENAI_API_KEY=sk-...
MODEL=openai:gpt-6-sol
```

A local model still works:

```
MODEL=ollama:qwen3.5:9b
```

LangSmith records every run when these are set:

```
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=langgraph-coding-agent
```

## Open the studio

```bash
python -m coding_agent.web
```

Then open http://127.0.0.1:8765.

| You do this | The studio does this |
|---|---|
| Add a client | Creates `clients/<id>/` with a Main project |
| Save the title | Rewrites the display name in `client.json` |
| Add a project | Creates `clients/<id>/projects/<project>/index.html` |
| Open a card | Loads chat and preview for that project only |
| Send a build request | Runs the agent, then reloads the iframe |

## Use it from the terminal

One shot, inside `./workspace`:

```bash
python -m coding_agent "Create a Python script that prints the Fibonacci sequence up to 20 and run it"
```

Or stay in a session:

```bash
python -m coding_agent
```

Point it at another folder with `--workspace /path/to/project`. It will not read or write outside that folder.

## LangGraph dev

```bash
pip install "langgraph-cli[inmem]"
langgraph dev
```

`langgraph.json` registers the graph as `coding_agent`. That server is the API LangSmith drives. The website on port 8765 is separate: it compiles one graph per project and keeps the tools inside that project's directory.

## Tools

| Tool | What it does |
|---|---|
| `list_dir` | List the project |
| `read_file` | Read a file with line numbers |
| `write_file` | Create or replace a file |
| `edit_file` | Replace one unique passage |
| `grep` | Search inside the project |
| `run_command` | Run a shell command there |
| Web search | Look up a current fact before writing it. OpenAI runs this during the model call on GPT-5 and GPT-6. |

Casual chat does not call these. The agent reaches for them when you ask it to create, change, or fix the open project.

## Layout

```
src/coding_agent/
  graph.py        the loop
  studio.py       one agent per project, events for the page
  web.py          the studio server
  clients.py      workspaces, titles, projects
  prompts.py      when to talk, when to edit
  tools/          files and shell
  workspace.py    the sandbox
frontend/         the three screens
clients/          one folder per client
workspace/        the terminal sandbox
```
