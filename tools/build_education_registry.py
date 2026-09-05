#!/usr/bin/env python3
"""Build the portable ROR education registry, lazy directory and extra map layer.

This selects all active education records in the pinned ROR release, independently
of the historical university CSV. ROR is a research-organisation registry, not a
complete worldwide accreditation or university register. Locations are GeoNames
localities and known relationships are carried through without inferring scope,
membership, accreditation or suitability for an Aura/GAJRA project.
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
from typing import Any

from audit_university_backlog import DEFAULT_ROR, REPO, ROR_HASH, display_name, iter_records, sha256

SOURCE_URL = "https://zenodo.org/records/21773148"
VERSION = "v2.11"
RELEASE_DATE = "2026-08-03"
RELATIONSHIP_TYPES = {"parent", "child", "related", "successor"}
GROUP_LAYERS = {
    "oceania": "oceania-universities",
    "fta_partner": "australia-fta-universities",
    "eu_framework": "eu-framework-universities",
    "named_treaty": "timor-leste-universities",
    "global_backlog": "world-universities",
}


def compact(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def text(value: Any) -> str:
    return " ".join(str(value or "").split())


def semantic_record(raw: dict[str, Any]) -> dict[str, Any]:
    locations = []
    for location in raw.get("locations") or []:
        details = location.get("geonames_details") or {}
        locations.append({
            "geonamesId": location.get("geonames_id"),
            "name": details.get("name") or "",
            "subdivisionCode": details.get("country_subdivision_code") or "",
            "subdivision": details.get("country_subdivision_name") or "",
            "countryCode": details.get("country_code") or "",
            "countryName": details.get("country_name") or "",
            "latitude": details.get("lat"), "longitude": details.get("lng"),
        })
    return {
        "id": raw["id"], "name": display_name(raw), "status": raw["status"],
        "types": raw.get("types") or [], "names": raw.get("names") or [],
        "websites": list(dict.fromkeys(link["value"] for link in raw.get("links") or []
                                       if link.get("type") == "website" and link.get("value"))),
        "domains": raw.get("domains") or [], "externalIds": raw.get("external_ids") or [],
        "locations": locations,
        "relationships": [{"id": relation["id"], "name": relation.get("label") or "", "type": relation["type"]}
                          for relation in raw.get("relationships") or []
                          if relation.get("type") in RELATIONSHIP_TYPES and relation.get("id")],
    }


def valid_coordinates(location: dict[str, Any]) -> bool:
    latitude, longitude = location["latitude"], location["longitude"]
    return (isinstance(latitude, (int, float)) and not isinstance(latitude, bool)
            and isinstance(longitude, (int, float)) and not isinstance(longitude, bool)
            and math.isfinite(latitude) and math.isfinite(longitude)
            and -90 <= latitude <= 90 and -180 <= longitude <= 180)


def mappable(location: dict[str, Any]) -> bool:
    return (valid_coordinates(location) and bool(location["name"])
            and isinstance(location["geonamesId"], int) and location["geonamesId"] > 0
            and bool(re.fullmatch(r"[A-Z]{2}", location["countryCode"])))


def mapped_identities(path: Path) -> dict[str, str]:
    result = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("classification") != "safe_active":
                continue
            rid = row.get("ror_id", "")
            if not re.fullmatch(r"https://ror\.org/[0-9a-z]{9}", rid) or row.get("ror_status") != "active":
                raise ValueError("Effective university ledger contains an invalid accepted ROR identity")
            group = row.get("scope_group", "")
            if group not in GROUP_LAYERS:
                raise ValueError(f"Unknown effective university group: {group}")
            layer = GROUP_LAYERS[group]
            if rid in result and result[rid] != layer:
                raise ValueError(f"ROR identity is assigned to multiple existing layers: {rid}")
            result[rid] = layer
    return result


def check_existing_map_ids(mapped: dict[str, str], layer_dir: Path) -> None:
    """Ensure directory links for accepted legacy records have an actual map pin."""
    by_layer = defaultdict(set)
    for rid, layer_id in mapped.items():
        by_layer[layer_id].add(rid)
    for layer_id, required in by_layer.items():
        path = layer_dir / f"{layer_id}.js"
        content = path.read_text(encoding="utf-8-sig")
        prefix = f'window.AURA_LOCATION_DATA["{layer_id}"]='
        if prefix not in content:
            raise ValueError(f"Missing expected map layer assignment in {path.name}")
        rows = json.loads(content.split(prefix, 1)[1].strip().removesuffix(";"))
        actual = {row[5] for row in rows if len(row) > 5}
        if not required.issubset(actual):
            raise ValueError(f"Refresh existing university layers before this registry: {layer_id} lacks {len(required - actual)} identities")


def build(args: argparse.Namespace) -> dict[str, Any]:
    source_hash = sha256(args.ror)
    if source_hash != ROR_HASH:
        raise ValueError("ROR hash mismatch: this registry is pinned to v2.11 dated 3 August 2026")
    if not args.matches.is_file():
        raise ValueError("Generate the effective university ledger before building this registry")
    mapped = mapped_identities(args.matches)
    if not args.defer_map_link_check:
        check_existing_map_ids(mapped, args.existing_layers_dir)
    match_hash = hashlib.sha256(args.matches.read_bytes().replace(b"\r\n", b"\n")).hexdigest().upper()
    organisations = []
    for raw in iter_records(args.ror):
        if raw.get("status") == "active" and "education" in (raw.get("types") or []):
            organisation = semantic_record(raw)
            if not organisation["name"] or not re.fullmatch(r"https://ror\.org/[0-9a-z]{9}", organisation["id"]):
                raise ValueError("Active education record is missing its official name or identifier")
            organisations.append(organisation)
    organisations.sort(key=lambda item: item["id"])
    all_ids = {organisation["id"] for organisation in organisations}
    if len(all_ids) != len(organisations):
        raise ValueError("Duplicate ROR records in source")
    if not set(mapped).issubset(all_ids):
        raise ValueError("Effective map ledger includes identities absent from the active education registry")
    countries, chunks = set(), defaultdict(list)
    search_rows, points, additional_ids = [], [], set()
    invalid_coords = unmappable = location_count = multi_location = 0
    relations = Counter()
    for organisation in organisations:
        locations = organisation["locations"]
        country_codes = {location["countryCode"] for location in locations if location["countryCode"]}
        if any(not re.fullmatch(r"[A-Z]{2}", code) for code in country_codes):
            raise ValueError("Unexpected country code in ROR locality")
        countries.update(country_codes)
        for code in sorted(country_codes or {"ZZ"}):
            chunks[code].append(organisation)
        primary = locations[0] if locations else {}
        layer_id = mapped.get(organisation["id"], "education-registry")
        country_pairs = sorted({(location["countryCode"], location["countryName"])
                                for location in locations if location["countryCode"]})
        search_terms = {entry["value"] for entry in organisation["names"]
                        if entry.get("value") and entry["value"] != organisation["name"]}
        for location in locations:
            search_terms.update(value for value in (location["name"], location["subdivision"],
                                                   location["countryCode"], location["countryName"]) if value)
        search_rows.append([
            organisation["id"], organisation["name"], primary.get("countryCode", ""),
            primary.get("countryName", ""), primary.get("name", ""), bool(organisation["websites"]),
            sorted({entry["type"] for entry in organisation["externalIds"]}),
            sorted({entry["type"] for entry in organisation["relationships"]}), layer_id,
            country_pairs, sorted(search_terms),
        ])
        relations.update(entry["type"] for entry in organisation["relationships"])
        multi_location += len(locations) > 1
        location_count += len(locations)
        for number, location in enumerate(locations, 1):
            invalid_coords += not valid_coordinates(location)
            unmappable += not mappable(location)
            if organisation["id"] in mapped or not mappable(location):
                continue
            detail = ", ".join(value for value in (location["name"], location["subdivision"], location["countryName"]) if value)
            if len(locations) > 1:
                detail += f" · Location {number} of {len(locations)}"
            detail += " · GeoNames locality; not a campus pin"
            search = " ".join([location["countryCode"], location["countryName"], location["name"], location["subdivision"],
                               str(location["geonamesId"]), *[entry["value"] for entry in organisation["names"]],
                               *organisation["types"], "ROR education registry"])
            points.append([organisation["name"], location["latitude"], location["longitude"], text(detail),
                           f"Education organisation · {location['countryName'] or location['countryCode']}",
                           organisation["id"], text(search)])
            additional_ids.add(organisation["id"])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    layer_path = args.output_dir / "layers" / "education-registry.js"
    layer_path.parent.mkdir(parents=True, exist_ok=True)
    layer_bytes = (b"window.AURA_LOCATION_DATA=window.AURA_LOCATION_DATA||{};\n"
                   b'window.AURA_LOCATION_DATA["education-registry"]=' + compact(points).rstrip(b"\n") + b";\n")
    layer_path.write_bytes(layer_bytes)
    counts = {
        "organisations": len(organisations), "countries": len(countries), "localityEntries": location_count,
        "validLocalityEntries": location_count - unmappable, "invalidCoordinateEntries": invalid_coords,
        "unmappableLocalityEntries": unmappable, "multiLocationOrganisations": multi_location,
        "existingMappedOrganisations": len(mapped), "additionalMapOrganisations": len(additional_ids),
        "additionalMapPoints": len(points), "unmappedOrganisations": len(all_ids - set(mapped) - additional_ids),
        "relationships": dict(sorted(relations.items())),
    }
    source = {
        "name": "Research Organization Registry (ROR)", "version": VERSION,
        "updatedAt": RELEASE_DATE, "url": SOURCE_URL, "sha256": source_hash,
        "licence": "CC0 1.0", "localitySource": "GeoNames", "localityLicence": "CC BY 4.0",
    }
    map_layer = {
        "id": "education-registry", "src": "data/layers/education-registry.js", "defaultVisible": False,
        "mappedCount": len(points), "organisationCount": len(additional_ids),
        "sourceCount": len(organisations), "unresolvedCount": counts["unmappedOrganisations"],
        "sha256": hashlib.sha256(layer_bytes).hexdigest().upper(),
        "matchFile": args.matches.name, "matchSha256": match_hash,
    }
    full = {
        "schemaVersion": "aura-education-registry/1.0", "registryVersion": VERSION,
        "registryUpdatedAt": RELEASE_DATE, "sourceUrl": SOURCE_URL, "source": source,
        "coverage": "All active ROR v2.11 records with the education type; ROR covers research organisations and is not a complete global university or accreditation register.",
        "coordinateBasis": "GeoNames locality coordinates, not campus or building positions. Every ROR locality is retained.",
        "relationshipBasis": "Only source parent, child, related and successor links; these do not establish peak-body membership, accreditation, project suitability or affiliation with Aura or GAJRA.",
        "counts": counts, "mapLayer": map_layer, "organisations": organisations,
    }
    full_path = args.output_dir / "education-registry-v2.11.json"
    full_path.write_bytes(compact(full))
    index = {
        "schemaVersion": "aura-education-registry-index/1.0", "registryVersion": VERSION,
        "registryUpdatedAt": RELEASE_DATE, "sourceUrl": SOURCE_URL, "counts": counts,
        "fields": ["rorId", "name", "countryCode", "countryName", "locality", "hasWebsite", "externalIdTypes", "relationshipTypes", "mapLayerId", "countries", "searchTerms"],
        "localityNotice": "The first ROR locality is used only for directory searching; details retain all locations.",
        "sourceSha256": source_hash, "matchFile": args.matches.name, "matchSha256": match_hash,
        "rows": search_rows,
    }
    index_path = args.output_dir / "education-registry-index.json"
    index_path.write_bytes(compact(index))
    chunk_dir = args.output_dir / "education-registry"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    chunk_sizes = {}
    for code, entries in sorted(chunks.items()):
        payload = compact({"schemaVersion": full["schemaVersion"], "registryVersion": VERSION,
                           "registryUpdatedAt": RELEASE_DATE, "sourceUrl": SOURCE_URL,
                           "sourceSha256": source_hash, "countryCode": code,
                           "organisations": entries})
        (chunk_dir / f"{code}.json").write_bytes(payload)
        chunk_sizes[code] = len(payload)
    return {
        "counts": counts, "sourceSha256": source_hash, "matchSha256": match_hash,
        "existingMapLinksChecked": not args.defer_map_link_check,
        "mapLayer": map_layer, "files": {"registryBytes": full_path.stat().st_size,
        "indexBytes": index_path.stat().st_size, "layerBytes": layer_path.stat().st_size,
        "countryChunks": len(chunks), "largestCountryChunks": sorted(chunk_sizes.items(), key=lambda pair: pair[1], reverse=True)[:5]},
    }


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--ror", type=Path, default=DEFAULT_ROR)
    command.add_argument("--matches", type=Path, default=REPO / "data" / "university-matches-2026-09-05.csv")
    command.add_argument("--output-dir", type=Path, default=REPO / "data")
    command.add_argument("--existing-layers-dir", type=Path, default=REPO / "data" / "layers")
    command.add_argument("--defer-map-link-check", action="store_true",
                         help="Build before legacy layers are refreshed; rerun without this flag before publishing")
    return command


if __name__ == "__main__":
    print(json.dumps(build(parser().parse_args()), ensure_ascii=False, indent=2))
