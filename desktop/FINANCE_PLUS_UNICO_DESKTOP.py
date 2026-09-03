#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FINANCE_PLUS_UNICO DESKTOP V1.0
Desktop edition of FinancePlus for Windows/macOS/Linux.
Local-first: SQLite + local archive. Optional cloud integrations can be enabled in Configurazione.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import sqlite3
import sys
import textwrap
import threading
import time
import webbrowser
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME = "FINANCE_PLUS_UNICO DESKTOP"
APP_VERSION = "1.1"
NAVY = "#0E2F5A"
BLUE = "#0F5EA8"
COPPER = "#B87333"
BG = "#F4F7FB"
CARD = "#FFFFFF"
TEXT = "#1D2A38"
MUTED = "#6B7787"
BORDER = "#DDE4EC"
GREEN = "#2E7D32"
AMBER = "#B26A00"
RED = "#B3261E"


def default_data_dir() -> Path:
    if sys.platform.startswith("win"):
        root = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or str(Path.home())
        return Path(root) / "FinancePlusUnico"
    return Path.home() / ".financeplus_unico"


def euro(value: Any) -> str:
    try:
        n = float(value or 0)
        s = f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"€ {s}"
    except Exception:
        return "—"


def pct(value: Any, decimals: int = 1) -> str:
    try:
        return f"{float(value) * 100:.{decimals}f}%".replace(".", ",")
    except Exception:
        return "N/D"


