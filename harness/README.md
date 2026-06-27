# cre8-mcp-ui — local MCP Apps host harness

A local **MCP Apps (SEP-1865) host** for rendering this server's `show_contact_form`
UI in a sandboxed iframe — without depending on Claude Desktop. Use it to watch the
real migration render and exercise the `save_contact` → `list_contacts` round-trip.

This is the official
[`modelcontextprotocol/ext-apps` `basic-host`](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/basic-host)
example, vendored verbatim. It's built on `@modelcontextprotocol/ext-apps/app-bridge`
(the same bridge family `@mcp-ui/client` wraps): it connects to an MCP server over
Streamable HTTP, reads each tool's `_meta.ui.resourceUri`, fetches the
`text/html;profile=mcp-app` resource, and mounts it in a cross-origin sandboxed
iframe whose CSP headers are built from the resource's `_meta.ui.csp`.

## Prerequisites

- Node 18+ and `bun` (the `serve` script runs `serve.ts` via bun).
- The Python server runnable in Streamable HTTP mode (see repo root).

## Run

**Terminal 1 — the cre8-mcp-ui server over Streamable HTTP + CORS:**

```bash
# from the repo root
MCP_TRANSPORT=streamable-http MCP_PORT=3001 python server.py
# serves http://localhost:3001/mcp  (matches the harness default below)
```

**Terminal 2 — the harness:**

```bash
cd harness
npm install
npm start          # build once, then serve (host :8080, sandbox :8081)
# or: npm run dev   # rebuild-on-change watch mode
```

The harness targets `http://localhost:3001/mcp` by default. To point elsewhere,
set `SERVERS` (see `.env.example`):

```bash
SERVERS='["http://localhost:3001/mcp"]' npm start
```

**Then open:**

```
http://localhost:8080/?server=cre8-mcp-ui&tool=show_contact_form&call=true
```

The query params auto-select the server + tool and invoke it on load.

## What to expect

1. The cre8 contact form renders inside a sandboxed iframe (not a raw-HTML dump).
2. The contacts list hydrates via the form's `data-cre8-onload="tool:list_contacts"`
   hook.
3. Submitting calls `save_contact`, the form clears, and the list refreshes in place
   via the `data-cre8-refresh` hook.
4. The host console logs the AppBridge `ui/initialize` handshake and the proxied
   `tools/call` for `save_contact` / `list_contacts`.

## Troubleshooting

- **Blank iframe / SDK or cre8-wc fails to load:** the sandbox CSP comes from the
  server resource's `_meta.ui.csp`. Widen the domains in
  `cre8_mcp_ui/build_ui_resource.py` (`APP_CSP_RESOURCE_DOMAINS` /
  `APP_CSP_CONNECT_DOMAINS`) — they already include `esm.sh` and `cdn.jsdelivr.net`.
- **Connection refused / CORS error:** confirm the server is running in
  `streamable-http` mode on port 3001 (CORS is enabled only on that path).
- **`bun: command not found`:** install bun (https://bun.sh) or swap the `serve`
  script to `npx tsx serve.ts`.
- **app-bridge API mismatch after `npm install`:** pin to the versions already in
  `package.json` (`@modelcontextprotocol/ext-apps@^1.7.0`, `@modelcontextprotocol/sdk@^1.29.0`).

---

Upstream license/credit: this directory is a vendored copy of the MCP `ext-apps`
`basic-host` example. See the homepage link in `package.json`.
