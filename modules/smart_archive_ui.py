from __future__ import annotations

import re
from typing import Any, Callable

import pandas as pd
import streamlit as st
from googleapiclient.discovery import build

from document_ai import RULES
from services.google_auth import load_credentials_json
from services.smart_archive import (
    SmartArchivePreview,
    analyze_smart_document,
    archive_smart_document,
)

SUPPORTED_UPLOADS = [
    "pdf",
    "jpg",
    "jpeg",
    "png",
    "tif",
    "tiff",
    "webp",
    "heic",
    "heif",
    "txt",
    "csv",
    "md",
    "json",
    "xml",
    "docx",
    "xlsx",
    "xlsm",
    "pptx",
]
CATEGORIES = list(dict.fromkeys([category for category, _ in RULES] + ["Altro"]))


def _records_df(records: list[dict]) -> pd.DataFrame:
    rows = []
    for record in records or []:
        row = {"Record ID": record.get("id", "")}
        row.update(record.get("fields", {}))
        rows.append(row)
    return pd.DataFrame(rows)


def _load_catalog(db) -> tuple[list[dict], list[dict]]:
    if not db:
        return [], []
    return (
        db.list_records("clienti", max_records=5000),
        db.list_records("pratiche", max_records=5000),
    )


def _client_label(record: dict) -> str:
    fields = record.get("fields", {})
    name = str(fields.get("Cliente", record.get("id", "Cliente")))
    vat = str(fields.get("Partita IVA", "") or "")
    return f"{name} — P.IVA {vat}" if vat else name


def _practice_belongs_to(practice: dict, client_id: str, client_name: str) -> bool:
    fields = practice.get("fields", {})
    linked = fields.get("Cliente collegato", [])
    if client_id and isinstance(linked, list) and client_id in linked:
        return True
    return bool(
        client_name
        and str(fields.get("Cliente", "")).casefold() == client_name.casefold()
    )


def _review_controls(
    item: dict[str, Any],
    index: int,
    clients: list[dict],
    practices: list[dict],
) -> dict[str, Any]:
    preview: SmartArchivePreview = item["preview"]
    client_by_id = {record["id"]: record for record in clients}
    client_options = [""] + list(client_by_id)
    default_client = preview.client_id if preview.client_id in client_by_id else ""

    with st.expander(
        f"{index + 1}. {preview.original_name} — {preview.document_type}",
        expanded=bool(preview.warnings or preview.duplicate_record_id),
    ):
        a, b, c, d = st.columns(4)
        a.metric("Confidenza", f"{preview.confidence:.0%}")
        b.metric(
            "Testo OCR", f"{preview.extracted_chars:,}".replace(",", ".") + " caratteri"
        )
        c.metric("Privacy", preview.sensitivity)
        d.metric("Duplicato", "Sì" if preview.duplicate_record_id else "No")

        if preview.duplicate_record_id:
            st.error(
                "Documento già presente: il duplicato SHA-256 non verrà caricato di nuovo."
            )
            if preview.duplicate_url:
                st.link_button("Apri documento esistente", preview.duplicate_url)
        if preview.warnings:
            st.warning(" • ".join(preview.warnings))

        a, b = st.columns(2)
        category = a.selectbox(
            "Categoria verificata",
            CATEGORIES,
            index=CATEGORIES.index(preview.category)
            if preview.category in CATEGORIES
            else len(CATEGORIES) - 1,
            key=f"smart_category_{preview.sha256}_{index}",
            disabled=bool(preview.duplicate_record_id),
        )
        year = b.number_input(
            "Esercizio/anno",
            min_value=0,
            max_value=2100,
            value=int(preview.document_year or 0),
            key=f"smart_year_{preview.sha256}_{index}",
            disabled=bool(preview.duplicate_record_id),
        )

        chosen_client = st.selectbox(
            "Cliente",
            client_options,
            index=client_options.index(default_client),
            format_func=lambda record_id: (
                "— Da verificare —"
                if not record_id
                else _client_label(client_by_id[record_id])
            ),
            key=f"smart_client_{preview.sha256}_{index}",
            disabled=bool(preview.duplicate_record_id),
        )
        chosen_client_name = (
            str(client_by_id[chosen_client].get("fields", {}).get("Cliente", ""))
            if chosen_client
            else ""
        )

        compatible_practices = [
            practice
            for practice in practices
            if _practice_belongs_to(practice, chosen_client, chosen_client_name)
        ]
        practice_by_id = {practice["id"]: practice for practice in compatible_practices}
        practice_options = [""] + list(practice_by_id)
        default_practice = (
            preview.practice_id if preview.practice_id in practice_by_id else ""
        )
        chosen_practice = st.selectbox(
            "Pratica (opzionale)",
            practice_options,
            index=practice_options.index(default_practice),
            format_func=lambda record_id: (
                "— Nessuna pratica —"
                if not record_id
                else str(
                    practice_by_id[record_id]
                    .get("fields", {})
                    .get("Pratica ID", record_id)
                )
            ),
            key=f"smart_practice_{preview.sha256}_{index}_{chosen_client}",
            disabled=bool(preview.duplicate_record_id),
        )
        practice_code = (
            str(practice_by_id[chosen_practice].get("fields", {}).get("Pratica ID", ""))
            if chosen_practice
            else ""
        )
        final_name = st.text_input(
            "Nome definitivo",
            value=preview.proposed_name,
            key=f"smart_name_{preview.sha256}_{index}",
            disabled=bool(preview.duplicate_record_id),
        )
        include = st.checkbox(
            "Archivia questo documento",
            value=not bool(preview.duplicate_record_id),
            key=f"smart_include_{preview.sha256}_{index}",
            disabled=bool(preview.duplicate_record_id),
        )

    return {
        "include": include and not preview.duplicate_record_id,
        "client_id": chosen_client or None,
        "client_name": chosen_client_name or None,
        "practice_id": chosen_practice or None,
        "practice_code": practice_code or None,
        "category": category,
        "document_year": int(year) or None,
        "final_name": final_name.strip() or preview.original_name,
    }


