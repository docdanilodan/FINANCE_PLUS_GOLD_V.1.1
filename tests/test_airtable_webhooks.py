from __future__ import annotations

from services.airtable_webhooks import AirtableWebhookClient


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _Session:
    def __init__(self, pages=None):
        self.headers = {}
        self.pages = list(pages or [])
        self.get_calls = []
        self.post_calls = []

    def get(self, url, *, params=None, timeout):
        self.get_calls.append((url, params, timeout))
        return _Response(self.pages.pop(0))

    def post(self, url, *, json=None, timeout):
        self.post_calls.append((url, json, timeout))
        return _Response({"ok": True})


def _client(session):
    client = AirtableWebhookClient(token="pat-test", base_id="app00000000000000")
    client.session = session
    return client


def test_drain_payloads_uses_returned_cursor_until_queue_is_empty():
    session = _Session(
        [
            {"payloads": [{"baseTransactionNumber": 4}], "cursor": 5, "mightHaveMore": True},
            {"payloads": [{"baseTransactionNumber": 5}], "cursor": 6, "mightHaveMore": False},
        ]
    )
    result = _client(session).drain_payloads("ach00000000000000")
    assert result["cursor"] == 6
    assert len(result["payloads"]) == 2
    assert session.get_calls[0][1]["limit"] == 50
    assert session.get_calls[1][1]["cursor"] == 5


def test_enable_notifications_uses_official_toggle_endpoint():
    session = _Session()
    _client(session).enable_notifications("ach00000000000000", enable=False)
    url, payload, timeout = session.post_calls[0]
    assert url.endswith("/ach00000000000000/enableNotifications")
    assert payload == {"enable": False}
    assert timeout == 30
