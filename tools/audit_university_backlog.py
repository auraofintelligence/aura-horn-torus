#!/usr/bin/env python3
"""Match previously unscoped historical universities against the pinned ROR dump.

Only current ROR identity and locality fields from accepted records are public.
The source CSV, candidate identities and reasons remain in the ignored work/
audit. ROR locality coordinates are not campus or building coordinates. Both
input hashes are pinned so a changed historical list cannot silently shift IDs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit

from prepare_university_match_catalogue import (
    DEFAULT_OUTPUT as DEFAULT_SCOPED,
    DEFAULT_ROR,
    OUTPUT_FIELDS,
    REPO,
    held_output,
    read_rows,
    safe_output,
)

SOURCE_HASH = "5D91F265476BCB5051404C5949BA3F0F8D67CE54BC78A8BF95206ED79A57B991"
ROR_HASH = "5984C0455F5AF6DD9AF69E8AD5DF3220D28EE0804B67A4D987EF98F079CE1DAA"
NAME_TYPES = {"ror_display", "label", "alias"}
CURRENT_TYPES = {"ror_display", "label"}
DEFAULT_OUTPUT = REPO / "data" / "university-backlog-matches-v2.11.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def normal_name(value: str) -> str:
    """Keep every script and diacritic; never transliterate to ASCII."""
    value = unicodedata.normalize("NFKC", value or "").casefold().replace("&", " and ")
    return " ".join("".join(ch if ch.isalnum() or unicodedata.category(ch).startswith("M") else " " for ch in value).split())


def canonical_host(value: str) -> str:
    """Exact hostname only: no parent-domain, redirect or subdomain inference."""
    value = (value or "").strip()
    if not value:
        return ""
    try:
        parts = urlsplit(value if "://" in value else "//" + value)
        if parts.username or parts.password:
            return ""
        host = (parts.hostname or "").casefold().rstrip(".")
        if host.startswith("www."):
            host = host[4:]
        return host.encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        return ""


def iter_records(path: Path) -> Iterator[dict[str, Any]]:
    """Read the 305 MB array incrementally without retaining the full dump."""
    decoder = json.JSONDecoder()
    with path.open(encoding="utf-8") as handle:
        buffer = handle.read(1024 * 1024).lstrip()
        if not buffer.startswith("["):
            raise ValueError("ROR dump must be a JSON array")
        buffer = buffer[1:]
        while True:
            buffer = buffer.lstrip(" \t\r\n,")
            if buffer.startswith("]"):
                return
            try:
                value, position = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    raise ValueError("Incomplete ROR JSON array")
                buffer += chunk
                continue
            yield value
            buffer = buffer[position:]


def display_name(record: dict[str, Any]) -> str:
    for kind in ("ror_display", "label"):
        for name in record.get("names", []):
            if kind in name.get("types", []):
                return name.get("value", "")
    return ""


def build_indexes(path: Path, countries: set[str]) -> tuple[dict, dict, dict, dict]:
    records, names, sites = {}, defaultdict(set), defaultdict(set)
    country_labels: dict[str, Counter] = defaultdict(Counter)
    for raw in iter_records(path):
        rid = raw["id"]
        locations = raw.get("locations") or []
        record_countries = set()
        for location in locations:
            details = location.get("geonames_details") or {}
            code = details.get("country_code", "")
            record_countries.add(code)
            if code and details.get("country_name"):
                country_labels[code][details["country_name"]] += 1
        hosts = {canonical_host(value) for value in raw.get("domains") or []}
        hosts.update(canonical_host(link.get("value", "")) for link in raw.get("links") or []
                     if link.get("type") == "website")
        hosts.discard("")
        # All countries and organisation types participate in site conflicts.
        for host in hosts:
            sites[host].add(rid)
        matched_names = defaultdict(set)
        for entry in raw.get("names") or []:
            kinds = NAME_TYPES.intersection(entry.get("types") or [])
            key = normal_name(entry.get("value", ""))
            if kinds and key:
                matched_names[key].update(kinds)
        if record_countries.intersection(countries):
            for country in record_countries.intersection(countries):
                for key in matched_names:
                    names[(country, key)].add(rid)
        # Lightweight records also support globally unique official-site checks.
        records[rid] = {
            "id": rid, "status": raw.get("status", ""),
            "types": raw.get("types") or [], "name": display_name(raw),
            "names": dict(matched_names), "hosts": hosts, "locations": locations,
        }
    labels = {code: values.most_common(1)[0][0] for code, values in country_labels.items()}
    return records, names, sites, labels


def valid_location(record: dict, country: str) -> bool:
    locations = record["locations"]
    if len(locations) != 1:
        return False
    location = locations[0]
    details = location.get("geonames_details") or {}
    try:
        latitude, longitude = float(details["lat"]), float(details["lng"])
        geonames_id = int(location.get("geonames_id", 0))
    except (ValueError, TypeError, KeyError):
        return False
    return (math.isfinite(latitude) and math.isfinite(longitude)
            and -90 <= latitude <= 90 and -180 <= longitude <= 180
            and geonames_id > 0 and bool(details.get("name"))
            and details.get("country_code") == country)


def classify(country: str, source_name: str, source_site: str,
             records: dict, names: dict, sites: dict) -> tuple[str, str, str, dict]:
    key, host = normal_name(source_name), canonical_host(source_site)
    exact = names.get((country, key), set()) if key else set()
    active = {rid for rid in exact if records[rid]["status"] == "active"}
    inactive = exact - active
    site = sites.get(host, set()) if host else set()
    evidence = {"normalised_name": key, "source_host": host,
                "exact_active_ids": sorted(active), "exact_inactive_ids": sorted(inactive),
                "official_site_ids": sorted(site)}
    if inactive:
        return ("review" if active else "inactive_history",
                "held_inactive_name_conflict" if active else "held_inactive_exact_name", "", evidence)
    if len(active) > 1:
        return "review", "held_ambiguous_active_exact_name", "", evidence
    if not active:
        return ("review", "held_review_site_only", "", evidence) if site else (
            "unmatched", "unmatched", "", evidence)
    rid = next(iter(active))
    record = records[rid]
    if "education" not in record["types"]:
        return "review", "held_non_education_identity", "", evidence
    if site and rid not in site:
        return "review", "held_site_name_conflict", "", evidence
    if len(record["locations"]) != 1:
        return "review", "held_multiple_ror_locations", "", evidence
    if not valid_location(record, country):
        return "review", "held_invalid_ror_location", "", evidence
    current_name = bool(record["names"][key].intersection(CURRENT_TYPES))
    clean_site = site == {rid}
    if not current_name and not clean_site:
        return "review", "held_alias_without_clean_domain_agreement", "", evidence
    method = "safe_active_exact_name_site_agreement" if clean_site else "safe_active_exact_name_only"
    evidence["name_types"] = sorted(record["names"][key])
    return "safe_active", method, rid, evidence


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    source_hash, ror_hash = sha256(args.source), sha256(args.ror)
    if source_hash != SOURCE_HASH or ror_hash != ROR_HASH:
        raise ValueError("Input hash mismatch: this audit is pinned to the original list and ROR v2.11")
    scoped = read_rows(args.scoped)
    scoped_ids = {int(row["source_row_number"]) for row in scoped}
    if len(scoped_ids) != len(scoped):
        raise ValueError("Existing scoped ledger contains duplicate source rows")
    with args.source.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.reader(handle))
    if any(len(row) != 3 for row in source_rows):
        raise ValueError("Historical source must have three columns and no header")
    if not scoped_ids.issubset(range(1, len(source_rows) + 1)):
        raise ValueError("Scoped ledger refers outside the historical source")
    backlog = [(number, row) for number, row in enumerate(source_rows, 1) if number not in scoped_ids]
    records, names, sites, labels = build_indexes(args.ror, {row[0] for _, row in backlog})
    output, audit = [], []
    by_country: dict[str, Counter] = defaultdict(Counter)
    for number, (country, source_name, source_site) in backlog:
        classification, method, rid, evidence = classify(country, source_name, source_site, records, names, sites)
        if rid:
            record = records[rid]
            location = record["locations"][0]
            details = location["geonames_details"]
            row = safe_output(
                source_row_number=str(number), scope_group="global_backlog",
                source_country=country, source_country_name=details["country_name"],
                ror_id=rid, ror_name=record["name"], ror_status=record["status"],
                geonames_id=str(location["geonames_id"]), locality=details["name"],
                subdivision_name=details.get("country_subdivision_name") or "",
                latitude=str(details["lat"]), longitude=str(details["lng"]), match_method=method,
            )
        else:
            row = held_output(str(number), "global_backlog", classification, country, labels.get(country, ""), method)
        output.append(row)
        by_country[country][classification] += 1
        audit.append({**row, "source_name": source_name, "source_website": source_site, **evidence})
    # Independent release checks use the indexed source fields, never candidates.
    for row in output:
        if row["classification"] == "safe_active":
            record = records[row["ror_id"]]
            if record["status"] != "active" or "education" not in record["types"] or not valid_location(record, row["source_country"]):
                raise ValueError(f"Unsafe release row {row['source_row_number']}")
            if row["ror_name"] != record["name"]:
                raise ValueError("Public name differs from the ROR display name")
        elif any(row[field] for field in ("ror_id", "ror_name", "ror_status", "geonames_id", "locality", "subdivision_name", "latitude", "longitude")):
            raise ValueError("Held row leaked candidate identity or coordinates")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)
    safe = [row for row in output if row["classification"] == "safe_active"]
    summary = {
        "sourceSha256": source_hash, "rorSha256": ror_hash, "rorVersion": "v2.11",
        "rorReleaseDate": "2026-08-03", "sourceRows": len(source_rows),
        "existingScopedRows": len(scoped), "backlogRows": len(output),
        "safeSourceRows": len(safe), "uniqueRor": len({row["ror_id"] for row in safe}),
        "heldRows": len(output) - len(safe), "classifications": dict(Counter(row["classification"] for row in output)),
        "methods": dict(Counter(row["match_method"] for row in output)),
        "countries": {country: dict(counts) for country, counts in sorted(by_country.items())},
        "coordinateBasis": "ROR v2.11 GeoNames locality centroid; not a campus or building pin",
        "currency": "Identity and status are matched to the pinned 3 August 2026 ROR snapshot; no live status or website check is implied.",
        "output": str(args.output),
    }
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps({"summary": summary, "audit": audit}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--source", type=Path, default=Path.home() / "Downloads" / "world-universities.csv")
    command.add_argument("--scoped", type=Path, default=DEFAULT_SCOPED)
    command.add_argument("--ror", type=Path, default=DEFAULT_ROR)
    command.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    command.add_argument("--audit", type=Path, default=REPO / "work" / "university-backlog-audit-v2.11.json")
    return command


if __name__ == "__main__":
    print(json.dumps(prepare(parser().parse_args()), ensure_ascii=False, indent=2))
