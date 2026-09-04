from __future__ import annotations

from datetime import date

import pytest

from services.openai_usage import OpenAIUsageClient, flatten_costs, load_project_labels


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _Session:
    def __init__(self, payloads):
        self.headers = {}
        self.payloads = list(payloads)
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, params, timeout))
        return _Response(self.payloads.pop(0))


def test_openai_costs_are_read_only_grouped_and_paginated():
    session = _Session(
        [
            {"data": [{"start_time": 1, "results": []}], "has_more": True, "next_page": "next"},
            {"data": [{"start_time": 2, "results": []}], "has_more": False, "next_page": None},
        ]
    )
    client = OpenAIUsageClient(admin_key="admin-test", base_url="https://api.example/v1", session=session)
    buckets = client.costs(
        start=date(2026, 8, 1),
        end=date(2026, 9, 1),
        project_ids=["proj_documenti"],
    )

    assert len(buckets) == 2
    assert all(call[0] == "https://api.example/v1/organization/costs" for call in session.calls)
    assert all(("group_by", "project_id") in call[1] for call in session.calls)
    assert all(("group_by", "line_item") in call[1] for call in session.calls)
    assert all(("project_ids", "proj_documenti") in call[1] for call in session.calls)
    assert all(
        name not in {"api_key_id", "api_key_ids"}
        for _, params, _ in session.calls
        for name, _ in params
    )
    assert ("page", "next") in session.calls[1][1]


def test_openai_cost_interval_must_be_positive():
    client = OpenAIUsageClient(admin_key="admin-test", session=_Session([]))
    with pytest.raises(ValueError):
        client.costs(start=date(2026, 9, 1), end=date(2026, 9, 1))


def test_flatten_costs_maps_project_ids_to_valid_dashboard_rows():
    rows = flatten_costs(
        [
            {
                "start_time": 1788220800,
                "results": [
                    {
                        "object": "organization.costs.result",
                        "project_id": "proj_documenti",
                        "line_item": "input_tokens",
                        "amount": {"value": 1.25, "currency": "usd"},
                    }
                ],
            }
        ],
        {"proj_documenti": "DOCUMENTI"},
    )
    assert rows[0]["Modulo"] == "DOCUMENTI"
    assert rows[0]["Project ID"] == "proj_documenti"
    assert rows[0]["Voce"] == "input_tokens"
    assert rows[0]["Importo"] == 1.25
    assert rows[0]["Valuta"] == "USD"
    assert "admin-test" not in str(rows)


def test_project_label_mapping_fails_closed_on_invalid_json():
    assert load_project_labels("not-json") == {}
    assert load_project_labels('["project"]') == {}
