from services.drive_preview import protected_drive_preview


def test_cse_preview_allows_only_direct_google_drive_https_url():
    decision = protected_drive_preview(
        {
            "Protezione Drive": "CSE",
            "Documento": "bilancio.pdf",
            "URL Drive": "https://drive.google.com/file/d/file-1/view",
            "Policy elaborazione AI": "Bloccata",
        }
    )
    assert decision.allowed is True
    assert decision.ai_policy == "Bloccata"


def test_preview_is_denied_for_non_cse_document():
    decision = protected_drive_preview(
        {
            "Protezione Drive": "Standard",
            "Documento": "bilancio.pdf",
            "URL Drive": "https://drive.google.com/file/d/file-1/view",
        }
    )
    assert decision.allowed is False


def test_cse_preview_rejects_untrusted_or_non_https_url():
    assert protected_drive_preview(
        {"Protezione Drive": "CSE", "Documento": "bilancio.pdf", "URL Drive": "https://example.com/file.pdf"}
    ).allowed is False
    assert protected_drive_preview(
        {
            "Protezione Drive": "CSE",
            "Documento": "bilancio.pdf",
            "URL Drive": "http://drive.google.com/file/d/file-1/view",
        }
    ).allowed is False


def test_cse_preview_is_limited_to_pdf_and_images():
    decision = protected_drive_preview(
        {
            "Protezione Drive": "CSE",
            "Documento": "movimenti.xlsx",
            "URL Drive": "https://drive.google.com/file/d/file-1/view",
        }
    )
    assert decision.allowed is False
