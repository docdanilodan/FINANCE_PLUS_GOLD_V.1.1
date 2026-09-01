from __future__ import annotations

import pytest
from docx import Document

from services import smart_archive
from services.pdf_extraction import extract_document_content
from services.smart_archive import (
    SmartArchivePreview,
    analyze_smart_document,
    archive_smart_document,
)


class FakeAirtable:
    def __init__(self, duplicate=None, fail_create=False):
        self.duplicate = duplicate
        self.fail_create = fail_create
        self.created = []

    def find_one(self, table, field, value):
        assert table == "documenti"
        assert field == "SHA-256"
        return self.duplicate

    def list_records(self, table, max_records=100):
        if table == "clienti":
            return [
                {
                    "id": "rec-client",
                    "fields": {
                        "Cliente": "POLMET SRL",
                        "Partita IVA": "12345678901",
                        "Codice Fiscale": "12345678901",
                    },
                }
            ]
        if table == "pratiche":
            return [
                {
                    "id": "rec-practice",
                    "fields": {
                        "Pratica ID": "POLMET-2026-001",
                        "Cliente collegato": ["rec-client"],
                        "Cliente": "POLMET SRL",
                        "Istituto": "Intesa Sanpaolo",
                    },
                }
            ]
        return []

    def create_record(self, table, fields):
        if self.fail_create:
            raise RuntimeError("Airtable non disponibile")
        self.created.append((table, fields))
        return {"id": "rec-document", "fields": fields}


class _Execute:
    def __init__(self, payload=None):
        self.payload = payload or {}

    def execute(self):
        return self.payload


class FakeFiles:
    def __init__(self):
        self.created = []
        self.deleted = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        return _Execute(
            {
                "id": "drive-file",
                "name": kwargs["body"]["name"],
                "webViewLink": "https://drive.example/file",
                "parents": kwargs["body"].get("parents", []),
                "appProperties": kwargs["body"].get("appProperties", {}),
            }
        )

    def delete(self, **kwargs):
        self.deleted.append(kwargs["fileId"])
        return _Execute()


class FakeDrive:
    def __init__(self):
        self.api = FakeFiles()

    def files(self):
        return self.api


def test_smart_analysis_classifies_matches_and_applies_privacy():
    raw = (
        "POLMET SRL partita iva 12345678901 Centrale Rischi Banca d'Italia "
        "mese di riferimento luglio 2026 accordato utilizzato"
    ).encode()
    preview = analyze_smart_document(
        raw,
        "centrale_rischi_polmet.txt",
        "text/plain",
        airtable=FakeAirtable(),
    )

    assert preview.category == "Centrale Rischi Banca d'Italia"
    assert preview.document_type == "Centrale Rischi"
    assert preview.sensitivity == "Altamente riservato"
    assert preview.ai_policy == "Bloccata"
    assert preview.client_id == "rec-client"
    assert preview.client_name == "POLMET SRL"
    assert preview.document_year == 2026
    assert preview.reference_date == "2026-07-31"
    assert preview.extraction_method == "local_text"


def test_smart_analysis_blocks_existing_sha256_duplicate():
    duplicate = {
        "id": "rec-existing",
        "fields": {"URL Drive": "https://drive.example/existing"},
    }
    preview = analyze_smart_document(
        b"durc documento unico di regolarita contributiva",
        "durc.txt",
        "text/plain",
        airtable=FakeAirtable(duplicate=duplicate),
    )

    assert preview.can_archive is False
    assert preview.duplicate_record_id == "rec-existing"
    assert preview.duplicate_url == "https://drive.example/existing"
    assert any("Duplicato" in warning for warning in preview.warnings)


