from services.photon_commerce import PhotonConfig


def test_sandbox_base_url():
    cfg = PhotonConfig("c", "u", "a", "p", "s", environment="sandbox")
    assert cfg.base_url == "https://sandbox-api.photoncommerce.com"
    assert cfg.headers["AUTHORIZATION"] == "apikey u:a"


def test_production_base_url():
    cfg = PhotonConfig("c", "u", "a", "p", "s", environment="production")
    assert cfg.base_url == "https://api.photoncommerce.com"
