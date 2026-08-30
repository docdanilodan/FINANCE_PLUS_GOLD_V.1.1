from services.google_auth import discover_google_profiles, token_env_name


def test_token_env_name_default_and_named():
    assert token_env_name("DEFAULT") == "GOOGLE_OAUTH_TOKEN_JSON"
    assert token_env_name("studio") == "GOOGLE_OAUTH_TOKEN_JSON_STUDIO"
    assert token_env_name("Pratiche") == "GOOGLE_OAUTH_TOKEN_JSON_PRATICHE"


def test_discover_explicit_profiles(monkeypatch):
    monkeypatch.setenv("FINANCEPLUS_GOOGLE_PROFILES", "default, studio, pratiche")
    assert discover_google_profiles() == ["DEFAULT", "STUDIO", "PRATICHE"]


def test_discover_profiles_from_available_tokens(monkeypatch):
    monkeypatch.delenv("FINANCEPLUS_GOOGLE_PROFILES", raising=False)
    monkeypatch.setenv("GOOGLE_OAUTH_TOKEN_JSON", "{}")
    monkeypatch.setenv("GOOGLE_OAUTH_TOKEN_JSON_STUDIO", "{}")
    monkeypatch.delenv("GOOGLE_OAUTH_TOKEN_JSON_PRATICHE", raising=False)
    assert discover_google_profiles() == ["DEFAULT", "STUDIO"]
