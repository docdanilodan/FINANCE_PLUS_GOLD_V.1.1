from financeplus.db.session import _sqlalchemy_database_url


def test_plain_postgresql_url_uses_psycopg3_driver():
    raw = "postgresql://user:pass@example.com/db?sslmode=require"
    assert _sqlalchemy_database_url(raw) == "postgresql+psycopg://user:pass@example.com/db?sslmode=require"


def test_explicit_psycopg_url_is_unchanged():
    raw = "postgresql+psycopg://user:pass@example.com/db"
    assert _sqlalchemy_database_url(raw) == raw


def test_sqlite_url_is_unchanged():
    raw = "sqlite:///financeplus_master.db"
    assert _sqlalchemy_database_url(raw) == raw
