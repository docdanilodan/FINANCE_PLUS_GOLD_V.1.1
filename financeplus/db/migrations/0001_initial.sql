-- APP_NUOVA_SETT_IA_00 MASTER initial schema.
-- PostgreSQL/Neon is the production source of truth. SQLite uses SQLAlchemy create_all for offline/test.
CREATE TABLE IF NOT EXISTS clients (
  id BIGSERIAL PRIMARY KEY,
  legal_name VARCHAR(255) NOT NULL,
  vat VARCHAR(32) DEFAULT '', tax_code VARCHAR(32) DEFAULT '', pec VARCHAR(255) DEFAULT '', rea VARCHAR(64) DEFAULT '',
  registered_office TEXT DEFAULT '', postal_code VARCHAR(16) DEFAULT '', city VARCHAR(120) DEFAULT '', province VARCHAR(16) DEFAULT '',
  ateco VARCHAR(32) DEFAULT '', legal_form VARCHAR(120) DEFAULT '', administrator VARCHAR(255) DEFAULT '', share_capital DOUBLE PRECISION,
  notes TEXT DEFAULT '', created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_clients_vat ON clients(vat);
CREATE INDEX IF NOT EXISTS ix_clients_tax_code ON clients(tax_code);

CREATE TABLE IF NOT EXISTS practices (
  id BIGSERIAL PRIMARY KEY, client_id BIGINT NOT NULL REFERENCES clients(id) ON DELETE CASCADE, code VARCHAR(120) NOT NULL UNIQUE,
  practice_type VARCHAR(80) DEFAULT '', institution VARCHAR(255) DEFAULT '', requested_amount DOUBLE PRECISION, status VARCHAR(80) DEFAULT 'Da avviare',
  priority VARCHAR(32) DEFAULT 'Media', owner VARCHAR(255) DEFAULT '', next_action TEXT DEFAULT '', next_action_due DATE,
  missing_documents TEXT DEFAULT '', documentation_status VARCHAR(80) DEFAULT 'Da verificare', alerts TEXT DEFAULT '', created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
  id BIGSERIAL PRIMARY KEY, client_id BIGINT REFERENCES clients(id) ON DELETE SET NULL, practice_id BIGINT REFERENCES practices(id) ON DELETE SET NULL,
  category VARCHAR(120) DEFAULT 'Altro', original_name VARCHAR(500) DEFAULT '', canonical_name VARCHAR(500) DEFAULT '', sha256 VARCHAR(64) NOT NULL UNIQUE,
  storage_uri TEXT DEFAULT '', source_channel VARCHAR(120) DEFAULT 'manuale', source_message_id VARCHAR(255) DEFAULT '', verification_status VARCHAR(64) DEFAULT 'DA_VERIFICARE',
  document_date DATE, fiscal_year INTEGER, metadata_json JSONB DEFAULT '{}'::jsonb, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_events (
  id BIGSERIAL PRIMARY KEY, client_id BIGINT REFERENCES clients(id) ON DELETE SET NULL, practice_id BIGINT REFERENCES practices(id) ON DELETE SET NULL,
  event_type VARCHAR(64) DEFAULT 'Nota', event_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, sender_role VARCHAR(64) DEFAULT '', sender_name VARCHAR(255) DEFAULT '',
  recipient_role VARCHAR(64) DEFAULT '', recipient_name VARCHAR(255) DEFAULT '', institution VARCHAR(255) DEFAULT '', amount DOUBLE PRECISION,
  instrument VARCHAR(64) DEFAULT '', subject VARCHAR(255) DEFAULT '', details TEXT DEFAULT '', status VARCHAR(64) DEFAULT 'INEVASA'
);

CREATE TABLE IF NOT EXISTS analyses (
  id BIGSERIAL PRIMARY KEY, client_id BIGINT REFERENCES clients(id) ON DELETE SET NULL, practice_id BIGINT REFERENCES practices(id) ON DELETE SET NULL,
  analysis_type VARCHAR(80) DEFAULT 'credit', data_quality INTEGER DEFAULT 0, score DOUBLE PRECISION, rating VARCHAR(32) DEFAULT 'INCOMPLETO',
  pd_label VARCHAR(120) DEFAULT 'NON CALCOLATA', result_json JSONB DEFAULT '{}'::jsonb, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mandates (
  id BIGSERIAL PRIMARY KEY, client_id BIGINT REFERENCES clients(id) ON DELETE SET NULL, practice_id BIGINT REFERENCES practices(id) ON DELETE SET NULL,
  percentage DOUBLE PRECISION DEFAULT 0, fixed_fee DOUBLE PRECISION DEFAULT 0, basis_amount DOUBLE PRECISION DEFAULT 0, notes TEXT DEFAULT '',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS operators (
  id BIGSERIAL PRIMARY KEY, code VARCHAR(80) NOT NULL UNIQUE, name VARCHAR(255) NOT NULL, category VARCHAR(120) DEFAULT '', active INTEGER DEFAULT 1,
  weights_json JSONB DEFAULT '{}'::jsonb, constraints_json JSONB DEFAULT '{}'::jsonb, required_documents_json JSONB DEFAULT '[]'::jsonb, source TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS audit_log (
  id BIGSERIAL PRIMARY KEY, occurred_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, actor VARCHAR(255) DEFAULT 'system', action VARCHAR(120) NOT NULL,
  entity_type VARCHAR(120) DEFAULT '', entity_id VARCHAR(120) DEFAULT '', source VARCHAR(255) DEFAULT '', detail_json JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS provenance_records (
  id BIGSERIAL PRIMARY KEY, feature VARCHAR(160) NOT NULL, source_chat VARCHAR(255) DEFAULT '', source_file VARCHAR(500) DEFAULT '', source_version VARCHAR(120) DEFAULT '',
  source_hash VARCHAR(128) DEFAULT '', master_path VARCHAR(500) DEFAULT '', status VARCHAR(120) DEFAULT '', notes TEXT DEFAULT '',
  CONSTRAINT uq_provenance_feature_source UNIQUE(feature, source_file, source_version)
);
