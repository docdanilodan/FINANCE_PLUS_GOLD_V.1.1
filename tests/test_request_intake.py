from datetime import date

from services.request_intake import RequestIntakeService, RequestPreview, _extract_documents, _parse_due_date


def test_parse_named_due_date():
    assert _parse_due_date("Hashcom ha documenti da integrare entro il 5 ottobre.", today=date(2026, 9, 30)) == "2026-10-05"


def test_extract_documents():
    docs = _extract_documents("Servono bilancio 2025, Centrale Rischi e DURC.")
    assert "Bilancio" in docs
    assert "Centrale Rischi" in docs
    assert "DURC" in docs


class FakeAirtable:
    def __init__(self):
        self.clients = {
            "rec_client": {"id": "rec_client", "fields": {"Cliente": "HASHCOM S.R.L."}},
        }
        self.practices = {
            "rec_practice": {
                "id": "rec_practice",
                "fields": {
                    "Pratica ID": "HASH-2026-001",
                    "Cliente": "HASHCOM S.R.L.",
                    "Cliente collegato": ["rec_client"],
                    "Prossima azione": "",
                    "Documenti mancanti": "",
                },
            }
        }
        self.events = []
        self.updated = None

    def find_one(self, table, field_name, value):
        return None

    def list_records(self, table, max_records=100, formula=None):
        if table == "clienti":
            return list(self.clients.values())
        if table == "pratiche":
            return list(self.practices.values())
        return []

    def get_record(self, table, record_id):
        return self.practices[record_id] if table == "pratiche" else self.clients[record_id]

    def update_record(self, table, record_id, fields):
        self.updated = (table, record_id, fields)
        if table == "pratiche":
            self.practices[record_id]["fields"].update(fields)
            return self.practices[record_id]
        raise AssertionError(table)

    def create_record(self, table, fields):
        if table == "eventi":
            self.events.append(fields)
            return {"id": f"evt{len(self.events)}", "fields": fields}
        raise AssertionError(table)


def test_approve_updates_only_after_explicit_call():
    db = FakeAirtable()
    svc = RequestIntakeService(db)
    preview = RequestPreview(
        source="ChatGPT Work",
        external_id="req-1",
        request_text="HASHCOM integra i documenti entro il 5 ottobre",
        fingerprint="abc",
        due_date="2026-10-05",
        requested_documents=["Bilancio"],
        client_id="rec_client",
        client_name="HASHCOM S.R.L.",
        practice_id="rec_practice",
        practice_code="HASH-2026-001",
        confidence=0.9,
        match_reason="test",
        duplicate=False,
        duplicate_reason="",
    )
    assert db.updated is None
    result = svc.approve(preview, approved_by="Danilo")
    assert result["status"] == "applied"
    assert db.updated[0] == "pratiche"
    assert db.updated[2]["Stato"] == "Integrazione"
    assert db.updated[2]["Scadenza prossima azione"] == "2026-10-05"
    assert "Bilancio" in db.updated[2]["Documenti mancanti"]
