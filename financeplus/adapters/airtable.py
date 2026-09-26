from __future__ import annotations
class AirtableAdapter:
    def __init__(self, token: str, base_id: str): self.token=token; self.base_id=base_id
    def _client(self):
        from services.airtable_adapter import AirtableGold
        return AirtableGold(token=self.token, base_id=self.base_id)
    def list_clients(self, limit: int=5000): return self._client().list_records("clienti", max_records=limit)
    def list_practices(self, limit: int=5000): return self._client().list_records("pratiche", max_records=limit)
