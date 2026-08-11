#!/usr/bin/env python3
"""Build compact, source-labelled globe layers for the static demo.

The browser uses JavaScript registration files instead of fetched JSON so the
site still works when index.html is opened directly from disk.  Generated point
rows use this compact schema:

    [name, latitude, longitude, detail, category, source_url, search_text, icon_url]

Only name and coordinates are required.  Empty values at the end are removed.
The source files are read only; generated files are written inside data/layers.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[1]
WORKSPACE = REPO.parent
DEFAULT_DOWNLOADS = Path.home() / "Downloads"
LAYERS_DIR = REPO / "data" / "layers"
MANIFEST_PATH = REPO / "data" / "location-layers.js"
DEFAULT_UNIVERSITY_MATCHES = REPO / "data" / "university-ror-matches-v2.11.csv"
POINT_SCHEMA = [
    "name",
    "latitude",
    "longitude",
    "detail",
    "category",
    "sourceUrl",
    "searchText",
    "iconUrl",
]


STARTER_POINTS = [
    ["Minjerribah (Straddie)", -27.49, 153.45, "Queensland, Australia"],
    ["Brisbane", -27.47, 153.03, "Queensland, Australia"],
    ["Sydney", -33.87, 151.21, "New South Wales, Australia"],
    ["Melbourne", -37.81, 144.96, "Victoria, Australia"],
    ["Perth", -31.95, 115.86, "Western Australia"],
    ["Darwin", -12.46, 130.84, "Northern Territory, Australia"],
    ["Hobart", -42.88, 147.33, "Tasmania, Australia"],
    ["Auckland", -36.85, 174.76, "Aotearoa New Zealand"],
    ["Suva", -18.14, 178.44, "Fiji"],
    ["Port Moresby", -9.44, 147.18, "Papua New Guinea"],
    ["Tokyo", 35.68, 139.69, "Japan"],
    ["Singapore", 1.35, 103.82, "Singapore"],
    ["Jakarta", -6.20, 106.85, "Indonesia"],
    ["Delhi", 28.61, 77.21, "India"],
    ["Beijing", 39.90, 116.41, "China"],
    ["Moscow", 55.76, 37.62, "Russia"],
    ["Cairo", 30.04, 31.24, "Egypt"],
    ["Nairobi", -1.29, 36.82, "Kenya"],
    ["Lagos", 6.52, 3.38, "Nigeria"],
    ["Cape Town", -33.92, 18.42, "South Africa"],
    ["London", 51.51, -0.13, "United Kingdom"],
    ["Paris", 48.86, 2.35, "France"],
    ["Berlin", 52.52, 13.40, "Germany"],
    ["Rome", 41.90, 12.50, "Italy"],
    ["Reykjavik", 64.15, -21.94, "Iceland"],
    ["New York", 40.71, -74.01, "United States"],
    ["Los Angeles", 34.05, -118.24, "United States"],
    ["Mexico City", 19.43, -99.13, "Mexico"],
    ["Sao Paulo", -23.55, -46.63, "Brazil", "", "", "São Paulo"],
    ["Buenos Aires", -34.60, -58.38, "Argentina"],
    ["Santiago", -33.45, -70.67, "Chile"],
    ["Honolulu", 21.31, -157.86, "United States"],
    ["Vancouver", 49.28, -123.12, "Canada"],
    ["McMurdo Station", -77.85, 166.67, "Antarctica"],
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def valid_coord(lat: Any, lon: Any) -> bool:
    try:
        latitude = float(lat)
        longitude = float(lon)
    except (TypeError, ValueError):
        return False
    return -90 <= latitude <= 90 and -180 <= longitude <= 180


def point(
    name: Any,
    lat: Any,
    lon: Any,
    detail: Any = "",
    category: Any = "",
    source_url: Any = "",
    search_text: Any = "",
    icon_url: Any = "",
) -> list[Any]:
    if not valid_coord(lat, lon):
        raise ValueError(f"Invalid coordinates for {name!r}: {lat!r}, {lon!r}")
    row: list[Any] = [
        clean_text(name) or "Unnamed place",
        round(float(lat), 7),
        round(float(lon), 7),
        clean_text(detail),
        clean_text(category),
        clean_text(source_url),
        clean_text(search_text),
        clean_text(icon_url),
    ]
    while len(row) > 3 and row[-1] == "":
        row.pop()
    return row


def parse_kml_points(path: Path) -> tuple[list[list[Any]], dict[str, Any]]:
    root = ET.parse(path).getroot()
    styles: dict[str, str] = {}
    style_maps: dict[str, str] = {}
    for style in root.iter():
        if local_name(style.tag) != "Style":
            continue
        style_id = style.attrib.get("id", "")
        href = next(
            (
                clean_text(node.text)
                for node in style.iter()
                if local_name(node.tag) == "href" and clean_text(node.text)
            ),
            "",
        )
        if style_id and href:
            styles[style_id] = href
    for style_map in root.iter():
        if local_name(style_map.tag) != "StyleMap":
            continue
        map_id = style_map.attrib.get("id", "")
        for pair in style_map:
            if local_name(pair.tag) != "Pair":
                continue
            key = next(
                (clean_text(node.text) for node in pair if local_name(node.tag) == "key"),
                "",
            )
            target = next(
                (
                    clean_text(node.text).lstrip("#")
                    for node in pair
                    if local_name(node.tag) == "styleUrl"
                ),
                "",
            )
            if key == "normal" and map_id and target:
                style_maps[map_id] = target
                break

    rows: list[list[Any]] = []
    folders: Counter[str] = Counter()
    skipped = 0

    def walk(container: ET.Element, folder: str = "") -> None:
        nonlocal skipped
        for child in container:
            kind = local_name(child.tag)
            if kind in {"Document", "Folder"}:
                next_folder = folder
                if kind == "Folder":
                    name_node = next(
                        (n for n in child if local_name(n.tag) == "name"), None
                    )
                    next_folder = clean_text(name_node.text if name_node is not None else "")
                walk(child, next_folder)
                continue
            if kind != "Placemark":
                continue
            name = next(
                (
                    clean_text(node.text)
                    for node in child
                    if local_name(node.tag) == "name"
                ),
                "Unnamed place",
            )
            coords = next(
                (
                    clean_text(node.text)
                    for node in child.iter()
                    if local_name(node.tag) == "Point"
                    for node in node.iter()
                    if local_name(node.tag) == "coordinates"
                ),
                "",
            )
            if not coords:
                skipped += 1
                continue
            first = coords.split()[0].split(",")
            if len(first) < 2 or not valid_coord(first[1], first[0]):
                skipped += 1
                continue
            style_ref = next(
                (
                    clean_text(node.text).lstrip("#")
                    for node in child
                    if local_name(node.tag) == "styleUrl"
                ),
                "",
            )
            style_ref = style_maps.get(style_ref, style_ref)
            icon_url = styles.get(style_ref, "")
            folders[folder or "Uncategorised"] += 1
            rows.append(
                point(
                    name,
                    first[1],
                    first[0],
                    folder,
                    folder,
                    "",
                    folder,
                    icon_url,
                )
            )

    walk(root)
    return rows, {"skipped": skipped, "folders": dict(folders)}


def extract_json_assignment(path: Path, variable: str) -> Any:
    text = path.read_text(encoding="utf-8-sig")
    marker = f"window.{variable} ="
    start = text.find(marker)
    if start < 0:
        raise ValueError(f"Could not find {marker!r} in {path}")
    start = text.find("[", start)
    end = text.find("\n];", start)
    if start < 0 or end < 0:
        raise ValueError(f"Could not isolate {variable} array in {path}")
    return json.loads(text[start : end + 2])


def parse_stradbroke_reference(path: Path) -> list[list[Any]]:
    records = extract_json_assignment(path, "QCEE_MYMAPS_PLACES")
    rows = []
    for record in records:
        if not valid_coord(record.get("lat"), record.get("lng")):
            continue
        area = clean_text(record.get("area"))
        folder = clean_text(record.get("folder"))
        category = clean_text(record.get("category"))
        rows.append(
            point(
                record.get("name"),
                record.get("lat"),
                record.get("lng"),
                area or folder,
                category or folder,
                "",
                f"{area} {folder} {record.get('geometryType', '')}",
                record.get("iconUrl"),
            )
        )
    return rows


def parse_world_cities(path: Path) -> list[list[Any]]:
    rows: list[list[Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"city", "lat", "lng", "country"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError("worldcities.csv does not have the expected headers")
        for record in reader:
            if not valid_coord(record.get("lat"), record.get("lng")):
                continue
            admin = clean_text(record.get("admin_name"))
            country = clean_text(record.get("country"))
            detail = ", ".join(part for part in (admin, country) if part)
            population = clean_text(record.get("population"))
            if population:
                try:
                    population_label = f"{int(float(population)):,}"
                    detail += (" · " if detail else "") + f"Population {population_label}"
                except (ValueError, OverflowError):
                    pass
            capital = clean_text(record.get("capital"))
            category = f"{capital.title()} capital" if capital else "City"
            search = " ".join(
                clean_text(record.get(key))
                for key in ("city_ascii", "country", "iso2", "iso3", "admin_name", "capital")
                if clean_text(record.get(key))
            )
            rows.append(
                point(
                    record.get("city"),
                    record.get("lat"),
                    record.get("lng"),
                    detail,
                    category,
                    "",
                    search,
                )
            )
    return rows


def count_university_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for row in csv.reader(handle) if row)


UNIVERSITY_SCOPE_LABELS = {
    "oceania": "Oceania",
    "fta_partner": "Australia in-force FTA partner outside Oceania",
    "eu_framework": "Australia-EU Framework Agreement",
    "named_treaty": "Named bilateral treaty",
}
UNIVERSITY_SCOPE_COUNTRIES = {
    "oceania": [
        "AS", "AU", "CC", "CK", "CX", "FJ", "FM", "GU", "HM", "KI", "MH", "MP",
        "NC", "NF", "NR", "NU", "NZ", "PF", "PG", "PN", "PW", "SB", "TK", "TO",
        "TV", "UM", "VU", "WF", "WS",
    ],
    "fta_partner": [
        "AE", "BN", "CA", "CL", "CN", "GB", "HK", "ID", "IN", "JP", "KH", "KR",
        "LA", "MM", "MX", "MY", "PE", "PH", "SG", "TH", "US", "VN",
    ],
    "eu_framework": [
        "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
        "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
        "SI", "ES", "SE",
    ],
    "named_treaty": ["TL"],
}


def parse_university_matches(
    path: Path,
) -> tuple[dict[str, list[list[Any]]], dict[str, Counter[str]], set[int]]:
    """Read the reviewed ROR match catalogue and publish safe active rows only.

    The tracked catalogue deliberately carries current ROR/GeoNames display
    fields rather than republishing the old index's website list.  Every row
    still keeps its original source row number so totals remain auditable.
    """
    grouped: dict[str, list[list[Any]]] = defaultdict(list)
    diagnostics: dict[str, Counter[str]] = defaultdict(Counter)
    source_rows: set[int] = set()
    seen_ror: dict[str, set[str]] = defaultdict(set)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
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
        if not required.issubset(set(reader.fieldnames or [])):
            missing = sorted(required - set(reader.fieldnames or []))
            raise ValueError(f"University match catalogue is missing: {', '.join(missing)}")
        for record in reader:
            try:
                source_row = int(clean_text(record.get("source_row_number")))
            except ValueError as exc:
                raise ValueError("University match row has an invalid source row number") from exc
            if source_row in source_rows:
                raise ValueError(f"Duplicate university source row: {source_row}")
            source_rows.add(source_row)
            group = clean_text(record.get("scope_group"))
            if group not in UNIVERSITY_SCOPE_LABELS:
                raise ValueError(f"Unknown university scope group: {group!r}")
            country_code = clean_text(record.get("source_country")).upper()
            if country_code not in UNIVERSITY_SCOPE_COUNTRIES[group]:
                raise ValueError(
                    f"University source row {source_row} is outside the declared {group} countries"
                )
            classification = clean_text(record.get("classification"))
            diagnostics[group][classification] += 1
            if classification != "safe_active":
                continue
            if clean_text(record.get("ror_status")) != "active":
                raise ValueError(f"Safe university row {source_row} is not active in ROR")
            ror_id = clean_text(record.get("ror_id"))
            if not re.fullmatch(r"https://ror\.org/[0-9a-z]{9}", ror_id):
                raise ValueError(f"Safe university row {source_row} has an invalid ROR ID")
            if not valid_coord(record.get("latitude"), record.get("longitude")):
                raise ValueError(f"Safe university row {source_row} lacks valid coordinates")
            if ror_id in seen_ror[group]:
                continue
            seen_ror[group].add(ror_id)
            country = clean_text(record.get("source_country_name"))
            locality = clean_text(record.get("locality"))
            subdivision = clean_text(record.get("subdivision_name"))
            detail = ", ".join(part for part in (locality, subdivision, country) if part)
            category = "University"
            if country or country_code:
                category += f" · {country or country_code}"
            search = " ".join(
                part
                for part in (
                    country_code,
                    country,
                    locality,
                    subdivision,
                    clean_text(record.get("ror_name")),
                    clean_text(record.get("geonames_id")),
                    UNIVERSITY_SCOPE_LABELS[group],
                    clean_text(record.get("match_method")),
                )
                if part
            )
            grouped[group].append(
                point(
                    record.get("ror_name"),
                    record.get("latitude"),
                    record.get("longitude"),
                    detail,
                    category,
                    ror_id,
                    search,
                )
            )
    return dict(grouped), diagnostics, source_rows


def parse_affinity(path: Path) -> list[list[Any]]:
    """Keep only low-risk map fields; never copy phones, reviews or contact data."""
    rows: list[list[Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for record in reader:
            if not valid_coord(record.get("latitude"), record.get("longitude")):
                continue
            city = clean_text(record.get("city"))
            country = clean_text(record.get("country"))
            detail = ", ".join(part for part in (city, country) if part)
            category = clean_text(record.get("category")) or "Uncategorised"
            rows.append(
                point(
                    record.get("name"),
                    record.get("latitude"),
                    record.get("longitude"),
                    detail,
                    category,
                    "",
                    f"{city} {country} {category} unverified archival",
                )
            )
    return rows


ABROAD_PATTERN = re.compile(
    r"\{\s*city:\s*\"(?P<city>[^\"]+)\",\s*"
    r"country:\s*\"(?P<country>[^\"]+)\",\s*"
    r"type:\s*\"(?P<type>[^\"]+)\",\s*"
    r"lat:\s*(?P<lat>-?\d+(?:\.\d+)?),\s*"
    r"lng:\s*(?P<lng>-?\d+(?:\.\d+)?)\s*\}"
)


def parse_missions_abroad(path: Path) -> tuple[list[list[Any]], int]:
    text = path.read_text(encoding="utf-8-sig")
    rows: list[list[Any]] = []
    reference_only = 0
    page_url = "https://auraofintelligence.github.io/Australian-world-travel/abroad.html"
    for match in ABROAD_PATTERN.finditer(text):
        record = match.groupdict()
        detail = record["country"]
        category = record["type"]
        if record["city"] == "Phoenix":
            reference_only += 1
            detail += " · DFAT refers enquiries to Los Angeles"
            category += " · reference only"
        rows.append(
            point(
                f"{record['city']} · {record['type']}",
                record["lat"],
                record["lng"],
                detail,
                category,
                page_url,
                f"{record['city']} {record['country']} Australian mission {record['type']}",
            )
        )
    return rows, reference_only


MISSION_CITY_PATTERN = re.compile(
    r"\{\s*country:\s*'(?P<country>(?:\\.|[^'])*)',\s*"
    r"city:\s*'(?P<city>(?:\\.|[^'])*)',\s*"
    r"type:\s*'(?P<type>(?:\\.|[^'])*)',"
)


def js_single_string(value: str) -> str:
    return value.replace("\\'", "'").replace("\\\\", "\\")


def count_missions_in_australia(path: Path) -> tuple[int, Counter[str]]:
    text = path.read_text(encoding="utf-8-sig")
    records = [
        {key: js_single_string(value) for key, value in match.groupdict().items()}
        for match in MISSION_CITY_PATTERN.finditer(text)
    ]
    return len(records), Counter(record["city"] for record in records)


def write_layer(layer_id: str, rows: Iterable[list[Any]]) -> int:
    data = list(rows)
    LAYERS_DIR.mkdir(parents=True, exist_ok=True)
    target = LAYERS_DIR / f"{layer_id}.js"
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    target.write_text(
        "window.AURA_LOCATION_DATA=window.AURA_LOCATION_DATA||{};\n"
        f"window.AURA_LOCATION_DATA[{json.dumps(layer_id)}]={payload};\n",
        encoding="utf-8",
        newline="\n",
    )
    return len(data)


def layer_metadata(**values: Any) -> dict[str, Any]:
    return values


def write_manifest(manifest: list[dict[str, Any]]) -> None:
    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2)
    starter_json = json.dumps(STARTER_POINTS, ensure_ascii=False, separators=(",", ":"))
    MANIFEST_PATH.write_text(
        "/* Generated by tools/build_location_layers.py. */\n"
        f"window.AURA_LOCATION_POINT_SCHEMA={json.dumps(POINT_SCHEMA, separators=(',', ':'))};\n"
        f"window.AURA_LOCATION_MANIFEST={manifest_json};\n"
        "window.AURA_LOCATION_DATA=window.AURA_LOCATION_DATA||{};\n"
        f"window.AURA_LOCATION_DATA[\"starter-world\"]={starter_json};\n",
        encoding="utf-8",
        newline="\n",
    )


def build(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "world_cities": Path(args.world_cities),
        "world_universities": Path(args.world_universities),
        "university_matches": Path(args.university_matches),
        "aura_alliance": Path(args.aura_alliance),
        "north_stradbroke_kmz": Path(args.north_stradbroke_kmz),
        "north_stradbroke_recovered": Path(args.north_stradbroke_recovered),
        "affinity": Path(args.affinity),
        "missions_in_australia": Path(args.missions_in_australia),
        "missions_abroad": Path(args.missions_abroad),
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing source file(s):\n" + "\n".join(missing))

    aura_alliance, alliance_diag = parse_kml_points(paths["aura_alliance"])
    north_stradbroke = parse_stradbroke_reference(paths["north_stradbroke_recovered"])
    world_cities = parse_world_cities(paths["world_cities"])
    universities_count = count_university_rows(paths["world_universities"])
    university_groups, university_diag, university_scope_rows = parse_university_matches(
        paths["university_matches"]
    )
    if len(university_scope_rows) > universities_count:
        raise ValueError("University match catalogue exceeds the historical source row count")
    affinity = parse_affinity(paths["affinity"])
    missions_abroad, missions_abroad_reference = parse_missions_abroad(paths["missions_abroad"])
    missions_in_australia_count, mission_cities = count_missions_in_australia(
        paths["missions_in_australia"]
    )

    counts = {
        "starter-world": len(STARTER_POINTS),
        "aura-alliance": write_layer("aura-alliance", aura_alliance),
        "north-stradbroke-reference": write_layer(
            "north-stradbroke-reference", north_stradbroke
        ),
        "aura-affinity": write_layer("aura-affinity", affinity),
        "australian-missions-abroad": write_layer(
            "australian-missions-abroad", missions_abroad
        ),
        "world-cities": write_layer("world-cities", world_cities),
        "oceania-universities": write_layer(
            "oceania-universities", university_groups.get("oceania", [])
        ),
        "australia-fta-universities": write_layer(
            "australia-fta-universities", university_groups.get("fta_partner", [])
        ),
        "eu-framework-universities": write_layer(
            "eu-framework-universities", university_groups.get("eu_framework", [])
        ),
    }

    university_scope_totals = {
        group: sum(university_diag.get(group, Counter()).values())
        for group in UNIVERSITY_SCOPE_LABELS
    }
    university_safe_totals = {
        group: int(university_diag.get(group, Counter()).get("safe_active", 0))
        for group in UNIVERSITY_SCOPE_LABELS
    }
    university_remaining = universities_count - sum(university_scope_totals.values())
    if university_remaining < 0:
        raise ValueError("University scope counts do not reconcile to the historical source")

    manifest = [
        layer_metadata(
            id="starter-world",
            label="Starter world places",
            colour="#d8b36a",
            mappedCount=counts["starter-world"],
            unresolvedCount=0,
            defaultOn=True,
            status="orientation",
            statusLabel="orientation only",
            sourceLabel="Original demo gazetteer",
            sourceFile="index.html",
            sourceUpdatedAt=None,
            importedAt=args.imported_at,
            coordinateBasis="approximate city or locality",
            warning="A small orientation set carried over from the original demo.",
            pointSize=0.072,
            opacity=1.0,
        ),
        layer_metadata(
            id="aura-alliance",
            label="First Aura Alliance",
            colour="#a78bfa",
            mappedCount=counts["aura-alliance"],
            unresolvedCount=alliance_diag["skipped"],
            defaultOn=False,
            status="archival",
            statusLabel="archival snapshot",
            sourceLabel="1st Step to Aura Alliance.kml",
            sourceFile=paths["aura_alliance"].name,
            sourceSha256=sha256(paths["aura_alliance"]),
            sourceUpdatedAt=None,
            importedAt=args.imported_at,
            coordinateBasis="source point",
            warning="Incomplete legacy planning list; businesses and places are not confirmed current.",
            pointSize=0.050,
            opacity=0.92,
            src="data/layers/aura-alliance.js",
        ),
        layer_metadata(
            id="north-stradbroke-reference",
            label="North Stradbroke reference",
            colour="#38bdf8",
            mappedCount=counts["north-stradbroke-reference"],
            unresolvedCount=0,
            defaultOn=False,
            status="reference",
            statusLabel="legacy reference",
            sourceLabel="North Stradbroke Island My Maps",
            sourceFile=paths["north_stradbroke_kmz"].name,
            sourceSha256=sha256(paths["north_stradbroke_kmz"]),
            sourceUpdatedAt=None,
            snapshotImportedAt="2026-08-10",
            importedAt=args.imported_at,
            coordinateBasis="human-placed source point or polygon centroid",
            warning="Recovered from the KMZ NetworkLink. Accuracy, currency and cultural authority are unverified.",
            pointSize=0.058,
            opacity=0.95,
            src="data/layers/north-stradbroke-reference.js",
        ),
        layer_metadata(
            id="australian-missions-abroad",
            label="Australian missions abroad",
            colour="#22c55e",
            mappedCount=counts["australian-missions-abroad"],
            unresolvedCount=0,
            referenceCount=missions_abroad_reference,
            defaultOn=False,
            status="checked",
            statusLabel="checked 19 May 2026",
            sourceLabel="Australian World Travel · Abroad",
            sourceUrl="https://auraofintelligence.github.io/Australian-world-travel/abroad.html",
            sourceFile=paths["missions_abroad"].name,
            sourceSha256=sha256(paths["missions_abroad"]),
            sourceUpdatedAt="2026-05-19",
            importedAt=args.imported_at,
            coordinateBasis="approximate city location",
            warning="City-level positions only. Missions can open, close or relocate; Phoenix is reference-only. Use current DFAT advice.",
            pointSize=0.060,
            opacity=0.96,
            src="data/layers/australian-missions-abroad.js",
        ),
        layer_metadata(
            id="world-cities",
            label="World cities",
            colour="#cbd5e1",
            mappedCount=counts["world-cities"],
            unresolvedCount=0,
            defaultOn=False,
            status="archival",
            statusLabel="version unknown",
            sourceLabel="SimpleMaps World Cities",
            sourceUrl="https://simplemaps.com/data/world-cities",
            sourceFile=paths["world_cities"].name,
            sourceSha256=sha256(paths["world_cities"]),
            sourceUpdatedAt=None,
            importedAt=args.imported_at,
            coordinateBasis="source city point",
            warning="Old local copy with no embedded version date. Basic dataset attribution: SimpleMaps, CC BY 4.0.",
            rightsNote="SimpleMaps Basic World Cities Database, Creative Commons Attribution 4.0.",
            pointSize=0.024,
            opacity=0.68,
            src="data/layers/world-cities.js",
        ),
        layer_metadata(
            id="oceania-universities",
            label="Oceania universities",
            colour="#fb923c",
            mappedCount=counts["oceania-universities"],
            unresolvedCount=university_scope_totals["oceania"] - university_safe_totals["oceania"],
            deduplicatedCount=university_safe_totals["oceania"] - counts["oceania-universities"],
            matchedSourceCount=university_safe_totals["oceania"],
            defaultOn=False,
            status="matched",
            statusLabel="strict active ROR matches",
            sourceLabel="UN M49 Oceania · ROR v2.11",
            sourceUrl="https://unstats.un.org/unsd/methodology/m49/",
            sourceFile=paths["world_universities"].name,
            sourceSha256=sha256(paths["world_universities"]),
            matchFile=paths["university_matches"].name,
            matchSha256=sha256(paths["university_matches"]),
            registrySourceUrl="https://zenodo.org/records/21773148",
            registryUpdatedAt="2026-08-03",
            sourceUpdatedAt="2015-11-02",
            importedAt=args.imported_at,
            coordinateBasis="ROR v2.11 / GeoNames locality centroid; not a campus pin",
            warning=(
                "Historical 2015 index matched only where an active ROR education identity was strict and unique. "
                f"{university_scope_totals['oceania'] - university_safe_totals['oceania']:,} Oceania rows remain held for review, inactive history or no match. "
                "Inclusion only means the historical listing matched a current ROR organisation."
            ),
            rightsNote=(
                "Published display fields come from ROR (CC0); embedded GeoNames locality data is CC BY 4.0. "
                "The historical index repository declares no licence."
            ),
            scopeSourceCount=university_scope_totals["oceania"],
            scopeAsAt="2026-08-11",
            scopeCountryCodes=UNIVERSITY_SCOPE_COUNTRIES["oceania"],
            pointSize=0.044,
            opacity=0.92,
            src="data/layers/oceania-universities.js",
        ),
        layer_metadata(
            id="australia-fta-universities",
            label="Universities in non-Oceania FTA partner economies",
            colour="#facc15",
            mappedCount=counts["australia-fta-universities"],
            unresolvedCount=university_scope_totals["fta_partner"] - university_safe_totals["fta_partner"],
            deduplicatedCount=(
                university_safe_totals["fta_partner"] - counts["australia-fta-universities"]
            ),
            matchedSourceCount=university_safe_totals["fta_partner"],
            defaultOn=False,
            status="matched",
            statusLabel="strict active ROR matches",
            sourceLabel="DFAT in-force FTA partners outside Oceania · ROR v2.11",
            sourceUrl="https://www.dfat.gov.au/trade/agreements/in-force",
            sourceFile=paths["world_universities"].name,
            sourceSha256=sha256(paths["world_universities"]),
            matchFile=paths["university_matches"].name,
            matchSha256=sha256(paths["university_matches"]),
            registrySourceUrl="https://zenodo.org/records/21773148",
            registryUpdatedAt="2026-08-03",
            sourceUpdatedAt="2015-11-02",
            importedAt=args.imported_at,
            coordinateBasis="ROR v2.11 / GeoNames locality centroid; not a campus pin",
            warning=(
                "Current ROR organisations selected through Australia's in-force FTA partner economies and a historical 2015 index. "
                f"{university_scope_totals['fta_partner'] - university_safe_totals['fta_partner']:,} scoped rows remain held and "
                f"{university_safe_totals['fta_partner'] - counts['australia-fta-universities']:,} duplicate historical listings were merged. "
                "Oceania is kept in its own layer to avoid duplicate points. Inclusion does not mean the institution participates in, endorses or is partnered through an FTA."
            ),
            rightsNote=(
                "Published display fields come from ROR (CC0); embedded GeoNames locality data is CC BY 4.0. "
                "This is not Australia's complete treaty network."
            ),
            scopeSourceCount=university_scope_totals["fta_partner"],
            scopeAsAt="2026-08-11",
            scopeCountryCodes=UNIVERSITY_SCOPE_COUNTRIES["fta_partner"],
            pointSize=0.036,
            opacity=0.84,
            src="data/layers/australia-fta-universities.js",
        ),
        layer_metadata(
            id="eu-framework-universities",
            label="Universities in EU member states",
            colour="#60a5fa",
            mappedCount=counts["eu-framework-universities"],
            unresolvedCount=university_scope_totals["eu_framework"] - university_safe_totals["eu_framework"],
            deduplicatedCount=(
                university_safe_totals["eu_framework"] - counts["eu-framework-universities"]
            ),
            matchedSourceCount=university_safe_totals["eu_framework"],
            defaultOn=False,
            status="matched",
            statusLabel="strict active ROR matches",
            sourceLabel="Australia-EU Framework Agreement · ROR v2.11",
            sourceUrl="https://www.dfat.gov.au/geo/europe/european-union/australia-european-union-eu-framework-agreement",
            sourceFile=paths["world_universities"].name,
            sourceSha256=sha256(paths["world_universities"]),
            matchFile=paths["university_matches"].name,
            matchSha256=sha256(paths["university_matches"]),
            registrySourceUrl="https://zenodo.org/records/21773148",
            registryUpdatedAt="2026-08-03",
            sourceUpdatedAt="2015-11-02",
            importedAt=args.imported_at,
            coordinateBasis="ROR v2.11 / GeoNames locality centroid; not a campus pin",
            warning=(
                "EU member states are included through the in-force Australia-EU Framework Agreement, not the not-yet-in-force Australia-EU FTA. "
                f"{university_scope_totals['eu_framework'] - university_safe_totals['eu_framework']:,} scoped rows remain held. "
                "Inclusion does not mean the institution participates in, endorses or is partnered through the agreement."
            ),
            rightsNote=(
                "Published display fields come from ROR (CC0); embedded GeoNames locality data is CC BY 4.0."
            ),
            scopeSourceCount=university_scope_totals["eu_framework"],
            scopeAsAt="2026-08-11",
            scopeCountryCodes=UNIVERSITY_SCOPE_COUNTRIES["eu_framework"],
            pointSize=0.034,
            opacity=0.80,
            src="data/layers/eu-framework-universities.js",
        ),
        layer_metadata(
            id="timor-leste-universities",
            label="Universities in Timor-Leste",
            colour="#2dd4bf",
            mappedCount=0,
            unresolvedCount=0,
            deduplicatedCount=0,
            matchedSourceCount=0,
            defaultOn=False,
            status="no-source-rows",
            statusLabel="no historical rows",
            sourceLabel="Australia-Timor-Leste Maritime Boundary Treaty",
            sourceUrl="https://www.dfat.gov.au/geo/timor-leste/australias-maritime-arrangements-with-timor-leste",
            sourceFile=paths["world_universities"].name,
            sourceSha256=sha256(paths["world_universities"]),
            matchFile=paths["university_matches"].name,
            matchSha256=sha256(paths["university_matches"]),
            sourceUpdatedAt="2015-11-02",
            importedAt=args.imported_at,
            coordinateBasis="none",
            warning=(
                "Timor-Leste is in the named bilateral treaty scope, but the historical university index contains no Timor-Leste rows."
            ),
            scopeSourceCount=0,
            scopeAsAt="2026-08-11",
            scopeCountryCodes=UNIVERSITY_SCOPE_COUNTRIES["named_treaty"],
            unavailableReason="No location was fabricated; a current source-led Timor-Leste university catalogue would be a separate future addition.",
        ),
        layer_metadata(
            id="world-universities",
            label="University index outside current scope",
            colour="#94a3b8",
            mappedCount=0,
            unresolvedCount=university_remaining,
            defaultOn=False,
            status="unresolved",
            statusLabel="not yet matched",
            sourceLabel="world-universities.csv",
            sourceFile=paths["world_universities"].name,
            sourceSha256=sha256(paths["world_universities"]),
            sourceUpdatedAt="2015-11-02",
            importedAt=args.imported_at,
            coordinateBasis="none",
            warning="Rows outside the current Oceania, in-force FTA partner and EU Framework Agreement scopes remain deliberately unmapped.",
            unavailableReason=f"{university_remaining:,} rows remain outside the current source-backed matching scope.",
        ),
        layer_metadata(
            id="foreign-missions-australia",
            label="Foreign missions in Australia",
            colour="#60a5fa",
            mappedCount=0,
            unresolvedCount=missions_in_australia_count,
            defaultOn=False,
            status="unresolved",
            statusLabel="needs verified coordinates",
            sourceLabel="Australian World Travel · Missions",
            sourceUrl="https://auraofintelligence.github.io/Australian-world-travel/missions.html",
            sourceFile=paths["missions_in_australia"].name,
            sourceSha256=sha256(paths["missions_in_australia"]),
            sourceUpdatedAt="2026-05-19",
            importedAt=args.imported_at,
            coordinateBasis="none",
            warning="Addresses and websites still need per-mission checks; city-centre dots would imply false precision.",
            unavailableReason=(
                f"{missions_in_australia_count} records across "
                f"{len(mission_cities)} cities need verified coordinates before mapping."
            ),
        ),
        layer_metadata(
            id="aura-affinity",
            label="Aura Affinity",
            colour="#f472b6",
            mappedCount=counts["aura-affinity"],
            unresolvedCount=0,
            defaultOn=False,
            status="unverified",
            statusLabel="unverified 2025 snapshot",
            sourceLabel="Aura Affinity",
            sourceUrl="https://auraofintelligence.github.io/aura-affinity/",
            sourceFile=paths["affinity"].name,
            sourceSha256=sha256(paths["affinity"]),
            sourceUpdatedAt="2025-09-01",
            importedAt=args.imported_at,
            coordinateBasis="Google Places point from source snapshot",
            warning="All records are unverified. Contact details and copied reviews were deliberately excluded.",
            rightsNote="Third-party reuse and Google Places display terms are TO BE CONFIRMED before publication.",
            pointSize=0.026,
            opacity=0.66,
            src="data/layers/aura-affinity.js",
        ),
    ]
    write_manifest(manifest)
    return {
        "counts": counts,
        "unresolved": {
            "oceania-universities": (
                university_scope_totals["oceania"] - university_safe_totals["oceania"]
            ),
            "australia-fta-universities": (
                university_scope_totals["fta_partner"]
                - university_safe_totals["fta_partner"]
            ),
            "eu-framework-universities": (
                university_scope_totals["eu_framework"]
                - university_safe_totals["eu_framework"]
            ),
            "world-universities": university_remaining,
            "foreign-missions-australia": missions_in_australia_count,
            "australian-missions-abroad": 0,
        },
        "referenceOnly": {"australian-missions-abroad": missions_abroad_reference},
        "allianceFolders": alliance_diag["folders"],
        "missionCities": dict(mission_cities),
        "outputs": [str(MANIFEST_PATH)]
        + [str(path) for path in sorted(LAYERS_DIR.glob("*.js"))],
    }


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument(
        "--world-cities",
        default=DEFAULT_DOWNLOADS / "worldcities.csv",
        type=Path,
    )
    command.add_argument(
        "--world-universities",
        default=DEFAULT_DOWNLOADS / "world-universities.csv",
        type=Path,
    )
    command.add_argument(
        "--university-matches",
        default=DEFAULT_UNIVERSITY_MATCHES,
        type=Path,
    )
    command.add_argument(
        "--aura-alliance",
        default=DEFAULT_DOWNLOADS / "1st Step to Aura Alliance.kml",
        type=Path,
    )
    command.add_argument(
        "--north-stradbroke-kmz",
        default=DEFAULT_DOWNLOADS / "North Stradbroke Island.kmz",
        type=Path,
    )
    command.add_argument(
        "--north-stradbroke-recovered",
        default=WORKSPACE
        / "quandamooka-country-events-engine"
        / "assets"
        / "place-data-mymaps.js",
        type=Path,
    )
    command.add_argument(
        "--affinity",
        default=WORKSPACE / "aura-affinity" / "aura-affinity.csv",
        type=Path,
    )
    command.add_argument(
        "--missions-in-australia",
        default=WORKSPACE / "Australian-world-travel" / "missions.html",
        type=Path,
    )
    command.add_argument(
        "--missions-abroad",
        default=WORKSPACE / "Australian-world-travel" / "abroad.html",
        type=Path,
    )
    command.add_argument("--imported-at", default="2026-08-11")
    return command


if __name__ == "__main__":
    result = build(parser().parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
