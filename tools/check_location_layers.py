#!/usr/bin/env python3
"""Validate the generated location catalogue without opening a browser."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO / "data" / "location-layers.js"


def sha256_repository_text(path: Path) -> str:
    """Hash text as Git stores it after the repository's LF normalisation."""
    content = path.read_bytes()
    canonical_content = content.replace(b"\r\n", b"\n")
    return hashlib.sha256(canonical_content).hexdigest().upper()


def read_manifest() -> tuple[list[dict], dict[str, list]]:
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    marker = "window.AURA_LOCATION_MANIFEST="
    start = text.index(marker) + len(marker)
    end = text.index(";\nwindow.AURA_LOCATION_DATA", start)
    manifest = json.loads(text[start:end])

    starter_marker = 'window.AURA_LOCATION_DATA["starter-world"]='
    starter_start = text.index(starter_marker) + len(starter_marker)
    starter_end = text.index(";", starter_start)
    return manifest, {"starter-world": json.loads(text[starter_start:starter_end])}


def read_layer(path: Path, layer_id: str) -> list:
    text = path.read_text(encoding="utf-8")
    marker = f'window.AURA_LOCATION_DATA["{layer_id}"]='
    start = text.index(marker) + len(marker)
    end = text.rindex(";")
    return json.loads(text[start:end])


