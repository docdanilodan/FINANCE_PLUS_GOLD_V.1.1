from pathlib import Path

app_path = Path("FinancePlus_Airtable/streamlit_app.py")
readme_path = Path("FinancePlus_Airtable/README.md")

app = app_path.read_text(encoding="utf-8")
readme = readme_path.read_text(encoding="utf-8")

client_import = "from client_fascicolo import build_client_fascicolo_pdf, safe_fascicolo_filename\n"
if client_import not in app:
    marker = "from airtable_client import AirtableAPIError, AirtableClient\n"
    if marker not in app:
        raise SystemExit("Import AirtableClient non trovato")
    app = app.replace(marker, marker + client_import, 1)

ui_marker = "    tab_anagrafica, tab_pratiche, tab_documenti, tab_email, tab_analisi = st.tabs(\n"
ui_block = '''    st.markdown("#### 📁 Fascicolo Cliente PDF")
    st.caption(
        "Genera un unico dossier con anagrafica, documenti, pratiche, documenti mancanti, email e analisi creditizie."
    )
    fascicolo_bytes = build_client_fascicolo_pdf(
        row.to_dict(),
        documenti,
        pratiche,
        email,
        analisi,
    )
    st.download_button(
        "📁 Scarica Fascicolo Cliente PDF",
        data=fascicolo_bytes,
        file_name=safe_fascicolo_filename(selected_name),
        mime="application/pdf",
        key=f"download_fascicolo_pdf_{selected_record_id}",
        use_container_width=True,
    )
    st.caption(
        f"Contenuto: {len(documenti)} documenti · {len(pratiche)} pratiche · "
        f"{len(email)} email · {len(analisi)} analisi creditizie."
    )

'''
if "download_fascicolo_pdf_" not in app:
    if ui_marker not in app:
        raise SystemExit("Punto di inserimento Fascicolo Cliente non trovato")
    app = app.replace(ui_marker, ui_block + ui_marker, 1)

readme_marker = "## Fascicolo Cliente PDF"
if readme_marker not in readme:
    readme += '''

## Fascicolo Cliente PDF

Dalla scheda **Clienti** e disponibile il pulsante **Scarica Fascicolo Cliente PDF**. Il dossier viene generato al momento dai record Airtable collegati e comprende:

- anagrafica camerale e dati identificativi;
- rating, ultimo bilancio, Centrale Rischi e stato verifica;
- conteggio documenti per categoria e archivio documentale completo con link Drive;
- pratiche, stato documentazione, completezza, documenti mancanti, prossime azioni, scadenze e alert;
- email collegate con priorita, azione richiesta, allegati e sintesi IA;
- analisi creditizie con KPI, score, rating, importi sostenibili, punti di forza, criticita e raccomandazioni.

I campi non presenti restano indicati con `—`: il Fascicolo Cliente non ricostruisce o inventa dati mancanti.
'''

app_path.write_text(app, encoding="utf-8")
readme_path.write_text(readme, encoding="utf-8")
