from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Callable

import pandas as pd
import streamlit as st

from services.gmail_drive_pipeline_v2 import sync_gmail_attachments
from services.mbox_archive_importer import classify_attachment_bundle, import_mbox, result_as_dict

DEFAULT_MBOX = "GHINZANI.mbox"
DEFAULT_ROOT = "data/archivio_smart"
MAX_INLINE_MB = 180


def _known_clients(db) -> list[str]:
    if db is None:
        return []
    try:
        records = db.list_records("clienti", max_records=5000)
    except Exception:
        return []
    result: list[str] = []
    for record in records:
        name = str(record.get("fields", {}).get("Cliente", "") or "").strip()
        if name and name not in result:
            result.append(name)
    return result


def _stage_upload(uploaded) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="financeplus_mbox_"))
    path = tmp / Path(uploaded.name or "upload.bin").name
    with path.open("wb") as fh:
        while True:
            chunk = uploaded.read(8 * 1024 * 1024)
            if not chunk:
                break
            fh.write(chunk)
    return path


def _download(label: str, raw: str, mime: str, key: str) -> None:
    if not raw:
        return
    path = Path(raw)
    if not path.exists() or not path.is_file():
        return
    size_mb = path.stat().st_size / 1024 / 1024
    if size_mb <= MAX_INLINE_MB:
        st.download_button(label, path.read_bytes(), path.name, mime, use_container_width=True, key=key)
    else:
        st.info(f"{path.name}: {size_mb:,.0f} MB. Creato sul server in `{path}`")


def _show_result(result: dict, key_prefix: str) -> None:
    metrics = st.columns(6)
    for col, key, label in zip(
        metrics,
        ["email_count", "attachment_count", "catalogued_count", "unclassified_count", "excluded_media_count", "duplicate_count"],
        ["Email", "Allegati", "Catalogati", "Da archiviare", "Foto/video esclusi", "Duplicati"],
    ):
        col.metric(label, int(result.get(key, 0) or 0))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _download("PDF email", str(result.get("email_pdf", "")), "application/pdf", f"{key_prefix}_email_pdf")
        _download("PDF allegati", str(result.get("attachment_pdf", "")), "application/pdf", f"{key_prefix}_att_pdf")
    with c2:
        _download("CSV email", str(result.get("email_csv", "")), "text/csv", f"{key_prefix}_email_csv")
        _download("CSV allegati", str(result.get("attachment_csv", "")), "text/csv", f"{key_prefix}_att_csv")
    with c3:
        _download("ZIP catalogati", str(result.get("catalogued_zip", "")), "application/zip", f"{key_prefix}_cat_zip")
    with c4:
        _download("ZIP da archiviare", str(result.get("unclassified_zip", "")), "application/zip", f"{key_prefix}_unc_zip")

    csv_path = Path(str(result.get("attachment_csv", "")))
    if not csv_path.exists():
        return
    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:
        st.warning(f"Catalogo creato; anteprima non disponibile: {exc}")
        return
    st.markdown("#### Ricerca nel catalogo")
    a, b = st.columns([2, 1])
    query = a.text_input("Cerca cliente, file, oggetto o mittente", key=f"{key_prefix}_query").strip().casefold()
    clients = ["Tutti"]
    if "Cliente" in df.columns:
        clients += sorted(df["Cliente"].dropna().astype(str).unique().tolist())
    client = b.selectbox("Cliente", clients, key=f"{key_prefix}_client")
    work = df
    if client != "Tutti" and "Cliente" in work.columns:
        work = work[work["Cliente"].astype(str) == client]
    if query:
        cols = [c for c in ["Cliente", "Nome file originale", "Oggetto email", "Mittente", "Estratto contenuto"] if c in work.columns]
        if cols:
            mask = work[cols].fillna("").astype(str).agg(" ".join, axis=1).str.casefold().str.contains(query, regex=False)
            work = work.loc[mask]
    st.dataframe(work.head(1000), use_container_width=True, hide_index=True)


