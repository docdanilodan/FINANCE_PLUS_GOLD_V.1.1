from services.event_orchestrator import FinancePlusEventOrchestrator


class FakeAirtable:
    def __init__(self):
        self.created = []
        self.updated = []

    def create_record(self, table, fields):
        self.created.append((table, fields))
        return {"id": "recAudit000000001", "fields": fields}

    def update_record(self, table, record_id, fields):
        self.updated.append((table, record_id, fields))
        return {"id": record_id, "fields": fields}


def test_document_sensitivity_high_risk():
    assert FinancePlusEventOrchestrator._document_sensitivity("Centrale Rischi") == "Altamente riservato"
    assert FinancePlusEventOrchestrator._document_sensitivity("Estratto conto") == "Altamente riservato"
    assert FinancePlusEventOrchestrator._document_sensitivity("Documento identità") == "Altamente riservato"


def test_document_sensitivity_confidential():
    assert FinancePlusEventOrchestrator._document_sensitivity("Bilancio") == "Riservato"
    assert FinancePlusEventOrchestrator._document_sensitivity("Contratto") == "Riservato"


def test_document_sensitivity_internal_default():
    assert FinancePlusEventOrchestrator._document_sensitivity("Visura camerale") == "Interno"
    assert FinancePlusEventOrchestrator._document_sensitivity("Altro") == "Interno"


def test_document_ai_policy():
    assert FinancePlusEventOrchestrator._document_ai_policy("Interno", "Standard") == "Consentita"
    assert FinancePlusEventOrchestrator._document_ai_policy("Riservato", "Standard") == "Solo con approvazione"
    assert FinancePlusEventOrchestrator._document_ai_policy("Altamente riservato", "Standard") == "Bloccata"
    assert FinancePlusEventOrchestrator._document_ai_policy("Interno", "CSE") == "Bloccata"


def test_cse_document_is_blocked_and_policy_written():
    airtable = FakeAirtable()
    orchestrator = FinancePlusEventOrchestrator(airtable=airtable)
    action, status, detail = orchestrator._handle_document(
        "recDocument000001",
        {
            "Tipo Documento": "Bilancio",
            "Sensibilità dati": "Riservato",
            "Protezione Drive": "CSE",
        },
    )
    assert action == "privacy-gate-cse"
    assert status == "Ignorato"
    assert "Client-Side Encryption" in detail
    assert any(update[2].get("Policy elaborazione AI") == "Bloccata" for update in airtable.updated)


def test_external_event_is_audit_only():
    airtable = FakeAirtable()
    orchestrator = FinancePlusEventOrchestrator(airtable=airtable)
    result = orchestrator.process_external_event(
        source="GitHub",
        event_type="pull_request.updated",
        external_id="pr-3",
        detail="PR aggiornata",
    )
    assert result["status"] == "Completato"
    assert airtable.updated == []
    assert airtable.created[0][0] == "eventi"
    assert airtable.created[0][1]["Sorgente tecnica"] == "GitHub"
