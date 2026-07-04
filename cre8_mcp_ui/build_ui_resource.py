"""
build_ui_resource — helper for wrapping cre8-wc UIs as mcp-ui resources.

Two entry points:

    from cre8_mcp_ui import from_schema, from_html

    # Path A: agent has an A2UI schema
    resource = from_schema(
        schema={"schema": "cre8-a2ui/1.0", "root": {...}},
        uri="ui://my-server/dashboard",
        title="Q4 Dashboard",
    )

    # Path B: agent has an HTML body fragment
    resource = from_html(
        '<cre8-card><h2 slot="header">Hello</h2></cre8-card>',
        uri="ui://my-server/greeting",
    )

Returns a `UIResource` instance ready to include in the `content` list of a
FastMCP tool result. Loads cre8-wc via CDN inside the iframe and wires the
mcp-ui postMessage bridge automatically.

Event binding convention (in schema or HTML):

    data-cre8-action="tool:saveContact"    # calls MCP tool, async by default
    data-cre8-action="prompt"              # injects follow-up into conversation
    data-cre8-action="link"                # asks host to open a URL
    data-cre8-action="notify"              # logs message to host
    data-cre8-action="intent:<name>"       # host-specific intent
    data-cre8-params='{"id":"123"}'        # JSON params, optional
    data-cre8-trigger="change"             # default is "click"

Inside a form scope (cre8-form, <form>, or [data-cre8-form-scope]), all
[name] fields are collected into params automatically — the agent gets
form data for free.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from mcp_ui_server import create_ui_resource

# Path to the page shell asset, resolved relative to this script.
_SHELL_PATH = Path(__file__).parent / "assets" / "page-shell.html"
_SHELL_TEMPLATE: str | None = None

# MCP Apps (SEP-1865) shell — speaks the JSON-RPC-over-postMessage dialect via
# the @modelcontextprotocol/ext-apps SDK so hosts like Claude Desktop render the
# UI in a sandboxed iframe instead of dumping raw HTML.
_APP_SHELL_PATH = Path(__file__).parent / "assets" / "page-shell-mcp-app.html"
_APP_SHELL_TEMPLATE: str | None = None

# Domains the MCP Apps iframe must be allowed to load, declared in the
# resource's _meta.ui.csp: the ext-apps SDK (esm.sh) and cre8-wc (jsdelivr).
APP_CSP_RESOURCE_DOMAINS = ["https://esm.sh", "https://cdn.jsdelivr.net"]
APP_CSP_CONNECT_DOMAINS = ["https://esm.sh", "https://cdn.jsdelivr.net"]
# The exact MIME type the MCP Apps spec requires for a ui:// resource.
APP_MIME_TYPE = "text/html;profile=mcp-app"

# Strict component-name pattern: HTML custom elements must start with a
# lowercase letter and contain a hyphen for cre8-* elements, but we also
# accept built-in tags like div, span, h1-h6, p, ul, li, etc.
_TAG_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_ATTR_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_:.-]*$")


def _load_shell() -> str:
    global _SHELL_TEMPLATE
    if _SHELL_TEMPLATE is None:
        _SHELL_TEMPLATE = _SHELL_PATH.read_text(encoding="utf-8")
    return _SHELL_TEMPLATE


def _load_app_shell() -> str:
    global _APP_SHELL_TEMPLATE
    if _APP_SHELL_TEMPLATE is None:
        _APP_SHELL_TEMPLATE = _APP_SHELL_PATH.read_text(encoding="utf-8")
    return _APP_SHELL_TEMPLATE


# ──────────────────────────────────────────────────────────────────────
# HTML escaping
# ──────────────────────────────────────────────────────────────────────

def _escape_text(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _escape_attr(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
        .replace("<", "&lt;")
    )


# ──────────────────────────────────────────────────────────────────────
# A2UI schema → HTML renderer
#
# Mirrors the JS renderer in the cre8-a2ui skill but runs server-side.
# ──────────────────────────────────────────────────────────────────────

def _events_to_attrs(events: dict[str, Any]) -> list[str]:
    """Translate node['events'] into data-cre8-action attributes."""
    if not events:
        return []
    # Only the first declared event becomes data-cre8-action because the
    # bridge uses a single attribute. Additional events can be added by
    # the caller as raw data-* attrs in props.
    trigger, ev = next(iter(events.items()))
    if not isinstance(ev, dict):
        return []
    ev_type = ev.get("type")
    out: list[str] = []
    if ev_type == "tool":
        tool_name = ev.get("toolName")
        if not tool_name:
            raise ValueError("event type='tool' requires 'toolName'")
        out.append(f'data-cre8-action="tool:{_escape_attr(str(tool_name))}"')
        if ev.get("params"):
            out.append(f"data-cre8-params='{_escape_attr(json.dumps(ev['params']))}' ")
    elif ev_type == "prompt":
        out.append('data-cre8-action="prompt"')
        payload = {}
        if "text" in ev:
            payload["text"] = ev["text"]
        if payload:
            out.append(f"data-cre8-params='{_escape_attr(json.dumps(payload))}'")
    elif ev_type == "link":
        out.append('data-cre8-action="link"')
        if "url" in ev:
            out.append(f"data-cre8-params='{_escape_attr(json.dumps({'url': ev['url']}))}'")
    elif ev_type == "notify":
        out.append('data-cre8-action="notify"')
        if "message" in ev:
            out.append(
                f"data-cre8-params='{_escape_attr(json.dumps({'message': ev['message']}))}'"
            )
    elif ev_type == "intent":
        intent_name = ev.get("intent")
        if not intent_name:
            raise ValueError("event type='intent' requires 'intent'")
        out.append(f'data-cre8-action="intent:{_escape_attr(str(intent_name))}"')
        if ev.get("params"):
            out.append(f"data-cre8-params='{_escape_attr(json.dumps(ev['params']))}'")
    else:
        raise ValueError(f"Unknown event type: {ev_type!r}")
    if trigger != "click":
        out.append(f'data-cre8-trigger="{_escape_attr(trigger)}"')
    return out


def _render_attrs(props: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key, val in props.items():
        if not _ATTR_NAME_RE.match(key):
            raise ValueError(f"Invalid attribute name: {key!r}")
        if val is True:
            out.append(key)
        elif val is False or val is None:
            continue
        else:
            out.append(f'{key}="{_escape_attr(str(val))}"')
    return out


def _inject_slot_attr(html: str, slot_name: str) -> str:
    """Add slot="<name>" to the outermost element of an HTML string."""
    m = re.match(r"^(<[a-z][a-z0-9-]*)(\s|>)", html)
    if m:
        return html[: m.end(1)] + f' slot="{_escape_attr(slot_name)}"' + html[m.end(1):]
    return f'<span slot="{_escape_attr(slot_name)}">{html}</span>'


def _render_node(node: dict[str, Any]) -> str:
    if not isinstance(node, dict):
        raise ValueError(f"Schema node must be a dict, got {type(node).__name__}")
    if "html" in node:
        return str(node["html"])
    if "text" in node:
        return _escape_text(str(node["text"]))

    tag = node.get("component")
    if not tag or not _TAG_RE.match(tag):
        raise ValueError(f"Invalid or missing 'component': {tag!r}")

    attrs = _render_attrs(node.get("props") or {})
    attrs.extend(_events_to_attrs(node.get("events") or {}))

    children_html: list[str] = []
    slots = node.get("slots") or {}
    for slot_name, items in slots.items():
        if not isinstance(items, list):
            items = [items]
        for child in items:
            if not isinstance(child, dict):
                # Treat plain strings as text nodes for convenience.
                if isinstance(child, str):
                    rendered = _escape_text(child)
                    if slot_name != "default":
                        rendered = f'<span slot="{_escape_attr(slot_name)}">{rendered}</span>'
                    children_html.append(rendered)
                continue
            rendered = _render_node(child)
            if slot_name != "default":
                rendered = _inject_slot_attr(rendered, slot_name)
            children_html.append(rendered)

    attrs_str = (" " + " ".join(attrs)) if attrs else ""
    return f"<{tag}{attrs_str}>{''.join(children_html)}</{tag}>"


def render_schema(schema: dict[str, Any]) -> str:
    """Render a cre8-a2ui schema to an HTML body fragment."""
    if not isinstance(schema, dict) or "root" not in schema:
        raise ValueError("schema must be a dict with a 'root' key")
    return _render_node(schema["root"])


# ──────────────────────────────────────────────────────────────────────
# Page-shell wrapping
# ──────────────────────────────────────────────────────────────────────

def wrap_in_shell(
    body_html: str,
    *,
    title: str = "cre8-wc UI",
    theme_css: str = "",
) -> str:
    """Inject a body fragment into the classic mcp-ui page shell (full HTML doc)."""
    shell = _load_shell()
    return (
        shell.replace("{{title}}", _escape_text(title))
        .replace("{{theme_css}}", theme_css)
        .replace("{{body}}", body_html)
    )


# ──────────────────────────────────────────────────────────────────────
# MCP Apps (SEP-1865) page rendering
#
# Unlike the classic path, an MCP App is served as a real `ui://` *resource*
# (mimeType text/html;profile=mcp-app) that the tool references via
# _meta.ui.resourceUri — the host fetches and renders it in a sandboxed iframe.
# These helpers produce the full HTML document and the matching CSP metadata.
# ──────────────────────────────────────────────────────────────────────

def render_app_page(
    body_html: str,
    *,
    title: str = "cre8-wc UI",
    app_name: str = "cre8-mcp-ui",
    theme_css: str = "",
) -> str:
    """Wrap a body fragment in the MCP Apps shell, returning a full HTML doc.

    The result is meant to be returned verbatim from an `@mcp.resource(...)`
    handler registered with `mime_type=APP_MIME_TYPE` and `meta=app_csp_meta()`.
    """
    shell = _load_app_shell()
    return (
        shell.replace("{{title}}", _escape_text(title))
        .replace("{{app_name}}", _escape_attr(app_name))
        .replace("{{theme_css}}", theme_css)
        .replace("{{body}}", body_html)
    )


def render_app_page_from_schema(
    schema: dict[str, Any],
    *,
    title: str = "cre8-wc UI",
    app_name: str = "cre8-mcp-ui",
    theme_css: str = "",
) -> str:
    """Render a cre8-a2ui schema into a full MCP Apps HTML document."""
    return render_app_page(
        render_schema(schema),
        title=title,
        app_name=app_name,
        theme_css=theme_css,
    )


def app_csp_meta(
    *,
    resource_domains: list[str] | None = None,
    connect_domains: list[str] | None = None,
) -> dict[str, Any]:
    """Build the `_meta` dict for an MCP Apps `ui://` resource.

    Returns ``{"ui": {"csp": {...}}}`` — every external origin the iframe loads
    from must be listed here or the host sandbox blocks it.
    """
    return {
        "ui": {
            "csp": {
                "resourceDomains": resource_domains or list(APP_CSP_RESOURCE_DOMAINS),
                "connectDomains": connect_domains or list(APP_CSP_CONNECT_DOMAINS),
            }
        }
    }


def app_tool_meta(
    resource_uri: str,
    *,
    csp: bool = True,
    resource_domains: list[str] | None = None,
    connect_domains: list[str] | None = None,
    prefer_frame: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the tool `_meta` that links a tool to its MCP Apps UI resource.

    Emits both shapes of the association key:
      - ``ui.resourceUri`` — the SEP-1865 nested key (other spec-compliant hosts)
      - ``ui/resourceUri`` — the deprecated flat key claude.ai still requires
        (anthropics/claude-ai-mcp #71). Without it claude.ai never links the tool
        to its resource and renders nothing.

    Also carries the CSP allowlist on the *tool* meta (``ui.csp``) in addition to
    the resource meta, since claude.ai reads the sandbox policy from the tool's
    ``ui`` block. Omit it with ``csp=False`` if you set CSP only on the resource.
    """
    _validate_uri(resource_uri)
    ui: dict[str, Any] = {"resourceUri": resource_uri}
    if csp:
        ui["csp"] = {
            "resourceDomains": resource_domains or list(APP_CSP_RESOURCE_DOMAINS),
            "connectDomains": connect_domains or list(APP_CSP_CONNECT_DOMAINS),
        }
    if prefer_frame:
        ui["preferredFrameSize"] = prefer_frame
    return {
        "ui": ui,                        # spec-compliant (nested)
        "ui/resourceUri": resource_uri,  # deprecated flat key — claude.ai reads THIS
    }


