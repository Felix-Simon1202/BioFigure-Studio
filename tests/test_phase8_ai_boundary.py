"""Phase 8 offline policy tests use synthetic draft content only."""

import json

import pytest

from backend.core.ai_boundary import AI_MODE, AiBoundaryError, ThemeDraft, request_model, validate_draft
from backend.core.specs import ChartSpec, IllustrationSpec


def illustration(**changes):
    value = {
        "spec_version": "1.3",
        "document_kind": "mechanism",
        "title": "合成机制草案",
        "canvas": {"width": 960, "height": 640},
        "nodes": [],
        "edges": [],
        "groups": [],
        "sections": [],
        "flow_links": [],
        "evidence_records": [],
        "provenance": {
            "registry_version": "1.0",
            "mechanism_schema_version": "1.0",
            "composition_schema_version": "1.0",
            "component_ids": [],
        },
    }
    value.update(changes)
    return json.dumps(value, ensure_ascii=False)


def test_mode_is_off_and_all_model_requests_fail_closed():
    assert AI_MODE == "off"
    for mode in ("off", "local", "cloud", "unexpected"):
        with pytest.raises(AiBoundaryError, match="目前关闭"):
            request_model(mode=mode, payload={"column": "private"}, consent=True)


def test_synthetic_drafts_validate_without_running():
    chart = validate_draft("chart", '{"spec_version":"1.2","dataset_id":"session-1","chart_type":"scatter"}', current_dataset_id="session-1")
    assert isinstance(chart, ChartSpec)
    assert chart.chart_type == "scatter"
    theme = validate_draft("theme", '{"theme_id":"modern_soft","palette_id":"clay"}')
    assert isinstance(theme, ThemeDraft)
    assert theme.palette_version == "1.0"
    document = validate_draft("illustration", illustration())
    assert isinstance(document, IllustrationSpec)


@pytest.mark.parametrize("raw", [
    '{"spec_version":"1.2","dataset_id":"session-2","chart_type":"scatter"}',
    '{"spec_version":"1.2","dataset_id":"session-1","chart_type":"scatter","command":"dir"}',
    '{"spec_version":"1.2","dataset_id":"session-1","chart_type":"scatter","title":"<script>"}',
    '{"spec_version":"1.2","dataset_id":"session-1","chart_type":"scatter","title":"https://example.test"}',
    '{"spec_version":"1.2","dataset_id":"session-1","chart_type":"scatter","title":"C:\\\\secret"}',
    '{"spec_version":"1.2","dataset_id":"session-1","chart_type":"scatter","chart_type":"line"}',
    '{"spec_version":"1.2","dataset_id":"session-1","chart_type":"scatter","point_size":NaN}',
    '```json\n{}\n```',
])
def test_chart_draft_refuses_untrusted_content(raw):
    with pytest.raises(AiBoundaryError):
        validate_draft("chart", raw, current_dataset_id="session-1")


def test_theme_cannot_change_data_or_scientific_fields():
    with pytest.raises(AiBoundaryError):
        validate_draft("theme", '{"theme_id":"modern_soft","palette_id":"clay","dataset_id":"session-1"}')


def test_illustration_draft_cannot_claim_user_verification():
    node = {
        "id": "n1", "component_id": "protein_generic", "x": 30, "y": 30,
        "width": 100, "height": 80, "scientific_status": "verified", "evidence_ids": ["e1"],
    }
    evidence = {
        "id": "e1", "evidence_type": "user_note", "citation": "synthetic",
        "added_by": "test", "date": "2026-10-18",
    }
    provenance = {
        "registry_version": "1.0", "mechanism_schema_version": "1.0",
        "composition_schema_version": "1.0", "component_ids": ["protein_generic"],
    }
    with pytest.raises(AiBoundaryError, match="不能标记"):
        validate_draft("illustration", illustration(nodes=[node], evidence_records=[evidence], provenance=provenance))
