from services.hybrid_data_provider import HybridDataProvider, is_neon_record


class FakeHybrid(HybridDataProvider):
    def __init__(self, rows_by_key, airtable=None):
        super().__init__(
            database_url="postgresql://redacted",
            airtable=airtable,
            connect_fn=None,
        )
        self.rows_by_key = rows_by_key

    def _fetchall(self, sql, params=()):
        lowered = " ".join(sql.lower().split())
        if "exists(select 1 from clients" in lowered:
            return [{"has_clients": self.rows_by_key.get("has_clients", False)}]
        if "from clients" in lowered and "join" not in lowered:
            return self.rows_by_key.get("clients", [])
        if "from practices p" in lowered:
            return self.rows_by_key.get("practices", [])
        if "from documents d" in lowered:
            return self.rows_by_key.get("documents", [])
        if "from analyses a" in lowered:
            return self.rows_by_key.get("analyses", [])
        return []


class FakeAirtable:
    def __init__(self):
        self.created = []

    def list_records(self, table, max_records=100, formula=None):
        return [{"id": "rec1", "fields": {"Cliente": "Fallback SRL"}}]

    def create_record(self, table, fields):
        self.created.append((table, fields))
        return {"id": "rec-created", "fields": fields}


def test_empty_neon_falls_back_to_airtable():
    db = FakeHybrid({"has_clients": False}, airtable=FakeAirtable())
    assert db.read_source == "airtable"
    assert db.list_records("clienti")[0]["fields"]["Cliente"] == "Fallback SRL"


def test_neon_clients_activate_core_read_source():
    db = FakeHybrid(
        {
            "has_clients": True,
            "clients": [
                {
                    "id": 7,
                    "legal_name": "ALFA SRL",
                    "vat": "01234567890",
                    "tax_code": "",
                    "pec": "",
                    "rea": "",
                    "registered_office": "Via Roma 1",
                    "postal_code": "00100",
                    "city": "Roma",
                    "province": "RM",
                    "ateco": "62.01",
                    "legal_form": "SRL",
                    "administrator": "Mario Rossi",
                    "share_capital": 10000.0,
                    "notes": "",
                }
            ],
        },
        airtable=FakeAirtable(),
    )
    records = db.list_records("clienti")
    assert db.read_source == "neon"
    assert records[0]["id"] == "neon:clienti:7"
    assert records[0]["fields"]["Cliente"] == "ALFA SRL"


def test_neon_record_write_is_blocked():
    db = FakeHybrid({"has_clients": True}, airtable=FakeAirtable())
    try:
        db.update_record("clienti", "neon:clienti:7", {"Cliente": "BETA SRL"})
    except RuntimeError as exc:
        assert "read-shadow" in str(exc)
    else:
        raise AssertionError("Neon write must be blocked in read-shadow phase")


def test_airtable_write_remains_available_for_legacy_record():
    airtable = FakeAirtable()
    db = FakeHybrid({"has_clients": False}, airtable=airtable)
    result = db.create_record("pratiche", {"Pratica ID": "FP-1"})
    assert result["id"] == "rec-created"
    assert airtable.created


def test_record_origin_helper():
    assert is_neon_record("neon:clienti:1") is True
    assert is_neon_record("recABC") is False
