from financeplus.engines.documents import extract_text_bytes, classify_document


def test_text_extraction_is_deterministic():
    text, warnings = extract_text_bytes("sample.txt", b"Bilancio 2025 ACME SRL")
    assert "ACME SRL" in text
    assert warnings == []


def test_classifier_fails_safe_without_legacy_module():
    result = classify_document("sample.txt", b"Bilancio 2025 ACME SRL")
    assert result.category
    assert result.status in {"RICHIEDE SORGENTE ORIGINALE", "IMPLEMENTATO", "DA TESTARE / REVISIONE UMANA"}
