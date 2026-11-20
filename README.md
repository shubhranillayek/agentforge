# AgentForge — Lightweight Python AI Agent Toolkit

AgentForge is an MIT-licensed Python 3.10+ toolkit by [Shubhranil Layek](https://github.com/shubhranillayek) for building tool-using agents. It provides a configurable think → act → observe loop, type-hint-based tool schemas and bounded in-memory conversation history. The core has no required third-party runtime dependencies.

**Status:** version 0.1.0, alpha. You supply the LLM adapter; this is not a hosted model or a guarantee of production readiness.

Built by [Shubhranil Layek](https://shubhranillayek.github.io/) — Python developer working on Telegram bots, automation and AI agents.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-active-success.svg)](#)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](./CONTRIBUTING.md)
[![GitHub stars](https://img.shields.io/github/stars/shubhranillayek/agentforge?style=social)](https://github.com/shubhranillayek/agentforge/stargazers)
[![Made with Python](https://img.shields.io/badge/made%20with-Python-3776AB.svg)](https://www.python.org/)

Define tools with plain type hints, point them at any LLM, and let your agent
**think → act → observe** in a loop until the job is done. No framework lock-in,
no heavy dependencies — a small core you can inspect and extend.

`git clone https://github.com/shubhranillayek/agentforge.git`  ·  [Quick Start](#-quick-start)  ·  [Examples](#-examples)  ·  [Architecture](./docs/architecture.md)

---

## 🌟 Why AgentForge?

Most agent frameworks are heavy, opinionated, and lock you into one provider. AgentForge is the opposite:

- **🪶 Tiny core.** The agent loop is small and explicit. Inspect [`agentforge/core.py`](./agentforge/core.py).
- **🔌 Provider-agnostic.** Bring your own LLM client — Anthropic, OpenAI, Ollama, anything that speaks `(messages, tools) -> str`.
- **🧰 Tools from type hints.** The `@tool` decorator infers the JSON schema your model needs. Zero boilerplate.
- **🧠 Built-in memory.** A bounded conversation buffer retains recent messages. Older messages are dropped when its capacity is reached.
- **🧪 Hackable by design.** An `Agent` is a dataclass with one method. Subclass it, extend it, ship it.

> Think of it as the "hello world" of agentic systems — clear enough to learn from, solid enough to build on.

## 🚀 Quick Start

```bash
git clone https://github.com/shubhranillayek/agentforge.git
cd agentforge
python -m venv .venv
source .venv/bin/activate   # on Windows: .venv\Scripts\activate
pip install -e .
```

**Adapter required:** define `my_llm_client` using the adapter contract below before running this snippet. It is not a built-in client.

```python
from agentforge import Agent, AgentConfig, tool, ToolRegistry

@tool(description="Add two numbers together.")
def add(a: int, b: int) -> int:
    return a + b

agent = Agent(
    name="mathie",
    llm=my_llm_client,                 # any callable: (messages, tools) -> str
    tools=ToolRegistry(add),
    config=AgentConfig(max_steps=6),
)

print(agent.run("What is 7 plus 5?"))  # -> "7 plus 5 is 12."
```

That is the whole API. `@tool` builds the schema, `Agent` runs the loop, and `my_llm_client` is *your* function — no SDK forced on you.

## 🧰 Defining Tools

Type hints become the tool's schema automatically:

```python
@tool(description="Search the web and return the top results.")
def web_search(query: str, max_results: int = 3) -> list[dict]:
    return call_your_search_api(query, max_results)

@tool(description="Fetch the text content of a URL.")
def fetch_page(url: str) -> str:
    return requests.get(url).text
```

The agent then sees:

```json
{
  "name": "web_search",
  "description": "Search the web and return the top results.",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": { "type": "string" },
      "max_results": { "type": "integer", "default": 3 }
    },
    "required": ["query"]
  }
}
```

## 🔌 Wiring Up an LLM

An LLM adapter is a callable with this signature:

```python
def my_llm_client(messages: list[dict], tools: list[dict]) -> str:
    ...
```

The adapter receives the retained conversation messages and tool schemas. It must return either:

- A fenced JSON action block containing `tool` and `args`, to request a registered tool (a bare JSON object with a `tool` key, without the fence, is also accepted); or
- Plain text, to finish the task.

If the adapter itself raises, `run()` does not crash - it returns a string starting with `Error: LLM call failed:`. Invalid JSON in an action block is fed back to the model as an error so it can try again, rather than being shown to the user as the answer.

For example, an action response is:

````text
```json
{"tool": "add", "args": {"a": 7, "b": 5}}
```
````

Provider SDK responses and native tool-call formats must be translated into this contract by your adapter. Optional SDK dependencies in `pyproject.toml` do not provide a complete integration by themselves. Review [`agentforge/core.py`](./agentforge/core.py) for parsing and execution behavior.

## Google Workspace (via MCP)

An agent can also use tools from an MCP server. The bridge in [`agentforge/mcp.py`](./agentforge/mcp.py) starts a server over stdio (standard library only), lists its tools, and wraps them as normal AgentForge tools:

```python
from agentforge.mcp import MCPClient, mcp_registry

with MCPClient(["uvx", "workspace-mcp"]) as client:
    agent = Agent(name="google", llm=my_llm_client, tools=mcp_registry(client))
    print(agent.run("What is on my calendar today?"))
```

Pointed at a Google Workspace MCP server, that gives the agent your Google Calendar, Drive and Docs. [`examples/google_workspace_agent.py`](./examples/google_workspace_agent.py) is a ready example, and [docs/google-workspace.md](./docs/google-workspace.md) walks through the setup - Google Cloud project, APIs, OAuth client, and sign-in. Your Google sign-in and tokens stay with the MCP server on your machine; AgentForge never stores them.

## 📦 Examples

| Example | What it shows |
| --- | --- |
| [`examples/research_agent.py`](./examples/research_agent.py) | A web research loop: search → fetch → summarise |
| [`examples/autonomous_coder.py`](./examples/autonomous_coder.py) | A coding agent with filesystem tools |
| [`examples/google_workspace_agent.py`](./examples/google_workspace_agent.py) | Google Calendar, Drive and Docs through an MCP server (setup in [docs/google-workspace.md](./docs/google-workspace.md)) |

One thing to know about `autonomous_coder.py`: its filesystem tools have no path restrictions, so they can read or write anything the process can reach. That is fine with the stub, but with a real model only run it in a folder you are happy for it to change.

Both ship with a deterministic stub LLM, so they run with **no API keys**:

```bash
python examples/research_agent.py
python examples/autonomous_coder.py
```

## 🏗️ How It Works

```
                            run(task)
                               |
                               v
        +--------+    +----------+    +----------+    +---------+
        | THINK  |--->|   ACT    |--->| OBSERVE  |--->|  DONE?  |
        | (LLM)  |    |  (tool)  |    | (result) |    |         |
        +--------+    +----------+    +----------+    +---------+
            ^                                              |
            +------------------- memory -------------------+
                               (no -> loop)
```

The agent emits a JSON action block `{"tool": "...", "args": {...}}` to call a tool, or plain text when it has the final answer. Steps are recorded in a bounded in-memory buffer, so the model receives the retained conversation history rather than unlimited or persistent memory.

## 📁 Project Structure

```
agentforge/
├── agentforge/
│   ├── __init__.py      # public API
│   ├── core.py          # the Agent loop
│   ├── tools.py         # @tool decorator + schema inference
│   ├── memory.py        # bounded conversation buffer
│   └── mcp.py           # MCP bridge: use tools from any MCP server
├── examples/
│   ├── research_agent.py
│   └── autonomous_coder.py
├── tests/
│   ├── test_agent.py
│   ├── test_mcp.py
│   ├── test_memory.py
│   └── test_tools.py
├── docs/
│   └── architecture.md
├── .github/
│   ├── workflows/       # CI: pytest + ruff on Python 3.10-3.12
│   └── ISSUE_TEMPLATE/
├── pyproject.toml
└── README.md
```

## 🗺️ Roadmap

- [x] Core agent loop (think → act → observe)
- [x] Type-hint-driven tool schemas
- [x] Bounded conversation memory
- [ ] Streaming responses
- [ ] Structured output validation (Pydantic)
- [ ] Multi-agent orchestration
- [ ] Built-in tracing and evals

## Frequently asked questions

### What is this AgentForge project?

This is Shubhranil Layek's Python toolkit at [`shubhranillayek/agentforge`](https://github.com/shubhranillayek/agentforge). It implements a configurable agent loop, registered tools and bounded conversation history.

### Is AgentForge production-ready?

The package metadata classifies version 0.1.0 as alpha. Evaluate adapters, error handling, tool permissions and testing for your use case before a production deployment. Streaming, multi-agent orchestration and built-in tracing remain roadmap items.

### Does the core require an API key?

The core itself does not. A real model-backed adapter may require provider credentials, an SDK and usage fees, depending on the service you choose.

### Is conversation memory persistent?

Not across restarts, but it is kept between `run()` calls on the same agent, so a second call carries on from the earlier conversation. Call `agent.reset()` if you want a clean start. The built-in conversation buffer is bounded and in memory - it retains recent messages and drops older messages at capacity.

## 🤝 Contributing

Contributions are welcome! See [`CONTRIBUTING.md`](./CONTRIBUTING.md) to get started.

```bash
git clone https://github.com/shubhranillayek/agentforge.git
cd agentforge
python -m venv .venv
source .venv/bin/activate   # on Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

## ⭐ Show Your Support

If AgentForge helped you build something, give it a star — it helps the next contributor find it.

[![Star History Chart](https://api.star-history.com/svg?repos=shubhranillayek/agentforge&type=Date)](https://star-history.com/#shubhranillayek/agentforge&Date)

## 📄 License

[MIT](./LICENSE) © Shubhranil Layek
