from services.azure_document_intelligence import (
    AzureDocumentIntelligenceClient,
    AzureDocumentIntelligenceConfig,
)


class _Response:
    def __init__(self, status_code, payload=None, headers=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}
        self.text = text
        self.ok = 200 <= status_code < 300

    def json(self):
        return self._payload


class _Session:
    def __init__(self):
        self.posts = []
        self.gets = []
        self.poll_count = 0

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return _Response(
            202,
            headers={"operation-location": "https://example.test/operations/1"},
        )

    def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        self.poll_count += 1
        if self.poll_count == 1:
            return _Response(200, {"status": "running"})
        return _Response(
            200,
            {
                "status": "succeeded",
                "analyzeResult": {"content": "# Bilancio\nRicavi 100"},
            },
        )


def test_azure_adapter_polls_and_extracts_content():
    session = _Session()
    config = AzureDocumentIntelligenceConfig(
        endpoint="https://example.test",
        key="secret",
        poll_interval_seconds=0.0,
    )
    content = AzureDocumentIntelligenceClient(config, session=session).analyze_bytes(b"%PDF")
    assert "Bilancio" in content
    assert len(session.posts) == 1
    assert len(session.gets) == 2
    assert session.posts[0][1]["params"]["outputContentFormat"] == "markdown"
