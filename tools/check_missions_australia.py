#!/usr/bin/env python3
"""Read-only release checks for the repaired mission directory and map layer."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(cache: bool = False) -> dict:
    raw = (ROOT / "data/missions-australia.json").read_bytes().replace(b"\r\n", b"\n")
    catalogue = json.loads(raw)
    rows = catalogue["records"]
    assert len(rows) == 141
    assert {r["legacyRowNumber"] for r in rows} == set(range(1, 142))
    assert len({r["id"] for r in rows}) == 141
    assert catalogue["checkedAt"] == "2026-09-06"
    mapped = [r for r in rows if r["status"] == "mapped"]
    coordinate_reviews = json.loads((ROOT / "data/missions-australia-coordinate-reviews.json").read_text(encoding="utf-8"))
    accepted = {r["id"]: r for r in coordinate_reviews["reviews"] if r["decision"] == "accept"}
    assert set(accepted) <= {r["id"] for r in mapped}
    assert catalogue["counts"] == {"sourceRecords": 141, "mapped": len(mapped), "held": 141-len(mapped)}
    layer_text = (ROOT / "data/layers/foreign-missions-australia.js").read_text(encoding="utf-8")
    layer = json.JSONDecoder().raw_decode(layer_text.split('window.AURA_LOCATION_DATA["foreign-missions-australia"]=', 1)[1])[0]
    assert len(layer) == len(mapped)
    points = {p[8]["id"]: p for p in layer}
    assert len(points) == len(mapped)
    forbidden = re.compile(r"phone|email|fax|staff|spouse|residence|personName", re.I)
    for row in rows:
        assert row["id"] == f"mission-au-{row['legacyRowNumber']:03d}"
        assert row["checkedAt"] == catalogue["checkedAt"]
        assert row["status"] in {"held", "mapped"} and row["reason"]
        assert not any(forbidden.fullmatch(key) for key in row)
        for field in ("sourceUrl", "website", "coordinateSourceUrl"):
            assert not row[field] or re.match(r"^https?://[^\s]+$", row[field]), (row["id"], field)
        if row["status"] == "held":
            assert row["latitude"] is None and row["longitude"] is None and not row["coordinateSourceUrl"]
            assert row["id"] not in points
            continue
        assert row["address"] and row["sources"]
        assert not re.search(r"\b(?:P\.?\s*O\.?\s*Box|GPO|Locked Bag)\b", row["address"], re.I)
        assert math.isfinite(row["latitude"]) and -44 <= row["latitude"] <= -9
        assert math.isfinite(row["longitude"]) and 112 <= row["longitude"] <= 154
        review = accepted.get(row["id"])
        if review:
            assert row["address"] == review["expectedAddress"]
            assert row["coordinateSourceUrl"] == review["sourceUrl"]
            assert row["latitude"] == review["latitude"] and row["longitude"] == review["longitude"]
            assert row["coordinateEvidence"]["sourceFeatureId"] == review["sourceFeatureId"]
            assert row["coordinateEvidence"]["licence"] == "CC BY 4.0"
            assert row["coordinateEvidence"]["postcodeVerified"] is False
            assert row["coordinateSourceUrl"].startswith("https://services1.arcgis.com/E5n4f1VY84i0xSjy/arcgis/rest/services/ACTGOV_ADDRESSES/FeatureServer/0/query?")
        else:
            assert re.match(r"^https://www.openstreetmap.org/(node|way|relation)/\d+$", row["coordinateSourceUrl"])
        point = points[row["id"]]
        assert point[1:3] == [row["latitude"], row["longitude"]]
        assert point[5] == row["sourceUrl"] and point[8]["address"] == row["address"]
        assert point[8]["coordinateSourceUrl"] == row["coordinateSourceUrl"]
        if cache and not review:
            from geocode_missions_australia import query_for, cache_path, strict_match
            query = query_for(row["address"])
            saved = json.loads(cache_path(query).read_text(encoding="utf-8"))
            assert saved["query"] == query
            location, _ = strict_match(row, saved["results"])
            assert location and [location["latitude"],location["longitude"]] == point[1:3]
    for number in (1, 77, 83, 139):
        row = next(r for r in rows if r["legacyRowNumber"] == number)
        assert row["status"] == "held" and not row["address"], number
    reviews = json.loads((ROOT / "data/missions-australia-reviewed.json").read_text(encoding="utf-8"))
    for review in reviews["reviews"]:
        row = next(r for r in rows if r["legacyRowNumber"] == review["sourceRowNumber"])
        assert row["country"] == review["country"]
        if review["decision"] == "address-verified":
            assert row["address"] == review["officialAddress"] and row["sources"] == review["sources"]
            if review.get("officialType"):
                assert row["type"] == review["officialType"]
    manifest_text = (ROOT / "data/location-layers.js").read_text(encoding="utf-8")
    manifest = json.JSONDecoder().raw_decode(manifest_text.split("window.AURA_LOCATION_MANIFEST=", 1)[1])[0]
    entry = next(m for m in manifest if m["id"] == "foreign-missions-australia")
    assert entry["mappedCount"] == len(mapped) and entry["unresolvedCount"] == 141-len(mapped)
    assert entry["sourceSha256"] == hashlib.sha256(raw).hexdigest().upper()
    assert "OpenStreetMap" in entry["rightsNote"] and "ODbL" in entry["rightsNote"] and "ACTGOV" in entry["rightsNote"]
    return {"status": "ok", **catalogue["counts"], "addressesChecked": sum(bool(r["address"]) for r in rows), "cacheChecked": cache}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", action="store_true")
    print(json.dumps(check(parser.parse_args().cache), indent=2))
