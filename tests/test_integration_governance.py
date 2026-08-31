from __future__ import annotations

from services.airtable_mcp_policy import evaluate_airtable_mcp_action
from services.drive_classification import resolve_drive_classification
from services.pdf_extraction import _cloud_allowed, extract_document_content


class _Execute:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _Files:
    def __init__(self, labels):
        self.labels = labels

    def listLabels(self, **kwargs):
        assert kwargs["fileId"] == "file-1"
        return _Execute({"labels": self.labels})


class _Drive:
    def __init__(self, labels):
        self._files = _Files(labels)

    def files(self):
        return self._files


def test_airtable_mcp_reads_allowed(monkeypatch):
    monkeypatch.delenv("FINANCEPLUS_AIRTABLE_MCP_RECORD_WRITE", raising=False)
    decision = evaluate_airtable_mcp_action("list_records")
    assert decision.allowed is True
    assert decision.requires_approval is False
    assert decision.mode == "read"


def test_airtable_mcp_record_write_staged_by_default(monkeypatch):
    monkeypatch.delenv("FINANCEPLUS_AIRTABLE_MCP_RECORD_WRITE", raising=False)
    decision = evaluate_airtable_mcp_action("update_record", sensitivity="Interno")
    assert decision.allowed is False
    assert decision.requires_approval is True
    assert decision.mode == "staged"


def test_airtable_mcp_structural_change_always_requires_approval(monkeypatch):
    monkeypatch.setenv("FINANCEPLUS_AIRTABLE_MCP_RECORD_WRITE", "true")
    decision = evaluate_airtable_mcp_action("create_automation", sensitivity="Interno")
    assert decision.allowed is False
    assert decision.requires_approval is True


def test_airtable_mcp_highly_confidential_write_blocked(monkeypatch):
    monkeypatch.setenv("FINANCEPLUS_AIRTABLE_MCP_RECORD_WRITE", "true")
    decision = evaluate_airtable_mcp_action("update_record", sensitivity="Altamente riservato")
    assert decision.allowed is False
    assert decision.mode == "blocked"


def test_drive_label_can_raise_sensitivity(monkeypatch):
    monkeypatch.setenv(
        "FINANCEPLUS_DRIVE_LABEL_MAP_JSON",
        '{"choice-secret":"Altamente riservato","choice-conf":"Riservato"}',
    )
    drive = _Drive(
        [
            {
                "id": "label-1",
                "fields": {
                    "field-1": {"selection": ["choice-secret"]},
                },
            }
        ]
    )
    decision = resolve_drive_classification(drive, "file-1", fallback="Interno")
    assert decision.sensitivity == "Altamente riservato"
    assert decision.source == "google-drive-label"


def test_drive_label_without_mapping_keeps_financeplus_policy(monkeypatch):
    monkeypatch.setenv("FINANCEPLUS_DRIVE_LABEL_MAP_JSON", "{}")
    decision = resolve_drive_classification(_Drive([]), "file-1", fallback="Riservato")
    assert decision.sensitivity == "Riservato"


def test_pdf_cloud_blocked_for_highly_confidential(monkeypatch):
    monkeypatch.setenv("FINANCEPLUS_ADOBE_ALLOW_CONFIDENTIAL", "true")
    assert _cloud_allowed("Altamente riservato", "Bloccata") is False


def test_pdf_confidential_cloud_disabled_by_default(monkeypatch):
    monkeypatch.delenv("FINANCEPLUS_ADOBE_ALLOW_CONFIDENTIAL", raising=False)
    assert _cloud_allowed("Riservato", "Solo con approvazione") is False


def test_local_text_extraction_does_not_use_cloud(monkeypatch):
    monkeypatch.setenv("PDF_SERVICES_CLIENT_ID", "test")
    monkeypatch.setenv("PDF_SERVICES_CLIENT_SECRET", "test")
    result = extract_document_content(
        b"bilancio 2025",
        "nota.txt",
        mime_type="text/plain",
        allow_cloud=False,
    )
    assert result.text == "bilancio 2025"
    assert result.method == "local_text"
    assert result.cloud_used is False
