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

## Deploy to Vercel (remote MCP Apps connection)

The repo ships a Vercel Python serverless deployment so the server is reachable
over HTTPS and can be added as a remote MCP connector serving `ui://` resources.

```
api/index.py     # module-level ASGI `app` — FastMCP Streamable HTTP, stateless + CORS
vercel.json      # rewrite all paths to the function; bundle cre8_mcp_ui/assets
requirements.txt # runtime deps (Vercel provides the ASGI server; no uvicorn)
.vercelignore    # excludes the local Node harness + dev artifacts
```

Deploy either way:

```bash
# CLI (from the repo root)
npm i -g vercel
vercel deploy            # preview
vercel deploy --prod     # production
```

…or connect the GitHub repo in the Vercel dashboard and every push deploys.

Once live, the MCP endpoint is:

```
https://<your-deployment>.vercel.app/mcp
```

Add that URL as a **custom / remote MCP connector** in your host (e.g. Claude).
The host discovers `show_contact_form`, fetches the
`ui://cre8-mcp-ui/contact-form` resource (`text/html;profile=mcp-app`), and
renders it in a sandboxed iframe. The deployment runs in **stateless HTTP** mode
(`mcp.settings.stateless_http = True`), which is what serverless needs — but it
also means the in-memory `_CONTACTS` store does not persist across cold starts;
swap it for a real datastore before relying on it in production.

## API dashboard (agent-designed)

A second flow lets the agent turn any API into a dashboard:

1. `show_api_dashboard` → renders an input where the user pastes an endpoint URL.
2. `fetch_api(url)` → the server GETs the endpoint (with an SSRF guard that
   refuses non-public hosts), returns the JSON to the app **and** the model.
3. The agent inspects the data and calls `render_dashboard(spec)` with a compact
   dashboard DSL (`stats` / `chart` / `table` / `list` / `note` sections); the
   `ui://cre8-mcp-ui/dashboard` resource renders it server-side into cre8-wc
   (charts via the bundled `cre8-chart` / Chart.js).

All network calls happen server-side through tools, so the sandboxed iframe
stays fully self-contained. See `cre8_mcp_ui/dashboard.py` for the DSL.

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
