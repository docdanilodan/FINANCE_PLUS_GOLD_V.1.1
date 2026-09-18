from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Dict


@dataclass(frozen=True)
class ProviderReadiness:
    key: str
    label: str
    category: str
    configured: bool
    role: str
    optional: bool = True
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _present(*names: str) -> bool:
    return all(bool(os.getenv(name, "").strip()) for name in names)


def system_of_record() -> str:
    """Return the configured SMART F+ core data backend.

    Neon/PostgreSQL is preferred when a deployment connection string is
    available. Airtable remains a compatibility layer while the web UI is
    migrated. SQLite remains the local/offline continuity backend.
    """
    explicit = os.getenv("FINANCEPLUS_SYSTEM_OF_RECORD", "").strip().lower()
    if explicit in {"neon", "postgres", "postgresql"}:
        return "neon"
    if explicit == "airtable":
        return "airtable"
    if explicit == "sqlite":
        return "sqlite"
    if _present("NEON_DATABASE_URL") or _present("DATABASE_URL"):
        return "neon"
    if _present("AIRTABLE_TOKEN"):
        return "airtable"
    return "sqlite"


def provider_registry() -> Dict[str, ProviderReadiness]:
    sor = system_of_record()
    return {
        "neon": ProviderReadiness(
            key="neon",
            label="Neon PostgreSQL",
            category="database",
            configured=_present("NEON_DATABASE_URL") or _present("DATABASE_URL"),
            role="preferred cloud system of record",
            optional=False,
            note="Required for cloud-first SMART F+; SQLite remains the offline fallback.",
        ),
        "sqlite": ProviderReadiness(
            key="sqlite",
            label="SQLite",
            category="database",
            configured=True,
            role="local/offline continuity",
            optional=False,
        ),
        "airtable": ProviderReadiness(
            key="airtable",
            label="Airtable",
            category="compatibility_crm",
            configured=_present("AIRTABLE_TOKEN"),
            role="legacy web compatibility / operational mirror",
            optional=True,
            note="Must not become a second core source of truth when Neon is active.",
        ),
        "openai": ProviderReadiness(
            key="openai",
            label="OpenAI Responses API",
            category="ai",
            configured=_present("OPENAI_API_KEY"),
            role="AI analysis and operational recommendations",
            optional=True,
        ),
        "azure_document_intelligence": ProviderReadiness(
            key="azure_document_intelligence",
            label="Azure AI Document Intelligence",
            category="document_intelligence",
            configured=_present(
                "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT",
                "AZURE_DOCUMENT_INTELLIGENCE_KEY",
            ),
            role="structured OCR / document extraction",
            optional=True,
        ),
        "adobe_pdf_services": ProviderReadiness(
            key="adobe_pdf_services",
            label="Adobe PDF Services",
            category="document_intelligence",
            configured=_present("PDF_SERVICES_CLIENT_ID", "PDF_SERVICES_CLIENT_SECRET"),
            role="PDF-to-Markdown quality layer",
            optional=True,
        ),
        "photon": ProviderReadiness(
            key="photon",
            label="Photon Commerce",
            category="document_intelligence",
            configured=_present(
                "PHOTON_CLIENT_ID",
                "PHOTON_USERNAME",
                "PHOTON_API_KEY",
                "PHOTON_PASSWORD",
                "PHOTON_SECRET_KEY",
            ),
            role="invoice/statement specialist extraction",
            optional=True,
        ),
        "asana_bridge": ProviderReadiness(
            key="asana_bridge",
            label="Asana bridge",
            category="workflow",
            configured=_present("FINANCEPLUS_ASANA_BRIDGE_URL"),
            role="deadlines and assignments",
            optional=True,
            note="ChatGPT plugin connectivity is separate from deployment/API connectivity.",
        ),
        "monday_bridge": ProviderReadiness(
            key="monday_bridge",
            label="monday.com bridge",
            category="workflow",
            configured=_present("FINANCEPLUS_MONDAY_BRIDGE_URL"),
            role="practice pipeline and work management",
            optional=True,
            note="ChatGPT plugin connectivity is separate from deployment/API connectivity.",
        ),
        "attio_bridge": ProviderReadiness(
            key="attio_bridge",
            label="Attio bridge",
            category="crm",
            configured=_present("FINANCEPLUS_ATTIO_BRIDGE_URL"),
            role="optional CRM mirror",
            optional=True,
            note="Disabled safely when no active Attio workspace/API bridge is available.",
        ),
        "posthog": ProviderReadiness(
            key="posthog",
            label="PostHog",
            category="telemetry",
            configured=_present("POSTHOG_API_KEY") or _present("POSTHOG_PROJECT_API_KEY"),
            role="privacy-safe product and AI telemetry",
            optional=True,
        ),
    }


def health_snapshot() -> dict:
    providers = provider_registry()
    sor = system_of_record()
    return {
        "system_of_record": sor,
        "cloud_core_ready": sor == "neon" and providers["neon"].configured,
        "providers": {key: value.to_dict() for key, value in providers.items()},
    }
