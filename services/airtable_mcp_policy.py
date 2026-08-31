from __future__ import annotations

import os
from dataclasses import dataclass, asdict


READ_ACTIONS = {
    "list_records",
    "get_record",
    "search_records",
    "list_bases",
    "get_base",
    "list_tables",
    "get_table",
    "list_fields",
    "get_field",
}

RECORD_WRITE_ACTIONS = {
    "create_record",
    "update_record",
    "upsert_record",
    "delete_record",
}

STRUCTURAL_ACTIONS = {
    "create_base",
    "update_base",
    "delete_base",
    "create_table",
    "update_table",
    "delete_table",
    "create_field",
    "update_field",
    "delete_field",
    "create_interface",
    "update_interface",
    "delete_interface",
    "create_automation",
    "update_automation",
    "delete_automation",
}


@dataclass
class AirtableMcpDecision:
    action: str
    mode: str
    allowed: bool
    requires_approval: bool
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def _truthy(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def evaluate_airtable_mcp_action(
    action: str,
    sensitivity: str = "Interno",
    source: str = "agent",
) -> AirtableMcpDecision:
    """Central governance policy for future Airtable MCP/agent bridges.

    FinancePlus deliberately distinguishes record-level writes from structural
    changes. Reads are permitted. Record writes are staged by default and can
    only become directly executable after explicit configuration. Structural,
    interface and automation changes always require human approval.
    """
    normalized = (action or "").strip().lower()
    sensitivity = (sensitivity or "Interno").strip()

    if normalized in READ_ACTIONS:
        return AirtableMcpDecision(
            action=normalized,
            mode="read",
            allowed=True,
            requires_approval=False,
            reason="Operazione di sola lettura consentita dalla policy FinancePlus.",
        )

    if sensitivity == "Altamente riservato":
        return AirtableMcpDecision(
            action=normalized,
            mode="blocked",
            allowed=False,
            requires_approval=True,
            reason="Operazione bloccata su dati altamente riservati; richiesta revisione umana.",
        )

    if normalized in STRUCTURAL_ACTIONS:
        return AirtableMcpDecision(
            action=normalized,
            mode="staged",
            allowed=False,
            requires_approval=True,
            reason="Modifiche a schema, interfacce o automazioni Airtable richiedono sempre approvazione umana.",
        )

    if normalized in RECORD_WRITE_ACTIONS:
        direct_write = _truthy("FINANCEPLUS_AIRTABLE_MCP_RECORD_WRITE", default=False)
        if direct_write and sensitivity == "Interno":
            return AirtableMcpDecision(
                action=normalized,
                mode="write",
                allowed=True,
                requires_approval=False,
                reason="Write-back record abilitato esplicitamente per dati interni.",
            )
        return AirtableMcpDecision(
            action=normalized,
            mode="staged",
            allowed=False,
            requires_approval=True,
            reason="Write-back Airtable mantenuto in staging fino ad approvazione.",
        )

    return AirtableMcpDecision(
        action=normalized,
        mode="blocked",
        allowed=False,
        requires_approval=True,
        reason=f"Azione Airtable MCP non riconosciuta ({source}); principio deny-by-default.",
    )
