"""
cre8-mcp-ui — a Python FastMCP server that serves @tmorrow/cre8-wc components as
interactive mcp-ui resources, with a real postMessage data-communication loop.

Built with the `cre8-mcp-ui` skill:
  - tools return `list[UIResource]` (ui:// rawHtml, cre8-wc loaded from CDN)
  - the page shell auto-wires `events`/`data-cre8-action` to the host bridge
  - form-scope `[name]` fields are collected and delivered to callback tools

Data-communication loop demonstrated here (a contact book):
  1. host calls `show_contact_form`  → returns a cre8-wc form UI
  2. user submits → shell collects {name,email,notes} → postMessage → host
  3. host invokes `save_contact(...)` (below) → persists, returns the record
  4. host calls `list_contacts`        → reads the data back as a cre8-wc list

Run (stdio, default — desktop MCP clients / Claude Desktop):
    pip install -e .
    python server.py

Run (HTTP/SSE — web hosts such as the cre8-studio workspace):
    MCP_TRANSPORT=sse MCP_HOST=0.0.0.0 MCP_PORT=8000 python server.py
"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP
from mcp_ui_server.core import UIResource

from cre8_mcp_ui import from_schema

mcp = FastMCP("cre8-mcp-ui")

# In-memory store for the demo. Swap for Supabase / your persistence layer.
_CONTACTS: list[dict] = []

SERVER = "cre8-mcp-ui"


@mcp.tool()
def show_contact_form() -> list[UIResource]:
    """Render a cre8-wc contact form. Submit calls save_contact via postMessage."""
    schema = {
        "schema": "cre8-a2ui/1.0",
        "target": "web-components",
        "root": {
            "component": "cre8-card",
            "slots": {
                "header": [
                    {"component": "h2", "slots": {"default": [{"text": "Add a contact"}]}}
                ],
                "default": [
                    {
                        # data-cre8-form-scope marks the subtree whose [name]
                        # fields are collected when the submit button fires.
                        "component": "cre8-form",
                        "props": {"data-cre8-form-scope": True},
                        "slots": {
                            "default": [
                                {
                                    "component": "cre8-input",
                                    "props": {
                                        "name": "name",
                                        "label": "Full name",
                                        "required": True,
                                    },
                                },
                                {
                                    "component": "cre8-input",
                                    "props": {
                                        "name": "email",
                                        "label": "Email",
                                        "type": "email",
                                        "required": True,
                                    },
                                },
                                {
                                    "component": "cre8-textarea",
                                    "props": {"name": "notes", "label": "Notes", "rows": 3},
                                },
                                {
                                    "component": "cre8-button",
                                    "props": {"variant": "primary"},
                                    "events": {
                                        "click": {"type": "tool", "toolName": "save_contact"}
                                    },
                                    "slots": {"default": [{"text": "Save contact"}]},
                                },
                            ]
                        },
                    }
                ],
            },
        },
    }
    return [
        from_schema(
            schema,
            uri=f"ui://{SERVER}/contact-form",
            title="Add contact",
        )
    ]


@mcp.tool()
def save_contact(name: str, email: str, notes: str = "") -> dict:
    """Persist a contact. Called by the form UI via the postMessage bridge."""
    record = {
        "id": f"contact-{len(_CONTACTS) + 1}",
        "name": name,
        "email": email,
        "notes": notes,
    }
    _CONTACTS.append(record)
    return {"ok": True, "contact": record}


@mcp.tool()
def list_contacts() -> list[UIResource]:
    """Read the saved contacts back as a cre8-wc list UI."""
    if _CONTACTS:
        items = [
            {
                "component": "cre8-list-item",
                "props": {"headline": c["name"], "supporting-text": c["email"]},
            }
            for c in _CONTACTS
        ]
    else:
        items = [
            {
                "component": "cre8-empty-state",
                "props": {
                    "headline": "No contacts yet",
                    "description": "Add one with the contact form.",
                },
            }
        ]
    schema = {
        "schema": "cre8-a2ui/1.0",
        "target": "web-components",
        "root": {"component": "cre8-list", "slots": {"default": items}},
    }
    return [
        from_schema(
            schema,
            uri=f"ui://{SERVER}/contacts-{len(_CONTACTS)}",
            title="Contacts",
        )
    ]


def main() -> None:
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport in ("sse", "streamable-http", "http"):
        mcp.settings.host = os.environ.get("MCP_HOST", "127.0.0.1")
        mcp.settings.port = int(os.environ.get("MCP_PORT", "8000"))
        mcp.run(transport="sse" if transport == "sse" else "streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
