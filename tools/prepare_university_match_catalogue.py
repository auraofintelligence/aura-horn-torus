#!/usr/bin/env python3
"""Prepare the minimal publishable ROR match catalogue used by the globe.

The full audits stay in ``work/``.  The tracked output contains one row for
each scoped historical source row, but publishes current ROR/GeoNames fields
only for records that pass the stricter release gate.  Historical names,
websites and free-text audit notes are deliberately left out.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
WORK = REPO / "work"
DEFAULT_OCEANIA = WORK / "university-coordinate-audit-oceania-ror-v2.11-2026-08-11.csv"
DEFAULT_PARTNERS = (
    WORK
    / "university-agreement-audit"
    / "university-agreement-coordinate-audit-ror-v2.11.csv"
)
DEFAULT_ROR = WORK / "ror-jp-kr-audit" / "v2.11-2026-08-03-ror-data.json"
DEFAULT_OUTPUT = REPO / "data" / "university-ror-matches-v2.11.csv"

OUTPUT_FIELDS = [
    "source_row_number",
    "scope_group",
    "classification",
    "source_country",
    "source_country_name",
    "ror_id",
    "ror_name",
    "ror_status",
    "geonames_id",
    "locality",
    "subdivision_name",
    "latitude",
    "longitude",
    "match_method",
]


def normal_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    text = text.replace("&", " and ")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    words = re.findall(r"[a-z0-9]+", text)
    return " ".join(words)


def truthy(value: Any) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes"}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def ror_location_counts(path: Path) -> dict[str, int]:
    records = json.loads(path.read_text(encoding="utf-8"))
    return {str(record.get("id")): len(record.get("locations") or []) for record in records}


def safe_output(
    *,
    source_row_number: str,
    scope_group: str,
    source_country: str,
    source_country_name: str,
    ror_id: str,
    ror_name: str,
    ror_status: str,
    geonames_id: str,
    locality: str,
    subdivision_name: str,
    latitude: str,
    longitude: str,
    match_method: str,
) -> dict[str, str]:
    return {
        "source_row_number": source_row_number,
        "scope_group": scope_group,
        "classification": "safe_active",
        "source_country": source_country,
        "source_country_name": source_country_name,
        "ror_id": ror_id,
        "ror_name": ror_name,
        "ror_status": ror_status,
        "geonames_id": geonames_id,
        "locality": locality,
        "subdivision_name": subdivision_name,
        "latitude": latitude,
        "longitude": longitude,
        "match_method": match_method,
    }


def held_output(
    source_row_number: str,
    scope_group: str,
    classification: str,
    source_country: str,
    source_country_name: str,
    match_method: str,
) -> dict[str, str]:
    row = {field: "" for field in OUTPUT_FIELDS}
    row.update(
        {
            "source_row_number": source_row_number,
            "scope_group": scope_group,
            "classification": classification,
            "source_country": source_country,
            "source_country_name": source_country_name,
            "match_method": match_method,
        }
    )
    return row


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    location_counts = ror_location_counts(args.ror)
    output: list[dict[str, str]] = []

    for row in read_rows(args.oceania_audit):
        classification = row.get("classification", "")
        source_name = row.get("source_name", "")
        ror_name = row.get("ror_name", "")
        ror_id = row.get("ror_id", "")
        domain_evidence = row.get("domain_evidence", "").strip()
        release_safe = classification == "safe_active" and truthy(row.get("publish_ready"))
        if release_safe and row.get("match_method", "") == "automatic-strict-domain":
            release_safe = False
            classification = "review"
            match_method = "held-domain-only-identity"
        elif release_safe and location_counts.get(ror_id, 0) != 1:
            release_safe = False
            classification = "review"
            match_method = "held-multiple-ror-locations"
        elif release_safe and normal_name(source_name) != normal_name(ror_name) and not domain_evidence:
            release_safe = False
            classification = "review"
            match_method = "held-alias-without-domain-agreement"
        else:
            match_method = row.get("match_method", "")

        if release_safe:
            output.append(
                safe_output(
                    source_row_number=row.get("source_row_number", ""),
                    scope_group="oceania",
                    source_country=row.get("source_country", ""),
                    source_country_name=row.get("source_country_name", ""),
                    ror_id=ror_id,
                    ror_name=ror_name,
                    ror_status=row.get("ror_status", ""),
                    geonames_id=row.get("geonames_id", ""),
                    locality=row.get("locality", ""),
                    subdivision_name=row.get("subdivision_name", ""),
                    latitude=row.get("latitude", ""),
                    longitude=row.get("longitude", ""),
                    match_method=match_method,
                )
            )
        else:
            held_class = "inactive_history" if classification == "inactive_history" else classification
            output.append(
                held_output(
                    row.get("source_row_number", ""),
                    "oceania",
                    held_class,
                    row.get("source_country", ""),
                    row.get("source_country_name", ""),
                    match_method,
                )
            )

    partner_rows = read_rows(args.partner_audit)
    partner_country_names = {
        row.get("source_country_code", ""): row.get("geonames_country_name", "")
        for row in partner_rows
        if row.get("geonames_country_name")
    }
    for row in partner_rows:
        group = {
            "FTA outside Oceania": "fta_partner",
            "EU Framework": "eu_framework",
            "Named treaty": "named_treaty",
            "Named bilateral": "named_treaty",
        }.get(row.get("agreement_group", ""))
        if not group:
            raise ValueError(f"Unknown agreement group: {row.get('agreement_group')!r}")
        disposition = row.get("disposition", "")
        classification = {
            "safe": "safe_active",
            "review": "review",
            "inactive": "inactive_history",
            "unmatched": "unmatched",
        }.get(disposition, disposition)
        ror_id = row.get("ror_id", "")
        matched_types = {
            part.strip() for part in row.get("ror_matched_name_types", "").split("|") if part.strip()
        }
        alias_only = matched_types == {"alias"}
        site_agreement = row.get("match_status", "") == "safe_active_exact_name_site_agreement"
        warnings = row.get("warnings", "").strip()
        release_safe = classification == "safe_active"
        if release_safe and location_counts.get(ror_id, 0) != 1:
            release_safe = False
            classification = "review"
            match_method = "held-multiple-ror-locations"
        elif release_safe and alias_only and (not site_agreement or warnings):
            release_safe = False
            classification = "review"
            match_method = "held-alias-without-clean-domain-agreement"
        else:
            match_method = row.get("match_status", "")

        country_code = row.get("source_country_code", "")
        country_name = row.get("geonames_country_name", "") or partner_country_names.get(
            country_code, ""
        )
        if release_safe:
            output.append(
                safe_output(
                    source_row_number=row.get("source_row_number", ""),
                    scope_group=group,
                    source_country=country_code,
                    source_country_name=country_name,
                    ror_id=ror_id,
                    ror_name=row.get("ror_current_name", ""),
                    ror_status=row.get("ror_status", ""),
                    geonames_id=row.get("geonames_id", ""),
                    locality=row.get("geonames_locality", ""),
                    subdivision_name=row.get("geonames_admin_name", ""),
                    latitude=row.get("latitude", ""),
                    longitude=row.get("longitude", ""),
                    match_method=match_method,
                )
            )
        else:
            output.append(
                held_output(
                    row.get("source_row_number", ""),
                    group,
                    classification,
                    country_code,
                    country_name,
                    match_method,
                )
            )

    output.sort(key=lambda row: int(row["source_row_number"]))
    source_rows = [int(row["source_row_number"]) for row in output]
    if len(source_rows) != len(set(source_rows)):
        raise ValueError("Scoped university audits contain duplicate source rows")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)

    summary: dict[str, dict[str, int]] = {}
    for group in ("oceania", "fta_partner", "eu_framework", "named_treaty"):
        rows = [row for row in output if row["scope_group"] == group]
        safe_rows = [row for row in rows if row["classification"] == "safe_active"]
        summary[group] = {
            "sourceRows": len(rows),
            "safeSourceRows": len(safe_rows),
            "uniqueRor": len({row["ror_id"] for row in safe_rows}),
            "held": len(rows) - len(safe_rows),
        }
    return {"output": str(args.output), "rows": len(output), "groups": summary}


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--oceania-audit", type=Path, default=DEFAULT_OCEANIA)
    command.add_argument("--partner-audit", type=Path, default=DEFAULT_PARTNERS)
    command.add_argument("--ror", type=Path, default=DEFAULT_ROR)
    command.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return command


if __name__ == "__main__":
    print(json.dumps(prepare(parser().parse_args()), indent=2))
