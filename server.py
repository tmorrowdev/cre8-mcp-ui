"""
cre8-mcp-ui — a Python FastMCP server that serves @tmorrow/cre8-wc components as
interactive UI under the MCP Apps extension (SEP-1865), so hosts like Claude
Desktop render them as sandboxed, interactive iframes instead of raw HTML.

Built with the `cre8-mcp-ui` skill, migrated from classic mcp-ui to MCP Apps:
  - the UI is a real `ui://` *resource* (mimeType text/html;profile=mcp-app)
  - `show_contact_form` references it via `_meta.ui.resourceUri`; the host fetches
    and renders the resource in a sandboxed iframe
  - the page shell loads the @modelcontextprotocol/ext-apps SDK, performs the
    `ui/initialize` handshake, and routes `data-cre8-action` clicks to
    `app.callServerTool(...)` over the MCP Apps JSON-RPC postMessage channel
  - `save_contact` / `list_contacts` are plain data tools the app calls back into

Data-communication loop (a contact book):
  1. host calls `show_contact_form`  → host renders the contact-form resource
  2. on load the app calls `list_contacts` → renders existing contacts
  3. user submits → app calls `save_contact(...)` → app re-calls `list_contacts`
     → the rendered list updates in place

Run (stdio, default — Claude Desktop and other desktop MCP clients):
    pip install -e .
    python server.py

Run (Streamable HTTP + CORS — for the local MCP Apps host in harness/):
    MCP_TRANSPORT=streamable-http MCP_PORT=3001 python server.py
    # serves http://localhost:3001/mcp

Run (SSE — legacy web hosts):
    MCP_TRANSPORT=sse MCP_HOST=0.0.0.0 MCP_PORT=8000 python server.py
"""

from __future__ import annotations

import json
import os

from mcp import types
from mcp.server.fastmcp import FastMCP

from cre8_mcp_ui import (
    APP_MIME_TYPE,
    app_csp_meta,
    app_tool_meta,
    render_app_page_from_schema,
)

mcp = FastMCP("cre8-mcp-ui")


def _advertise_ui_extension(server: FastMCP) -> None:
    """Declare the MCP Apps UI extension in the `initialize` capabilities.

    A host inspects the server's capabilities before deciding whether to fetch
    and render `ui://` resources; if the `io.modelcontextprotocol/ui` extension
    is absent it can skip `resources/read` entirely and nothing renders. FastMCP
    builds capabilities automatically and exposes no hook for extensions, so we
    wrap the low-level server's `create_initialization_options` and attach the
    extension to the (extra-allowing) ServerCapabilities model.
    """
    low = server._mcp_server
    original = low.create_initialization_options
    extension = {"io.modelcontextprotocol/ui": {"mimeTypes": [APP_MIME_TYPE]}}

    def with_ui_extension(*args, **kwargs):
        opts = original(*args, **kwargs)
        opts.capabilities = opts.capabilities.model_copy(
            update={"extensions": extension}
        )
        return opts

    low.create_initialization_options = with_ui_extension


_advertise_ui_extension(mcp)

# In-memory store for the demo. Swap for Supabase / your persistence layer.
_CONTACTS: list[dict] = []

SERVER = "cre8-mcp-ui"
CONTACT_FORM_URI = f"ui://{SERVER}/contact-form"


def _json_content(obj: dict) -> list[types.TextContent]:
    """Return a JSON payload the app reads via result.content[0].text."""
    return [types.TextContent(type="text", text=json.dumps(obj))]


# ──────────────────────────────────────────────────────────────────────
# UI resource — the MCP App the host renders in a sandboxed iframe
# ──────────────────────────────────────────────────────────────────────

