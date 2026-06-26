# cre8-mcp-ui-server

A standalone Python **FastMCP** server that serves [`@tmorrow/cre8-wc`](https://www.npmjs.com/package/@tmorrow/cre8-wc)
components as interactive **mcp-ui** resources, with a real `postMessage`
data-communication loop. Scaffolded with the `cre8-mcp-ui` skill.

Each UI-returning tool returns `list[UIResource]` — a `ui://` resource whose
`rawHtml` loads cre8-wc from CDN and wires the host bridge. The agent never
writes JavaScript: declarative `events` (or `data-cre8-action` attributes) are
auto-wired, and form-scope `[name]` fields are collected and delivered to
callback tools.

## Layout

```
cre8-mcp-ui-server/
├── pyproject.toml            # deps: mcp, mcp-ui-server
├── server.py                 # FastMCP entry point + tools (contact book demo)
└── cre8_mcp_ui/
    ├── __init__.py           # re-exports from_schema, from_html, ...
    ├── build_ui_resource.py  # schema/HTML → UIResource (page-shell wrapper)
    └── assets/
        └── page-shell.html   # cre8-wc CDN + mcp-ui postMessage bridge
```

## Install & run

```bash
cd ~/Projects/cre8-mcp-ui-server
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# stdio (default) — desktop MCP clients / Claude Desktop
python server.py

# HTTP/SSE — web hosts (e.g. the cre8-studio workspace)
MCP_TRANSPORT=sse MCP_HOST=0.0.0.0 MCP_PORT=8000 python server.py
```

## The data-communication loop (contact book demo)

1. Host calls `show_contact_form` → returns a cre8-wc form UI.
2. User submits → the page shell collects `{name, email, notes}` from the form
   scope and `postMessage`s a `tool` action to the host.
3. Host invokes `save_contact(name, email, notes)` → persists, returns the record
   (resolves the in-iframe `Promise`).
4. Host calls `list_contacts` → reads the data back as a cre8-wc list UI.

Swap the in-memory `_CONTACTS` list in `server.py` for Supabase or your own
persistence layer.

## Connecting an MCP host

**Claude Desktop / any stdio MCP client** — add to the client's MCP config:

```json
{
  "mcpServers": {
    "cre8-mcp-ui": {
      "command": "python",
      "args": ["/Users/tylersmbp/Projects/cre8-mcp-ui-server/server.py"]
    }
  }
}
```

**A web host (browser)** — run with `MCP_TRANSPORT=sse` and point the host's
mcp-ui client at `http://<host>:<port>/sse`. The host must render `ui://`
resources in a sandboxed iframe and implement `onUIAction` so `tool` actions
posted by the bridge are invoked and their results posted back as
`ui-message-response` (this resolves the iframe `Promise`).

## Event-binding cheatsheet (in schema `events` or as `data-cre8-action`)

| Action | Schema sugar |
| --- | --- |
| Call a tool | `events: { click: { type: "tool", toolName: "save_contact" } }` |
| Inject a prompt | `events: { click: { type: "prompt", text: "..." } }` |
| Open a link | `events: { click: { type: "link", url: "..." } }` |
| Notify host | `events: { click: { type: "notify", message: "..." } }` |

Wrap inputs in `cre8-form` (or any `[data-cre8-form-scope]`) so their `[name]`
values are collected automatically when the submit button fires.
