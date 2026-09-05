#!/usr/bin/env python3
"""Combine the original audited scopes, remaining world rows and sourced reviews.

This preserves the original ledger. Only accepted review rows gain ROR fields;
historical mergers and unresolved candidates remain visible in the audit trail.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from prepare_university_match_catalogue import OUTPUT_FIELDS, read_rows
from audit_university_backlog import ROR_HASH, sha256

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
REVIEW_METHOD = "reviewed_official_same_identity"


def complete(ror_path: Path) -> dict:
    if sha256(ror_path) != ROR_HASH:
        raise ValueError("ROR input must match the verified v2.11 snapshot bytes")
    base = read_rows(DATA / "university-ror-matches-v2.11.csv")
    backlog = read_rows(DATA / "university-backlog-matches-v2.11.csv")
    rows = base + backlog
    row_numbers = [int(row["source_row_number"]) for row in rows]
    if len(row_numbers) != len(set(row_numbers)) or set(row_numbers) != set(range(1, 9364)):
        raise ValueError("Base and backlog must cover all 9,363 rows exactly once")
    by_row = {int(row["source_row_number"]): row for row in rows}
    registry = {record["id"]: record for record in json.loads(ror_path.read_text(encoding="utf-8"))}
    review_path = DATA / "university-reviewed-matches.json"
    review_doc = json.loads(review_path.read_text(encoding="utf-8"))
    if review_doc.get("registryVersion") != "2.11" or review_doc.get("checkedAt") != "2026-09-05":
        raise ValueError("Unexpected review registry or date")
    promoted = []
    seen = set()
    for review in review_doc["reviews"]:
        number = int(review["sourceRowNumber"])
        if number in seen or number not in by_row:
            raise ValueError(f"Duplicate or unknown review source row {number}")
        seen.add(number)
        row = by_row[number]
        if row["source_country"] != review["sourceCountry"]:
            raise ValueError(f"Review country disagrees at {number}")
        if review["decision"] != "accept":
            continue
        if row["classification"] == "safe_active":
            raise ValueError(f"Review must resolve a held row: {number}")
        if not review.get("reason") or not review.get("sources") or any(
            not source.get("url", "").startswith("https://") or not source.get("supports")
            for source in review["sources"]
        ):
            raise ValueError(f"Review lacks explicit HTTPS evidence at {number}")
        record = registry[review["rorId"]]
        locations = record.get("locations", [])
        if record.get("status") != "active" or "education" not in record.get("types", []) or len(locations) != 1:
            raise ValueError(f"Reviewed ROR must be active education with one location: {number}")
        location = locations[0]
        geo = location["geonames_details"]
        if geo["country_code"] != row["source_country"]:
            raise ValueError(f"Reviewed ROR country disagrees at {number}")
        name = next(n["value"] for n in record["names"] if "ror_display" in n["types"])
        row.update(
            classification="safe_active", ror_id=record["id"], ror_name=name,
            ror_status="active", geonames_id=str(location["geonames_id"]),
            locality=geo["name"], subdivision_name=geo.get("country_subdivision_name") or "",
            source_country_name=geo["country_name"], latitude=str(geo["lat"]),
            longitude=str(geo["lng"]), match_method=REVIEW_METHOD,
        )
        promoted.append(number)
    # Every accepted output, including earlier work, must still agree with this
    # exact registry snapshot. This also catches swapped coordinate columns.
    for row in rows:
        if row["classification"] != "safe_active":
            continue
        record = registry[row["ror_id"]]
        if record["status"] != "active" or "education" not in record["types"] or len(record["locations"]) != 1:
            raise ValueError(f"Invalid publishable ROR identity: {row['source_row_number']}")
        loc = record["locations"][0]
        geo = loc["geonames_details"]
        display = next(n["value"] for n in record["names"] if "ror_display" in n["types"])
        if (row["ror_name"] != display or row["source_country"] != geo["country_code"]
            or str(loc["geonames_id"]) != row["geonames_id"]
            or float(row["latitude"]) != float(geo["lat"])
            or float(row["longitude"]) != float(geo["lng"])):
            raise ValueError(f"ROR display/location disagreement: {row['source_row_number']}")
    rows.sort(key=lambda row: int(row["source_row_number"]))
    target = DATA / "university-matches-2026-09-05.csv"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "checkedAt": "2026-09-05", "registryVersion": "2.11",
        "registryUpdatedAt": "2026-08-03", "registrySourceUrl": "https://zenodo.org/records/21773148",
        "registrySha256": ROR_HASH,
        "sourceCount": len(rows), "classifications": dict(Counter(r["classification"] for r in rows)),
        "reviewedPromotions": promoted,
        "uniqueMappedOrganisations": len({r["ror_id"] for r in rows if r["classification"] == "safe_active"}),
        "inputHashes": {
            path.name: hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest().upper()
            for path in [DATA / "university-ror-matches-v2.11.csv", DATA / "university-backlog-matches-v2.11.csv", review_path]
        },
        "outputSha256": hashlib.sha256(target.read_bytes()).hexdigest().upper(),
    }
    (DATA / "university-completion-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ror", type=Path, default=REPO / "work/ror-jp-kr-audit/v2.11-2026-08-03-ror-data.json")
    print(json.dumps(complete(parser.parse_args().ror), indent=2))