def test_archive_writes_drive_and_airtable_metadata(monkeypatch):
    monkeypatch.setattr(
        smart_archive,
        "_smart_archive_destination",
        lambda *args, **kwargs: (
            "folder-id",
            "CLIENTI/POLMET SRL/2026/POLMET-2026-001/CENTRALE_RISCHI",
        ),
    )
    airtable = FakeAirtable()
    drive = FakeDrive()
    preview = SmartArchivePreview(
        original_name="cr.pdf",
        mime_type="application/pdf",
        sha256="abc123",
        category="Centrale Rischi Banca d'Italia",
        document_type="Centrale Rischi",
        proposed_name="POLMET SRL_Centrale Rischi luglio 2026.pdf",
        client_id="rec-client",
        client_name="POLMET SRL",
        practice_id="rec-practice",
        practice_code="POLMET-2026-001",
        document_year=2026,
        reference_date="2026-07-31",
    )

    result = archive_smart_document(preview, b"pdf", airtable, drive)

    assert result["status"] == "archived"
    assert result["path"].endswith("CENTRALE_RISCHI")
    assert len(drive.api.created) == 1
    assert airtable.created[0][0] == "documenti"
    fields = airtable.created[0][1]
    assert fields["Cliente collegato"] == ["rec-client"]
    assert fields["Pratica collegata"] == ["rec-practice"]
    assert fields["Esercizio"] == 2026
    assert fields["Sensibilità dati"] == "Altamente riservato"
    assert fields["Policy elaborazione AI"] == "Bloccata"
    assert fields["SHA-256"] == "abc123"


def test_archive_rolls_back_new_drive_file_when_airtable_fails(monkeypatch):
    monkeypatch.setattr(
        smart_archive,
        "_smart_archive_destination",
        lambda *args, **kwargs: ("folder-id", "DA_VERIFICARE/ALTRI_DOCUMENTI"),
    )
    airtable = FakeAirtable(fail_create=True)
    drive = FakeDrive()
    preview = SmartArchivePreview(
        original_name="documento.txt",
        mime_type="text/plain",
        sha256="rollback",
        proposed_name="documento.txt",
    )

    with pytest.raises(RuntimeError, match="Airtable non disponibile"):
        archive_smart_document(preview, b"test", airtable, drive)

    assert drive.api.deleted == ["drive-file"]


def test_review_can_clear_an_automatic_client_and_practice_match(monkeypatch):
    captured = {}

    def destination(_drive, _root, client_name, _category, year, practice_code):
        captured.update(client_name=client_name, year=year, practice_code=practice_code)
        return "folder-id", "DA_VERIFICARE/ALTRI_DOCUMENTI"

    monkeypatch.setattr(smart_archive, "_smart_archive_destination", destination)
    airtable = FakeAirtable()
    preview = SmartArchivePreview(
        original_name="documento.txt",
        mime_type="text/plain",
        sha256="clear-match",
        proposed_name="POLMET SRL_Altro 2026.txt",
        client_id="rec-client",
        client_name="POLMET SRL",
        practice_id="rec-practice",
        practice_code="POLMET-2026-001",
        document_year=2026,
    )

    archive_smart_document(
        preview,
        b"test",
        airtable,
        FakeDrive(),
        client_id=None,
        client_name=None,
        practice_id=None,
        practice_code=None,
        document_year=None,
    )

    fields = airtable.created[0][1]
    assert "Cliente collegato" not in fields
    assert "Pratica collegata" not in fields
    assert "Esercizio" not in fields
    assert captured == {"client_name": None, "year": None, "practice_code": None}


def test_smart_destination_uses_client_year_practice_and_category(monkeypatch):
    calls = []

    def fake_folder(_drive, name, parent=None):
        calls.append((name, parent))
        return f"id-{len(calls)}"

    monkeypatch.setattr(smart_archive, "_find_or_create_folder", fake_folder)
    destination, path = smart_archive._smart_archive_destination(
        object(),
        "root",
        "POLMET SRL",
        "DURC",
        2026,
        "POLMET-2026-001",
    )

    assert destination == "id-6"
    assert path == "CLIENTI/POLMET SRL/2026/POLMET-2026-001/DURC"
    assert [name for name, _ in calls] == [
        "FINANCE_V.1.1_ARCHIVIO",
        "CLIENTI",
        "POLMET SRL",
        "2026",
        "POLMET-2026-001",
        "DURC",
    ]


def test_docx_is_extracted_locally_for_smart_classification():
    from io import BytesIO

    document = Document()
    document.add_paragraph("Bilancio analitico 2025 situazione contabile POLMET SRL")
    raw = BytesIO()
    document.save(raw)

    result = extract_document_content(
        raw.getvalue(),
        "situazione_contabile.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        allow_cloud=False,
    )

    assert result.method == "local_docx"
    assert "Bilancio analitico 2025" in result.text
