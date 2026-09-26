from services.integration_registry import health_snapshot, provider_registry, system_of_record


def _clear_core_env(monkeypatch):
    for name in (
        "FINANCEPLUS_SYSTEM_OF_RECORD",
        "NEON_DATABASE_URL",
        "DATABASE_URL",
        "AIRTABLE_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)


def test_system_of_record_prefers_neon(monkeypatch):
    _clear_core_env(monkeypatch)
    monkeypatch.setenv("NEON_DATABASE_URL", "postgresql://redacted")
    monkeypatch.setenv("AIRTABLE_TOKEN", "redacted")
    assert system_of_record() == "neon"


def test_system_of_record_keeps_airtable_compatibility(monkeypatch):
    _clear_core_env(monkeypatch)
    monkeypatch.setenv("AIRTABLE_TOKEN", "redacted")
    assert system_of_record() == "airtable"


def test_system_of_record_falls_back_to_sqlite(monkeypatch):
    _clear_core_env(monkeypatch)
    assert system_of_record() == "sqlite"


def test_registry_does_not_expose_secret_values(monkeypatch):
    _clear_core_env(monkeypatch)
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "https://example.cognitiveservices.azure.com")
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "SUPER_SECRET_KEY")
    payload = str(health_snapshot())
    assert "SUPER_SECRET_KEY" not in payload
    assert provider_registry()["azure_document_intelligence"].configured is True


def test_neon_cloud_core_ready(monkeypatch):
    _clear_core_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://redacted")
    snapshot = health_snapshot()
    assert snapshot["system_of_record"] == "neon"
    assert snapshot["cloud_core_ready"] is True
