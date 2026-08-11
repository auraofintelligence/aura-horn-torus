#!/usr/bin/env python3
"""Validate the generated location catalogue without opening a browser."""

from __future__ import annotations

import json
import math
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO / "data" / "location-layers.js"


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

    if errors:
        raise SystemExit("\n".join(errors))
    return {"layers": len(manifest), "summary": summary, "status": "ok"}


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False, indent=2))
