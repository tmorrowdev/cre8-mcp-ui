"""
Regression tests for build_ui_resource.

Run from the skill root after installing mcp-ui-server:

    pip install mcp-ui-server
    python scripts/test_build_ui_resource.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from cre8_mcp_ui import build_ui_resource as biu


def test_from_html_basic():
    res = biu.from_html(
        '<cre8-card><h2 slot="header">Hi</h2></cre8-card>',
        uri="ui://test/basic",
        title="Basic",
    )
    dumped = json.loads(res.model_dump_json())
    assert dumped["type"] == "resource"
    assert dumped["resource"]["uri"] == "ui://test/basic"
    assert dumped["resource"]["mimeType"].startswith("text/html")
    body = dumped["resource"]["text"]
    assert "<!doctype html>" in body.lower()
    assert "@tmorrow/cre8-wc" in body
    assert "<cre8-card>" in body
    assert "cre8Bridge" in body
    print("✓ from_html_basic")


def test_from_schema_simple():
    schema = {
        "schema": "cre8-a2ui/1.0",
        "root": {
            "component": "cre8-stat",
            "props": {"label": "Revenue", "value": "$2.4M"},
        },
    }
    res = biu.from_schema(schema, uri="ui://test/stat")
    body = json.loads(res.model_dump_json())["resource"]["text"]
    assert '<cre8-stat label="Revenue" value="$2.4M">' in body
    print("✓ from_schema_simple")


def test_from_schema_with_slots():
    schema = {
        "schema": "cre8-a2ui/1.0",
        "root": {
            "component": "cre8-card",
            "props": {},
            "slots": {
                "header": [{"component": "h2", "slots": {"default": [{"text": "Title"}]}}],
                "default": [{"text": "Body content"}],
            },
        },
    }
    res = biu.from_schema(schema, uri="ui://test/card")
    body = json.loads(res.model_dump_json())["resource"]["text"]
    assert '<h2 slot="header">' in body
    assert "Title" in body
    assert "Body content" in body
    print("✓ from_schema_with_slots")


def test_events_to_tool_action():
    schema = {
        "schema": "cre8-a2ui/1.0",
        "root": {
            "component": "cre8-button",
            "events": {"click": {"type": "tool", "toolName": "save_contact"}},
            "slots": {"default": [{"text": "Save"}]},
        },
    }
    res = biu.from_schema(schema, uri="ui://test/btn")
    body = json.loads(res.model_dump_json())["resource"]["text"]
    assert 'data-cre8-action="tool:save_contact"' in body
    print("✓ events_to_tool_action")


def test_events_with_params():
    schema = {
        "schema": "cre8-a2ui/1.0",
        "root": {
            "component": "cre8-button",
            "events": {"click": {"type": "tool", "toolName": "buy", "params": {"sku": "abc"}}},
            "slots": {"default": [{"text": "Buy"}]},
        },
    }
    res = biu.from_schema(schema, uri="ui://test/buy")
    body = json.loads(res.model_dump_json())["resource"]["text"]
    assert 'data-cre8-action="tool:buy"' in body
    assert "sku" in body
    print("✓ events_with_params")


def test_prompt_event():
    schema = {
        "schema": "cre8-a2ui/1.0",
        "root": {
            "component": "cre8-button",
            "events": {"click": {"type": "prompt", "text": "Tell me more"}},
            "slots": {"default": [{"text": "Ask"}]},
        },
    }
    res = biu.from_schema(schema, uri="ui://test/prompt")
    body = json.loads(res.model_dump_json())["resource"]["text"]
    assert 'data-cre8-action="prompt"' in body
    assert "Tell me more" in body
    print("✓ prompt_event")


def test_invalid_uri():
    try:
        biu.from_html("<p>hi</p>", uri="not-a-ui-uri")
    except ValueError as e:
        assert "ui://" in str(e)
        print("✓ invalid_uri rejected")
        return
    raise AssertionError("expected ValueError for non-ui:// uri")


def test_boolean_attr():
    schema = {
        "schema": "cre8-a2ui/1.0",
        "root": {
            "component": "cre8-input",
            "props": {"required": True, "disabled": False, "name": "email"},
        },
    }
    res = biu.from_schema(schema, uri="ui://test/input")
    body = json.loads(res.model_dump_json())["resource"]["text"]
    assert "<cre8-input " in body
    assert " required" in body and 'required="' not in body
    assert "disabled" not in body
    assert 'name="email"' in body
    print("✓ boolean_attr")


def test_html_escaping():
    res = biu.from_schema(
        {
            "schema": "cre8-a2ui/1.0",
            "root": {
                "component": "p",
                "slots": {"default": [{"text": "<script>alert(1)</script>"}]},
            },
        },
        uri="ui://test/esc",
    )
    body = json.loads(res.model_dump_json())["resource"]["text"]
    assert "<div id=\"cre8-root\"><p><script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
    print("✓ html_escaping")


def test_blob_encoding():
    res = biu.from_html("<p>x</p>", uri="ui://test/blob", encoding="blob")
    dumped = json.loads(res.model_dump_json())
    assert "blob" in dumped["resource"]
    assert "text" not in dumped["resource"]
    print("✓ blob_encoding")


def test_theme_css_injected():
    res = biu.from_html(
        "<p>x</p>",
        uri="ui://test/theme",
        theme_css=":root { --cre8-color-primary: #ff00aa; }",
    )
    body = json.loads(res.model_dump_json())["resource"]["text"]
    assert "--cre8-color-primary: #ff00aa" in body
    assert 'id="cre8-theme-tokens"' in body
    print("✓ theme_css_injected")


def test_invalid_component_name():
    try:
        biu.from_schema(
            {"schema": "cre8-a2ui/1.0", "root": {"component": "BadName"}},
            uri="ui://test/bad",
        )
    except ValueError as e:
        assert "component" in str(e).lower()
        print("✓ invalid_component_name rejected")
        return
    raise AssertionError("expected ValueError for invalid component name")


def main():
    test_from_html_basic()
    test_from_schema_simple()
    test_from_schema_with_slots()
    test_events_to_tool_action()
    test_events_with_params()
    test_prompt_event()
    test_invalid_uri()
    test_boolean_attr()
    test_html_escaping()
    test_blob_encoding()
    test_theme_css_injected()
    test_invalid_component_name()
    print("\nAll tests passed.")


if __name__ == "__main__":
    main()
