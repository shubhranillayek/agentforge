# Google Workspace with AgentForge (Calendar, Drive, Docs)

AgentForge can use your Google Calendar, Drive and Docs through an MCP
server. AgentForge itself does not talk to Google. It starts a separate
program - an MCP server - on your machine, and that server is what signs
in to Google and calls the Google APIs. AgentForge just turns the
server's tools into normal AgentForge tools, using the bridge in
`agentforge/mcp.py`.

The server used in this guide is `workspace-mcp`:

- PyPI package: `workspace-mcp`
- Project: `google_workspace_mcp`
- It covers Gmail, Drive, Docs, Sheets, Calendar and more, with Google
  OAuth sign-in.

You can use a different Google Workspace MCP server if you prefer. The
example reads the server command from an environment variable, so
swapping servers does not need a code change.

One thing to be clear about before you start: your Google credentials
and OAuth tokens live with the MCP server on your machine. Nothing
Google-related is stored in AgentForge or in this repository. Do not
commit OAuth client secrets or token files to any repo.

## What you need

- Python 3.10+ and this repo installed (see the Quick Start in the
  README - use a virtualenv).
- `uv`, which provides the `uvx` command used to run the server.
- A Google account.

No extra Python packages are needed for AgentForge itself: the MCP
bridge in `agentforge/mcp.py` only uses the standard library.

## Step 1: Create a Google Cloud project

1. Go to the Google Cloud Console and create a new project. Any name is
   fine, for example `agentforge-workspace`.
2. In that project, open "APIs & Services" -> "Library" and enable:
   - Google Calendar API
   - Google Drive API
   - Google Docs API
   - Enable Gmail API and Google Sheets API too if you want those tools
     later; the server exposes more than Calendar, Drive and Docs.

## Step 2: Create an OAuth client

1. In the same project, open "APIs & Services" -> "Credentials".
2. If asked, configure the OAuth consent screen first (External, your
   own email as the user and support contact is enough for personal
   use). While the app is in "Testing" mode, add your own Google
   account as a test user, otherwise sign-in will be refused.
3. Create credentials -> "OAuth client ID" -> application type
   **Desktop app**.
4. Note the client ID and client secret. You will pass them to the MCP
   server as environment variables in Step 4. They are yours - do not
   share them and do not put them in code.

## Step 3: Run the MCP server once and sign in

Run the server once on its own, in a terminal:

```bash
uvx workspace-mcp
```

The first run downloads the server and walks you through Google
sign-in in a browser: pick the account, and approve the access the
server asks for (Calendar, Drive, Docs, matching the APIs you
enabled). This creates the OAuth token the server reuses later, stored
by the server on your machine. When it is waiting for connections
instead of asking you anything, sign-in is done - you can stop it with
Ctrl+C.

If your version of the server asks for a tool selection or a transport
flag, the defaults are fine for this guide; the AgentForge bridge
talks to it over stdio, which is the default way `uvx workspace-mcp`
runs when started like this.

## Step 4: Set the environment variables

In the terminal where you will run the example:

```bash
export GOOGLE_OAUTH_CLIENT_ID="your-client-id"
export GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret"
```

Optional: if you want a different server command - another server, or
this one limited to fewer tools - set:

```bash
export GOOGLE_WORKSPACE_MCP_COMMAND="uvx workspace-mcp --tools calendar drive docs"
```

The example defaults to `uvx workspace-mcp` when this is not set.

## Step 5: Run the example

```bash
python examples/google_workspace_agent.py
```

It connects to the server, lists how many tools it got, and runs an
agent with a stub LLM that reports the connection. The stub does not
call any Google tool - it is there so the wiring is easy to check.

To actually use the tools, replace `stub_llm` in
`examples/google_workspace_agent.py` with a real LLM adapter (the
README's "Wiring Up an LLM" section shows the contract), then give the
agent tasks in your own words. Things a real adapter can do with these
tools, once connected:

- "aaj ke calendar events batao" - list today's calendar events
- "Drive me 'report' naam ki file dhoondo" - search Drive for a file
  with "report" in the name
- "is Doc ka summary banao" - read a Doc and summarise it (give the
  agent the document name or ID in the task)

## How it works, briefly

`MCPClient` in `agentforge/mcp.py` starts the server as a subprocess
and speaks MCP (JSON-RPC over stdio) to it: `initialize`, then
`tools/list`, then `tools/call` for each action the model picks.
`mcp_registry(client)` wraps every server tool as an AgentForge `Tool`,
using the server's own `inputSchema` for the parameters, so the agent
loop does not know or care that the tools came from MCP. The same
bridge works with any MCP server, not just the Google one.

## Problems people usually hit

- **Sign-in refused / not a test user:** your OAuth app is in Testing
  mode and your Google account is not listed as a test user. Add it
  under the OAuth consent screen settings.
- **`uvx` not found:** install `uv` first, or set
  `GOOGLE_WORKSPACE_MCP_COMMAND` to however you start the server.
- **The example says an env var is missing:** Step 4 was done in a
  different terminal. Export the variables in the same terminal you
  run the example from.
- **A tool fails with a Google API error:** the API for that service
  is probably not enabled in your Cloud project (Step 1), or the
  sign-in token predates enabling it - run the server once more on
  its own and sign in again.
