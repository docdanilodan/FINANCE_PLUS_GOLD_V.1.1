from __future__ import annotations

import json
import os
import sys

from googleapiclient.discovery import build

from services.airtable_adapter import AirtableGold
from services.drive_classification import ai_policy_for_sensitivity, resolve_drive_classification
from services.google_auth import discover_google_profiles, load_credentials, token_env_name


RANK = {"Interno": 1, "Riservato": 2, "Altamente riservato": 3}


def _strict_mode() -> bool:
    return os.getenv("FINANCEPLUS_DRIVE_SYNC_STRICT", "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _reconcile_profile(profile: str, airtable: AirtableGold | None) -> dict:
    creds = load_credentials(profile)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    summary = {
        "profile": profile,
        "scanned": 0,
        "labelled": 0,
        "updated_drive": 0,
        "updated_airtable": 0,
        "errors": [],
    }

    page_token = None
    while True:
        response = drive.files().list(
            q="trashed = false and appProperties has { key='financeplusSensitivity' }",
            spaces="drive",
            pageSize=100,
            pageToken=page_token,
            fields="nextPageToken,files(id,name,webViewLink,appProperties)",
        ).execute()

        for item in response.get("files", []):
            summary["scanned"] += 1
            try:
                props = dict(item.get("appProperties", {}) or {})
                current = props.get("financeplusSensitivity", "Interno")
                if current not in RANK:
                    current = "Interno"
                decision = resolve_drive_classification(drive, item.get("id", ""), fallback=current)
                if decision.source == "google-drive-label":
                    summary["labelled"] += 1

                # Drive labels are permitted to tighten FinancePlus security,
                # never to weaken an existing FinancePlus classification.
                if RANK.get(decision.sensitivity, 0) <= RANK.get(current, 0):
                    continue

                protection = props.get("financeplusDriveProtection", "Standard")
                policy = ai_policy_for_sensitivity(decision.sensitivity, protection)
                props.update(
                    {
                        "financeplusSensitivity": decision.sensitivity,
                        "financeplusAiPolicy": policy,
                        "financeplusClassificationSource": decision.source,
                    }
                )
                drive.files().update(
                    fileId=item["id"],
                    body={"appProperties": props},
                    fields="id,appProperties",
                ).execute()
                summary["updated_drive"] += 1

                if airtable and item.get("webViewLink"):
                    record = airtable.find_one("documenti", "URL Drive", item["webViewLink"])
                    if record:
                        airtable.update_record(
                            "documenti",
                            record["id"],
                            {
                                "Sensibilità dati": decision.sensitivity,
                                "Policy elaborazione AI": policy,
                            },
                        )
                        summary["updated_airtable"] += 1
            except Exception as exc:
                summary["errors"].append(
                    {"file_id": item.get("id", ""), "name": item.get("name", ""), "error": str(exc)}
                )

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return summary


def main() -> int:
    strict = _strict_mode()
    if not os.getenv("FINANCEPLUS_DRIVE_LABEL_MAP_JSON", "").strip().strip("{}"):
        print("DRIVE_CLASSIFICATION_SKIPPED FINANCEPLUS_DRIVE_LABEL_MAP_JSON non configurato")
        return 1 if strict else 0

    profiles = discover_google_profiles()
    if not profiles:
        print("DRIVE_CLASSIFICATION_SKIPPED nessun profilo Google configurato")
        return 1 if strict else 0

    airtable = AirtableGold() if os.getenv("AIRTABLE_TOKEN", "").strip() else None
    results: dict[str, dict] = {}
    failed = False
    for profile in profiles:
        env_name = token_env_name(profile)
        if not os.getenv(env_name, "").strip():
            results[profile] = {"status": "skipped", "reason": f"{env_name} non configurato"}
            failed = True
            continue
        try:
            results[profile] = _reconcile_profile(profile, airtable)
            if results[profile]["errors"]:
                failed = True
        except Exception as exc:
            results[profile] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
            failed = True

    print(json.dumps({"profiles": profiles, "results": results}, ensure_ascii=False, indent=2))
    if not failed:
        print("DRIVE_RECONCILIATION_OK")
    return 1 if strict and failed else 0


if __name__ == "__main__":
    sys.exit(main())