def safe_filename(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", str(text or "file")).strip("_")
    return text or "file"


def parse_num(raw: Any) -> float | None:
    text = str(raw or "").strip().replace("€", "").replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def open_path(path: str | Path) -> None:
    p = str(path)
    try:
        if sys.platform.startswith("win"):
            os.startfile(p)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{p}"')
        else:
            os.system(f'xdg-open "{p}" >/dev/null 2>&1 &')
    except Exception as exc:
        messagebox.showerror("Apertura file", str(exc))


@dataclass
class Classification:
    category: str
    confidence: float
    company: str = ""
    year: int | None = None


CLASS_RULES = [
    ("Visura camerale", ["visura", "camera di commercio", "registro imprese", "rea"]),
    ("Bilancio", ["bilancio", "stato patrimoniale", "conto economico", "nota integrativa", "situazione contabile"]),
    ("Centrale Rischi", ["centrale rischi", "banca d'italia", "rischi", "accordato operativo", "utilizzato"]),
    ("Estratto conto", ["estratto conto", "movimenti", "saldo contabile", "saldo disponibile"]),
    ("DURC", ["durc", "regolarità contributiva", "inps", "inail"]),
    ("Fattura", ["fattura", "invoice", "imponibile", "iva"]),
    ("Contratto", ["contratto", "accordo", "scrittura privata", "fornitura"]),
    ("Preventivo / Offerta", ["preventivo", "offerta", "quotazione", "proposal"]),
    ("Business Plan", ["business plan", "piano industriale", "forecast", "proiezione"]),
    ("Curriculum", ["curriculum", "esperienza professionale", "istruzione", "cv"]),
]


def classify_text(text: str, filename: str = "") -> Classification:
    corpus = f"{filename}\n{text}".lower()
    best_cat = "Altro"
    best_hits = 0
    for category, terms in CLASS_RULES:
        hits = sum(1 for term in terms if term in corpus)
        if hits > best_hits:
            best_cat = category
            best_hits = hits
    confidence = min(0.98, 0.45 + best_hits * 0.16) if best_hits else 0.35
    company = ""
    m = re.search(r"\b([A-ZÀ-Ü][A-ZÀ-Ü0-9&'. -]{3,80}\b(?:SRL|S\.R\.L\.|SPA|S\.P\.A\.|SNC|SAS))\b", text.upper())
    if m:
        company = re.sub(r"\s+", " ", m.group(1)).strip()
    y = None
    years = re.findall(r"\b(20\d{2})\b", corpus)
    if years:
        y = max(int(v) for v in years)
    return Classification(best_cat, confidence, company, y)


def suggested_name(c: Classification, original: str) -> str:
    ext = Path(original).suffix or ".pdf"
    company = safe_filename(c.company or "Documento")
    cat = safe_filename(c.category)
    year = str(c.year or datetime.now().year)
    return f"{company}_{cat}_{year}{ext}"


def extract_text_from_file(path: Path) -> tuple[str, str]:
    ext = path.suffix.lower()
    try:
        if ext in {".txt", ".csv", ".md", ".json", ".xml"}:
            return path.read_text(encoding="utf-8", errors="replace")[:200000], ""
        if ext == ".pdf":
            try:
                from pypdf import PdfReader
            except Exception:
                return "", "Installa pypdf per leggere il testo dei PDF."
            reader = PdfReader(str(path))
            text = "\n".join((p.extract_text() or "") for p in reader.pages)
            return text[:300000], "" if text.strip() else "PDF senza testo estraibile: possibile scansione."
    except Exception as exc:
        return "", str(exc)
    return "", "Formato non estratto automaticamente."


class Store:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir = self.data_dir / "archive"
        self.output_dir = self.data_dir / "output"
        self.archive_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        self.db_path = self.data_dir / "financeplus.db"
        self.config_path = self.data_dir / "config.json"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._schema()

    def _schema(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS clients(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL, vat TEXT, cf TEXT, pec TEXT, rea TEXT,
          legal_form TEXT, address TEXT, city TEXT, province TEXT,
          ateco TEXT, activity TEXT, administrator TEXT, notes TEXT,
          rating TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS practices(
          id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER,
          code TEXT, type TEXT, bank TEXT, amount REAL, status TEXT,
          priority TEXT, owner TEXT, next_action TEXT, due_date TEXT,
          missing_docs TEXT, completeness REAL DEFAULT 0,
          alerts TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS documents(
          id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER,
          title TEXT, doc_type TEXT, year TEXT, doc_date TEXT, origin TEXT,
          verify_status TEXT, original_name TEXT, definitive_name TEXT,
          path TEXT, sha256 TEXT UNIQUE, sensitivity TEXT DEFAULT 'Interno',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS emails(
          id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER,
          dt TEXT, sender TEXT, subject TEXT, priority TEXT, action_required TEXT,
          attachments INTEGER DEFAULT 0, managed TEXT DEFAULT 'No', ai_summary TEXT
        );
        CREATE TABLE IF NOT EXISTS analyses(
          id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER,
          dt TEXT, year TEXT, revenue REAL, ebitda REAL, pfn REAL,
          pfn_ebitda REAL, dscr REAL, score REAL, rating TEXT,
          sustainable_min REAL, sustainable_max REAL,
          strengths TEXT, weaknesses TEXT, recommendations TEXT
        );
        CREATE TABLE IF NOT EXISTS mandates(
          id INTEGER PRIMARY KEY AUTOINCREMENT, dt TEXT, client TEXT, practice TEXT,
          requested REAL, approved REAL, fee_pct REAL, fixed REAL,
          vat REAL, withholding REAL, fee_base REAL, taxable_fee REAL,
          total_due REAL
        );
        """)
        self.conn.commit()

    def q(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return list(self.conn.execute(sql, tuple(params)).fetchall())

    def one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, tuple(params)).fetchone()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        cur = self.conn.execute(sql, tuple(params))
        self.conn.commit()
        return int(cur.lastrowid or 0)

    def load_config(self) -> dict[str, Any]:
        defaults = {
            "airtable_token": "", "airtable_base_id": "appoNJtS64JIcZUhT",
            "google_oauth_token_json": "", "google_drive_folder_id": "",
            "openai_api_key": "", "adobe_client_id": "", "adobe_client_secret": "",
            "allow_adobe_confidential": False, "archive_dir": str(self.archive_dir),
        }
        try:
            if self.config_path.exists():
                defaults.update(json.loads(self.config_path.read_text(encoding="utf-8")))
        except Exception:
            pass
        return defaults

    def save_config(self, cfg: dict[str, Any]):
        self.config_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    def seed_demo(self):
        if self.one("SELECT id FROM clients LIMIT 1"):
            return
        c1 = self.execute("INSERT INTO clients(name,vat,cf,pec,rea,legal_form,address,city,province,ateco,activity,administrator,notes,rating) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("ACME INDUSTRIA SRL","01234567890","01234567890","acme@pec.example.it","CE-123456","SRL","Via Innovazione 25","Caserta","CE","25.62.00","Lavorazioni meccaniche di precisione","Mario Rossi","Cliente demo per guida illustrata","BBB"))
        c2 = self.execute("INSERT INTO clients(name,vat,pec,city,province,ateco,administrator,rating) VALUES (?,?,?,?,?,?,?,?)",
            ("OMEGA TECH SRL","09876543210","omega@pec.example.it","Napoli","NA","62.01.00","Laura Bianchi","A"))
        self.execute("INSERT INTO practices(client_id,code,type,bank,amount,status,priority,owner,next_action,due_date,missing_docs,completeness,alerts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (c1,"FP-2026-014","Finanziamento","Intesa Sanpaolo",500000,"In istruttoria","Alta","D. D'Angelo","Integrazione documentale","05/09/2026","Bilancio 2025 definitivo",82,"CR aggiornata richiesta"))
        self.execute("INSERT INTO practices(client_id,code,type,bank,amount,status,priority,owner,next_action,due_date,missing_docs,completeness,alerts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (c1,"FP-2026-009","Factoring","Banca IFIS",250000,"Integrazione","Media","D. D'Angelo","Invio integrazione","03/09/2026","Contratto cliente",91,""))
        demo_docs = [
            ("Bilancio 2025.pdf","Bilancio","2025","30/06/2026","Gmail","Verificato","bilancio.pdf","ACME_Bilancio_2025.pdf"),
            ("CR 07-2026.pdf","Centrale Rischi","2026","31/07/2026","Drive","Verificato","cr.pdf","ACME_CR_2026-07.pdf"),
            ("Visura camerale.pdf","Visura camerale","2026","18/08/2026","Upload","Da verificare","visura.pdf","ACME_Visura_2026.pdf"),
        ]
        for i,d in enumerate(demo_docs):
            fake = self.archive_dir / d[7]
            fake.write_text(f"Documento dimostrativo {d[0]}", encoding="utf-8")
            self.execute("INSERT OR IGNORE INTO documents(client_id,title,doc_type,year,doc_date,origin,verify_status,original_name,definitive_name,path,sha256,sensitivity) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (c1,*d,str(fake),hashlib.sha256(f"demo{i}".encode()).hexdigest(),"Interno" if i<2 else "Riservato"))
        self.execute("INSERT INTO emails(client_id,dt,sender,subject,priority,action_required,attachments,managed,ai_summary) VALUES (?,?,?,?,?,?,?,?,?)",
            (c1,"31/08/2026 10:42","banca@example.it","Integrazione pratica FP-2026-014","Alta","Inviare bilancio definitivo",2,"No","Richiesta integrazione entro 5 settembre"))
        self.execute("INSERT INTO emails(client_id,dt,sender,subject,priority,action_required,attachments,managed,ai_summary) VALUES (?,?,?,?,?,?,?,?,?)",
            (c1,"30/08/2026 16:12","cliente@example.it","Documenti contabili aggiornati","Media","Archiviare allegati",3,"Sì","Ricevuti documenti contabili aggiornati"))
        self.execute("INSERT INTO analyses(client_id,dt,year,revenue,ebitda,pfn,pfn_ebitda,dscr,score,rating,sustainable_min,sustainable_max,strengths,weaknesses,recommendations) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (c1,"31/08/2026","2025",5500000,825000,1100000,1.33,1.41,78,"BBB",350000,650000,"Marginalità positiva; DSCR > 1,2x","Capitale circolante da presidiare","Ridurre DSO e mantenere buffer di liquidità"))


class ScrollFrame(ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.window = self.canvas.create_window((0,0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window, width=e.width))
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", self._wheel)

    def _wheel(self, event):
        try: self.canvas.yview_scroll(int(-event.delta/120), "units")
        except Exception: pass


class FinancePlusApp:
    NAV = [
        ("dashboard", "Dashboard"),
        ("clients", "Clienti"),
        ("documents", "Documenti"),
        ("docai", "Document AI"),
        ("gmail", "Gmail & Drive"),
        ("analytics", "Analytics"),
        ("cr", "Centrale Rischi"),
        ("bank", "Conti Correnti"),
        ("bp", "Business Plan"),
        ("dossier", "Dossier Banca"),
        ("mandates", "Mandati"),
        ("config", "Configurazione"),
    ]

    def __init__(self, root: tk.Tk, store: Store, initial_screen="dashboard", demo=False):
        self.root = root
        self.store = store
        self.demo = demo
        self.initial_screen = initial_screen
        self.current_page = "dashboard"
        self.selected_client_id: int | None = None
        self.last_analysis: dict[str, Any] = {}
        self.last_cr: dict[str, Any] = {}
        self.last_bank: dict[str, Any] = {}
        self.last_bp: list[dict[str, Any]] = []
        self.docai_paths: list[Path] = []
        self.cfg = store.load_config()
        if demo:
            store.seed_demo()
        self._style()
        self._layout()
        self.navigate(initial_screen.split("_")[0] if initial_screen else "dashboard")
        self.root.after(250, self._apply_initial_state)

    def _style(self):
        self.root.title(f"{APP_NAME} V{APP_VERSION}")
        self.root.geometry("1600x960")
        self.root.minsize(1200, 760)
        self.root.configure(bg=BG)
        style = ttk.Style()
        try: style.theme_use("clam")
        except Exception: pass
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD, relief="solid", borderwidth=1)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Card.TLabel", background=CARD, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=BG, foreground=NAVY, font=("Segoe UI", 24, "bold"))
        style.configure("H2.TLabel", background=BG, foreground=NAVY, font=("Segoe UI", 17, "bold"))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Metric.TLabel", background=CARD, foreground=NAVY, font=("Segoe UI", 20, "bold"))
        style.configure("MetricName.TLabel", background=CARD, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(12,8), foreground="white", background=BLUE)
        style.map("Primary.TButton", background=[("active", NAVY)])
        style.configure("Secondary.TButton", font=("Segoe UI", 10), padding=(10,7))
        style.configure("Treeview", font=("Segoe UI", 9), rowheight=27, background="white", fieldbackground="white")
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#EAF0F7", foreground=NAVY)
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(12,8), font=("Segoe UI", 9, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "white")], foreground=[("selected", BLUE)])

    def _layout(self):
        self.sidebar = tk.Frame(self.root, bg=NAVY, width=235)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        tk.Label(self.sidebar, text="FINANCE+", bg=NAVY, fg="white", font=("Segoe UI", 22, "bold")).pack(anchor="w", padx=20, pady=(24,0))
        tk.Label(self.sidebar, text="UNICO DESKTOP V1.0", bg=NAVY, fg="#BDD3EC", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=20, pady=(0,18))
        self.status_label = tk.Label(self.sidebar, text="● Database locale attivo\n● Archivio documenti attivo\n● Data Quality Gate attivo", justify="left", bg=NAVY, fg="#CBE8D0", font=("Segoe UI", 9))
        self.status_label.pack(anchor="w", padx=20, pady=(0,16))
        tk.Frame(self.sidebar, bg="#315174", height=1).pack(fill="x", padx=16, pady=4)
        self.nav_buttons: dict[str, tk.Button] = {}
        for key, label in self.NAV:
            b = tk.Button(self.sidebar, text=label, anchor="w", relief="flat", bd=0, bg=NAVY, fg="#E6EEF7", activebackground="#214A78", activeforeground="white", font=("Segoe UI", 10, "bold"), command=lambda k=key:self.navigate(k), padx=18, pady=8, cursor="hand2")
            b.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = b
        tk.Frame(self.sidebar, bg="#315174", height=1).pack(fill="x", padx=16, pady=(12,8))
        tk.Label(self.sidebar, text="Dati e credenziali restano sul PC.\nLe integrazioni cloud sono opzionali.", justify="left", bg=NAVY, fg="#9FB4CC", font=("Segoe UI", 8)).pack(anchor="w", padx=20)

        self.main = tk.Frame(self.root, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)
        top = tk.Frame(self.main, bg=BG)
        top.pack(fill="x", padx=28, pady=(22,8))
        tk.Label(top, text=APP_NAME, bg=BG, fg=NAVY, font=("Segoe UI", 24, "bold")).pack(side="left")
        tk.Label(top, text="  CRM • Document AI • Analisi • Automazioni", bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(side="left", pady=(8,0))
        self.page_host = tk.Frame(self.main, bg=BG)
        self.page_host.pack(fill="both", expand=True, padx=24, pady=(0,18))

    def clear_page(self):
        for w in self.page_host.winfo_children():
            w.destroy()

    def navigate(self, key: str):
        key = key if key in dict(self.NAV) else "dashboard"
        self.current_page = key
        for k,b in self.nav_buttons.items():
            b.configure(bg="#1B4B80" if k==key else NAVY, fg="white" if k==key else "#E6EEF7")
        self.clear_page()
        fn = getattr(self, f"page_{key}")
        fn()

    def _apply_initial_state(self):
        s = self.initial_screen
        try:
            if s.startswith("clients_") and hasattr(self, "clients_notebook"):
                idx = {"clients_anagrafica":0,"clients_edit":0,"clients_new_client":0,"clients_pratiche":1,"clients_new_practice":1,"clients_documenti":2,"clients_email":3,"clients_analisi":4,"clients_pdf":5}.get(s,0)
                self.clients_notebook.select(idx)
                if s=="clients_edit": self.root.after(100, self.toggle_client_edit)
                if s=="clients_new_client": self.root.after(100, self.show_new_client_dialog)
                if s=="clients_new_practice": self.root.after(100, self.toggle_new_practice)
            elif s=="docai_result":
                self.docai_text.delete("1.0","end"); self.docai_text.insert("1.0","Bilancio e situazione contabile ACME INDUSTRIA SRL esercizio 2025. Stato patrimoniale, conto economico, ricavi, EBITDA.")
                self.docai_company_var.set("ACME INDUSTRIA SRL"); self.docai_year_var.set("2025"); self.run_docai()
            elif s=="gmail_result": self.gmail_demo_result()
            elif s=="analytics_result": self.fill_demo_analytics(); self.calculate_analytics()
            elif s=="cr_result": self.show_demo_cr()
            elif s=="bank_result": self.show_demo_bank()
            elif s=="bp_result": self.fill_demo_bp(); self.calculate_bp()
            elif s=="dossier_result": self.root.after(100, self.generate_dossier_preview)
            elif s=="mandates_result": self.fill_demo_mandate(); self.calculate_mandate()
        except Exception as exc:
            print("Initial state warning:", exc)

    # ---- UI helpers ----
    def sf(self, title: str, subtitle: str = "") -> ScrollFrame:
        sf = ScrollFrame(self.page_host)
        sf.pack(fill="both", expand=True)
        head = ttk.Frame(sf.inner)
        head.pack(fill="x", padx=8, pady=(4,12))
        ttk.Label(head, text=title, style="H2.TLabel").pack(anchor="w")
        if subtitle: ttk.Label(head, text=subtitle, style="Muted.TLabel").pack(anchor="w", pady=(3,0))
        return sf

    def card(self, parent, title: str | None = None, padx=14, pady=12):
        f = ttk.Frame(parent, style="Card.TFrame")
        f.pack(fill="x", padx=8, pady=7)
        if title:
            ttk.Label(f, text=title, style="Card.TLabel", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=padx, pady=(pady,6))
        return f

    def metrics(self, parent, items: list[tuple[str,str]], columns=4):
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=8, pady=6)
        for i,(name,val) in enumerate(items):
            c = ttk.Frame(row, style="Card.TFrame")
            c.grid(row=0, column=i, sticky="nsew", padx=5)
            row.columnconfigure(i, weight=1)
            ttk.Label(c, text=name, style="MetricName.TLabel").pack(anchor="w", padx=14, pady=(12,2))
            ttk.Label(c, text=val, style="Metric.TLabel").pack(anchor="w", padx=14, pady=(0,12))
        return row

    def tree(self, parent, columns: list[tuple[str,str,int]], height=8):
        frame = ttk.Frame(parent, style="Card.TFrame")
        frame.pack(fill="both", expand=True, padx=8, pady=7)
        keys = [c[0] for c in columns]
        tv = ttk.Treeview(frame, columns=keys, show="headings", height=height)
        vs = ttk.Scrollbar(frame, orient="vertical", command=tv.yview)
        hs = ttk.Scrollbar(frame, orient="horizontal", command=tv.xview)
        tv.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        for key,label,width in columns:
            tv.heading(key, text=label)
            tv.column(key, width=width, anchor="w")
        tv.grid(row=0,column=0,sticky="nsew",padx=(1,0),pady=(1,0))
        vs.grid(row=0,column=1,sticky="ns",pady=(1,0))
        hs.grid(row=1,column=0,sticky="ew",padx=(1,0))
        frame.rowconfigure(0,weight=1); frame.columnconfigure(0,weight=1)
        return tv

    def labeled_entry(self, parent, label, var: tk.Variable | None = None, width=24, row=None, col=None):
        box = ttk.Frame(parent, style="Card.TFrame" if str(parent.cget("style") if hasattr(parent,'cget') else '') == 'Card.TFrame' else "TFrame")
        if row is None: box.pack(side="left", fill="x", expand=True, padx=6, pady=5)
        else: box.grid(row=row, column=col, sticky="ew", padx=6, pady=5); parent.columnconfigure(col, weight=1)
        ttk.Label(box, text=label, style="Card.TLabel" if isinstance(parent, ttk.Frame) and parent.cget("style")=="Card.TFrame" else "TLabel").pack(anchor="w")
        e = ttk.Entry(box, textvariable=var, width=width)
        e.pack(fill="x", pady=(3,0))
        return e

    # ---- Dashboard ----
    def page_dashboard(self):
        sf = self.sf("Dashboard - Centro di controllo operativo", "Stato CRM, pratiche, documenti, analisi e alert dossier")
        counts = {t:self.store.one(f"SELECT COUNT(*) c FROM {t}")["c"] for t in ["clients","practices","documents","emails","analyses"]}
        self.metrics(sf.inner, [("Clienti",str(counts['clients'])),("Pratiche",str(counts['practices'])),("Documenti",str(counts['documents'])),("Email",str(counts['emails'])),("Analisi",str(counts['analyses']))], 5)
        c = self.card(sf.inner, "Pratiche da presidiare")
        rows = self.store.q("SELECT p.*, c.name client FROM practices p LEFT JOIN clients c ON c.id=p.client_id WHERE COALESCE(p.missing_docs,'')<>'' OR COALESCE(p.alerts,'')<>'' ORDER BY p.priority='Alta' DESC, p.due_date LIMIT 50")
        tv = self.tree(c, [("code","Pratica",120),("client","Cliente",190),("bank","Istituto",150),("status","Stato",120),("priority","Priorità",80),("complete","Completezza",90),("missing","Documenti mancanti",210),("action","Prossima azione",180),("due","Scadenza",90),("alerts","Alert",180)],height=6)
        for r in rows: tv.insert("","end",values=(r["code"],r["client"],r["bank"],r["status"],r["priority"],f"{r['completeness']:.0f}%",r["missing_docs"],r["next_action"],r["due_date"],r["alerts"]))
        c2 = self.card(sf.inner, "Email prioritarie")
        tv2 = self.tree(c2, [("dt","Data",125),("client","Cliente",190),("sender","Mittente",180),("subject","Oggetto",280),("priority","Priorità",80),("action","Azione richiesta",220),("managed","Gestita",75)],height=4)
        for r in self.store.q("SELECT e.*, c.name client FROM emails e LEFT JOIN clients c ON c.id=e.client_id WHERE priority IN ('Alta','Urgente','Critica') ORDER BY dt DESC LIMIT 30"):
            tv2.insert("","end",values=(r["dt"],r["client"],r["sender"],r["subject"],r["priority"],r["action_required"],r["managed"]))
        info = tk.Label(sf.inner, text="Pipeline unica: Gmail / Upload → Document AI → SHA-256 → Archivio → CRM → Analytics + CR + CC → Business Plan → Dossier", bg="#EAF4FF", fg="#234E7D", font=("Segoe UI",10,"bold"), padx=14,pady=10,anchor="w")
        info.pack(fill="x",padx=8,pady=8)

    # ---- Clients ----
    def page_clients(self):
        sf = self.sf("Clienti - Anagrafica, pratiche e fascicolo completo", "Ricerca cliente, gestione dossier, documenti, email, analisi e PDF")
        bar = ttk.Frame(sf.inner); bar.pack(fill="x", padx=8, pady=4)
        self.client_search_var=tk.StringVar(); ttk.Entry(bar,textvariable=self.client_search_var,width=45).pack(side="left",padx=(0,8)); ttk.Button(bar,text="Cerca",style="Secondary.TButton",command=self.refresh_client_list).pack(side="left")
        ttk.Button(bar,text="+ Nuovo cliente",style="Primary.TButton",command=self.show_new_client_dialog).pack(side="right")
        self.client_combo = ttk.Combobox(bar,state="readonly",width=38); self.client_combo.pack(side="right",padx=8); self.client_combo.bind("<<ComboboxSelected>>",lambda e:self.load_selected_client())
        self.client_container=ttk.Frame(sf.inner); self.client_container.pack(fill="both",expand=True,padx=8,pady=5)
        self.refresh_client_list(); self.load_selected_client()

    def refresh_client_list(self):
        q=self.client_search_var.get().strip() if hasattr(self,'client_search_var') else ''
        rows=self.store.q("SELECT id,name,vat,city,ateco FROM clients WHERE name LIKE ? OR vat LIKE ? OR city LIKE ? OR ateco LIKE ? ORDER BY name", tuple([f"%{q}%"]*4))
        self.client_map={f"{r['name']}  |  {r['vat'] or 'P.IVA n/d'}":r['id'] for r in rows}
        vals=list(self.client_map)
        self.client_combo['values']=vals
        if vals:
            if self.client_combo.get() not in vals: self.client_combo.current(0)
            self.selected_client_id=self.client_map[self.client_combo.get()]

    def load_selected_client(self):
        if not hasattr(self,'client_container'): return
        for w in self.client_container.winfo_children(): w.destroy()
        if not self.client_combo.get():
            ttk.Label(self.client_container,text="Nessun cliente presente. Usa '+ Nuovo cliente'.").pack(pady=20); return
        self.selected_client_id=self.client_map[self.client_combo.get()]
        c=self.store.one("SELECT * FROM clients WHERE id=?",(self.selected_client_id,))
        pcs=self.store.one("SELECT COUNT(*) c FROM practices WHERE client_id=?",(c['id'],))['c']; docs=self.store.one("SELECT COUNT(*) c FROM documents WHERE client_id=?",(c['id'],))['c']; emails=self.store.one("SELECT COUNT(*) c FROM emails WHERE client_id=?",(c['id'],))['c']; ana=self.store.one("SELECT COUNT(*) c FROM analyses WHERE client_id=?",(c['id'],))['c']
        head=ttk.Frame(self.client_container); head.pack(fill="x",pady=4); ttk.Label(head,text=c['name'],font=("Segoe UI",16,"bold"),foreground=NAVY).pack(side="left")
        ttk.Label(head,text=f"  Pratiche {pcs}   •   Documenti {docs}   •   Email {emails}   •   Analisi {ana}",foreground=MUTED).pack(side="left",pady=(4,0))
        nb=ttk.Notebook(self.client_container); nb.pack(fill="both",expand=True,pady=6); self.clients_notebook=nb
        tabs=[ttk.Frame(nb) for _ in range(6)]; names=["Anagrafica","Pratiche","Documenti","Email","Analisi","PDF Cliente"]
        for t,n in zip(tabs,names): nb.add(t,text=n)
        self.build_client_anagrafica(tabs[0],c); self.build_client_practices(tabs[1],c); self.build_client_docs(tabs[2],c); self.build_client_emails(tabs[3],c); self.build_client_analyses(tabs[4],c); self.build_client_pdf(tabs[5],c)

    def build_client_anagrafica(self,parent,c):
        box=ttk.Frame(parent,style="Card.TFrame"); box.pack(fill="x",padx=6,pady=8)
        lines=[("P.IVA",c['vat']),("Codice fiscale",c['cf']),("PEC",c['pec']),("REA",c['rea']),("Forma giuridica",c['legal_form']),("Sede",c['address']),("Comune",f"{c['city'] or ''} ({c['province'] or ''})"),("ATECO",c['ateco']),("Attività",c['activity']),("Amministratore",c['administrator']),("Rating FinancePlus",c['rating'])]
        grid=ttk.Frame(box,style="Card.TFrame"); grid.pack(fill="x",padx=14,pady=12)
        for i,(k,v) in enumerate(lines):
            f=ttk.Frame(grid,style="Card.TFrame"); f.grid(row=i//2,column=i%2,sticky="ew",padx=8,pady=4); grid.columnconfigure(i%2,weight=1)
            ttk.Label(f,text=k,style="Card.TLabel",font=("Segoe UI",9,"bold"),foreground=MUTED).pack(anchor="w"); ttk.Label(f,text=v or "—",style="Card.TLabel",font=("Segoe UI",10)).pack(anchor="w")
        ttk.Button(parent,text="Modifica anagrafica",style="Primary.TButton",command=self.toggle_client_edit).pack(anchor="w",padx=8,pady=4)
        self.client_edit_frame=ttk.Frame(parent,style="Card.TFrame")
        self.client_edit_vars={k:tk.StringVar(value=c[k] or "") for k in ['name','vat','cf','pec','rea','address','city','province','ateco','activity','administrator','notes']}

    def toggle_client_edit(self):
        f=self.client_edit_frame
        if f.winfo_ismapped(): f.pack_forget(); return
        f.pack(fill="x",padx=6,pady=8)
        for w in f.winfo_children(): w.destroy()
        ttk.Label(f,text="Modifica anagrafica",style="Card.TLabel",font=("Segoe UI",11,"bold")).pack(anchor="w",padx=14,pady=(12,4))
        grid=ttk.Frame(f,style="Card.TFrame"); grid.pack(fill="x",padx=8,pady=4)
        labels=[('name','Ragione sociale'),('vat','P.IVA'),('cf','CF'),('pec','PEC'),('rea','REA'),('address','Sede legale'),('city','Comune'),('province','Provincia'),('ateco','ATECO'),('activity','Attività'),('administrator','Amministratore'),('notes','Note')]
        for i,(k,l) in enumerate(labels): self.labeled_entry(grid,l,self.client_edit_vars[k],row=i//3,col=i%3)
        ttk.Button(f,text="Salva modifiche",style="Primary.TButton",command=self.save_client).pack(anchor="e",padx=14,pady=12)

    def save_client(self):
        v=self.client_edit_vars
        self.store.execute("UPDATE clients SET name=?,vat=?,cf=?,pec=?,rea=?,address=?,city=?,province=?,ateco=?,activity=?,administrator=?,notes=? WHERE id=?",(v['name'].get(),v['vat'].get(),v['cf'].get(),v['pec'].get(),v['rea'].get(),v['address'].get(),v['city'].get(),v['province'].get(),v['ateco'].get(),v['activity'].get(),v['administrator'].get(),v['notes'].get(),self.selected_client_id))
        messagebox.showinfo("Clienti","Anagrafica aggiornata."); self.refresh_client_list(); self.load_selected_client()

    def show_new_client_dialog(self):
        if self.current_page!='clients': return
        top=tk.Toplevel(self.root); top.title("Nuovo cliente"); top.geometry("720x480"); top.configure(bg=BG); top.transient(self.root)
        vars={k:tk.StringVar() for k in ['name','vat','cf','pec','rea','address','city','province','ateco','activity','administrator']}
        ttk.Label(top,text="Nuovo cliente",style="H2.TLabel").pack(anchor="w",padx=20,pady=(18,8))
        grid=ttk.Frame(top); grid.pack(fill="both",expand=True,padx=14,pady=4)
        labels=[('name','Ragione sociale'),('vat','P.IVA'),('cf','CF'),('pec','PEC'),('rea','REA'),('address','Sede legale'),('city','Comune'),('province','Provincia'),('ateco','ATECO'),('activity','Attività'),('administrator','Amministratore')]
        for i,(k,l) in enumerate(labels): self.labeled_entry(grid,l,vars[k],row=i//2,col=i%2)
        def save():
            if not vars['name'].get().strip(): messagebox.showwarning("Nuovo cliente","Inserire la ragione sociale."); return
            self.store.execute("INSERT INTO clients(name,vat,cf,pec,rea,address,city,province,ateco,activity,administrator) VALUES (?,?,?,?,?,?,?,?,?,?,?)",tuple(vars[k].get() for k in ['name','vat','cf','pec','rea','address','city','province','ateco','activity','administrator']))
            top.destroy(); self.refresh_client_list(); self.load_selected_client()
        ttk.Button(top,text="Crea cliente",style="Primary.TButton",command=save).pack(anchor="e",padx=20,pady=14)
        if self.initial_screen=="clients_new_client" and self.demo:
            vars['name'].set("NUOVA IMPRESA SRL"); vars['vat'].set("11122233344"); vars['pec'].set("nuova@pec.example.it"); vars['city'].set("Caserta"); vars['province'].set("CE"); vars['ateco'].set("46.90.00")

    def build_client_practices(self,parent,c):
        tv=self.tree(parent,[("code","Pratica",110),("type","Tipo",110),("bank","Istituto",150),("amount","Importo",100),("status","Stato",110),("priority","Priorità",75),("owner","Responsabile",120),("complete","Completezza",95),("missing","Documenti mancanti",190),("action","Prossima azione",160),("due","Scadenza",90)],height=7)
        for r in self.store.q("SELECT * FROM practices WHERE client_id=? ORDER BY id DESC",(c['id'],)):
            tv.insert("","end",values=(r['code'],r['type'],r['bank'],euro(r['amount']),r['status'],r['priority'],r['owner'],f"{r['completeness']:.0f}%",r['missing_docs'],r['next_action'],r['due_date']))
        ttk.Button(parent,text="+ Nuova pratica",style="Primary.TButton",command=self.toggle_new_practice).pack(anchor="w",padx=8,pady=5)
        self.new_practice_frame=ttk.Frame(parent,style="Card.TFrame")

    def toggle_new_practice(self):
        f=self.new_practice_frame
        if f.winfo_ismapped(): f.pack_forget(); return
        f.pack(fill="x",padx=6,pady=7)
        for w in f.winfo_children(): w.destroy()
        ttk.Label(f,text="Nuova pratica",style="Card.TLabel",font=("Segoe UI",11,"bold")).pack(anchor="w",padx=14,pady=(10,3))
        self.practice_vars={k:tk.StringVar() for k in ['code','type','bank','amount','status','priority','owner','action','due','missing']}
        self.practice_vars['code'].set(f"FP-{datetime.now().year}-{(self.store.one('SELECT COUNT(*) c FROM practices')['c']+1):03d}"); self.practice_vars['type'].set('Finanziamento'); self.practice_vars['status'].set('Da avviare'); self.practice_vars['priority'].set('Media'); self.practice_vars['due'].set(date.today().strftime('%d/%m/%Y'))
        grid=ttk.Frame(f,style="Card.TFrame"); grid.pack(fill="x",padx=8,pady=4)
        specs=[('code','Pratica ID'),('type','Tipo'),('bank','Banca / intermediario'),('amount','Importo richiesto €'),('status','Stato'),('priority','Priorità'),('owner','Responsabile'),('action','Prossima azione'),('due','Scadenza'),('missing','Documenti mancanti')]
        for i,(k,l) in enumerate(specs): self.labeled_entry(grid,l,self.practice_vars[k],row=i//3,col=i%3)
        ttk.Button(f,text="Crea pratica",style="Primary.TButton",command=self.create_practice).pack(anchor="e",padx=14,pady=10)
        if self.initial_screen=="clients_new_practice" and self.demo:
            self.practice_vars['bank'].set('Crédit Agricole'); self.practice_vars['amount'].set('300000'); self.practice_vars['owner'].set("D. D'Angelo"); self.practice_vars['action'].set('Invio dossier banca'); self.practice_vars['missing'].set('DURC aggiornato')

    def create_practice(self):
        v=self.practice_vars; amount=parse_num(v['amount'].get()) or 0
        self.store.execute("INSERT INTO practices(client_id,code,type,bank,amount,status,priority,owner,next_action,due_date,missing_docs,completeness) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(self.selected_client_id,v['code'].get(),v['type'].get(),v['bank'].get(),amount,v['status'].get(),v['priority'].get(),v['owner'].get(),v['action'].get(),v['due'].get(),v['missing'].get(),50 if v['missing'].get().strip() else 80))
        messagebox.showinfo("Pratiche","Pratica creata."); self.load_selected_client()

    def build_client_docs(self,parent,c):
        tv=self.tree(parent,[("title","Documento",190),("type","Tipo",130),("year","Esercizio",70),("date","Data",90),("origin","Origine",80),("verify","Verifica",90),("def","Nome definitivo",220),("sens","Sensibilità",110)],height=8)
        for r in self.store.q("SELECT * FROM documents WHERE client_id=? ORDER BY id DESC",(c['id'],)): tv.insert("","end",values=(r['title'],r['doc_type'],r['year'],r['doc_date'],r['origin'],r['verify_status'],r['definitive_name'],r['sensitivity']))
        ttk.Button(parent,text="Aggiungi documento al cliente",style="Primary.TButton",command=lambda:self.add_document(client_id=c['id'])).pack(anchor="w",padx=8,pady=5)

    def build_client_emails(self,parent,c):
        tv=self.tree(parent,[("dt","Data",125),("sender","Mittente",180),("subject","Oggetto",260),("priority","Priorità",80),("action","Azione richiesta",210),("att","Allegati",65),("managed","Gestita",70),("sum","Sintesi IA",260)],height=8)
        for r in self.store.q("SELECT * FROM emails WHERE client_id=? ORDER BY dt DESC",(c['id'],)): tv.insert("","end",values=(r['dt'],r['sender'],r['subject'],r['priority'],r['action_required'],r['attachments'],r['managed'],r['ai_summary']))

    def build_client_analyses(self,parent,c):
        tv=self.tree(parent,[("dt","Data",100),("year","Esercizio",70),("rev","Ricavi",110),("ebitda","EBITDA",100),("pfn","PFN",100),("lev","PFN/EBITDA",90),("dscr","DSCR",70),("score","Score",60),("rating","Rating",70),("sust","Sostenibile",150),("rec","Raccomandazioni",280)],height=8)
        for r in self.store.q("SELECT * FROM analyses WHERE client_id=? ORDER BY id DESC",(c['id'],)): tv.insert("","end",values=(r['dt'],r['year'],euro(r['revenue']),euro(r['ebitda']),euro(r['pfn']),f"{r['pfn_ebitda']:.2f}x" if r['pfn_ebitda'] is not None else 'N/D',f"{r['dscr']:.2f}x" if r['dscr'] is not None else 'N/D',r['score'],r['rating'],f"{euro(r['sustainable_min'])} - {euro(r['sustainable_max'])}",r['recommendations']))

    def build_client_pdf(self,parent,c):
        box=ttk.Frame(parent,style="Card.TFrame"); box.pack(fill="x",padx=8,pady=12)
        ttk.Label(box,text="Reportistica cliente",style="Card.TLabel",font=("Segoe UI",12,"bold")).pack(anchor="w",padx=16,pady=(16,4))
        ttk.Label(box,text="Genera documenti riepilogativi con anagrafica, pratiche, documenti, email e analisi.",style="Card.TLabel").pack(anchor="w",padx=16,pady=(0,12))
        row=ttk.Frame(box,style="Card.TFrame"); row.pack(fill="x",padx=16,pady=(0,16))
        ttk.Button(row,text="Genera Report documenti + pratiche PDF",style="Primary.TButton",command=lambda:self.generate_client_pdf(c,False)).pack(side="left",padx=(0,8))
        ttk.Button(row,text="Genera Fascicolo Cliente completo PDF",style="Secondary.TButton",command=lambda:self.generate_client_pdf(c,True)).pack(side="left")

    def generate_client_pdf(self,c,full=True):
        out=self.store.output_dir / f"{safe_filename(c['name'])}_{'Fascicolo_Cliente' if full else 'Report_Documenti'}.pdf"
        try:
            self._reportlab_client_pdf(out,c,full); messagebox.showinfo("PDF Cliente",f"Creato:\n{out}"); open_path(out)
        except Exception as exc: messagebox.showerror("PDF Cliente",str(exc))

    def _reportlab_client_pdf(self,out,c,full):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        styles=getSampleStyleSheet(); styles.add(ParagraphStyle(name='Navy',parent=styles['Heading1'],textColor=colors.HexColor(NAVY)))
        doc=SimpleDocTemplate(str(out),pagesize=A4,rightMargin=36,leftMargin=36,topMargin=36,bottomMargin=36)
        story=[Paragraph(f"FINANCE_PLUS - {'Fascicolo Cliente' if full else 'Report Documenti'}",styles['Navy']),Paragraph(c['name'],styles['Heading2']),Spacer(1,10)]
        data=[["P.IVA",c['vat'] or '—'],["PEC",c['pec'] or '—'],["ATECO",c['ateco'] or '—'],["Sede",f"{c['address'] or ''} {c['city'] or ''} ({c['province'] or ''})".strip()]]
        t=Table(data,colWidths=[120,350]); t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.4,colors.HexColor(BORDER)),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#EAF0F7')),('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('PADDING',(0,0),(-1,-1),7)])); story += [t,Spacer(1,14)]
        prs=self.store.q("SELECT * FROM practices WHERE client_id=?",(c['id'],)); story.append(Paragraph("Pratiche",styles['Heading2'])); pdata=[["Pratica","Istituto","Importo","Stato","Priorità"]]+[[r['code'],r['bank'],euro(r['amount']),r['status'],r['priority']] for r in prs]; pt=Table(pdata,repeatRows=1,colWidths=[85,120,95,105,65]); pt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(NAVY)),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.3,colors.grey),('FONTSIZE',(0,0),(-1,-1),8),('PADDING',(0,0),(-1,-1),5)])); story += [pt,Spacer(1,14)]
        docs=self.store.q("SELECT * FROM documents WHERE client_id=?",(c['id'],)); story.append(Paragraph("Documenti",styles['Heading2'])); ddata=[["Documento","Tipo","Esercizio","Origine","Verifica"]]+[[r['title'],r['doc_type'],r['year'],r['origin'],r['verify_status']] for r in docs]; dt=Table(ddata,repeatRows=1,colWidths=[170,110,60,65,80]); dt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(BLUE)),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.3,colors.grey),('FONTSIZE',(0,0),(-1,-1),8),('PADDING',(0,0),(-1,-1),5)])); story += [dt]
        if full:
            story += [PageBreak(),Paragraph("Email e Analisi",styles['Navy'])]
            for r in self.store.q("SELECT * FROM emails WHERE client_id=? ORDER BY dt DESC",(c['id'],)): story += [Paragraph(f"<b>{r['dt']} - {r['subject']}</b>",styles['BodyText']),Paragraph(r['ai_summary'] or r['action_required'] or '',styles['BodyText']),Spacer(1,6)]
            for r in self.store.q("SELECT * FROM analyses WHERE client_id=? ORDER BY id DESC",(c['id'],)): story += [Paragraph(f"Analisi {r['year']} - Rating {r['rating']} - Score {r['score']}",styles['Heading3']),Paragraph(f"Ricavi {euro(r['revenue'])}; EBITDA {euro(r['ebitda'])}; PFN {euro(r['pfn'])}; DSCR {r['dscr']}; PFN/EBITDA {r['pfn_ebitda']}",styles['BodyText']),Paragraph(r['recommendations'] or '',styles['BodyText'])]
        doc.build(story)

    # ---- Documents ----
    def page_documents(self):
        sf=self.sf("Archivio documentale unico", "Ricerca, classificazione, SHA-256, sensibilità e apertura file")
        bar=ttk.Frame(sf.inner); bar.pack(fill="x",padx=8,pady=5)
        self.doc_search=tk.StringVar(); self.doc_type_filter=tk.StringVar(value="Tutti"); self.doc_origin_filter=tk.StringVar(value="Tutte")
        self.labeled_entry(bar,"Cerca documento",self.doc_search);
        types=[r['doc_type'] for r in self.store.q("SELECT DISTINCT doc_type FROM documents WHERE doc_type<>'' ORDER BY doc_type")]; origins=[r['origin'] for r in self.store.q("SELECT DISTINCT origin FROM documents WHERE origin<>'' ORDER BY origin")]
        bx=ttk.Frame(bar); bx.pack(side="left",fill="x",expand=True,padx=6); ttk.Label(bx,text="Tipo").pack(anchor='w'); ttk.Combobox(bx,textvariable=self.doc_type_filter,values=['Tutti']+types,state='readonly').pack(fill='x',pady=(3,0))
        bx2=ttk.Frame(bar); bx2.pack(side="left",fill="x",expand=True,padx=6); ttk.Label(bx2,text="Origine").pack(anchor='w'); ttk.Combobox(bx2,textvariable=self.doc_origin_filter,values=['Tutte']+origins,state='readonly').pack(fill='x',pady=(3,0))
        ttk.Button(bar,text="Filtra",style="Secondary.TButton",command=self.refresh_documents).pack(side="left",padx=6,pady=(18,0)); ttk.Button(bar,text="+ Aggiungi documento",style="Primary.TButton",command=self.add_document).pack(side="left",padx=6,pady=(18,0))
        self.doc_metric_frame=ttk.Frame(sf.inner); self.doc_metric_frame.pack(fill="x")
        self.doc_tree=self.tree(sf.inner,[("client","Cliente",170),("title","Documento",190),("type","Tipo",120),("year","Esercizio",70),("date","Data",85),("origin","Origine",70),("verify","Verifica",85),("def","Nome definitivo",220),("sens","Sensibilità",100),("sha","SHA-256",150)],height=15)
        self.doc_tree.bind("<Double-1>",self.open_selected_document); self.refresh_documents()

    def refresh_documents(self):
        if not hasattr(self,'doc_tree'): return
        for i in self.doc_tree.get_children(): self.doc_tree.delete(i)
        q=self.doc_search.get().strip(); typ=self.doc_type_filter.get(); origin=self.doc_origin_filter.get(); sql="SELECT d.*, c.name client FROM documents d LEFT JOIN clients c ON c.id=d.client_id WHERE 1=1"; p=[]
        if q: sql+=" AND (d.title LIKE ? OR d.definitive_name LIKE ? OR c.name LIKE ?)"; p += [f"%{q}%"]*3
        if typ!='Tutti': sql+=" AND d.doc_type=?"; p.append(typ)
        if origin!='Tutte': sql+=" AND d.origin=?"; p.append(origin)
        sql+=" ORDER BY d.id DESC"; rows=self.store.q(sql,p)
        for r in rows: self.doc_tree.insert("","end",iid=str(r['id']),values=(r['client'],r['title'],r['doc_type'],r['year'],r['doc_date'],r['origin'],r['verify_status'],r['definitive_name'],r['sensitivity'],r['sha256'][:16]+'…'))
        for w in self.doc_metric_frame.winfo_children(): w.destroy()
        self.metrics(self.doc_metric_frame,[("Documenti filtrati",str(len(rows))),("Verificati",str(sum(1 for r in rows if r['verify_status']=='Verificato'))),("Da verificare",str(sum(1 for r in rows if r['verify_status']!='Verificato')))],3)

    def add_document(self,client_id=None):
        path=filedialog.askopenfilename(title="Seleziona documento",filetypes=[("Documenti","*.pdf *.txt *.csv *.md *.xlsx *.docx"),("Tutti i file","*.*")])
        if not path: return
        p=Path(path); sha=sha256_file(p)
        if self.store.one("SELECT id FROM documents WHERE sha256=?",(sha,)): messagebox.showinfo("Archivio","Documento già presente (SHA-256 identico)."); return
        text,warn=extract_text_from_file(p); cls=classify_text(text,p.name); dest_name=suggested_name(cls,p.name); dest=self.store.archive_dir/dest_name
        if dest.exists(): dest=self.store.archive_dir/f"{dest.stem}_{int(time.time())}{dest.suffix}"
        shutil.copy2(p,dest)
        cid=client_id or self.selected_client_id
        self.store.execute("INSERT INTO documents(client_id,title,doc_type,year,doc_date,origin,verify_status,original_name,definitive_name,path,sha256,sensitivity) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(cid,p.name,cls.category,str(cls.year or ''),date.today().strftime('%d/%m/%Y'),'Upload','Da verificare',p.name,dest.name,str(dest),sha,'Riservato' if cls.category in {'Bilancio','Centrale Rischi','Estratto conto'} else 'Interno'))
        messagebox.showinfo("Archivio",f"Documento archiviato.\nCategoria: {cls.category}\nNome: {dest.name}" + (f"\nNota: {warn}" if warn else ""))
        if self.current_page=='documents': self.refresh_documents()
        elif self.current_page=='clients': self.load_selected_client()

    def open_selected_document(self,event=None):
        sel=self.doc_tree.selection()
        if not sel: return
        r=self.store.one("SELECT path FROM documents WHERE id=?",(int(sel[0]),));
        if r and r['path']: open_path(r['path'])

    # ---- Document AI ----
    def page_docai(self):
        sf=self.sf("Document AI - riconoscimento, naming e SHA-256", "Analisi content-first di PDF/TXT/CSV/MD e proposta nome definitivo")
        c=self.card(sf.inner,"Input documentale")
        row=ttk.Frame(c,style="Card.TFrame"); row.pack(fill="x",padx=12,pady=6)
        ttk.Button(row,text="Seleziona file",style="Primary.TButton",command=self.select_docai_files).pack(side="left"); self.docai_files_label=ttk.Label(row,text="Nessun file selezionato",style="Card.TLabel",foreground=MUTED); self.docai_files_label.pack(side="left",padx=12)
        self.docai_text=tk.Text(c,height=5,wrap="word",font=("Segoe UI",9),relief="solid",bd=1); self.docai_text.pack(fill="x",padx=14,pady=6)
        row2=ttk.Frame(c,style="Card.TFrame"); row2.pack(fill="x",padx=8,pady=5); self.docai_company_var=tk.StringVar(); self.docai_year_var=tk.StringVar(); self.labeled_entry(row2,"Azienda / soggetto (opzionale)",self.docai_company_var); self.labeled_entry(row2,"Anno (opzionale)",self.docai_year_var)
        ttk.Button(c,text="Analizza",style="Primary.TButton",command=self.run_docai).pack(anchor="e",padx=14,pady=10)
        self.docai_tree=self.tree(sf.inner,[("file","File",190),("cat","Categoria",140),("conf","Confidenza",80),("company","Soggetto",190),("year","Anno",60),("name","Nome proposto",280),("sha","SHA-256",160),("note","Nota",210)],height=10)

    def select_docai_files(self):
        paths=filedialog.askopenfilenames(title="Seleziona documenti",filetypes=[("Documenti","*.pdf *.txt *.csv *.md"),("Tutti","*.*")]); self.docai_paths=[Path(p) for p in paths]
        self.docai_files_label.configure(text=f"{len(self.docai_paths)} file selezionati" if self.docai_paths else "Nessun file selezionato")

    def run_docai(self):
        for i in self.docai_tree.get_children(): self.docai_tree.delete(i)
        pasted=self.docai_text.get("1.0","end").strip(); paths=self.docai_paths or ([None] if pasted else [])
        if not paths: messagebox.showwarning("Document AI","Seleziona almeno un file o incolla del testo."); return
        for p in paths:
            if p is None: fname="testo_incollato.txt"; text=pasted; warn=""; sha="—"; cls=classify_text(text,fname)
            else:
                text,warn=extract_text_from_file(p); text=(text+'\n'+pasted).strip(); fname=p.name; sha=sha256_file(p); cls=classify_text(text,fname)
            if self.docai_company_var.get().strip(): cls.company=self.docai_company_var.get().strip()
            y=re.sub(r'\D','',self.docai_year_var.get());
            if y: cls.year=int(y[:4])
            self.docai_tree.insert("","end",values=(fname,cls.category,f"{cls.confidence:.0%}",cls.company or '—',cls.year or '—',suggested_name(cls,fname),sha[:16]+'…' if sha!='—' else '—',warn or '—'))

    # ---- Gmail Drive ----
    def page_gmail(self):
        sf=self.sf("Gmail → Document AI → Drive → CRM", "Sincronizzazione allegati con deduplica SHA-256; funzionamento cloud quando OAuth è configurato")
        c=self.card(sf.inner,"Parametri sincronizzazione")
        self.gmail_profile=tk.StringVar(value="PRINCIPALE"); self.gmail_query=tk.StringVar(value="has:attachment newer_than:1d -in:spam -in:trash"); self.gmail_folder=tk.StringVar(value=self.cfg.get('google_drive_folder_id','')); self.gmail_max=tk.IntVar(value=50)
        row=ttk.Frame(c,style="Card.TFrame"); row.pack(fill="x",padx=8,pady=5); self.labeled_entry(row,"Profilo Google",self.gmail_profile); self.labeled_entry(row,"Drive folder ID",self.gmail_folder)
        row2=ttk.Frame(c,style="Card.TFrame"); row2.pack(fill="x",padx=8,pady=5); self.labeled_entry(row2,"Query Gmail",self.gmail_query)
        bx=ttk.Frame(row2,style="Card.TFrame"); bx.pack(side="left",fill="x",expand=True,padx=6,pady=5); ttk.Label(bx,text="Messaggi massimi",style="Card.TLabel").pack(anchor='w'); tk.Scale(bx,from_=1,to=200,orient='horizontal',variable=self.gmail_max,bg=CARD,highlightthickness=0,troughcolor="#DCE6F1",activebackground=BLUE).pack(fill='x')
        ttk.Button(c,text="Sincronizza",style="Primary.TButton",command=self.sync_gmail).pack(anchor="e",padx=14,pady=10)
        self.gmail_result_frame=ttk.Frame(sf.inner); self.gmail_result_frame.pack(fill="x")
        note="OAuth Google NON configurato" if not self.cfg.get('google_oauth_token_json') else "OAuth Google configurato"
        tk.Label(sf.inner,text=f"Stato: {note}. Configura i token in 'Configurazione' per usare Gmail/Drive reali.",bg="#FFF7E6" if 'NON' in note else '#EEF9F0',fg=AMBER if 'NON' in note else GREEN,padx=12,pady=8,anchor='w').pack(fill='x',padx=8,pady=7)

    def gmail_demo_result(self):
        for w in self.gmail_result_frame.winfo_children(): w.destroy()
        self.metrics(self.gmail_result_frame,[("Messaggi","46"),("Allegati","87"),("Caricati","73"),("Duplicati","14")],4)
        tk.Label(self.gmail_result_frame,text="Sincronizzazione dimostrativa completata: classificazione content-aware e deduplica SHA-256 applicate.",bg="#EEF9F0",fg=GREEN,padx=12,pady=8,anchor='w').pack(fill='x',padx=8,pady=6)

    def sync_gmail(self):
        token_json=self.cfg.get('google_oauth_token_json','').strip()
        if not token_json:
            if self.demo: self.gmail_demo_result(); return
            messagebox.showwarning("Gmail & Drive","OAuth Google non configurato. Vai in Configurazione."); return
        for w in self.gmail_result_frame.winfo_children(): w.destroy()
        ttk.Label(self.gmail_result_frame,text="Sincronizzazione in corso…",style="Muted.TLabel").pack(anchor='w',padx=10,pady=10); self.root.update_idletasks()
        def worker():
            try: result=self._gmail_sync_real(token_json)
            except Exception as exc: result={'error':str(exc)}
            self.root.after(0,lambda:self._gmail_sync_done(result))
        threading.Thread(target=worker,daemon=True).start()

    def _gmail_sync_real(self, token_json: str) -> dict[str,Any]:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        info=json.loads(token_json); creds=Credentials.from_authorized_user_info(info)
        gmail=build('gmail','v1',credentials=creds,cache_discovery=False); drive=build('drive','v3',credentials=creds,cache_discovery=False)
        q=self.gmail_query.get(); maxr=self.gmail_max.get(); msgs=gmail.users().messages().list(userId='me',q=q,maxResults=maxr).execute().get('messages',[])
        attachments=uploaded=duplicates=0; errors=[]
        for m in msgs:
            try:
                full=gmail.users().messages().get(userId='me',id=m['id'],format='full').execute(); parts=[]
                def walk(ps):
                    for p in ps or []:
                        if p.get('filename') and p.get('body',{}).get('attachmentId'): parts.append(p)
                        walk(p.get('parts'))
                walk(full.get('payload',{}).get('parts',[]))
                for p in parts:
                    attachments+=1; aid=p['body']['attachmentId']; data=gmail.users().messages().attachments().get(userId='me',messageId=m['id'],id=aid).execute().get('data',''); raw=base64.urlsafe_b64decode(data+'==='); sha=hashlib.sha256(raw).hexdigest()
                    if self.store.one("SELECT id FROM documents WHERE sha256=?",(sha,)): duplicates+=1; continue
                    temp=self.store.archive_dir/safe_filename(p['filename']); temp.write_bytes(raw); text,_=extract_text_from_file(temp); cls=classify_text(text,p['filename']); final=self.store.archive_dir/suggested_name(cls,p['filename']);
                    if final!=temp: temp.replace(final)
                    meta={'name':final.name}; folder=self.gmail_folder.get().strip();
                    if folder: meta['parents']=[folder]
                    media=MediaFileUpload(str(final),resumable=False); d=drive.files().create(body=meta,media_body=media,fields='id,webViewLink').execute(); uploaded+=1
                    self.store.execute("INSERT INTO documents(title,doc_type,year,doc_date,origin,verify_status,original_name,definitive_name,path,sha256,sensitivity) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(p['filename'],cls.category,str(cls.year or ''),date.today().strftime('%d/%m/%Y'),'Gmail','Da verificare',p['filename'],final.name,str(final),sha,'Riservato' if cls.category in {'Bilancio','Centrale Rischi','Estratto conto'} else 'Interno'))
            except Exception as exc: errors.append(str(exc))
        return {'messages':len(msgs),'attachments':attachments,'uploaded':uploaded,'duplicates':duplicates,'errors':errors}

    def _gmail_sync_done(self,r):
        for w in self.gmail_result_frame.winfo_children(): w.destroy()
        if r.get('error'): tk.Label(self.gmail_result_frame,text=r['error'],bg="#FDECEC",fg=RED,padx=12,pady=8).pack(fill='x',padx=8); return
        self.metrics(self.gmail_result_frame,[("Messaggi",str(r['messages'])),("Allegati",str(r['attachments'])),("Caricati",str(r['uploaded'])),("Duplicati",str(r['duplicates']))],4)
        tk.Label(self.gmail_result_frame,text="Sincronizzazione completata." + (f" Errori: {len(r.get('errors',[]))}" if r.get('errors') else ''),bg="#EEF9F0",fg=GREEN,padx=12,pady=8,anchor='w').pack(fill='x',padx=8,pady=6)

    # ---- Analytics ----
    def page_analytics(self):
        sf=self.sf("FinancePlus Analytics Engine", "Data Quality Gate, KPI, score, rating AAA-D e semaforo")
        c=self.card(sf.inner,"Dati economico-finanziari")
        self.analytics_vars={k:tk.StringVar() for k in ['revenue','ebitda','ebit','financial_debt','cash','equity','current_assets','current_liabilities','cfads','debt_service']}
        labels=[('revenue','Ricavi'),('ebitda','EBITDA'),('ebit','EBIT'),('financial_debt','Debiti finanziari'),('cash','Cassa'),('equity','Patrimonio netto'),('current_assets','Attivo corrente'),('current_liabilities','Passivo corrente'),('cfads','CFADS'),('debt_service','Servizio del debito')]
        grid=ttk.Frame(c,style="Card.TFrame"); grid.pack(fill='x',padx=8,pady=4)
        for i,(k,l) in enumerate(labels): self.labeled_entry(grid,l,self.analytics_vars[k],row=i//2,col=i%2)
        ttk.Button(c,text="Calcola KPI e rating",style="Primary.TButton",command=self.calculate_analytics).pack(anchor='e',padx=14,pady=10)
        self.analytics_result=ttk.Frame(sf.inner); self.analytics_result.pack(fill='x')

    def fill_demo_analytics(self):
        vals={'revenue':5500000,'ebitda':825000,'ebit':610000,'financial_debt':1450000,'cash':350000,'equity':1800000,'current_assets':3200000,'current_liabilities':2100000,'cfads':740000,'debt_service':525000}
        for k,v in vals.items(): self.analytics_vars[k].set(str(v))

    def calculate_analytics(self):
        vals={k:parse_num(v.get()) for k,v in self.analytics_vars.items()}; present=sum(v is not None for v in vals.values()); dq=round(present/len(vals)*100)
        rev=vals['revenue']; ebitda=vals['ebitda']; debt=vals['financial_debt']; cash=vals['cash']; eq=vals['equity']; ca=vals['current_assets']; cl=vals['current_liabilities']; cfads=vals['cfads']; ds=vals['debt_service']
        margin=ebitda/rev if rev and ebitda is not None else None; pfn=(debt-cash) if debt is not None and cash is not None else None; lev=pfn/ebitda if pfn is not None and ebitda else None; cr=ca/cl if ca is not None and cl else None; dscr=cfads/ds if cfads is not None and ds else None; de=debt/eq if debt is not None and eq else None
        score=50
        if margin is not None: score += 12 if margin>=.15 else 7 if margin>=.08 else -5
        if lev is not None: score += 14 if lev<=1.5 else 7 if lev<=3 else -12
        if dscr is not None: score += 14 if dscr>=1.4 else 7 if dscr>=1.15 else -15
        if cr is not None: score += 6 if cr>=1.3 else 2 if cr>=1 else -6
        if de is not None: score += 4 if de<=1 else -4 if de>2 else 0
        score=max(0,min(100,round(score*dq/100)))
        rating='AAA' if score>=92 else 'AA' if score>=86 else 'A' if score>=80 else 'BBB' if score>=72 else 'BB' if score>=63 else 'B' if score>=52 else 'CCC' if score>=40 else 'D'
        semaphore='VERDE' if score>=80 else 'GIALLO' if score>=63 else 'ROSSO'
        self.last_analysis={'data_quality':dq,'ebitda_margin':margin,'pfn':pfn,'pfn_ebitda':lev,'current_ratio':cr,'dscr':dscr,'debt_equity':de,'score':score,'rating':rating,'semaphore':semaphore,**vals}
        for w in self.analytics_result.winfo_children(): w.destroy()
        self.metrics(self.analytics_result,[("Data Quality",f"{dq}%"),("Score",str(score)),("Rating",rating),("Semaforo",semaphore)],4)
        t=self.tree(self.analytics_result,[("kpi","KPI",180),("value","Valore",160),("note","Lettura",500)],height=6)
        kpis=[('EBITDA margin',pct(margin),'>= 15% robusto'),('PFN',euro(pfn),'Debito finanziario netto'),('PFN/EBITDA',f"{lev:.2f}x" if lev is not None else 'N/D','<= 3x preferibile'),('Current Ratio',f"{cr:.2f}x" if cr is not None else 'N/D','> 1x equilibrio corrente'),('DSCR',f"{dscr:.2f}x" if dscr is not None else 'N/D','>= 1,2x sostenibilità debito'),('Debt/Equity',f"{de:.2f}x" if de is not None else 'N/D','Leva patrimoniale')]
        for x in kpis:t.insert('','end',values=x)

    # ---- CR ----
    def page_cr(self):
        sf=self.sf("Centrale Rischi multi-mese", "CSV atteso: month, granted, used, past_due, bad_debt")
        c=self.card(sf.inner,"Importazione CR")
        self.cr_file_label=ttk.Label(c,text="Nessun CSV selezionato",style="Card.TLabel",foreground=MUTED); self.cr_file_label.pack(side='left',padx=14,pady=16)
        ttk.Button(c,text="Carica CSV Centrale Rischi",style="Primary.TButton",command=self.load_cr_csv).pack(side='right',padx=14,pady=12)
        self.cr_result_frame=ttk.Frame(sf.inner); self.cr_result_frame.pack(fill='x')

    def load_cr_csv(self):
        p=filedialog.askopenfilename(filetypes=[('CSV','*.csv')]);
        if not p:return
        self.cr_file_label.configure(text=Path(p).name)
        try:
            rows=list(csv.DictReader(open(p,encoding='utf-8-sig'))); self.analyze_cr_rows(rows)
        except Exception as exc: messagebox.showerror('Centrale Rischi',str(exc))

    def analyze_cr_rows(self,rows):
        data=[]
        for r in rows:
            data.append({'month':r.get('month',''),'granted':parse_num(r.get('granted')) or 0,'used':parse_num(r.get('used')) or 0,'past_due':parse_num(r.get('past_due')) or 0,'bad_debt':parse_num(r.get('bad_debt')) or 0})
        if not data:return
        latest=data[-1]; utils=[x['used']/x['granted'] if x['granted'] else 0 for x in data]; self.last_cr={'months':len(data),'granted_latest':latest['granted'],'used_latest':latest['used'],'latest_utilization':utils[-1],'avg_utilization':sum(utils)/len(utils),'past_due_latest':latest['past_due'],'bad_debt_latest':latest['bad_debt'],'trend':'in aumento' if len(utils)>1 and utils[-1]>utils[0]+.05 else 'stabile'}
        self.render_cr_result()

    def show_demo_cr(self):
        rows=[]
        for i,m in enumerate(['09/2025','10/2025','11/2025','12/2025','01/2026','02/2026','03/2026','04/2026','05/2026','06/2026','07/2026','08/2026']): rows.append({'month':m,'granted':850000,'used':560000+i*4700,'past_due':0 if i<9 else 12500,'bad_debt':0})
        self.analyze_cr_rows(rows)

    def render_cr_result(self):
        for w in self.cr_result_frame.winfo_children():w.destroy()
        r=self.last_cr; self.metrics(self.cr_result_frame,[("Affidato",euro(r['granted_latest'])),("Utilizzato",euro(r['used_latest'])),("Utilizzo",pct(r['latest_utilization'])),("Scaduti",euro(r['past_due_latest']))],4)
        t=self.tree(self.cr_result_frame,[("k","Indicatore",220),("v","Valore",180),("n","Nota",430)],height=5)
        for x in [('Mesi analizzati',r['months'],'Serie storica disponibile'),('Utilizzo medio',pct(r['avg_utilization']),'Media used/granted'),('Sofferenze',euro(r['bad_debt_latest']),'Ultimo mese'),('Trend',r['trend'],'Confronto inizio/fine serie')]: t.insert('','end',values=x)

    # ---- Bank accounts ----
    def page_bank(self):
        sf=self.sf("Conti correnti e cash-flow", "CSV atteso: date, amount. Positivo = entrata; negativo = uscita")
        c=self.card(sf.inner,"Importazione movimenti")
        self.bank_file_label=ttk.Label(c,text="Nessun CSV selezionato",style="Card.TLabel",foreground=MUTED); self.bank_file_label.pack(side='left',padx=14,pady=16)
        ttk.Button(c,text="Carica CSV movimenti",style="Primary.TButton",command=self.load_bank_csv).pack(side='right',padx=14,pady=12)
        self.bank_result_frame=ttk.Frame(sf.inner); self.bank_result_frame.pack(fill='x')

    def load_bank_csv(self):
        p=filedialog.askopenfilename(filetypes=[('CSV','*.csv')]);
        if not p:return
        self.bank_file_label.configure(text=Path(p).name)
        try: rows=list(csv.DictReader(open(p,encoding='utf-8-sig'))); self.analyze_bank_rows(rows)
        except Exception as exc: messagebox.showerror('Conti Correnti',str(exc))

    def analyze_bank_rows(self,rows):
        vals=[]; monthly={}
        for r in rows:
            a=parse_num(r.get('amount')) or 0; vals.append(a); d=str(r.get('date','')); m=d[:7] if re.match(r'\d{4}-\d{2}',d) else d[-7:]; monthly[m]=monthly.get(m,0)+a
        inflow=sum(v for v in vals if v>0); outflow=-sum(v for v in vals if v<0); net=sum(vals); neg=sum(1 for v in monthly.values() if v<0); avg=net/max(1,len(monthly)); self.last_bank={'transactions':len(vals),'inflows':inflow,'outflows':outflow,'net_cash_flow':net,'avg_monthly_net':avg,'negative_months':neg,'months':monthly}; self.render_bank_result()

    def show_demo_bank(self):
        rows=[]
        for m in range(1,7):
            rows += [{'date':f'2026-{m:02d}-05','amount':'220000'},{'date':f'2026-{m:02d}-15','amount':'-145000'},{'date':f'2026-{m:02d}-25','amount':'-45000' if m not in [2,5] else '-105000'}]
        self.analyze_bank_rows(rows)

    def render_bank_result(self):
        for w in self.bank_result_frame.winfo_children():w.destroy()
        r=self.last_bank; self.metrics(self.bank_result_frame,[("Entrate",euro(r['inflows'])),("Uscite",euro(r['outflows'])),("Cash-flow netto",euro(r['net_cash_flow'])),("Mesi negativi",str(r['negative_months']))],4)
        t=self.tree(self.bank_result_frame,[("month","Mese",120),("net","Cash-flow netto",160),("status","Esito",120)],height=6)
        for m,v in sorted(r['months'].items()): t.insert('','end',values=(m,euro(v),'Positivo' if v>=0 else 'Negativo'))

    # ---- Business plan ----
    def page_bp(self):
        sf=self.sf("Business Plan a 5 anni", "Proiezione ricavi, EBITDA, imposte proxy, CAPEX, capitale circolante e cash-flow")
        c=self.card(sf.inner,"Assunzioni")
        self.bp_vars={k:tk.StringVar() for k in ['base','growth','margin','tax','capex','wc']}; self.bp_vars['growth'].set('5');self.bp_vars['margin'].set('15');self.bp_vars['tax'].set('24');self.bp_vars['wc'].set('10')
        grid=ttk.Frame(c,style="Card.TFrame"); grid.pack(fill='x',padx=8,pady=5); labels=[('base','Ricavi base €'),('growth','Crescita ricavi %'),('margin','EBITDA margin %'),('tax','Tax rate proxy %'),('capex','CAPEX €'),('wc','Capitale circolante %')]
        for i,(k,l) in enumerate(labels): self.labeled_entry(grid,l,self.bp_vars[k],row=i//3,col=i%3)
        ttk.Button(c,text="Proietta 5 anni",style="Primary.TButton",command=self.calculate_bp).pack(anchor='e',padx=14,pady=10)
        self.bp_result_frame=ttk.Frame(sf.inner); self.bp_result_frame.pack(fill='x')

    def fill_demo_bp(self): self.bp_vars['base'].set('5500000');self.bp_vars['growth'].set('5');self.bp_vars['margin'].set('15');self.bp_vars['tax'].set('24');self.bp_vars['capex'].set('650000');self.bp_vars['wc'].set('10')

    def calculate_bp(self):
        base=parse_num(self.bp_vars['base'].get()) or 0; growth=(parse_num(self.bp_vars['growth'].get()) or 0)/100; margin=(parse_num(self.bp_vars['margin'].get()) or 0)/100; tax=(parse_num(self.bp_vars['tax'].get()) or 0)/100; capex=parse_num(self.bp_vars['capex'].get()) or 0; wc=(parse_num(self.bp_vars['wc'].get()) or 0)/100
        rows=[]; rev=base
        for i in range(1,6):
            rev*=1+growth; ebitda=rev*margin; taxes=ebitda*tax; cap=capex if i==1 else 0; nwc=rev*wc; cash=ebitda-taxes-cap; rows.append({'year':datetime.now().year+i,'revenue':rev,'ebitda':ebitda,'tax':taxes,'capex':cap,'working_capital':nwc,'operating_cashflow':cash})
        self.last_bp=rows
        for w in self.bp_result_frame.winfo_children():w.destroy()
        t=self.tree(self.bp_result_frame,[("year","Anno",70),("rev","Ricavi",130),("ebitda","EBITDA",120),("tax","Tax proxy",110),("capex","CAPEX",110),("wc","Capitale circolante",140),("cash","Cash-flow operativo",150)],height=6)
        for r in rows:t.insert('','end',values=(r['year'],euro(r['revenue']),euro(r['ebitda']),euro(r['tax']),euro(r['capex']),euro(r['working_capital']),euro(r['operating_cashflow'])))
        ttk.Button(self.bp_result_frame,text="Esporta CSV",style="Secondary.TButton",command=self.export_bp_csv).pack(anchor='e',padx=8,pady=5)

    def export_bp_csv(self):
        p=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')],initialfile='Business_Plan_5_anni.csv');
        if not p:return
        with open(p,'w',newline='',encoding='utf-8-sig') as f: w=csv.DictWriter(f,fieldnames=self.last_bp[0].keys());w.writeheader();w.writerows(self.last_bp)

    # ---- Dossier ----
    def page_dossier(self):
        sf=self.sf("Dossier Banca PDF + Markdown", "Generazione dossier usando cliente CRM e le ultime analisi disponibili")
        c=self.card(sf.inner,"Cliente")
        rows=self.store.q("SELECT id,name,vat,pec,ateco,address,city,province FROM clients ORDER BY name"); self.dossier_map={r['name']:r['id'] for r in rows}; self.dossier_client=tk.StringVar(value=rows[0]['name'] if rows else '')
        box=ttk.Frame(c,style="Card.TFrame"); box.pack(fill='x',padx=14,pady=10); ttk.Label(box,text='Cliente Airtable/Locale',style='Card.TLabel').pack(anchor='w'); ttk.Combobox(box,textvariable=self.dossier_client,values=list(self.dossier_map),state='readonly').pack(fill='x',pady=(4,0))
        ttk.Button(c,text="Genera dossier",style="Primary.TButton",command=self.generate_dossier_preview).pack(anchor='e',padx=14,pady=10)
        self.dossier_result_frame=ttk.Frame(sf.inner); self.dossier_result_frame.pack(fill='both',expand=True)

    def generate_dossier_preview(self):
        name=self.dossier_client.get(); cid=self.dossier_map.get(name); c=self.store.one("SELECT * FROM clients WHERE id=?",(cid,)) if cid else None
        if not c: return
        ana=self.store.one("SELECT * FROM analyses WHERE client_id=? ORDER BY id DESC LIMIT 1",(cid,)); a=dict(ana) if ana else self.last_analysis
        score=a.get('score','N/D') if isinstance(a,dict) else 'N/D'; rating=a.get('rating','N/D') if isinstance(a,dict) else 'N/D'; dscr=a.get('dscr') if isinstance(a,dict) else None; lev=a.get('pfn_ebitda') if isinstance(a,dict) else None
        md=f"# Dossier Bancario - {c['name']}\n\n**P.IVA:** {c['vat'] or '—'}  \n**PEC:** {c['pec'] or '—'}  \n**ATECO:** {c['ateco'] or '—'}\n\n## Executive Summary\nProfilo economico-finanziario con rating **{rating}**, score **{score}**, DSCR **{dscr if dscr is not None else 'N/D'}** e PFN/EBITDA **{lev if lev is not None else 'N/D'}**.\n\n## Raccomandazioni\n- Presidio del capitale circolante.\n- Riduzione dei tempi medi di incasso.\n- Mantenimento di un buffer di liquidità coerente con il servizio del debito.\n"
        self.last_dossier_md=md
        for w in self.dossier_result_frame.winfo_children():w.destroy()
        box=ttk.Frame(self.dossier_result_frame,style='Card.TFrame'); box.pack(fill='x',padx=8,pady=7); ttk.Label(box,text=f"Dossier bancario - {c['name']}",style='Card.TLabel',font=('Segoe UI',13,'bold')).pack(anchor='w',padx=14,pady=(12,4)); ttk.Label(box,text=f"Rating {rating}   •   Score {score}   •   DSCR {dscr if dscr is not None else 'N/D'}   •   PFN/EBITDA {lev if lev is not None else 'N/D'}",style='Card.TLabel',foreground=NAVY).pack(anchor='w',padx=14,pady=4); ttk.Label(box,text="Raccomandazioni: presidio capitale circolante, riduzione DSO, buffer liquidità.",style='Card.TLabel',wraplength=900).pack(anchor='w',padx=14,pady=(4,12))
        row=ttk.Frame(self.dossier_result_frame); row.pack(fill='x',padx=8,pady=5); ttk.Button(row,text='Esporta PDF',style='Primary.TButton',command=lambda:self.export_dossier(c,True)).pack(side='left',padx=(0,6)); ttk.Button(row,text='Esporta Markdown',style='Secondary.TButton',command=lambda:self.export_dossier(c,False)).pack(side='left')

    def export_dossier(self,c,pdf=True):
        if pdf:
            out=self.store.output_dir/f"{safe_filename(c['name'])}_Dossier_Banca.pdf"; self._simple_text_pdf(out,f"Dossier Banca - {c['name']}",self.last_dossier_md); messagebox.showinfo('Dossier',f'Creato: {out}'); open_path(out)
        else:
            out=self.store.output_dir/f"{safe_filename(c['name'])}_Dossier_Banca.md"; out.write_text(self.last_dossier_md,encoding='utf-8'); messagebox.showinfo('Dossier',f'Creato: {out}'); open_path(out)

    def _simple_text_pdf(self,out,title,body):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer
        styles=getSampleStyleSheet(); styles.add(ParagraphStyle(name='Navy',parent=styles['Heading1'],textColor=colors.HexColor(NAVY)))
        story=[Paragraph(title,styles['Navy']),Spacer(1,12)]
        for block in body.replace('# ','').split('\n\n'):
            if block.strip(): story.append(Paragraph(block.replace('**',''),styles['BodyText'])); story.append(Spacer(1,8))
        SimpleDocTemplate(str(out),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=42,bottomMargin=42).build(story)

    # ---- Mandates ----
    def page_mandates(self):
        sf=self.sf("Mandati - calcolo compenso", "Aliquote, IVA e ritenuta sono input espliciti; storico salvato nel database")
        c=self.card(sf.inner,"Nuovo calcolo")
        self.mandate_vars={k:tk.StringVar() for k in ['client','practice','requested','approved','fee_pct','fixed','vat','withholding']}; self.mandate_vars['fee_pct'].set('2');self.mandate_vars['fixed'].set('0');self.mandate_vars['vat'].set('22');self.mandate_vars['withholding'].set('0')
        grid=ttk.Frame(c,style='Card.TFrame'); grid.pack(fill='x',padx=8,pady=5); labels=[('client','Cliente'),('practice','Pratica / banca'),('requested','Richiesto €'),('approved','Deliberato/erogato €'),('fee_pct','Compenso %'),('fixed','Compenso fisso €'),('vat','IVA %'),('withholding','Ritenuta %')]
        for i,(k,l) in enumerate(labels): self.labeled_entry(grid,l,self.mandate_vars[k],row=i//4,col=i%4)
        ttk.Button(c,text='Calcola mandato',style='Primary.TButton',command=self.calculate_mandate).pack(anchor='e',padx=14,pady=10)
        self.mandate_result_frame=ttk.Frame(sf.inner); self.mandate_result_frame.pack(fill='x'); self.render_mandate_history()

    def fill_demo_mandate(self):
        v=self.mandate_vars; v['client'].set('ACME INDUSTRIA SRL');v['practice'].set('FP-2026-014 / Intesa');v['requested'].set('500000');v['approved'].set('450000');v['fee_pct'].set('2');v['fixed'].set('1500');v['vat'].set('22');v['withholding'].set('0')

    def calculate_mandate(self):
        v=self.mandate_vars; requested=parse_num(v['requested'].get()) or 0; approved=parse_num(v['approved'].get()) or 0; base=approved if approved>0 else requested; fee_pct=(parse_num(v['fee_pct'].get()) or 0)/100; fixed=parse_num(v['fixed'].get()) or 0; vat=(parse_num(v['vat'].get()) or 0)/100; wh=(parse_num(v['withholding'].get()) or 0)/100; taxable=base*fee_pct+fixed; total=taxable+taxable*vat-taxable*wh
        self.store.execute("INSERT INTO mandates(dt,client,practice,requested,approved,fee_pct,fixed,vat,withholding,fee_base,taxable_fee,total_due) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(datetime.now().strftime('%d/%m/%Y %H:%M'),v['client'].get(),v['practice'].get(),requested,approved,fee_pct,fixed,vat,wh,base,taxable,total)); self.render_mandate_history((base,taxable,total))

    def render_mandate_history(self,metrics=None):
        for w in self.mandate_result_frame.winfo_children():w.destroy()
        if metrics:self.metrics(self.mandate_result_frame,[("Base",euro(metrics[0])),("Imponibile",euro(metrics[1])),("Totale da incassare",euro(metrics[2]))],3)
        t=self.tree(self.mandate_result_frame,[("dt","Data",120),("client","Cliente",180),("practice","Pratica",170),("base","Base",105),("taxable","Imponibile",105),("total","Totale",105)],height=7)
        for r in self.store.q("SELECT * FROM mandates ORDER BY id DESC LIMIT 50"):t.insert('','end',values=(r['dt'],r['client'],r['practice'],euro(r['fee_base']),euro(r['taxable_fee']),euro(r['total_due'])))
        ttk.Button(self.mandate_result_frame,text='Esporta storico CSV',style='Secondary.TButton',command=self.export_mandates).pack(anchor='e',padx=8,pady=5)

    def export_mandates(self):
        p=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')],initialfile='Mandati_FINANCE_PLUS.csv');
        if not p:return
        rows=self.store.q("SELECT * FROM mandates ORDER BY id")
        with open(p,'w',newline='',encoding='utf-8-sig') as f:
            w=csv.writer(f); w.writerow(rows[0].keys() if rows else []); [w.writerow(tuple(r)) for r in rows]

    # ---- Config ----
    def page_config(self):
        sf=self.sf("Configurazione", "Percorsi locali, integrazioni cloud e credenziali. Le chiavi restano nel file config.json sul PC")
        c=self.card(sf.inner,"Archivio locale")
        tk.Label(c,text=f"Directory dati: {self.store.data_dir}\nDatabase: {self.store.db_path}\nArchivio documenti: {self.store.archive_dir}\nOutput: {self.store.output_dir}",justify='left',bg=CARD,fg=TEXT,font=('Segoe UI',9),padx=14,pady=10).pack(fill='x')
        row=ttk.Frame(c,style='Card.TFrame'); row.pack(fill='x',padx=14,pady=(0,12)); ttk.Button(row,text='Apri cartella dati',style='Secondary.TButton',command=lambda:open_path(self.store.data_dir)).pack(side='left'); ttk.Button(row,text='Carica dati demo',style='Secondary.TButton',command=self.load_demo_manual).pack(side='left',padx=6)
        c2=self.card(sf.inner,"Integrazioni cloud")
        self.config_vars={k:tk.StringVar(value=str(self.cfg.get(k,''))) for k in ['airtable_base_id','airtable_token','google_drive_folder_id','google_oauth_token_json','openai_api_key','adobe_client_id','adobe_client_secret']}
        grid=ttk.Frame(c2,style='Card.TFrame'); grid.pack(fill='x',padx=8,pady=5); specs=[('airtable_base_id','Airtable Base ID'),('airtable_token','Airtable Token'),('google_drive_folder_id','Google Drive Folder ID'),('google_oauth_token_json','Google OAuth Token JSON'),('openai_api_key','OpenAI API Key'),('adobe_client_id','Adobe PDF Services Client ID'),('adobe_client_secret','Adobe PDF Services Secret')]
        for i,(k,l) in enumerate(specs):
            e=self.labeled_entry(grid,l,self.config_vars[k],row=i//2,col=i%2);
            if 'token' in k or 'key' in k or 'secret' in k: e.configure(show='•')
        self.adobe_conf_var=tk.BooleanVar(value=bool(self.cfg.get('allow_adobe_confidential',False))); ttk.Checkbutton(c2,text='Consenti Adobe anche per documenti Riservati (sconsigliato senza policy interna)',variable=self.adobe_conf_var).pack(anchor='w',padx=14,pady=5)
        row2=ttk.Frame(c2,style='Card.TFrame'); row2.pack(fill='x',padx=14,pady=12); ttk.Button(row2,text='Salva configurazione',style='Primary.TButton',command=self.save_config).pack(side='right'); ttk.Button(row2,text='Test Airtable',style='Secondary.TButton',command=self.test_airtable).pack(side='left'); ttk.Button(row2,text='Test Google OAuth',style='Secondary.TButton',command=self.test_google).pack(side='left',padx=6)
        st=self.card(sf.inner,"Stato integrazioni")
        cfg=self.cfg; states=[('Airtable','Configurato' if cfg.get('airtable_token') else 'Non configurato'),('Google Gmail/Drive','Configurato' if cfg.get('google_oauth_token_json') else 'Non configurato'),('OpenAI','Configurato' if cfg.get('openai_api_key') else 'Non configurato'),('Adobe PDF Services','Configurato' if cfg.get('adobe_client_id') and cfg.get('adobe_client_secret') else 'Non configurato')]
        for name,state in states: tk.Label(st,text=f"● {name}: {state}",bg=CARD,fg=GREEN if state=='Configurato' else AMBER,font=('Segoe UI',9,'bold'),anchor='w',padx=14,pady=5).pack(fill='x')

    def save_config(self):
        for k,v in self.config_vars.items(): self.cfg[k]=v.get().strip()
        self.cfg['allow_adobe_confidential']=bool(self.adobe_conf_var.get()); self.store.save_config(self.cfg); messagebox.showinfo('Configurazione','Configurazione salvata sul PC.')

    def load_demo_manual(self):
        self.store.seed_demo(); messagebox.showinfo('Dati demo','Dati dimostrativi caricati se il database era vuoto.')

    def test_airtable(self):
        token=self.config_vars.get('airtable_token').get().strip(); base=self.config_vars.get('airtable_base_id').get().strip()
        if not token or not base: messagebox.showwarning('Airtable','Token o Base ID mancanti.'); return
        try:
            import requests
            r=requests.get(f'https://api.airtable.com/v0/meta/bases/{base}/tables',headers={'Authorization':f'Bearer {token}'},timeout=15); messagebox.showinfo('Airtable',f'HTTP {r.status_code}: ' + ('connessione riuscita' if r.ok else r.text[:300]))
        except Exception as exc: messagebox.showerror('Airtable',str(exc))

    def test_google(self):
        raw=self.config_vars.get('google_oauth_token_json').get().strip()
        if not raw: messagebox.showwarning('Google','Token JSON mancante.'); return
        try:
            info=json.loads(raw); from google.oauth2.credentials import Credentials; from googleapiclient.discovery import build; creds=Credentials.from_authorized_user_info(info); profile=build('oauth2','v2',credentials=creds,cache_discovery=False).userinfo().get().execute(); messagebox.showinfo('Google',f"Connesso: {profile.get('email','account Google')}")
        except Exception as exc: messagebox.showerror('Google',str(exc))


def build_arg_parser():
    p=argparse.ArgumentParser(description=APP_NAME)
    p.add_argument('--data-dir',default='')
    p.add_argument('--screen',default='dashboard')
    p.add_argument('--demo',action='store_true')
    return p


def main():
    args=build_arg_parser().parse_args(); data_dir=Path(args.data_dir).expanduser() if args.data_dir else default_data_dir(); store=Store(data_dir)
    root=tk.Tk(); app=FinancePlusApp(root,store,args.screen,args.demo); root.mainloop()


if __name__=='__main__':
    main()
