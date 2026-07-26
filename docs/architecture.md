# Architecture

AgentForge is deliberately tiny. This document explains the moving parts and the contract between them.

## The Agent Loop

An `Agent` is a dataclass with a single public method, `run(task)`:

1. The task is appended to memory as a `user` message.
2. The agent calls the LLM with the full message history plus tool schemas.
3. The LLM response is parsed for a JSON action block:
   - **Found** — the named tool is invoked with `args`; the result is appended to memory as a `tool` message; loop.
   - **Not found** — the response is treated as the final answer; return it.
4. The loop halts at `config.max_steps` to bound runaway agents.

```
memory --> LLM(messages, tools) --> parse --> tool? --yes--> observe --> memory
                                          \--no--> final answer
```

## Components

### `core.py`
Owns the loop and the action-block protocol (`{"tool": ..., "args": ...}`). Subclass `Agent` to customise parsing, tracing, or stopping.

### `tools.py`
The `@tool` decorator inspects a function's signature and type hints and builds a JSON Schema. `ToolRegistry` holds the toolset and exposes `.schemas()` to the LLM.

### `memory.py`
`ConversationBufferMemory` is a bounded, append-only log. Swap it for a summarising or vector-backed memory without touching the loop.

## The LLM Contract

The agent never imports an LLM SDK. It calls `llm(messages, tools) -> str`. This single seam is what makes AgentForge provider-agnostic: implement it for any backend, and the loop is unchanged.

## Extending

- **Streaming:** subclass `Agent` and yield from a `run_stream` method.
- **Structured output:** validate the final answer against a Pydantic model inside `run`.
- **Multi-agent:** compose agents as tools of an orchestrator agent.