def _contact_form_schema() -> dict:
    """cre8-a2ui schema: contact form + a list region that hydrates on load.

    The submit button declares its callback tool via `events`, plus refresh/
    target/reset hints the MCP Apps shell uses to re-query and re-render the
    contact list after a successful save. The list container declares an
    `onload` hook so existing contacts render as soon as the iframe connects.
    """
    return {
        "schema": "cre8-a2ui/1.0",
        "target": "web-components",
        "root": {
            "component": "div",
            "slots": {
                "default": [
                    {
                        "component": "cre8-card",
                        "slots": {
                            "header": [
                                {"component": "h2", "slots": {"default": [{"text": "Add a contact"}]}}
                            ],
                            # cre8-card's template is <slot name="header">, <slot>
                            # (default = body), <slot name="footer"> — body content
                            # goes in the DEFAULT slot; there is no "body" slot.
                            "default": [
                                {
                                    # data-cre8-form-scope marks the subtree whose
                                    # [name] fields are collected on submit.
                                    "component": "div",
                                    "props": {"data-cre8-form-scope": True},
                                    "slots": {
                                        "default": [
                                            # cre8-wc 2.x unifies text inputs under
                                            # <cre8-field> (cre8-input/-textarea were
                                            # removed). label/name/type/value/required
                                            # are attributes; value is a readable prop.
                                            {
                                                "component": "cre8-field",
                                                "props": {
                                                    "name": "name",
                                                    "label": "Full name",
                                                    "required": True,
                                                },
                                            },
                                            {
                                                "component": "cre8-field",
                                                "props": {
                                                    "name": "email",
                                                    "label": "Email",
                                                    "type": "email",
                                                    "required": True,
                                                },
                                            },
                                            {
                                                "component": "cre8-field",
                                                "props": {"name": "notes", "label": "Notes"},
                                            },
                                            {
                                                "component": "cre8-button",
                                                "props": {
                                                    "variant": "primary",
                                                    # 2.x cre8-button takes its label
                                                    # from the `text` attribute.
                                                    "text": "Save contact",
                                                    "type": "button",
                                                    "data-cre8-refresh": "tool:list_contacts",
                                                    "data-cre8-target": "#cre8-contacts",
                                                    "data-cre8-reset": True,
                                                },
                                                "events": {
                                                    "click": {"type": "tool", "toolName": "save_contact"}
                                                },
                                            },
                                        ]
                                    },
                                }
                            ],
                        },
                    },
                    {
                        # Hydrates on connect and after each save via the shell's
                        # onload / refresh hooks.
                        "component": "cre8-list",
                        "props": {
                            "id": "cre8-contacts",
                            "data-cre8-onload": "tool:list_contacts",
                            "data-cre8-target": "#cre8-contacts",
                        },
                    },
                ]
            },
        },
    }


@mcp.resource(
    CONTACT_FORM_URI,
    mime_type="text/html;profile=mcp-app",
    meta=app_csp_meta(),
)
def contact_form_view() -> str:
    """The contact-form MCP App (HTML served to the host's sandboxed iframe)."""
    return render_app_page_from_schema(
        _contact_form_schema(),
        title="Add a contact",
        app_name=SERVER,
    )


# ──────────────────────────────────────────────────────────────────────
# Tools
# ──────────────────────────────────────────────────────────────────────

@mcp.tool(meta=app_tool_meta(CONTACT_FORM_URI))
def show_contact_form() -> list[types.TextContent]:
    """Show an interactive cre8-wc contact form.

    Links to the `ui://cre8-mcp-ui/contact-form` resource via `_meta.ui`; the
    host renders that resource as a sandboxed iframe. Submitting calls
    `save_contact` and the list refreshes in place.
    """
    return [
        types.TextContent(
            type="text",
            text="Showing the contact form. Fill it in and click “Save contact”.",
        )
    ]


@mcp.tool(meta={"ui": {"visibility": ["model", "app"]}})
def save_contact(name: str, email: str, notes: str = "") -> list[types.TextContent]:
    """Persist a contact. Called by the contact-form app via callServerTool."""
    record = {
        "id": f"contact-{len(_CONTACTS) + 1}",
        "name": name,
        "email": email,
        "notes": notes,
    }
    _CONTACTS.append(record)
    return _json_content({"ok": True, "contact": record, "count": len(_CONTACTS)})


@mcp.tool(meta={"ui": {"visibility": ["model", "app"]}})
def list_contacts() -> list[types.TextContent]:
    """Read the saved contacts back. Called by the app to render the list."""
    return _json_content({"contacts": _CONTACTS})


def _run_http_with_cors(host: str, port: int) -> None:
    """Serve over Streamable HTTP with permissive CORS.

    A browser-based MCP Apps host (the local harness in ``harness/``) cannot use
    stdio and makes cross-origin requests, so it needs CORS and a stateless
    transport. Mirrors the official ext-apps ``say-server`` pattern.
    """
    import uvicorn
    from starlette.middleware.cors import CORSMiddleware

    mcp.settings.stateless_http = True
    app = mcp.streamable_http_app()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["mcp-session-id", "Mcp-Session-Id"],
    )
    uvicorn.run(app, host=host, port=port)


def main() -> None:
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport in ("sse", "streamable-http", "http"):
        host = os.environ.get("MCP_HOST", "127.0.0.1")
        # Default 3001 to match the harness's basic-host SERVERS default.
        port = int(os.environ.get("MCP_PORT", "3001"))
        mcp.settings.host = host
        mcp.settings.port = port
        if transport == "sse":
            mcp.run(transport="sse")
        else:
            _run_http_with_cors(host, port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
