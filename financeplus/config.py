from __future__ import annotations
from dataclasses import dataclass
import os
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or default)

@dataclass(frozen=True)
class Settings:
    app_name: str = "APP_NUOVA_SETT_IA_00 MASTER"
    environment: str = _env("FINANCEPLUS_ENV", "development")
    database_url: str = _env("DATABASE_URL", "sqlite:///financeplus_master.db")
    local_storage_dir: Path = Path(_env("FINANCEPLUS_STORAGE_DIR", "financeplus_data"))
    airtable_token: str = _env("AIRTABLE_TOKEN")
    airtable_base_id: str = _env("AIRTABLE_BASE_ID")
    google_oauth_token_json: str = _env("GOOGLE_OAUTH_TOKEN_JSON")
    google_drive_folder_id: str = _env("GOOGLE_DRIVE_FOLDER_ID")
    aruba_d_dangelo_password: str = _env("ARUBA_D_DANGELO_PASSWORD")
    aruba_pratiche_password: str = _env("ARUBA_PRATICHE_PASSWORD")
    onedrive_configured: bool = bool(_env("ONEDRIVE_ACCESS_TOKEN"))
    phantom_rules_path: str = _env("PHANTOM_RULES_PATH")
    mcc_rules_path: str = _env("MCC_RULES_PATH")
    matcher_catalog_path: str = _env("MATCHER_CATALOG_PATH")

    @property
    def production_database(self) -> bool:
        return self.database_url.startswith(("postgresql://", "postgresql+psycopg://"))

    def integration_status(self) -> dict[str, str]:
        return {
            "Database": "PostgreSQL/Neon" if self.production_database else "SQLite fallback",
            "Airtable": "CONFIGURATO" if self.airtable_token else "RICHIEDE CREDENZIALI",
            "Google": "CONFIGURATO" if self.google_oauth_token_json else "RICHIEDE CREDENZIALI",
            "Aruba D.Dangelo": "CONFIGURATO" if self.aruba_d_dangelo_password else "RICHIEDE CREDENZIALI",
            "Aruba Pratiche": "CONFIGURATO" if self.aruba_pratiche_password else "RICHIEDE CREDENZIALI",
            "OneDrive": "CONFIGURATO" if self.onedrive_configured else "DA TESTARE / RICHIEDE CREDENZIALI",
            "PHANTOM": "REGOLE DISPONIBILI" if self.phantom_rules_path else "RICHIEDE SORGENTE ORIGINALE / CALIBRAZIONE",
            "MCC": "RULESET DISPONIBILE" if self.mcc_rules_path else "RICHIEDE SORGENTE ORIGINALE / RULESET",
            "Matcher": "CATALOGO DISPONIBILE" if self.matcher_catalog_path else "RICHIEDE SORGENTE ORIGINALE / CATALOGO",
        }

settings = Settings()
