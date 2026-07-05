"""Tests for the dashboard DSL -> cre8-a2ui expansion and token codec."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from cre8_mcp_ui import dashboard as db
from cre8_mcp_ui import render_schema


def test_token_roundtrip():
    spec = {"title": "T", "sections": [{"type": "note", "text": "hi"}]}
    token = db.encode_spec(spec)
    # URL-safe: no chars that need escaping in a ui:// path segment.
    assert "/" not in token and "+" not in token and " " not in token
    assert db.decode_spec(token) == spec


def test_stats_section_renders_grid_and_badge():
    spec = {"sections": [{"type": "stats", "items": [
        {"label": "Users", "value": "1,234", "status": "success"},
        {"label": "Repos", "value": "8"},
    ]}]}
    html = render_schema(db.spec_to_schema(spec))
    assert "<cre8-grid" in html and 'variant="2up"' in html
    assert "1,234" in html and "Users" in html
    assert '<cre8-badge text="success" status="success">' in html


def test_chart_data_goes_to_properties_not_attribute():
    spec = {"sections": [{"type": "chart", "chartType": "line", "title": "S",
                          "labels": ["a", "b"], "datasets": [{"label": "x", "data": [1, 2]}]}]}
    html = render_schema(db.spec_to_schema(spec))
    assert '<cre8-chart' in html and 'type="line"' in html
    # data is a JS property (attribute:false) delivered via data-cre8-props.
    assert "data-cre8-props=" in html
    assert "datasets" in html and 'data="' not in html


def test_table_section_structure():
    spec = {"sections": [{"type": "table", "columns": ["A", "B"],
                          "rows": [["1", "2"], ["3", "4"]]}]}
    html = render_schema(db.spec_to_schema(spec))
    assert "<cre8-table>" in html
    assert html.count("<cre8-table-header-cell>") == 2
    assert html.count("<cre8-table-row>") == 2
    assert html.count("<cre8-table-cell>") == 4


def test_note_uses_status_not_variant():
    spec = {"sections": [{"type": "note", "text": "watch out", "status": "warning"}]}
    html = render_schema(db.spec_to_schema(spec))
    # cre8-inline-alert colour is `status`; `variant` is only subtle/transparent.
    assert '<cre8-inline-alert status="warning">' in html
    assert "watch out" in html


def test_unknown_section_becomes_error_note():
    spec = {"sections": [{"type": "bogus"}]}
    html = render_schema(db.spec_to_schema(spec))
    assert '<cre8-inline-alert status="error">' in html


def test_empty_spec_is_safe():
    html = render_schema(db.spec_to_schema({"sections": []}))
    assert "cre8-inline-alert" in html  # falls back to an info note
