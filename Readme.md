# 🛠️ Coding Agent

An autonomous coding agent that **writes, runs, and fixes code** for you.
Built with **LangGraph** (ReAct-style tool-calling agent), supports both
**Groq** and **Google Gemini** as the LLM backend, and ships with a clean
**Streamlit** chat UI.

The agent works inside a sandboxed `workspace/` folder — it can list,
read, write, and delete files there, run Python scripts, and run shell
commands (installing packages, running tests, etc.), but it can never
touch anything outside that folder.

## Project structure

```
coding-agent/
├── pyproject.toml            # dependencies (managed by uv)
├── .env.example               # copy to .env and add your API keys
├── .gitignore
├── app.py                     # Streamlit UI — the entry point
├── workspace/                  # sandbox — the agent's files live here
└── src/
    └── coding_agent/
        ├── __init__.py
        ├── config.py           # env vars, workspace path, model discovery
        ├── tools.py            # sandboxed file + code-execution tools
        ├── prompts.py          # system prompt
        └── agent.py            # builds the LangGraph agent
```

## 1. Prerequisites

- Python 3.10+
- [`uv`](https://docs.astral.sh/uv/) installed:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
  (or `pip install uv`)
- A **Groq** API key — free at https://console.groq.com/keys
- A **Google** API key — free at https://aistudio.google.com/apikey

You only strictly need one of the two keys, but the app supports switching
between providers live from the sidebar if you have both.

## 2. Setup

```bash
# from inside the coding-agent/ folder
cp .env.example .env
```

Open `.env` and paste in your keys:

```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
GOOGLE_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxx
```

Install dependencies (uv creates a `.venv` automatically):

```bash
uv sync
```

## 3. Run it

```bash
uv run streamlit run app.py
```

Streamlit will print a local URL (usually `http://localhost:8501`) —
open it in your browser.

## 4. Using the agent

- Pick **Groq** or **Google** in the sidebar, and a model (the list is
  fetched live from the provider's API — no need to keep this code updated
  as new models ship).
- Type requests in the chat box, e.g.:
  - "Write a Python function that checks if a string is a palindrome, and
    a few test cases, then run the tests."
  - "Create a Flask app with a `/health` endpoint, then run it briefly to
    make sure it starts without errors."
  - "There's a bug in `main.py` — read it, find the bug, and fix it."
- Watch the sidebar's **Workspace** panel — every file the agent creates
  shows up there, with a preview and a download button.
- Tool calls (file reads/writes, commands run) show up as collapsible
  "🔧" expanders in the chat so you can see exactly what the agent did.
- Click **New conversation** in the sidebar to reset the chat history
  (this does not delete workspace files).

## 5. How it works

- `tools.py` defines LangChain `@tool` functions (`list_files`,
  `read_file`, `write_file`, `delete_path`, `run_python_file`,
  `run_shell_command`), each of which resolves paths against
  `workspace/` and refuses anything that resolves outside it.
- `agent.py` uses `langgraph.prebuilt.create_react_agent` to wire the
  chosen chat model (`ChatGroq` or `ChatGoogleGenerativeAI`) up to those
  tools, with a `MemorySaver` checkpointer so each chat session
  (`thread_id`) keeps its own conversation memory.
- `app.py` streams the agent's steps (`agent.stream(..., stream_mode="values")`)
  and renders assistant text, tool calls, and tool results live in the
  Streamlit chat.

## 6. Customizing

- **Change the agent's behavior**: edit `SYSTEM_PROMPT` in `prompts.py`.
- **Add a new tool**: write a new `@tool`-decorated function in `tools.py`
  and add it to `ALL_TOOLS`.
- **Change the execution timeout**: edit `RUN_TIMEOUT_SECONDS` in
  `tools.py` (default 30s).
- **Add another provider**: extend `get_llm()` in `agent.py`.

## Notes on safety

- The `run_shell_command` tool can run arbitrary shell commands (e.g. to
  install packages or run tests), but only inside the `workspace/`
  directory, with a 30-second timeout. Don't expose this app on the
  public internet without adding your own authentication/sandboxing —
  it's designed for local, single-user use.