def check() -> dict:
    manifest, data = read_manifest()
    errors: list[str] = []
    seen_ids: set[str] = set()
    expected_files: set[str] = set()
    summary: dict[str, dict[str, int]] = {}

    for layer in manifest:
        layer_id = layer.get("id", "")
        if not layer_id or layer_id in seen_ids:
            errors.append(f"Missing or duplicate layer id: {layer_id!r}")
            continue
        seen_ids.add(layer_id)
        source_hash = layer.get("sourceSha256")
        if source_hash and (len(source_hash) != 64 or any(ch not in "0123456789ABCDEF" for ch in source_hash)):
            errors.append(f"{layer_id}: invalid source SHA-256")
        match_hash = layer.get("matchSha256")
        if match_hash and (len(match_hash) != 64 or any(ch not in "0123456789ABCDEF" for ch in match_hash)):
            errors.append(f"{layer_id}: invalid match SHA-256")

        src = layer.get("src")
        if src:
            path = REPO / src
            expected_files.add(path.name)
            if not path.is_file():
                errors.append(f"{layer_id}: missing {src}")
                continue
            try:
                data[layer_id] = read_layer(path, layer_id)
            except (ValueError, json.JSONDecodeError) as exc:
                errors.append(f"{layer_id}: could not parse generated data: {exc}")
                continue

        points = data.get(layer_id, [])
        mapped = int(layer.get("mappedCount", 0))
        unresolved = int(layer.get("unresolvedCount", 0))
        if len(points) != mapped:
            errors.append(f"{layer_id}: manifest says {mapped}, file has {len(points)}")
        if mapped == 0 and not layer.get("unavailableReason"):
            errors.append(f"{layer_id}: zero mapped points need an explanation")

        for index, point in enumerate(points):
            if not isinstance(point, list) or not 3 <= len(point) <= 8:
                errors.append(f"{layer_id}[{index}]: invalid compact point shape")
                continue
            lat, lon = point[1], point[2]
            if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                errors.append(f"{layer_id}[{index}]: coordinates are not numeric")
                continue
            if not math.isfinite(lat) or not math.isfinite(lon) or not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                errors.append(f"{layer_id}[{index}]: coordinates are out of range")

        summary[layer_id] = {"mapped": len(points), "unresolved": unresolved}

    actual_files = {path.name for path in (REPO / "data" / "layers").glob("*.js")}
    stale = sorted(actual_files - expected_files)
    if stale:
        errors.append("Unregistered generated files: " + ", ".join(stale))

    public_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [MANIFEST_PATH, *(REPO / "data" / "layers").glob("*.js")]
    )
    for leak in ("C:\\Users\\", "C:/Users/", "lukec"):
        if leak.lower() in public_text.lower():
            errors.append(f"Public data contains a local path fragment: {leak}")

    affinity = data.get("aura-affinity", [])
    if any(len(point) > 7 or (len(point) > 5 and point[5]) for point in affinity):
        errors.append("Aura Affinity output contains fields beyond the approved minimal map subset")

    cities = data.get("world-cities", [])
    city_population_labels = sum(
        1 for point in cities if len(point) > 3 and "Population " in str(point[3])
    )
    if cities and city_population_labels < 40_000:
        errors.append("World Cities selected-place details are missing population labels")

    alliance = data.get("aura-alliance", [])
    if alliance and sum(1 for point in alliance if len(point) > 7 and point[7]) != len(alliance):
        errors.append("Aura Alliance KML icon metadata was not preserved for every point")
    stradbroke = data.get("north-stradbroke-reference", [])
    if stradbroke and not any(len(point) > 7 and point[7] for point in stradbroke):
        errors.append("North Stradbroke My Maps icon metadata is missing")

    match_catalogue = REPO / "data" / "university-matches-2026-09-05.csv"
    match_catalogue_hash = ""
    safe_match_methods = {
        "safe_active_exact_name_site_agreement",
        "safe_active_exact_name_only",
        "automatic-strict-name",
        "automatic-strict-name+domain-within-country",
        "automatic-strict-name-within-country",
        "reviewed_official_same_identity",
    }
    group_search_labels = {
        "oceania": "Oceania",
        "fta_partner": "Australia in-force FTA partner outside Oceania",
        "eu_framework": "Australia-EU Framework Agreement",
        "named_treaty": "Named bilateral treaty",
        "global_backlog": "Rest of the historical world university index",
    }
    group_matches: dict[str, dict[str, dict[str, str]]] = {
        group: {} for group in group_search_labels
    }
    group_source_counts = {group: 0 for group in group_matches}
    group_safe_counts = {group: 0 for group in group_matches}
    group_countries: dict[str, set[str]] = {group: set() for group in group_matches}
    match_source_rows: set[int] = set()
    expected_match_fields = {
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
    }
    if not match_catalogue.is_file():
        errors.append("Missing tracked university ROR match catalogue")
    else:
        match_catalogue_hash = sha256_repository_text(match_catalogue)
        match_text = match_catalogue.read_text(encoding="utf-8-sig")
        for leak in ("C:\\Users\\", "C:/Users/", "lukec"):
            if leak.lower() in match_text.lower():
                errors.append(f"University match catalogue contains a local path fragment: {leak}")
        with match_catalogue.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or [])
            if fields != expected_match_fields:
                errors.append("University match catalogue fields do not match the minimal public schema")
            for row_number, record in enumerate(reader, start=2):
                try:
                    source_row = int(record.get("source_row_number", ""))
                except ValueError:
                    errors.append(f"University match row {row_number}: invalid source row number")
                    continue
                if source_row < 1 or source_row > 9363 or source_row in match_source_rows:
                    errors.append(f"University match row {row_number}: duplicate or out-of-range source row")
                    continue
                match_source_rows.add(source_row)
                group = record.get("scope_group", "")
                if group not in group_matches:
                    errors.append(f"University match row {row_number}: unknown scope group")
                    continue
                group_source_counts[group] += 1
                country_code = record.get("source_country", "").upper()
                if country_code:
                    group_countries[group].add(country_code)
                classification = record.get("classification", "")
                if classification not in {"safe_active", "review", "inactive_history", "unmatched"}:
                    errors.append(f"University match row {row_number}: unknown classification")
                    continue
                publication_fields = (
                    "ror_id",
                    "ror_name",
                    "ror_status",
                    "geonames_id",
                    "locality",
                    "subdivision_name",
                    "latitude",
                    "longitude",
                )
                if classification != "safe_active":
                    if any(record.get(field, "").strip() for field in publication_fields):
                        errors.append(
                            f"University match row {row_number}: held candidate fields reached the public ledger"
                        )
                    continue
                group_safe_counts[group] += 1
                ror_id = record.get("ror_id", "")
                if not re.fullmatch(r"https://ror\.org/[0-9a-z]{9}", ror_id):
                    errors.append(f"University match row {row_number}: invalid ROR ID")
                    continue
                if record.get("ror_status") != "active":
                    errors.append(f"University match row {row_number}: published ROR record is not active")
                try:
                    geonames_id = int(record.get("geonames_id", ""))
                    latitude = float(record.get("latitude", ""))
                    longitude = float(record.get("longitude", ""))
                except ValueError:
                    errors.append(f"University match row {row_number}: invalid location fields")
                    continue
                if geonames_id <= 0 or not (
                    math.isfinite(latitude)
                    and math.isfinite(longitude)
                    and -90 <= latitude <= 90
                    and -180 <= longitude <= 180
                ):
                    errors.append(f"University match row {row_number}: invalid GeoNames location")
                    continue
                match_method = record.get("match_method", "")
                if match_method not in safe_match_methods:
                    errors.append(f"University match row {row_number}: match method is not approved")
                if group in {"fta_partner", "eu_framework", "named_treaty"} and not match_method.startswith(
                    "safe_active_"
                ):
                    errors.append(f"University match row {row_number}: partner match method is not strict")
                previous = group_matches[group].get(ror_id)
                if previous:
                    if any(
                        previous.get(field) != record.get(field)
                        for field in ("ror_name", "geonames_id", "latitude", "longitude")
                    ):
                        errors.append(f"University match row {row_number}: duplicate ROR identity disagrees")
                else:
                    group_matches[group][ror_id] = record

    groups = tuple(group_countries)
    for at, group in enumerate(groups):
        for other in groups[at + 1 :]:
            overlap = group_countries[group] & group_countries[other]
            if overlap:
                errors.append(
                    f"University country scopes overlap between {group} and {other}: {', '.join(sorted(overlap))}"
                )

    university_layer_groups = {
        "oceania-universities": "oceania",
        "australia-fta-universities": "fta_partner",
        "eu-framework-universities": "eu_framework",
        "timor-leste-universities": "named_treaty",
        "world-universities": "global_backlog",
    }
    scoped_university_rows = 0
    declared_scope_countries: dict[str, set[str]] = {}
    for layer_id, group in university_layer_groups.items():
        layer = next((item for item in manifest if item.get("id") == layer_id), None)
        if not layer:
            errors.append(f"Missing university layer: {layer_id}")
            continue
        scope_count = int(layer.get("scopeSourceCount", 0))
        scoped_university_rows += scope_count
        mapped_count = int(layer.get("mappedCount", 0))
        held_count = int(layer.get("unresolvedCount", 0))
        duplicate_count = int(layer.get("deduplicatedCount", 0))
        matched_count = int(layer.get("matchedSourceCount", 0))
        if mapped_count + held_count + duplicate_count != scope_count:
            errors.append(
                f"{layer_id}: mapped, duplicate and held rows do not reconcile to scopeSourceCount"
            )
        if mapped_count + duplicate_count != matched_count:
            errors.append(f"{layer_id}: matchedSourceCount does not reconcile to mapped points")
        if scope_count != group_source_counts[group]:
            errors.append(f"{layer_id}: scopeSourceCount does not match the publication ledger")
        if matched_count != group_safe_counts[group]:
            errors.append(f"{layer_id}: matchedSourceCount does not match safe ledger rows")
        scope_codes = layer.get("scopeCountryCodes", [])
        if not isinstance(scope_codes, list) or len(scope_codes) != len(set(scope_codes)) or any(
            not re.fullmatch(r"[A-Z]{2}", str(code)) for code in scope_codes
        ):
            errors.append(f"{layer_id}: invalid scopeCountryCodes")
            scope_code_set: set[str] = set()
        else:
            scope_code_set = set(scope_codes)
        declared_scope_countries[group] = scope_code_set
        if not group_countries[group].issubset(scope_code_set):
            errors.append(f"{layer_id}: publication ledger contains a country outside its scope")
        expected_scope_date = "2026-09-05" if group == "global_backlog" else "2026-08-11"
        if layer.get("scopeAsAt") != expected_scope_date:
            errors.append(f"{layer_id}: missing official-scope as-at date")
        if layer.get("matchFile") != match_catalogue.name or layer.get("matchReviewedAt") != "2026-09-05":
            errors.append(f"{layer_id}: incorrect reviewed catalogue provenance")
        if match_catalogue_hash and layer.get("matchSha256") != match_catalogue_hash:
            errors.append(f"{layer_id}: matchSha256 does not match the publication ledger")
        expected_records = group_matches[group]
        university_points = data.get(layer_id, [])
        point_ids = [str(point[5]) for point in university_points if len(point) > 5]
        if len(point_ids) != len(set(point_ids)):
            errors.append(f"{layer_id}: duplicate ROR IDs in public points")
        if set(point_ids) != set(expected_records):
            errors.append(f"{layer_id}: public points do not match the safe ROR ledger")
        if mapped_count and (
            "locality" not in str(layer.get("coordinateBasis", "")).lower()
            or "not a campus" not in str(layer.get("coordinateBasis", "")).lower()
        ):
            errors.append(f"{layer_id}: coordinate basis must say locality, not campus")
        for index, university in enumerate(university_points):
            if len(university) < 6 or not str(university[5]).startswith("https://ror.org/"):
                errors.append(f"{layer_id}[{index}]: missing record-level ROR source")
                continue
            expected = expected_records.get(str(university[5]))
            if not expected:
                continue
            if str(university[0]) != expected.get("ror_name"):
                errors.append(f"{layer_id}[{index}]: current ROR name does not match the ledger")
            if abs(float(university[1]) - float(expected["latitude"])) > 0.0000001 or abs(
                float(university[2]) - float(expected["longitude"])
            ) > 0.0000001:
                errors.append(f"{layer_id}[{index}]: coordinates do not match the ledger")
            expected_detail = ", ".join(
                value
                for value in (
                    expected.get("locality", "").strip(),
                    expected.get("subdivision_name", "").strip(),
                    expected.get("source_country_name", "").strip(),
                )
                if value
            )
            country = expected.get("source_country_name", "").strip() or expected.get(
                "source_country", ""
            ).strip()
            expected_category = "University" + (f" · {country}" if country else "")
            expected_search = " ".join(
                value
                for value in (
                    expected.get("source_country", "").strip().upper(),
                    expected.get("source_country_name", "").strip(),
                    expected.get("locality", "").strip(),
                    expected.get("subdivision_name", "").strip(),
                    expected.get("ror_name", "").strip(),
                    expected.get("geonames_id", "").strip(),
                    group_search_labels[group],
                    expected.get("match_method", "").strip(),
                )
                if value
            )
            if len(university) < 7 or str(university[3]) != expected_detail or str(
                university[4]
            ) != expected_category or str(university[6]) != expected_search:
                errors.append(f"{layer_id}[{index}]: public detail fields do not match the safe ledger")

    declared_groups = tuple(declared_scope_countries)
    for at, group in enumerate(declared_groups):
        for other in declared_groups[at + 1 :]:
            overlap = declared_scope_countries[group] & declared_scope_countries[other]
            if overlap:
                errors.append(
                    f"Declared university scopes overlap between {group} and {other}: {', '.join(sorted(overlap))}"
                )
    original_scopes = [codes for group, codes in declared_scope_countries.items() if group != "global_backlog"]
    if len(set().union(*original_scopes)) != 79:
        errors.append("Original university scope does not contain 79 disjoint ISO2 areas")
    if declared_scope_countries.get("named_treaty") != {"TL"}:
        errors.append("Named bilateral treaty university scope must identify Timor-Leste")

    university_backlog = next(
        (item for item in manifest if item.get("id") == "world-universities"), None
    )
    if not university_backlog:
        errors.append("Missing world-universities backlog layer")
    elif scoped_university_rows != 9363:
        errors.append("All university scopes do not reconcile to 9,363 source rows")

    if match_source_rows != set(range(1, 9364)):
        errors.append("University publication ledger does not account for every historical source row")

    completion_path = REPO / "data" / "university-completion-summary.json"
    completion = json.loads(completion_path.read_text(encoding="utf-8"))
    if completion.get("outputSha256") != match_catalogue_hash:
        errors.append("University completion summary hash disagrees with effective ledger")
    for name, digest in completion.get("inputHashes", {}).items():
        if Path(name).name != name or sha256_repository_text(REPO / "data" / name) != digest:
            errors.append(f"University completion input drift: {name}")
    reviews = json.loads((REPO / "data" / "university-reviewed-matches.json").read_text(encoding="utf-8"))
    accepted_reviews = {int(r["sourceRowNumber"]): r for r in reviews["reviews"] if r["decision"] == "accept"}
    with match_catalogue.open(encoding="utf-8", newline="") as handle:
        reviewed_rows = {int(r["source_row_number"]): r for r in csv.DictReader(handle) if r["match_method"] == "reviewed_official_same_identity"}
    if set(reviewed_rows) != set(accepted_reviews) or set(reviewed_rows) != set(completion["reviewedPromotions"]):
        errors.append("Reviewed promotions do not match the evidence ledger")
    for number, row in reviewed_rows.items():
        evidence = accepted_reviews.get(number, {})
        if row["ror_id"] != evidence.get("rorId") or not evidence.get("sources") or not evidence.get("reason"):
            errors.append(f"Reviewed institution lacks matching identity evidence: {number}")

    if errors:
        raise SystemExit("\n".join(errors))
    return {"layers": len(manifest), "summary": summary, "status": "ok"}


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False, indent=2))