def _bootstrap_google(profiles: dict[str, str], secret: Callable[[str, str], str]) -> None:
    token = secret("AIRTABLE_TOKEN", "")
    base_id = secret("AIRTABLE_BASE_ID", "")
    if token:
        os.environ["AIRTABLE_TOKEN"] = token
    if base_id:
        os.environ["AIRTABLE_BASE_ID"] = base_id
    drive_folder = secret("GOOGLE_DRIVE_FOLDER_ID", "")
    if drive_folder:
        os.environ["GOOGLE_DRIVE_FOLDER_ID"] = drive_folder
    for name, value in profiles.items():
        normalized = "".join(ch if ch.isalnum() else "_" for ch in name.upper()).strip("_")
        if value and normalized:
            os.environ[f"GOOGLE_OAUTH_TOKEN_JSON_{normalized}"] = value


def render_archive_smart(db, profiles: dict[str, str], secret: Callable[[str, str], str]) -> None:
    _bootstrap_google(profiles, secret)
    known_clients = _known_clients(db)

    st.subheader("📮 Archivio Smart / Posta")
    st.caption("MBOX → email e allegati → riconoscimento cliente → cartelle fisiche → PDF/CSV/ZIP → ricerca; più Gmail diretto.")
    s1, s2, s3 = st.columns(3)
    s1.info(f"Clienti CRM disponibili: {len(known_clients)}")
    s2.info(f"Profili Gmail disponibili: {len(profiles)}")
    s3.info("MBOX elaborato localmente sul server FinancePlus")

    tab_mbox, tab_export, tab_gmail = st.tabs(["📦 MBOX", "📎 Allegati esportati", "✉️ Gmail diretto"])

    with tab_mbox:
        st.markdown("### 1. Importazione MBOX")
        st.write("Per il tuo archivio puoi selezionare **GHINZANI.mbox** e premere **Importa e cataloga**. Con file multi-GB è preferibile il percorso locale/server per evitare il limite di upload del browser.")
        mode = st.radio("Sorgente", ["File .mbox", "Percorso locale/server"], horizontal=True, key="as_mbox_mode")
        uploaded = None
        local_path = DEFAULT_MBOX
        if mode == "File .mbox":
            uploaded = st.file_uploader("Seleziona GHINZANI.mbox", type=["mbox"], key="as_mbox_upload")
            if uploaded is not None:
                st.caption(f"{uploaded.name} — {uploaded.size / 1024 / 1024:,.1f} MB")
        else:
            local_path = st.text_input("Percorso MBOX", value=DEFAULT_MBOX, key="as_mbox_path")
        output_dir = st.text_input("Cartella di output", value=f"{DEFAULT_ROOT}/GHINZANI", key="as_mbox_output")
        o1, o2 = st.columns(2)
        exclude_media = o1.checkbox("Escludi foto/video dagli ZIP fisici", value=True, key="as_mbox_media")
        create_zips = o2.checkbox("Crea ZIP catalogati e DA_ARCHIVIARE", value=True, key="as_mbox_zip")

        if st.button("📥 Importa e cataloga", type="primary", use_container_width=True, key="as_mbox_run"):
            staged: Path | None = None
            try:
                if mode == "File .mbox":
                    if uploaded is None:
                        st.error("Seleziona prima il file .mbox.")
                        return
                    staged = _stage_upload(uploaded)
                    source = staged
                else:
                    source = Path(local_path).expanduser()
                bar = st.progress(0, text="Avvio importazione...")
                status = st.empty()

                def progress(email_no: int, attachment_no: int) -> None:
                    bar.progress(min(95, max(1, email_no % 96)), text=f"Email {email_no} • allegati {attachment_no}")
                    status.caption("Lettura in streaming: il file MBOX non viene caricato interamente in memoria.")

                result = import_mbox(
                    source,
                    output_dir,
                    known_clients=known_clients,
                    exclude_media_from_physical_archive=exclude_media,
                    create_zip_archives=create_zips,
                    progress=progress,
                )
                bar.progress(100, text="Importazione completata")
                st.session_state["archive_smart_mbox_result"] = result_as_dict(result)
                st.success("Archivio MBOX indicizzato e catalogato.")
            except Exception as exc:
                st.exception(exc)
            finally:
                if staged is not None:
                    shutil.rmtree(staged.parent, ignore_errors=True)
        if "archive_smart_mbox_result" in st.session_state:
            _show_result(st.session_state["archive_smart_mbox_result"], "as_mbox")

    with tab_export:
        st.markdown("### 2. Allegati esportati da MBOX Viewer")
        st.write("Carica lo ZIP esportato dall'app oppure indica una cartella/ZIP. FinancePlus prova a leggere PDF, DOCX, XLSX e testo per associare il cliente e crea cartelle con codice progressivo.")
        mode = st.radio("Sorgente allegati", ["ZIP", "Percorso cartella/ZIP"], horizontal=True, key="as_att_mode")
        uploaded = None
        local_path = ""
        if mode == "ZIP":
            uploaded = st.file_uploader("ZIP allegati", type=["zip"], key="as_att_upload")
        else:
            local_path = st.text_input("Percorso cartella o ZIP", key="as_att_path")
        output_dir = st.text_input("Cartella di output", value=f"{DEFAULT_ROOT}/ALLEGATI_GHINZANI", key="as_att_output")
        o1, o2 = st.columns(2)
        exclude_media = o1.checkbox("Escludi foto/video", value=True, key="as_att_media")
        create_zips = o2.checkbox("Crea ZIP finali", value=True, key="as_att_zip")
        if st.button("🗂️ Classifica allegati", type="primary", use_container_width=True, key="as_att_run"):
            staged: Path | None = None
            try:
                if mode == "ZIP":
                    if uploaded is None:
                        st.error("Carica prima lo ZIP degli allegati.")
                        return
                    staged = _stage_upload(uploaded)
                    source = staged
                else:
                    if not local_path.strip():
                        st.error("Indica il percorso della cartella o dello ZIP.")
                        return
                    source = Path(local_path).expanduser()
                bar = st.progress(0, text="Analisi allegati...")

                def progress(current: int, total: int) -> None:
                    bar.progress(int(current / max(total, 1) * 100), text=f"Allegato {current}/{total}")

                result = classify_attachment_bundle(
                    source,
                    output_dir,
                    known_clients=known_clients,
                    exclude_media_from_physical_archive=exclude_media,
                    create_zip_archives=create_zips,
                    progress=progress,
                )
                st.session_state["archive_smart_attachment_result"] = result_as_dict(result)
                st.success("Allegati classificati.")
            except Exception as exc:
                st.exception(exc)
            finally:
                if staged is not None:
                    shutil.rmtree(staged.parent, ignore_errors=True)
        if "archive_smart_attachment_result" in st.session_state:
            _show_result(st.session_state["archive_smart_attachment_result"], "as_att")

    with tab_gmail:
        st.markdown("### 3. Gmail diretto")
        st.write("Usa la pipeline Gmail → classificazione → Drive → Airtable già prevista in FinancePlus, con deduplica SHA-256 e associazione cliente/pratica.")
        if db is None:
            st.warning("Configura AIRTABLE_TOKEN.")
        if not profiles:
            st.warning("Configura almeno un profilo Google OAuth nei Secrets FinancePlus.")
        profile = st.selectbox("Profilo Gmail", list(profiles) if profiles else ["Non configurato"], key="as_gmail_profile")
        query = st.text_input("Query Gmail", value="has:attachment -in:spam -in:trash", key="as_gmail_query")
        c1, c2 = st.columns(2)
        max_messages = int(c1.number_input("Messaggi massimi per ciclo", 1, 500, 50, 10, key="as_gmail_max"))
        folder = c2.text_input("Drive folder ID (opzionale)", value=secret("GOOGLE_DRIVE_FOLDER_ID", ""), key="as_gmail_folder")
        disabled = db is None or not profiles
        if st.button("🔄 Sincronizza Gmail ora", type="primary", use_container_width=True, disabled=disabled, key="as_gmail_run"):
            try:
                os.environ["GOOGLE_OAUTH_TOKEN_JSON"] = profiles[profile]
                result = sync_gmail_attachments(query=query.strip() or "has:attachment -in:spam -in:trash", drive_folder_id=folder.strip() or None, max_messages=max_messages)
                st.session_state["archive_smart_gmail_result"] = result
                st.success("Sincronizzazione Gmail completata.")
            except Exception as exc:
                st.exception(exc)
        if "archive_smart_gmail_result" in st.session_state:
            result = st.session_state["archive_smart_gmail_result"]
            metrics = st.columns(6)
            for col, key, label in zip(metrics, ["messages", "attachments", "uploaded", "duplicates", "matched", "pending_review"], ["Messaggi", "Allegati", "Caricati", "Duplicati", "Associati", "Da verificare"]):
                col.metric(label, int(result.get(key, 0) or 0))
            if result.get("errors"):
                st.warning(f"Errori: {len(result['errors'])}")
                st.json(result["errors"][:20])
            with st.expander("Dettaglio tecnico"):
                st.json(result)
