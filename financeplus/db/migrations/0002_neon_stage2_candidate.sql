-- APP_NUOVA_SETT_IA_00 MASTER - Neon Stage2 candidate migration
-- TESTED ONLY on isolated Neon branch master-stage2-20260916 (2026-09-16).
-- DO NOT apply to production without a fresh preflight and explicit approval.
-- The existing public tables were found empty during Stage2. This script aborts if
-- any conflicting legacy table contains rows, preserving a fail-safe migration path.

DO $$
DECLARE n bigint;
BEGIN
  IF to_regclass('public.clients') IS NOT NULL THEN
    EXECUTE 'SELECT count(*) FROM public.clients' INTO n;
    IF n <> 0 THEN RAISE EXCEPTION 'clients is not empty (% rows): manual mapping required', n; END IF;
    IF to_regclass('public.pre_master_clients_20260916') IS NULL THEN ALTER TABLE public.clients RENAME TO pre_master_clients_20260916; END IF;
  END IF;
  IF to_regclass('public.practices') IS NOT NULL THEN
    EXECUTE 'SELECT count(*) FROM public.practices' INTO n;
    IF n <> 0 THEN RAISE EXCEPTION 'practices is not empty (% rows): manual mapping required', n; END IF;
    IF to_regclass('public.pre_master_practices_20260916') IS NULL THEN ALTER TABLE public.practices RENAME TO pre_master_practices_20260916; END IF;
  END IF;
  IF to_regclass('public.documents') IS NOT NULL THEN
    EXECUTE 'SELECT count(*) FROM public.documents' INTO n;
    IF n <> 0 THEN RAISE EXCEPTION 'documents is not empty (% rows): manual mapping required', n; END IF;
    IF to_regclass('public.pre_master_documents_20260916') IS NULL THEN ALTER TABLE public.documents RENAME TO pre_master_documents_20260916; END IF;
  END IF;
  IF to_regclass('public.mandates') IS NOT NULL THEN
    EXECUTE 'SELECT count(*) FROM public.mandates' INTO n;
    IF n <> 0 THEN RAISE EXCEPTION 'mandates is not empty (% rows): manual mapping required', n; END IF;
    IF to_regclass('public.pre_master_mandates_20260916') IS NULL THEN ALTER TABLE public.mandates RENAME TO pre_master_mandates_20260916; END IF;
  END IF;
  IF to_regclass('public.audit_log') IS NOT NULL THEN
    EXECUTE 'SELECT count(*) FROM public.audit_log' INTO n;
    IF n <> 0 THEN RAISE EXCEPTION 'audit_log is not empty (% rows): manual mapping required', n; END IF;
    IF to_regclass('public.pre_master_audit_log_20260916') IS NULL THEN ALTER TABLE public.audit_log RENAME TO pre_master_audit_log_20260916; END IF;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.clients (
 id BIGSERIAL PRIMARY KEY, legal_name VARCHAR(255) NOT NULL, vat VARCHAR(32) NOT NULL DEFAULT '',
 tax_code VARCHAR(32) NOT NULL DEFAULT '', pec VARCHAR(255) NOT NULL DEFAULT '', rea VARCHAR(64) NOT NULL DEFAULT '',
 registered_office TEXT NOT NULL DEFAULT '', postal_code VARCHAR(16) NOT NULL DEFAULT '', city VARCHAR(120) NOT NULL DEFAULT '',
 province VARCHAR(16) NOT NULL DEFAULT '', ateco VARCHAR(32) NOT NULL DEFAULT '', legal_form VARCHAR(120) NOT NULL DEFAULT '',
 administrator VARCHAR(255) NOT NULL DEFAULT '', share_capital DOUBLE PRECISION NULL, notes TEXT NOT NULL DEFAULT '',
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_clients_legal_name ON public.clients(legal_name);
CREATE INDEX IF NOT EXISTS ix_clients_vat ON public.clients(vat);
CREATE INDEX IF NOT EXISTS ix_clients_tax_code ON public.clients(tax_code);

CREATE TABLE IF NOT EXISTS public.practices (
 id BIGSERIAL PRIMARY KEY, client_id BIGINT NOT NULL REFERENCES public.clients(id) ON DELETE CASCADE,
 code VARCHAR(120) NOT NULL UNIQUE, practice_type VARCHAR(80) NOT NULL DEFAULT '', institution VARCHAR(255) NOT NULL DEFAULT '',
 requested_amount DOUBLE PRECISION NULL, status VARCHAR(80) NOT NULL DEFAULT 'Da avviare', priority VARCHAR(32) NOT NULL DEFAULT 'Media',
 owner VARCHAR(255) NOT NULL DEFAULT '', next_action TEXT NOT NULL DEFAULT '', next_action_due DATE NULL,
 missing_documents TEXT NOT NULL DEFAULT '', documentation_status VARCHAR(80) NOT NULL DEFAULT 'Da verificare',
 alerts TEXT NOT NULL DEFAULT '', created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.documents (
 id BIGSERIAL PRIMARY KEY, client_id BIGINT NULL REFERENCES public.clients(id) ON DELETE SET NULL,
 practice_id BIGINT NULL REFERENCES public.practices(id) ON DELETE SET NULL, category VARCHAR(120) NOT NULL DEFAULT 'Altro',
 original_name VARCHAR(500) NOT NULL DEFAULT '', canonical_name VARCHAR(500) NOT NULL DEFAULT '', sha256 VARCHAR(64) NOT NULL UNIQUE,
 storage_uri TEXT NOT NULL DEFAULT '', source_channel VARCHAR(120) NOT NULL DEFAULT 'manuale', source_message_id VARCHAR(255) NOT NULL DEFAULT '',
 verification_status VARCHAR(64) NOT NULL DEFAULT 'DA_VERIFICARE', document_date DATE NULL, fiscal_year INTEGER NULL,
 metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.crm_events (
 id BIGSERIAL PRIMARY KEY, client_id BIGINT NULL REFERENCES public.clients(id) ON DELETE SET NULL,
 practice_id BIGINT NULL REFERENCES public.practices(id) ON DELETE SET NULL, event_type VARCHAR(64) NOT NULL DEFAULT 'Nota',
 event_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, sender_role VARCHAR(64) NOT NULL DEFAULT '', sender_name VARCHAR(255) NOT NULL DEFAULT '',
 recipient_role VARCHAR(64) NOT NULL DEFAULT '', recipient_name VARCHAR(255) NOT NULL DEFAULT '', institution VARCHAR(255) NOT NULL DEFAULT '',
 amount DOUBLE PRECISION NULL, instrument VARCHAR(64) NOT NULL DEFAULT '', subject VARCHAR(255) NOT NULL DEFAULT '',
 details TEXT NOT NULL DEFAULT '', status VARCHAR(64) NOT NULL DEFAULT 'INEVASA'
);

CREATE TABLE IF NOT EXISTS public.analyses (
 id BIGSERIAL PRIMARY KEY, client_id BIGINT NULL REFERENCES public.clients(id) ON DELETE SET NULL,
 practice_id BIGINT NULL REFERENCES public.practices(id) ON DELETE SET NULL, analysis_type VARCHAR(80) NOT NULL DEFAULT 'credit',
 data_quality INTEGER NOT NULL DEFAULT 0, score DOUBLE PRECISION NULL, rating VARCHAR(32) NOT NULL DEFAULT 'INCOMPLETO',
 pd_label VARCHAR(120) NOT NULL DEFAULT 'NON CALCOLATA', result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.mandates (
 id BIGSERIAL PRIMARY KEY, client_id BIGINT NULL REFERENCES public.clients(id) ON DELETE SET NULL,
 practice_id BIGINT NULL REFERENCES public.practices(id) ON DELETE SET NULL, percentage DOUBLE PRECISION NOT NULL DEFAULT 0,
 fixed_fee DOUBLE PRECISION NOT NULL DEFAULT 0, basis_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
 notes TEXT NOT NULL DEFAULT '', created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS public.operators (
 id BIGSERIAL PRIMARY KEY, code VARCHAR(80) NOT NULL UNIQUE, name VARCHAR(255) NOT NULL, category VARCHAR(120) NOT NULL DEFAULT '',
 active INTEGER NOT NULL DEFAULT 1, weights_json JSONB NOT NULL DEFAULT '{}'::jsonb, constraints_json JSONB NOT NULL DEFAULT '{}'::jsonb,
 required_documents_json JSONB NOT NULL DEFAULT '[]'::jsonb, source TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS public.audit_log (
 id BIGSERIAL PRIMARY KEY, occurred_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, actor VARCHAR(255) NOT NULL DEFAULT 'system',
 action VARCHAR(120) NOT NULL, entity_type VARCHAR(120) NOT NULL DEFAULT '', entity_id VARCHAR(120) NOT NULL DEFAULT '',
 source VARCHAR(255) NOT NULL DEFAULT '', detail_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS public.provenance_records (
 id BIGSERIAL PRIMARY KEY, feature VARCHAR(160) NOT NULL, source_chat VARCHAR(255) NOT NULL DEFAULT '',
 source_file VARCHAR(500) NOT NULL DEFAULT '', source_version VARCHAR(120) NOT NULL DEFAULT '', source_hash VARCHAR(128) NOT NULL DEFAULT '',
 master_path VARCHAR(500) NOT NULL DEFAULT '', status VARCHAR(120) NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
 CONSTRAINT uq_provenance_feature_source UNIQUE(feature, source_file, source_version)
);
