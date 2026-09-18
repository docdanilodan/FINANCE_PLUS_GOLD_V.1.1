from __future__ import annotations

import io
import os
from dataclasses import dataclass, field

from pypdf import PdfReader


@dataclass
class ExtractionResult:
    text: str = ""
    method: str = "none"
    cloud_used: bool = False
    warnings: list[str] = field(default_factory=list)


def _truthy(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _local_pdf_text(raw: bytes, max_chars: int = 250_000) -> str:
    reader = PdfReader(io.BytesIO(raw))
    chunks: list[str] = []
    total = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        if not text:
            continue
        remaining = max_chars - total
        if remaining <= 0:
            break
        chunks.append(text[:remaining])
        total += min(len(text), remaining)
    return "\n\n".join(chunks).strip()


def _adobe_pdf_to_markdown(raw: bytes) -> str:
    # Imported lazily so FinancePlus remains operational when Adobe credentials
    # are not configured or the optional SDK is not needed for a given file.
    from adobe.pdfservices.operation.auth.service_principal_credentials import ServicePrincipalCredentials
    from adobe.pdfservices.operation.io.cloud_asset import CloudAsset
    from adobe.pdfservices.operation.io.stream_asset import StreamAsset
    from adobe.pdfservices.operation.pdf_services import PDFServices
    from adobe.pdfservices.operation.pdf_services_media_type import PDFServicesMediaType
    from adobe.pdfservices.operation.pdfjobs.jobs.pdf_to_markdown_job import PDFToMarkdownJob
    from adobe.pdfservices.operation.pdfjobs.result.pdf_to_markdown_result import PDFToMarkdownResult

    client_id = os.getenv("PDF_SERVICES_CLIENT_ID", "").strip()
    client_secret = os.getenv("PDF_SERVICES_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("Credenziali Adobe PDF Services non configurate")

    credentials = ServicePrincipalCredentials(client_id=client_id, client_secret=client_secret)
    pdf_services = PDFServices(credentials=credentials)
    input_asset = pdf_services.upload(input_stream=raw, mime_type=PDFServicesMediaType.PDF)
    job = PDFToMarkdownJob(input_asset=input_asset)
    location = pdf_services.submit(job)
    response = pdf_services.get_job_result(location, PDFToMarkdownResult)
    result_asset: CloudAsset = response.get_result().get_asset()
    stream_asset: StreamAsset = pdf_services.get_content(result_asset)
    content = stream_asset.get_input_stream()
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace").strip()
    return bytes(content).decode("utf-8", errors="replace").strip()


def _azure_document_to_markdown(raw: bytes) -> str:
    from services.azure_document_intelligence import (
        AzureDocumentIntelligenceClient,
        AzureDocumentIntelligenceConfig,
    )

    config = AzureDocumentIntelligenceConfig.from_env()
    if config is None:
        raise RuntimeError("Azure AI Document Intelligence non configurato")
    return AzureDocumentIntelligenceClient(config).analyze_bytes(raw)


def _cloud_allowed(
    sensitivity: str,
    ai_policy: str,
    provider: str = "adobe",
) -> bool:
    if ai_policy == "Bloccata" or sensitivity == "Altamente riservato":
        return False
    if sensitivity == "Riservato":
        if provider == "azure":
            return _truthy("FINANCEPLUS_AZURE_ALLOW_CONFIDENTIAL", default=False)
        return _truthy("FINANCEPLUS_ADOBE_ALLOW_CONFIDENTIAL", default=False)
    return True


def extract_document_content(
    raw: bytes,
    filename: str,
    mime_type: str = "",
    sensitivity: str = "Interno",
    ai_policy: str = "Consentita",
    allow_cloud: bool | None = None,
) -> ExtractionResult:
    """Extract document text without weakening FinancePlus privacy controls.

    PDFs are always eligible for local extraction. Azure AI Document
    Intelligence and Adobe PDF-to-Markdown are optional quality layers.
    Callers handling unclassified inbound documents should first call this
    function with ``allow_cloud=False``, classify the local result, then call
    it again with ``allow_cloud=True`` only if the resulting privacy policy
    permits cloud processing.

    FINANCEPLUS_PDF_EXTRACTOR accepts: auto, azure, adobe, local.
    In auto mode Azure is preferred when configured, then Adobe, then pypdf.
    """
    lower_name = (filename or "").lower()
    is_pdf = lower_name.endswith(".pdf") or mime_type == "application/pdf"

    if not raw:
        return ExtractionResult(warnings=["Documento vuoto"])

    if not is_pdf:
        if lower_name.endswith((".txt", ".csv", ".md", ".json", ".xml")) or mime_type.startswith("text/"):
            return ExtractionResult(text=raw.decode("utf-8", errors="replace")[:250_000], method="local_text")
        return ExtractionResult(method="unsupported")

    warnings: list[str] = []
    local_text = ""
    try:
        local_text = _local_pdf_text(raw)
    except Exception as exc:
        warnings.append(f"Estrazione PDF locale non riuscita: {exc}")

    mode = os.getenv("FINANCEPLUS_PDF_EXTRACTOR", "auto").strip().lower() or "auto"
    if mode not in {"auto", "azure", "adobe", "local"}:
        warnings.append(f"FINANCEPLUS_PDF_EXTRACTOR non riconosciuto ({mode}); usato auto")
        mode = "auto"

    azure_configured = bool(
        os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "").strip()
        and os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "").strip()
    )
    adobe_configured = bool(
        os.getenv("PDF_SERVICES_CLIENT_ID", "").strip()
        and os.getenv("PDF_SERVICES_CLIENT_SECRET", "").strip()
    )
    cloud_requested = True if allow_cloud is None else bool(allow_cloud)

    if (
        cloud_requested
        and mode in {"auto", "azure"}
        and azure_configured
        and _cloud_allowed(sensitivity, ai_policy, provider="azure")
    ):
        try:
            markdown = _azure_document_to_markdown(raw)
            if markdown:
                return ExtractionResult(
                    text=markdown[:400_000],
                    method="azure_document_intelligence",
                    cloud_used=True,
                    warnings=warnings,
                )
        except Exception as exc:
            warnings.append(f"Azure Document Intelligence non riuscito: {exc}")
            if mode == "azure" and not local_text:
                return ExtractionResult(method="azure_failed", warnings=warnings)

    if (
        cloud_requested
        and mode in {"auto", "adobe"}
        and adobe_configured
        and _cloud_allowed(sensitivity, ai_policy, provider="adobe")
    ):
        try:
            markdown = _adobe_pdf_to_markdown(raw)
            if markdown:
                return ExtractionResult(
                    text=markdown[:400_000],
                    method="adobe_pdf_to_markdown",
                    cloud_used=True,
                    warnings=warnings,
                )
        except Exception as exc:
            warnings.append(f"Adobe PDF to Markdown non riuscito: {exc}")
            if mode == "adobe" and not local_text:
                return ExtractionResult(method="adobe_failed", warnings=warnings)

    if cloud_requested and mode == "azure" and not _cloud_allowed(
        sensitivity, ai_policy, provider="azure"
    ):
        warnings.append("Azure bloccato dalla policy privacy FinancePlus; usata estrazione locale")
    if cloud_requested and mode == "adobe" and not _cloud_allowed(
        sensitivity, ai_policy, provider="adobe"
    ):
        warnings.append("Adobe bloccato dalla policy privacy FinancePlus; usata estrazione locale")

    return ExtractionResult(
        text=local_text,
        method="local_pypdf" if local_text else "none",
        cloud_used=False,
        warnings=warnings,
    )