# ──────────────────────────────────────────────────────────────────────
# Public entry points
# ──────────────────────────────────────────────────────────────────────

def _validate_uri(uri: str) -> None:
    if not isinstance(uri, str) or not uri.startswith("ui://"):
        raise ValueError(f"uri must be a string starting with 'ui://' (got: {uri!r})")


def from_html(
    body_html: str,
    *,
    uri: str,
    title: str = "cre8-wc UI",
    theme_css: str = "",
    encoding: str = "text",
) -> Any:
    """Wrap an HTML body fragment in the cre8 page shell. Returns a UIResource."""
    _validate_uri(uri)
    full_html = wrap_in_shell(body_html, title=title, theme_css=theme_css)
    return create_ui_resource(
        {
            "uri": uri,
            "content": {"type": "rawHtml", "htmlString": full_html},
            "encoding": encoding,
        }
    )


def from_schema(
    schema: dict[str, Any],
    *,
    uri: str,
    title: str = "cre8-wc UI",
    theme_css: str = "",
    encoding: str = "text",
) -> Any:
    """Render a cre8-a2ui schema and wrap it. Returns a UIResource."""
    _validate_uri(uri)
    body_html = render_schema(schema)
    return from_html(
        body_html,
        uri=uri,
        title=title,
        theme_css=theme_css,
        encoding=encoding,
    )


__all__ = [
    "from_html",
    "from_schema",
    "render_schema",
    "wrap_in_shell",
    # MCP Apps (SEP-1865)
    "render_app_page",
    "render_app_page_from_schema",
    "app_csp_meta",
    "app_tool_meta",
    "APP_MIME_TYPE",
    "APP_CSP_RESOURCE_DOMAINS",
    "APP_CSP_CONNECT_DOMAINS",
]