def _render_intake(
    db, profiles: dict[str, str], drive_folder_ids: dict[str, str]
) -> None:
    st.markdown("### 📥 Acquisizione intelligente")
    st.caption(
        "Dal telefono puoi caricare file o scattare una foto. OCR, riconoscimento, deduplica e abbinamento "
        "Cliente/Pratica avvengono prima dell'archiviazione definitiva."
    )
    if not db:
        st.warning(
            "Configura AIRTABLE_TOKEN: l'analisi locale è disponibile, ma l'archiviazione è disabilitata."
        )
    if not profiles:
        st.warning(
            "Configura almeno un profilo Google per salvare i documenti su Drive."
        )

    flash = st.session_state.pop("smart_archive_flash", None)
    if flash:
        message, level = flash
        getattr(st, level)(message)

    a, b = st.columns(2)
    profile = a.selectbox(
        "Profilo Google/Drive", list(profiles) if profiles else ["Non configurato"]
    )
    root_folder = b.text_input(
        "Cartella radice Drive (opzionale)",
        value=drive_folder_ids.get(profile, ""),
        key=f"smart_drive_root_{profile}",
    )
    uploads = st.file_uploader(
        "Carica documenti da PC o cellulare",
        type=SUPPORTED_UPLOADS,
        accept_multiple_files=True,
        key="smart_archive_uploads",
    )
    camera = st.camera_input(
        "Oppure fotografa un documento", key="smart_archive_camera"
    )

    if st.button("1️⃣ Analizza e riconosci", type="primary", use_container_width=True):
        sources: list[tuple[str, Any]] = [
            ("Upload PC/cellulare", upload) for upload in uploads or []
        ]
        if camera is not None:
            sources.append(("Fotocamera cellulare", camera))
        if not sources:
            st.warning("Seleziona almeno un documento o scatta una foto.")
        else:
            try:
                analysis_clients, analysis_practices = _load_catalog(db)
            except Exception as exc:
                st.warning(f"Matching Cliente/Pratica non disponibile: {exc}")
                analysis_clients, analysis_practices = [], []
            batch = []
            seen: dict[str, str] = {}
            progress = st.progress(0, text="Analisi documenti in corso…")
            for index, (source, uploaded) in enumerate(sources):
                raw = uploaded.getvalue()
                preview = analyze_smart_document(
                    raw,
                    uploaded.name,
                    getattr(uploaded, "type", "") or "",
                    airtable=db,
                    source=source,
                    clients=analysis_clients,
                    practices=analysis_practices,
                )
                if preview.sha256 in seen:
                    preview.duplicate_record_id = f"batch:{preview.sha256}"
                    preview.warnings.append(
                        f"Duplicato nel caricamento: già presente come {seen[preview.sha256]}"
                    )
                else:
                    seen[preview.sha256] = preview.original_name
                batch.append({"preview": preview, "raw": raw})
                progress.progress(
                    (index + 1) / len(sources),
                    text=f"Analizzato {index + 1}/{len(sources)}",
                )
            progress.empty()
            st.session_state["smart_archive_batch"] = batch
            st.success(
                f"Analisi completata: {len(batch)} documenti pronti per la verifica."
            )

    batch = st.session_state.get("smart_archive_batch", [])
    if not batch:
        st.info(
            "I documenti analizzati appariranno qui prima del salvataggio definitivo."
        )
        return

    previews = [item["preview"] for item in batch]
    overview = pd.DataFrame(
        [
            {
                "File": preview.original_name,
                "Tipo": preview.document_type,
                "Cliente proposto": preview.client_name or "Da verificare",
                "Pratica": preview.practice_code or "—",
                "Anno": preview.document_year or "—",
                "Confidenza": f"{preview.confidence:.0%}",
                "OCR": preview.extraction_method,
                "Duplicato": "Sì" if preview.duplicate_record_id else "No",
            }
            for preview in previews
        ]
    )
    st.dataframe(overview, use_container_width=True, hide_index=True)

    try:
        clients, practices = _load_catalog(db)
    except Exception as exc:
        st.error(f"Impossibile caricare Clienti/Pratiche da Airtable: {exc}")
        clients, practices = [], []

    st.markdown("### ✅ Verifica prima dell'archiviazione")
    choices = [
        _review_controls(item, index, clients, practices)
        for index, item in enumerate(batch)
    ]
    selected = sum(1 for choice in choices if choice["include"])
    confirmation = st.checkbox(
        f"Confermo categoria, cliente e nome dei {selected} documenti selezionati",
        disabled=selected == 0,
    )
    archive_disabled = not (db and profiles and confirmation and selected)
    if st.button(
        "2️⃣ Archivia su Drive e indicizza in Airtable",
        type="primary",
        use_container_width=True,
        disabled=archive_disabled,
    ):
        try:
            credentials = load_credentials_json(profiles[profile], profile)
            drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
        except Exception as exc:
            st.error(f"Connessione Google Drive non riuscita: {exc}")
            return

        remaining = []
        results = []
        progress = st.progress(0, text="Archiviazione in corso…")
        selected_items = [
            (item, choice) for item, choice in zip(batch, choices) if choice["include"]
        ]
        unselected_ids = {
            id(item) for item, choice in zip(batch, choices) if not choice["include"]
        }
        for index, (item, choice) in enumerate(selected_items):
            preview = item["preview"]
            try:
                result = archive_smart_document(
                    preview,
                    item["raw"],
                    db,
                    drive,
                    root_folder or None,
                    **{key: value for key, value in choice.items() if key != "include"},
                )
                results.append(result)
            except Exception as exc:
                preview.warnings.append(f"Archiviazione non riuscita: {exc}")
                remaining.append(item)
            progress.progress(
                (index + 1) / len(selected_items),
                text=f"Archiviato {index + 1}/{len(selected_items)}",
            )
        progress.empty()
        remaining.extend(item for item in batch if id(item) in unselected_ids)
        st.session_state["smart_archive_batch"] = remaining
        archived = sum(result.get("status") == "archived" for result in results)
        duplicates = sum(result.get("status") == "duplicate" for result in results)
        messages = []
        if archived:
            messages.append(
                f"{archived} documenti archiviati su Drive e indicizzati in Airtable"
            )
        if duplicates:
            messages.append(
                f"{duplicates} duplicati intercettati al momento del salvataggio"
            )
        if remaining:
            messages.append(f"{len(remaining)} documenti restano in verifica")
        else:
            st.session_state.pop("smart_archive_batch", None)
        st.session_state["smart_archive_flash"] = (
            ". ".join(messages) + ".",
            "warning" if remaining else "success",
        )
        st.rerun()


