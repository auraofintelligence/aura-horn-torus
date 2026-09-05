#!/usr/bin/env python3
"""Validate the portable education registry against its published data contract.

The default check needs only tracked public files. Pass --ror PATH to additionally
prove full coverage and field preservation against the pinned source snapshot.
No network requests or file writes are performed. Education is a ROR type, not
an assertion that every listed body is an accredited university.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from check_location_layers import read_layer, read_manifest

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
ROR_SHA256 = "5984C0455F5AF6DD9AF69E8AD5DF3220D28EE0804B67A4D987EF98F079CE1DAA"
VERSION, DATE = "v2.11", "2026-08-03"
SOURCE_URL = "https://zenodo.org/records/21773148"
RELATIONS = {"parent", "child", "related", "successor"}
LAYERS = {
    "oceania": "oceania-universities",
    "fta_partner": "australia-fta-universities",
    "eu_framework": "eu-framework-universities",
    "named_treaty": "timor-leste-universities",
    "global_backlog": "world-universities",
}
INDEX_FIELDS = [
    "rorId", "name", "countryCode", "countryName", "locality", "hasWebsite",
    "externalIdTypes", "relationshipTypes", "mapLayerId", "countries", "searchTerms",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load(path: Path) -> dict:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def file_hash(path: Path, *, normalise_text: bool = True) -> str:
    if not normalise_text:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest().upper()
    content = path.read_bytes()
    content = content.replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest().upper()


def is_ror(value: str) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"https://ror\.org/[0-9a-z]{9}", value))


def is_https(value: str) -> bool:
    try:
        url = urlsplit(value)
        return url.scheme == "https" and bool(url.hostname) and not url.username and not url.password
    except (TypeError, ValueError):
        return False


def snapshot(document: dict, label: str) -> None:
    require(document.get("registryVersion") == VERSION, f"{label}: wrong registry version")
    require(document.get("registryUpdatedAt") == DATE, f"{label}: wrong snapshot date")
    require(document.get("sourceUrl") == SOURCE_URL, f"{label}: wrong source URL")


def point_key(rid: str, latitude: float, longitude: float) -> tuple:
    # The original compact globe contract rounds coordinates to seven decimals.
    return rid, round(float(latitude), 7), round(float(longitude), 7)


def check_raw(path: Path, organisations: dict[str, dict]) -> None:
    require(file_hash(path, normalise_text=False) == ROR_SHA256, "Raw ROR snapshot hash mismatch")
    # Reuse only the streaming JSON reader, not the registry transformation.
    from audit_university_backlog import iter_records

    found = set()
    for raw in iter_records(path):
        if raw.get("status") != "active" or "education" not in raw.get("types", []):
            continue
        rid = raw["id"]
        require(rid not in found and rid in organisations, f"Raw ROR coverage differs: {rid}")
        found.add(rid)
        record = organisations[rid]
        names = raw.get("names") or []
        display = next(n["value"] for n in names if "ror_display" in n["types"])
        require(record["name"] == display, f"Raw display name differs: {rid}")
        for public, source in (("names", "names"), ("types", "types"), ("domains", "domains"), ("externalIds", "external_ids")):
            require(record[public] == (raw.get(source) or []), f"Raw {source} lost or changed: {rid}")
        expected_sites = list(dict.fromkeys(
            link["value"] for link in raw.get("links", [])
            if link.get("type") == "website" and link.get("value")
        ))
        require(record["websites"] == expected_sites, f"Raw websites lost or changed: {rid}")
        raw_locations = raw.get("locations") or []
        require(len(record["locations"]) == len(raw_locations), f"Raw localities lost or added: {rid}")
        field_pairs = {
            "name": "name", "subdivisionCode": "country_subdivision_code",
            "subdivision": "country_subdivision_name", "countryCode": "country_code",
            "countryName": "country_name", "latitude": "lat", "longitude": "lng",
        }
        for actual, original in zip(record["locations"], raw_locations):
            require(actual["geonamesId"] == original.get("geonames_id"), f"Raw GeoNames ID differs: {rid}")
            geo = original.get("geonames_details") or {}
            for public, source in field_pairs.items():
                expected = geo.get(source) if public in {"latitude", "longitude"} else geo.get(source) or ""
                require(actual[public] == expected, f"Raw locality {source} differs: {rid}")
        expected_relations = Counter(
            (r["id"], r.get("label") or "", r["type"])
            for r in raw.get("relationships", []) if r.get("type") in RELATIONS and r.get("id")
        )
        actual_relations = Counter((r["id"], r["name"], r["type"]) for r in record["relationships"])
        require(actual_relations == expected_relations, f"Raw supported relationships differ: {rid}")
    require(found == set(organisations), "Full extract omits or adds active ROR education identities")


def check(ror_path: Path | None = None) -> dict:
    full = load(DATA / "education-registry-v2.11.json")
    index = load(DATA / "education-registry-index.json")
    snapshot(full, "Full registry")
    snapshot(index, "Directory index")
    require(full.get("schemaVersion") == "aura-education-registry/1.0", "Wrong full-registry schema")
    require(index.get("schemaVersion") == "aura-education-registry-index/1.0", "Wrong index schema")
    require(full["source"]["sha256"] == ROR_SHA256 == index.get("sourceSha256"), "Published source hash is not the pinned ROR snapshot")
    require(full["source"]["licence"] == "CC0 1.0" and full["source"]["localityLicence"] == "CC BY 4.0", "Missing registry/locality licence provenance")

    organisations = {}
    countries = set()
    chunk_members = defaultdict(set)
    expected_points = Counter()
    relationship_counts = Counter()
    locations_count = multi_location = 0
    for record in full["organisations"]:
        rid = record.get("id")
        require(is_ror(rid) and rid not in organisations, f"Invalid or duplicate registry ID: {rid}")
        require(record.get("status") == "active" and "education" in record.get("types", []), f"Non-active/non-education record: {rid}")
        require(isinstance(record.get("name"), str) and record["name"], f"Missing organisation name: {rid}")
        organisations[rid] = record
        locations = record["locations"]
        require(bool(locations), f"Pinned record has no locality: {rid}")
        multi_location += len(locations) > 1
        locations_count += len(locations)
        for locality in locations:
            lat, lon = locality["latitude"], locality["longitude"]
            require(all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (lat, lon)), f"Invalid coordinates: {rid}")
            require(-90 <= lat <= 90 and -180 <= lon <= 180, f"Coordinates outside Earth: {rid}")
            code = locality["countryCode"]
            require(bool(re.fullmatch(r"[A-Z]{2}", code)), f"Invalid country code: {rid}")
            require(isinstance(locality["geonamesId"], int) and locality["geonamesId"] > 0 and bool(locality["name"]), f"Missing GeoNames locality: {rid}")
            countries.add(code)
            chunk_members[code].add(rid)
            expected_points[point_key(rid, lat, lon)] += 1
        for relation in record["relationships"]:
            require(is_ror(relation["id"]) and relation["type"] in RELATIONS and isinstance(relation["name"], str), f"Invalid registry relationship: {rid}")
            relationship_counts[relation["type"]] += 1
    require(len(organisations) == 26103, "The pinned release must contain 26,103 active education organisations")

    ledger_path = DATA / "university-matches-2026-09-05.csv"
    ledger_hash = file_hash(ledger_path)
    legacy = {}
    ledger_rows = set()
    with ledger_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            number = int(row["source_row_number"])
            require(number not in ledger_rows, "Duplicate historical ledger row")
            ledger_rows.add(number)
            if row["classification"] != "safe_active":
                continue
            rid, layer = row["ror_id"], LAYERS[row["scope_group"]]
            require(rid in organisations, f"Legacy mapped institution absent from full registry: {rid}")
            require(rid not in legacy or legacy[rid] == layer, f"Legacy ID occurs in different layers: {rid}")
            require(len(organisations[rid]["locations"]) == 1, f"Legacy single-pin match has multiple source localities: {rid}")
            legacy[rid] = layer
    require(ledger_rows == set(range(1, 9364)), "Historical ledger does not account for every source row")
    require(index["matchFile"] == ledger_path.name and index["matchSha256"] == ledger_hash, "Directory uses a different historical ledger")

    manifest, _ = read_manifest()
    manifest_by_id = {layer["id"]: layer for layer in manifest}
    map_layer = full["mapLayer"]
    require(map_layer["id"] == "education-registry" and map_layer["src"] == "data/layers/education-registry.js", "Unexpected registry map target")
    require(map_layer["matchFile"] == ledger_path.name and map_layer["matchSha256"] == ledger_hash, "Registry map uses a different historical ledger")
    require(map_layer["defaultVisible"] is False, "Large registry map layer must load on demand")
    actual_points = Counter()
    map_ids = {}
    for layer_id in [*LAYERS.values(), "education-registry"]:
        metadata = manifest_by_id.get(layer_id)
        require(metadata is not None, f"Map layer not registered: {layer_id}")
        points = read_layer(REPO / metadata["src"], layer_id) if metadata.get("src") else []
        require(len(points) == metadata["mappedCount"], f"Manifest point count differs: {layer_id}")
        ids = set()
        for point in points:
            require(len(point) >= 6 and point[5] in organisations, f"Unknown map ID in {layer_id}")
            rid = point[5]
            require(point[0] == " ".join(organisations[rid]["name"].split()), f"Map name differs from registry: {rid}")
            expected_layer = legacy.get(rid, "education-registry")
            require(layer_id == expected_layer, f"Institution mapped in wrong/duplicate layer: {rid}")
            ids.add(rid)
            actual_points[point_key(rid, point[1], point[2])] += 1
        expected_ids = set(organisations) - set(legacy) if layer_id == "education-registry" else {rid for rid, target in legacy.items() if target == layer_id}
        require(ids == expected_ids, f"Map identities lost or added in {layer_id}")
        map_ids[layer_id] = ids
    require(actual_points == expected_points, "Published pins do not retain every registry locality exactly once across layers")
    additional = map_ids["education-registry"]
    require(not additional.intersection(legacy), "Additional registry pins duplicate legacy mapped identities")
    require(file_hash(REPO / map_layer["src"]) == map_layer["sha256"], "Additional map layer hash mismatch")
    metadata = manifest_by_id["education-registry"]
    require(metadata.get("sourceSha256") == ROR_SHA256 and metadata.get("sourceUpdatedAt") == DATE, "Manifest registry snapshot provenance differs")
    require(metadata.get("defaultOn") is False, "Additional registry layer must be off by default")
    require(metadata.get("registryIndex") == "data/education-registry-index.json", "Manifest directory index link differs")
    require("locality" in metadata.get("coordinateBasis", "").lower() and "not a campus" in metadata.get("coordinateBasis", "").lower(), "Manifest must explain locality precision")

    require(index.get("fields") == INDEX_FIELDS, "Directory index must have the eleven-field country/alias contract")
    indexed = set()
    for row in index["rows"]:
        require(len(row) == len(INDEX_FIELDS), "Wrong directory index row width")
        rid = row[0]
        require(rid in organisations and rid not in indexed, f"Unknown or duplicate directory ID: {rid}")
        indexed.add(rid)
        record = organisations[rid]
        primary = record["locations"][0]
        require(row[1:5] == [record["name"], primary["countryCode"], primary["countryName"], primary["name"]], f"Directory name/primary locality differs: {rid}")
        require(row[5] is bool(record["websites"]), f"Directory website flag differs: {rid}")
        require(row[6] == sorted({item["type"] for item in record["externalIds"]}), f"Directory identifier types differ: {rid}")
        require(row[7] == sorted({item["type"] for item in record["relationships"]}), f"Directory relationship types differ: {rid}")
        require(row[8] == legacy.get(rid, "education-registry") and rid in map_ids[row[8]], f"Directory map link has no exact corresponding institution: {rid}")
        expected_countries = sorted({(loc["countryCode"], loc["countryName"]) for loc in record["locations"]})
        require(row[9] == [list(pair) for pair in expected_countries], f"Directory omits or changes a country: {rid}")
        require(isinstance(row[10], list) and all(isinstance(term, str) for term in row[10]) and len(row[10]) == len(set(row[10])), f"Invalid or duplicate directory search terms: {rid}")
        searchable = set(row[10]) | {record["name"]}
        required_terms = {entry["value"] for entry in record["names"] if entry.get("value")}
        for loc in record["locations"]:
            required_terms.update(loc[field] for field in ("name", "subdivision", "countryCode", "countryName") if loc[field])
        require(required_terms.issubset(searchable), f"Directory omits an alias or secondary locality: {rid}")
    require(indexed == set(organisations), "Directory and full registry identities differ")

    chunk_paths = {path.stem: path for path in (DATA / "education-registry").glob("*.json")}
    require(set(chunk_paths) == set(chunk_members), "Country chunks are missing or stale")
    for country, path in chunk_paths.items():
        chunk = load(path)
        snapshot(chunk, f"Chunk {country}")
        require(chunk.get("sourceSha256") == ROR_SHA256 and chunk.get("countryCode") == country, f"Country chunk provenance differs: {country}")
        chunk_ids = set()
        for record in chunk["organisations"]:
            rid = record["id"]
            require(rid in organisations and rid not in chunk_ids, f"Unknown or duplicate ID in country chunk {country}: {rid}")
            chunk_ids.add(rid)
            require(record == organisations[rid], f"Country details differ from full registry: {rid}")
        require(chunk_ids == chunk_members[country], f"Country chunk omits or adds an institution: {country}")

    additional_points = sum(count for (rid, _, _), count in actual_points.items() if rid in additional)
    expected_counts = {
        "organisations": len(organisations), "countries": len(countries),
        "localityEntries": locations_count, "validLocalityEntries": locations_count,
        "invalidCoordinateEntries": 0, "unmappableLocalityEntries": 0,
        "multiLocationOrganisations": multi_location,
        "existingMappedOrganisations": len(legacy), "additionalMapOrganisations": len(additional),
        "additionalMapPoints": additional_points, "unmappedOrganisations": 0,
        "relationships": dict(relationship_counts),
    }
    require(full["counts"] == expected_counts == index["counts"], "Registry/index counts disagree with actual data")
    require(map_layer["sourceCount"] == len(organisations) and map_layer["mappedCount"] == additional_points and map_layer["organisationCount"] == len(additional) and map_layer["unresolvedCount"] == 0, "Registry map count metadata disagrees")
    require(metadata["organisationCount"] == len(additional) and metadata["unresolvedCount"] == 0, "Manifest organisation count metadata disagrees")

    evidence = load(DATA / "university-applicability-evidence.json")
    bodies = {}
    for body in evidence["peakBodies"]:
        require(body["id"] not in bodies and is_https(body["url"]), "Invalid or duplicate association source")
        bodies[body["id"]] = body
    assessed = set()
    membership_count = 0
    for institution in evidence["institutions"]:
        rid = institution["rorId"]
        require(rid in organisations and rid not in assessed, f"Unknown or duplicate association evidence identity: {rid}")
        assessed.add(rid)
        require(institution["countryCode"] in {loc["countryCode"] for loc in organisations[rid]["locations"]}, f"Association evidence country differs: {rid}")
        require(institution.get("gajraStatus") == "not-assessed" and institution.get("capabilities") == [], f"Association membership incorrectly implies GAJRA status/capability: {rid}")
        require(bool(institution["memberships"]), f"Membership seed has no source: {rid}")
        member_bodies = set()
        for membership in institution["memberships"]:
            body_id = membership["bodyId"]
            require(body_id in bodies and body_id not in member_bodies, f"Unknown or duplicate association assertion: {rid}")
            member_bodies.add(body_id)
            membership_count += 1
            require(is_https(membership["sourceUrl"]) and bool(membership.get("evidence")) and membership.get("checkedAt") == "2026-09-05", f"Association assertion lacks dated HTTPS evidence: {rid}")
    require(evidence.get("counts") == {"institutionCount": len(assessed), "membershipCount": membership_count}, "Membership evidence counts differ from the sourced assertions")
    require(len(assessed) >= 8, "Membership evidence unexpectedly falls below the initial reviewed sample")

    if ror_path is not None:
        check_raw(ror_path, organisations)
    return {"status": "ok", "organisations": len(organisations), "localities": locations_count,
            "directoryRows": len(indexed), "countryChunks": len(chunk_paths),
            "additionalMapPoints": additional_points, "membershipEvidence": len(assessed),
            "membershipAssertions": membership_count,
            "rawSnapshotChecked": ror_path is not None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ror", type=Path, help="Also compare every exported identity and locality against the pinned raw ROR JSON")
    try:
        print(json.dumps(check(parser.parse_args().ror), indent=2))
    except (ValueError, KeyError, TypeError, OSError) as error:
        raise SystemExit(f"Education registry validation failed: {error}") from error
