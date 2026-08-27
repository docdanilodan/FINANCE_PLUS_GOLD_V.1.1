from __future__ import annotations
from datetime import date

def build_dossier_markdown(client: dict, financial: dict | None = None, cr: dict | None = None, bank: dict | None = None) -> str:
    financial=financial or {}; cr=cr or {}; bank=bank or {}
    name=client.get('Cliente') or client.get('name') or 'Cliente da verificare'
    return f'''# FINANCE PLUS GOLD — DOSSIER BANCA\n\n**Cliente:** {name}  \n**Data:** {date.today().isoformat()}\n\n## 1. Executive Summary\nDossier generato da dati strutturati. I valori mancanti restano esplicitamente non disponibili.\n\n## 2. Anagrafica\n- P.IVA: {client.get('Partita IVA','N/D')}\n- CF: {client.get('Codice Fiscale','N/D')}\n- PEC: {client.get('PEC','N/D')}\n- ATECO: {client.get('ATECO','N/D')}\n\n## 3. Analisi economico-finanziaria\n- Rating: {financial.get('rating','N/D')}\n- Score: {financial.get('score','N/D')}\n- Data Quality: {financial.get('data_quality','N/D')}\n- KPI: {financial.get('metrics','N/D')}\n\n## 4. Centrale Rischi\n{cr if cr else 'Non disponibile / non analizzata.'}\n\n## 5. Conti correnti\n{bank if bank else 'Non disponibili / non analizzati.'}\n\n## 6. Conclusioni\nOgni giudizio definitivo richiede verifica professionale dei documenti sorgente e coerenza temporale dei dati.\n'''
