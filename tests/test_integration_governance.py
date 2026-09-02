from __future__ import annotations

from pathlib import Path

from document_ai import DocumentResult
from scripts import sync_drive_classification as drive_sync
from services import gmail_drive_pipeline_v2 as gmail_v2
from services.airtable_mcp_policy import evaluate_airtable_mcp_action
from services.drive_classification import resolve_drive_classification
from services.pdf_extraction import ExtractionResult, _cloud_allowed, extract_document_content


def test_archive_workflows_expose_repository_root_to_python() -> None:
    """Scheduled archive scripts must be able to import the services package."""

    repository_root = Path(__file__).resolve().parents[1]
    for workflow_name in ("gmail_archive.yml", "aruba_archive.yml"):
        workflow = (repository_root / ".github" / "workflows" / workflow_name).read_text(
            encoding="utf-8"
        )
        assert "PYTHONPATH: ${{ github.workspace }}" in workflow


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


class _FailingFiles:
    def listLabels(self, **kwargs):
        raise PermissionError("labels scope missing")


class _FailingDrive:
    def files(self):
        return _FailingFiles()


def test_drive_sync_strict_mode_fails_when_label_map_is_missing(monkeypatch):
    monkeypatch.setenv("FINANCEPLUS_DRIVE_SYNC_STRICT", "true")
    monkeypatch.delenv("FINANCEPLUS_DRIVE_LABEL_MAP_JSON", raising=False)
    assert drive_sync.main() == 1


def test_drive_sync_strict_mode_rejects_malformed_or_empty_mapping(monkeypatch):
    monkeypatch.setenv("FINANCEPLUS_DRIVE_SYNC_STRICT", "true")
    monkeypatch.setenv("FINANCEPLUS_DRIVE_LABEL_MAP_JSON", "{ }")
    assert drive_sync.main() == 1
    monkeypatch.setenv("FINANCEPLUS_DRIVE_LABEL_MAP_JSON", '{"choice":"Non supportata"}')
    assert drive_sync.main() == 1
    monkeypatch.setenv("FINANCEPLUS_DRIVE_LABEL_MAP_JSON", '["choice-secret"]')
    assert drive_sync.main() == 1


def test_drive_sync_non_strict_mode_keeps_local_skip_behaviour(monkeypatch):
    monkeypatch.delenv("FINANCEPLUS_DRIVE_SYNC_STRICT", raising=False)
    monkeypatch.delenv("FINANCEPLUS_DRIVE_LABEL_MAP_JSON", raising=False)
    assert drive_sync.main() == 0


def test_drive_sync_strict_mode_fails_for_missing_profile_token(monkeypatch):
    monkeypatch.setenv("FINANCEPLUS_DRIVE_SYNC_STRICT", "true")
    monkeypatch.setenv("FINANCEPLUS_DRIVE_LABEL_MAP_JSON", '{"choice-secret":"Altamente riservato"}')
    monkeypatch.setenv("FINANCEPLUS_GOOGLE_PROFILES", "STUDIO")
    monkeypatch.delenv("GOOGLE_OAUTH_TOKEN_JSON_STUDIO", raising=False)
    assert drive_sync.main() == 1


def test_drive_sync_strict_mode_fails_when_a_profile_has_file_errors(monkeypatch):
    monkeypatch.setenv("FINANCEPLUS_DRIVE_SYNC_STRICT", "true")
    monkeypatch.setenv("FINANCEPLUS_DRIVE_LABEL_MAP_JSON", '{"choice-secret":"Altamente riservato"}')
    monkeypatch.setenv("FINANCEPLUS_GOOGLE_PROFILES", "STUDIO")
    monkeypatch.setenv("GOOGLE_OAUTH_TOKEN_JSON_STUDIO", "{}")
    monkeypatch.delenv("AIRTABLE_TOKEN", raising=False)
    monkeypatch.setattr(
        drive_sync,
        "_reconcile_profile",
        lambda profile, airtable: {
            "profile": profile,
            "scanned": 1,
            "labelled": 0,
            "updated_drive": 0,
            "updated_airtable": 0,
            "errors": [{"file_id": "file-1", "error": "Drive labels non disponibili"}],
        },
    )
    assert drive_sync.main() == 1