def _render_archive_table(db, only_review: bool = False) -> None:
    title = "⚠️ Coda da verificare" if only_review else "🔎 Archivio e ricerca"
    st.markdown(f"### {title}")
    if not db:
        st.warning("Airtable non autenticato.")
        return
    try:
        df = _records_df(db.list_records("documenti", max_records=5000))
    except Exception as exc:
        st.error(f"Lettura archivio non riuscita: {exc}")
        return
    if df.empty:
        st.info("Archivio vuoto.")
        return

    if only_review:
        status = (
            df.get("Stato Verifica", pd.Series("", index=df.index))
            .fillna("")
            .astype(str)
        )
        client = df.get("Cliente", pd.Series("", index=df.index)).fillna("").astype(str)
        df = df[status.str.casefold().ne("verificato") | client.str.strip().eq("")]
        if df.empty:
            st.success("Nessun documento in attesa di verifica.")
            return

    c1, c2, c3, c4 = st.columns(4)
    query = c1.text_input("Cerca", key=f"smart_search_{only_review}").strip().casefold()
    types = sorted(
        {
            str(value)
            for value in df.get("Tipo Documento", pd.Series(dtype=str)).dropna()
            if str(value).strip()
        }
    )
    origins = sorted(
        {
            str(value)
            for value in df.get("Origine", pd.Series(dtype=str)).dropna()
            if str(value).strip()
        }
    )
    statuses = sorted(
        {
            str(value)
            for value in df.get("Stato Verifica", pd.Series(dtype=str)).dropna()
            if str(value).strip()
        }
    )
    doc_type = c2.selectbox("Tipo", ["Tutti"] + types, key=f"smart_type_{only_review}")
    origin = c3.selectbox(
        "Origine", ["Tutte"] + origins, key=f"smart_origin_{only_review}"
    )
    verification = c4.selectbox(
        "Stato", ["Tutti"] + statuses, key=f"smart_status_{only_review}"
    )
    work = df.copy()
    if query:
        work = work[
            work.astype(str)
            .agg(" ".join, axis=1)
            .str.casefold()
            .str.contains(re.escape(query), regex=True, na=False)
        ]
    if doc_type != "Tutti" and "Tipo Documento" in work:
        work = work[work["Tipo Documento"].astype(str).eq(doc_type)]
    if origin != "Tutte" and "Origine" in work:
        work = work[work["Origine"].astype(str).eq(origin)]
    if verification != "Tutti" and "Stato Verifica" in work:
        work = work[work["Stato Verifica"].astype(str).eq(verification)]

    a, b, c = st.columns(3)
    a.metric("Documenti", len(work))
    b.metric(
        "Senza cliente",
        int(
            work.get("Cliente", pd.Series("", index=work.index))
            .fillna("")
            .astype(str)
            .str.strip()
            .eq("")
            .sum()
        ),
    )
    c.metric(
        "Da verificare",
        int(
            work.get("Stato Verifica", pd.Series("", index=work.index))
            .fillna("")
            .astype(str)
            .str.casefold()
            .ne("verificato")
            .sum()
        ),
    )
    wanted = [
        column
        for column in [
            "Cliente",
            "Pratica ID",
            "Documento",
            "Tipo Documento",
            "Esercizio",
            "Data Documento",
            "Origine",
            "Stato Verifica",
            "Sensibilità dati",
            "Nome Originale",
            "Nome Definitivo",
            "URL Drive",
            "SHA-256",
        ]
        if column in work.columns
    ]
    st.dataframe(
        work[wanted],
        use_container_width=True,
        hide_index=True,
        column_config={
            "URL Drive": st.column_config.LinkColumn("Drive", display_text="Apri")
        },
    )


def render_smart_archive(
    db,
    profiles: dict[str, str],
    secret: Callable[[str, str], str],
) -> None:
    st.subheader("🗂️ Archivio Smart")
    st.caption(
        "Scansione mobile • OCR locale • classificazione • Cliente/Pratica • Drive • Airtable • SHA-256"
    )
    drive_folder_ids = {}
    for profile in profiles:
        key = (
            "GOOGLE_DRIVE_FOLDER_ID"
            if profile == "PRINCIPALE"
            else f"GOOGLE_DRIVE_FOLDER_ID_{profile}"
        )
        drive_folder_ids[profile] = secret(key, "")
    intake, archive, review = st.tabs(
        ["📥 Acquisisci", "🔎 Archivio", "⚠️ Da verificare"]
    )
    with intake:
        _render_intake(db, profiles, drive_folder_ids)
    with archive:
        _render_archive_table(db, only_review=False)
    with review:
        _render_archive_table(db, only_review=True)
