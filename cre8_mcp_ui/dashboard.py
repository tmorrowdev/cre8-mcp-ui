"""
dashboard — a friendly dashboard DSL the agent produces, expanded into a
cre8-a2ui schema and rendered by the self-contained MCP App shell.

The agent inspects an API response (via the ``fetch_api`` tool) and emits a
compact spec; ``render_dashboard`` encodes it into the resource URI (so the
render is stateless — nothing is stored server-side) and the ``dashboard/{token}``
resource decodes and renders it.

DSL shape::

    {
      "title": "GitHub — octocat",
      "sections": [
        {"type": "stats", "items": [
            {"label": "Followers", "value": "1,234", "status": "success"},
            {"label": "Public repos", "value": "8"}
        ]},
        {"type": "chart", "chartType": "bar", "title": "Stars by repo",
         "labels": ["a", "b", "c"],
         "datasets": [{"label": "Stars", "data": [10, 42, 7]}]},
        {"type": "table", "title": "Repositories",
         "columns": ["Name", "Language", "Stars"],
         "rows": [["hello-world", "C", "1,984"], ["spoon-knife", "HTML", "12k"]]},
        {"type": "list", "title": "Recent activity",
         "items": [{"headline": "Pushed to main", "supporting": "2h ago"}]},
        {"type": "note", "text": "Rate limit: 58/60 remaining", "variant": "warning"}
      ]
    }

``chartType`` is any Chart.js type cre8-chart supports (bar, line, pie,
doughnut, radar, polarArea, scatter, bubble).
"""

from __future__ import annotations

import base64
import json
import zlib
from typing import Any

# ── token codec (spec <-> URL-safe string carried in the resource URI) ────────

def encode_spec(spec: dict[str, Any]) -> str:
    raw = json.dumps(spec, separators=(",", ":")).encode("utf-8")
    packed = zlib.compress(raw, 9)
    return base64.urlsafe_b64encode(packed).decode("ascii")


def decode_spec(token: str) -> dict[str, Any]:
    packed = base64.urlsafe_b64decode(token.encode("ascii"))
    raw = zlib.decompress(packed)
    spec = json.loads(raw)
    if not isinstance(spec, dict):
        raise ValueError("dashboard spec must be a JSON object")
    return spec


# ── DSL section -> cre8-a2ui nodes ────────────────────────────────────────────

def _heading(text: str, htype: str = "title-default") -> dict:
    return {"component": "cre8-heading", "props": {"type": htype},
            "slots": {"default": [{"text": text}]}}


def _card(body: list[dict], header: str | None = None) -> dict:
    slots: dict[str, list] = {"default": body}
    if header:
        slots["header"] = [_heading(header, "title-small")]
    return {"component": "cre8-card", "slots": slots}


def _stats(section: dict) -> dict:
    items = section.get("items", [])
    cards = []
    for item in items:
        inner = [
            _heading(str(item.get("value", "")), "display-small"),
            {"component": "div", "slots": {"default": [{"text": str(item.get("label", ""))}]}},
        ]
        if item.get("status"):
            inner.append({"component": "cre8-badge",
                          "props": {"text": str(item.get("status")), "status": str(item["status"])}})
        cards.append({"component": "cre8-grid-item", "slots": {"default": [_card(inner)]}})
    # Pick a responsive column layout from the number of tiles.
    variant = {1: "side-by-side", 2: "2up", 3: "3up"}.get(len(items), "4up")
    return {"component": "cre8-grid", "props": {"variant": variant, "gap": "lg"},
            "slots": {"default": cards}}


def _table(section: dict) -> dict:
    cols = section.get("columns", [])
    header = {
        "component": "cre8-table-header",
        "slots": {"default": [
            {"component": "cre8-table-header-cell", "slots": {"default": [{"text": str(c)}]}}
            for c in cols
        ]},
    }
    rows = []
    for row in section.get("rows", []):
        rows.append({
            "component": "cre8-table-row",
            "slots": {"default": [
                {"component": "cre8-table-cell", "slots": {"default": [{"text": str(cell)}]}}
                for cell in row
            ]},
        })
    body = {"component": "cre8-table-body", "slots": {"default": rows}}
    table = {"component": "cre8-table", "slots": {"default": [header, body]}}
    return _card([table], section.get("title"))


def _chart(section: dict) -> dict:
    chart = {
        "component": "cre8-chart",
        "props": {
            "type": section.get("chartType", "bar"),
            "height": section.get("height", 320),
            "aria-label": section.get("title", "Chart"),
        },
        # data is an attribute:false JS property -> delivered via data-cre8-props.
        "properties": {
            "data": {
                "labels": section.get("labels", []),
                "datasets": section.get("datasets", []),
            }
        },
    }
    if section.get("options"):
        chart["properties"]["options"] = section["options"]
    return _card([chart], section.get("title"))


def _list(section: dict) -> dict:
    items = []
    for it in section.get("items", []):
        headline = str(it.get("headline", ""))
        supporting = str(it.get("supporting", ""))
        content: list[dict] = [{"component": "strong", "slots": {"default": [{"text": headline}]}}]
        if supporting:
            content.append({"text": " — " + supporting})
        items.append({"component": "cre8-list-item", "slots": {"default": content}})
    return _card([{"component": "cre8-list", "slots": {"default": items}}], section.get("title"))


def _note(section: dict) -> dict:
    # cre8-inline-alert colour comes from `status` (info/success/warning/error/
    # neutral/attention/help); `variant` is only subtle/transparent. Accept either
    # "status" or "variant" from the DSL for the colour, defaulting to info.
    status = section.get("status") or section.get("variant") or "info"
    return {
        "component": "cre8-inline-alert",
        "props": {"status": str(status)},
        "slots": {"default": [{"text": str(section.get("text", ""))}]},
    }


_SECTION_BUILDERS = {
    "stats": _stats,
    "table": _table,
    "chart": _chart,
    "list": _list,
    "note": _note,
}


def spec_to_schema(spec: dict[str, Any]) -> dict[str, Any]:
    """Expand a dashboard DSL spec into a cre8-a2ui schema."""
    children: list[dict] = []
    if spec.get("title"):
        children.append(_heading(str(spec["title"]), "title-large"))
    for section in spec.get("sections", []):
        if not isinstance(section, dict):
            continue
        builder = _SECTION_BUILDERS.get(section.get("type"))
        if builder is None:
            children.append(_note({"text": f"Unknown section type: {section.get('type')!r}",
                                    "variant": "error"}))
            continue
        children.append(builder(section))
    if not children:
        children.append(_note({"text": "Empty dashboard.", "variant": "info"}))
    return {
        "schema": "cre8-a2ui/1.0",
        "target": "web-components",
        "root": {
            "component": "div",
            "props": {"id": "cre8-dashboard"},
            "slots": {"default": children},
        },
    }
