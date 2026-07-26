# Contributing to AgentForge

Thanks for your interest in making AgentForge better! This is a small project, so the bar is low and the welcome is warm.

## 🚀 Quick Contribute

1. **Fork** the repo and create your branch: `git checkout -b feat/my-feature`
2. **Install** in dev mode: `pip install -e ".[dev]"`
3. **Make your change.** Keep the core dependency-free and readable.
4. **Test it:** `pytest` (and `ruff check .`)
5. **Commit** using Conventional Commits: `feat: add streaming support`
6. **Open a PR** describing what and why.

## 🧭 Guidelines

- **Small core.** The agent loop should stay readable in one sitting. Push complexity to optional extras.
- **Provider-agnostic.** Never hard-code an LLM SDK in `agentforge/`. Keep provider code in examples or extras.
- **Type hints everywhere.** Tools depend on them for schema inference.
- **Docs as code.** If you add a feature, update the README and an example.

## 🐛 Reporting Bugs

Open an [issue](https://github.com/shubhranillayek/agentforge/issues) with:
- What you expected
- What happened
- A minimal repro (code + the LLM client you used)

## 💡 Feature Requests

Have an idea? Open an issue with the `enhancement` label. Sketch the API you would want — that is usually the hardest part.

## 📜 Code of Conduct

Be kind. Be clear. Assume good intent. We are building in the open.
