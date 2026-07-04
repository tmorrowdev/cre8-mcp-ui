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


def test_render_app_page_shell():
    html = biu.render_app_page(
        '<cre8-card><h2 slot="header">Hi</h2></cre8-card>',
        title="Demo",
        app_name="cre8-mcp-ui",
    )
    assert "<!doctype html>" in html.lower()
    # Self-contained MCP Apps shell: the ext-apps SDK is inlined and exposed on
    # globalThis (no external import), and the bridge still runs the App handshake.
    assert "globalThis.__cre8ExtApps" in html
    assert 'new App({ name: "cre8-mcp-ui"' in html
    # cre8-wc components are inlined (they self-register).
    assert "customElements.define" in html
    assert "<cre8-card>" in html
    # Zero external network references — nothing to be blocked by a host sandbox.
    assert "cdn.jsdelivr" not in html
    assert "esm.sh" not in html
    # Placeholders fully substituted.
    assert "{{body}}" not in html
    assert "{{app_name}}" not in html
    assert "{{title}}" not in html
    print("✓ render_app_page_shell")


def test_render_app_page_from_schema():
    html = biu.render_app_page_from_schema(
        {
            "schema": "cre8-a2ui/1.0",
            "root": {
                "component": "cre8-button",
                "events": {"click": {"type": "tool", "toolName": "save_contact"}},
                "slots": {"default": [{"text": "Save"}]},
            },
        },
        title="Form",
    )
    assert 'data-cre8-action="tool:save_contact"' in html
    assert "callServerTool" in html  # bridge routes actions through MCP Apps
    print("✓ render_app_page_from_schema")


def test_app_mime_type_constant():
    assert biu.APP_MIME_TYPE == "text/html;profile=mcp-app"
    print("✓ app_mime_type_constant")


def test_app_csp_meta():
    meta = biu.app_csp_meta()
    csp = meta["ui"]["csp"]
    assert "https://esm.sh" in csp["resourceDomains"]
    assert "https://cdn.jsdelivr.net" in csp["resourceDomains"]
    # Custom domains override the defaults.
    custom = biu.app_csp_meta(resource_domains=["https://x.dev"])
    assert custom["ui"]["csp"]["resourceDomains"] == ["https://x.dev"]
    print("✓ app_csp_meta")


def test_app_tool_meta():
    meta = biu.app_tool_meta("ui://demo/widget")
    assert meta["ui"]["resourceUri"] == "ui://demo/widget"
    assert meta["ui/resourceUri"] == "ui://demo/widget"  # legacy key claude.ai reads
    # CSP now rides on the tool meta too (claude.ai reads the sandbox policy here).
    assert "https://cdn.jsdelivr.net" in meta["ui"]["csp"]["resourceDomains"]
    assert "https://esm.sh" in meta["ui"]["csp"]["resourceDomains"]
    print("✓ app_tool_meta")


def test_app_tool_meta_csp_optional_and_frame():
    bare = biu.app_tool_meta("ui://demo/widget", csp=False)
    assert "csp" not in bare["ui"]
    sized = biu.app_tool_meta("ui://demo/widget", prefer_frame={"width": 480, "height": 640})
    assert sized["ui"]["preferredFrameSize"] == {"width": 480, "height": 640}
    print("✓ app_tool_meta_csp_optional_and_frame")


def test_contact_form_uses_cre8wc_2x_components():
    import server as srv

    html = srv.contact_form_view()
    # 2.x tags that must be present.
    assert "<cre8-field" in html
    # Card body content lives in the default slot (cre8-card has no "body" slot),
    # so the form-scope wrapper must NOT carry slot="body".
    assert 'slot="body"' not in html
    assert "data-cre8-form-scope" in html
    assert 'text="Save contact"' in html  # button label is an attribute in 2.x
    # Tags removed in the cre8-wc 2.0 migration must not reappear.
    for gone in ("<cre8-input", "<cre8-textarea", "<cre8-form", "<cre8-empty-state"):
        assert gone not in html, f"removed 2.x component leaked back: {gone}"
    print("✓ contact_form_uses_cre8wc_2x_components")


def test_server_advertises_ui_extension():
    import server as srv

    opts = srv.mcp._mcp_server.create_initialization_options()
    caps = opts.capabilities.model_dump(exclude_none=True)
    ext = caps.get("extensions", {})
    assert "io.modelcontextprotocol/ui" in ext
    assert biu.APP_MIME_TYPE in ext["io.modelcontextprotocol/ui"]["mimeTypes"]
    print("✓ server_advertises_ui_extension")


_BRAND_TOKENS_URL = (
    "https://cdn.jsdelivr.net/npm/@tmorrow/cre8-wc@2"
    "/dist/design-tokens/brands/cre8-a2ui/css/tokens_cre8-a2ui.css"
)

# The self-registering CDN bundle — the only cre8-wc entry that actually calls
# customElements.define() for every element. `./lib/index.js` merely re-exports
# classes and `./dist/index.js` does not exist, so neither registers elements.
_CRE8_WC_SCRIPT_URL = "https://cdn.jsdelivr.net/npm/@tmorrow/cre8-wc@2/cdn/cre8-wc.esm.js"


def test_self_registering_bundle_linked_classic_shell():
    body = json.loads(
        biu.from_html("<p>x</p>", uri="ui://test/reg").model_dump_json()
    )["resource"]["text"]
    assert f'src="{_CRE8_WC_SCRIPT_URL}"' in body
    assert 'src="https://cdn.jsdelivr.net/npm/@tmorrow/cre8-wc/dist/index.js"' not in body
    print("✓ self_registering_bundle_linked_classic_shell")


def test_app_shell_is_self_contained():
    """The MCP App shell inlines the SDK, components and tokens — no external URLs."""
    html = biu.render_app_page("<p>x</p>", title="T")
    assert "cdn.jsdelivr" not in html and "esm.sh" not in html  # nothing external
    assert "customElements.define" in html  # cre8-wc components inlined
    assert "globalThis.__cre8ExtApps" in html  # ext-apps SDK inlined
    assert "--cre8-" in html  # design tokens inlined
    print("✓ app_shell_is_self_contained")


def test_brand_tokens_linked_classic_shell():
    body = json.loads(
        biu.from_html("<p>x</p>", uri="ui://test/tok").model_dump_json()
    )["resource"]["text"]
    assert _BRAND_TOKENS_URL in body
    print("✓ brand_tokens_linked_classic_shell")


def test_brand_tokens_inlined_app_shell():
    # The app shell inlines the brand tokens; they precede the per-call theme
    # override block so overrides still win the cascade.
    html = biu.render_app_page("<p>x</p>", title="T")
    assert "--cre8-" in html
    assert html.index("cre8-brand-tokens") < html.index('id="cre8-theme-tokens"')
    print("✓ brand_tokens_inlined_app_shell")


def test_app_tool_meta_rejects_bad_uri():
    try:
        biu.app_tool_meta("nope")
    except ValueError as e:
        assert "ui://" in str(e)
        print("✓ app_tool_meta_rejects_bad_uri")
        return
    raise AssertionError("expected ValueError for non-ui:// uri")


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
    test_render_app_page_shell()
    test_render_app_page_from_schema()
    test_app_mime_type_constant()
    test_app_csp_meta()
    test_app_tool_meta()
    test_app_tool_meta_rejects_bad_uri()
    test_brand_tokens_linked_classic_shell()
    test_brand_tokens_linked_app_shell()
    print("\nAll tests passed.")


if __name__ == "__main__":
    main()