def test_drive_sync_emits_success_marker_after_complete_reconciliation(monkeypatch, capsys):
    monkeypatch.setenv("FINANCEPLUS_DRIVE_SYNC_STRICT", "true")
    monkeypatch.setenv("FINANCEPLUS_DRIVE_LABEL_MAP_JSON", '{"choice-secret":"Altamente riservato"}')
    monkeypatch.setenv("FINANCEPLUS_GOOGLE_PROFILES", "STUDIO")
    monkeypatch.setenv("GOOGLE_OAUTH_TOKEN_JSON_STUDIO", "{}")
    monkeypatch.delenv("AIRTABLE_TOKEN", raising=False)
    monkeypatch.setattr(
        drive_sync,
        "_reconcile_profile",
        lambda profile, airtable: {
            "profile": profile,
            "scanned": 0,
            "labelled": 0,
            "updated_drive": 0,
            "updated_airtable": 0,
            "errors": [],
        },
    )

    assert drive_sync.main() == 0
    output = capsys.readouterr().out
    assert '"profiles"' in output
    assert '"scanned": 0' in output
    assert '"labelled": 0' in output
    assert '"updated_drive": 0' in output
    assert '"updated_airtable": 0' in output
    assert "DRIVE_RECONCILIATION_OK" in output


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


def test_drive_label_read_failure_is_explicit(monkeypatch):
    monkeypatch.setenv("FINANCEPLUS_DRIVE_LABEL_MAP_JSON", '{"choice-secret":"Altamente riservato"}')
    decision = resolve_drive_classification(_FailingDrive(), "file-1", fallback="Riservato")
    assert decision.sensitivity == "Riservato"
    assert decision.source == "drive-labels-unavailable"
    assert "PermissionError" in decision.error


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


def test_unreadable_pdf_preflight_fails_closed():
    local = ExtractionResult(text="", method="none")
    classification = DocumentResult(category="Bilancio d'esercizio", confidence=0.95)
    assert gmail_v2._local_preflight_is_classifiable(
        local,
        classification,
        "allegato.pdf",
        "application/pdf",
    ) is False


def test_short_pdf_preflight_fails_closed_even_with_context_classification():
    local = ExtractionResult(text="saldo", method="local_pypdf")
    classification = DocumentResult(category="Estratto conto", confidence=0.95)
    assert gmail_v2._local_preflight_is_classifiable(
        local,
        classification,
        "documento.pdf",
        "application/pdf",
    ) is False


def test_meaningful_local_pdf_preflight_can_enable_optional_cloud_layer():
    local = ExtractionResult(
        text=("stato patrimoniale conto economico bilancio esercizio ricavi costi patrimonio " * 5),
        method="local_pypdf",
    )
    classification = DocumentResult(category="Bilancio d'esercizio", confidence=0.80)
    assert gmail_v2._local_preflight_is_classifiable(
        local,
        classification,
        "bilancio.pdf",
        "application/pdf",
    ) is True


def test_adobe_not_called_when_local_pdf_preflight_is_not_classifiable(monkeypatch):
    local = ExtractionResult(text="", method="none")

    def _must_not_be_called(**kwargs):
        raise AssertionError("cloud extractor must not be called")

    monkeypatch.setattr(gmail_v2, "extract_document_content", _must_not_be_called)
    classification, returned = gmail_v2._maybe_enhance_with_adobe(
        raw=b"pdf",
        filename="scansione.pdf",
        mime_type="application/pdf",
        context="mail generica",
        sensitivity="Interno",
        ai_policy="Consentita",
        local_result=local,
        preflight_classifiable=False,
    )
    assert classification is None
    assert returned is local
