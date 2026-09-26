from __future__ import annotations

def build_status_markdown(status_rows: list[dict]) -> str:
    lines=["# APP_NUOVA_SETT_IA_00 MASTER — Stato build","","| Modulo | Stato | Note |","|---|---|---|"]
    for r in status_rows: lines.append(f"| {r.get('module','')} | {r.get('status','')} | {r.get('notes','')} |")
    return "\n".join(lines)
