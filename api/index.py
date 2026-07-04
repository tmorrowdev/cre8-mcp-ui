"""
Vercel serverless entrypoint for the cre8-mcp-ui MCP Apps server.

Vercel's Python runtime serves the module-level ``app`` ASGI application. We
build the FastMCP server's Streamable HTTP app in **stateless** mode (each
request is self-contained — no server-side session state to pin to a single
warm lambda) and wrap it in permissive CORS so browser-based MCP Apps hosts
can reach it cross-origin.

The MCP endpoint is exposed at ``/mcp`` — connect a host to
``https://<deployment>/mcp`` and it will discover ``show_contact_form`` and
render the ``ui://cre8-mcp-ui/contact-form`` MCP App resource in a sandboxed
iframe.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# The repo root (which holds server.py and the cre8_mcp_ui package) is one level
# up from this api/ directory. Ensure it is importable inside the lambda bundle.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

os.environ.setdefault("MCP_TRANSPORT", "streamable-http")

from starlette.middleware.cors import CORSMiddleware  # noqa: E402

from server import mcp  # noqa: E402

# Stateless HTTP: no per-connection session kept in memory, so any lambda
# invocation can serve any request — the right model for serverless.
mcp.settings.stateless_http = True

_asgi = mcp.streamable_http_app()
_asgi.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["mcp-session-id", "Mcp-Session-Id"],
)

# Vercel's @vercel/python runtime looks for a module-level ASGI/WSGI callable
# named ``app``.
app = _asgi
