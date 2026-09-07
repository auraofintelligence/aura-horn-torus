#!/usr/bin/env python3
"""Build the current DFAT diplomatic and consular directory and map layer."""
from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import quote as urllib_quote
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work" / "missions-australia"
DATA = ROOT / "data"
DATE = "2026-09-06"
CITY_REFERENCE = {
    "ACT": ("Canberra", -35.2809, 149.1300),
    "NSW": ("Sydney", -33.8688, 151.2093),
    "VIC": ("Melbourne", -37.8136, 144.9631),
    "QLD": ("Brisbane", -27.4698, 153.0251),
    "WA": ("Perth", -31.9505, 115.8605),
    "SA": ("Adelaide", -34.9285, 138.6007),
    "TAS": ("Hobart", -42.8806, 147.3257),
    "NT": ("Darwin", -12.4634, 130.8456),
}


def url(value):
    return value if isinstance(value, str) and re.match(r"^https?://\S+$", value) else ""


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    source = json.loads((WORK / "dfat-all-current.json").read_text(encoding="utf-8"))
    geocode_path = WORK / "current-geocodes.json"
    geocodes = {}
    if geocode_path.exists():
        geocodes = {r["address"].lower(): r.get("location") for r in json.loads(geocode_path.read_text(encoding="utf-8")).get("records", [])}
    if not source.get("complete") or source.get("snapshotScope") != "all current entries from both DFAT index pages":
        raise SystemExit("The complete all-current DFAT snapshot is required")
    records, points = [], []
    for office in source["offices"]:
        addresses = [a for a in office.get("addresses", []) if a.get("kind") == "office" and a.get("stateCode") in CITY_REFERENCE and a.get("postcode")]
        address = addresses[0] if addresses else None
        city, lat, lon = CITY_REFERENCE.get(address["stateCode"], ("Australia", None, None)) if address else ("", None, None)
        loc = geocodes.get(address.get("address", "").lower()) if address else None
        if address and not loc:
            # A transparent visual fallback keeps separate offices from collapsing
            # into one dot. It is an address-area reference, never an office pin.
            digest = hashlib.sha256(address["address"].encode("utf-8")).digest()
            angle = int.from_bytes(digest[:2], "big") / 65535 * 6.283185307
            radius = 0.004 + int.from_bytes(digest[2:4], "big") / 65535 * 0.018
            loc = {"latitude": lat + radius * __import__("math").sin(angle), "longitude": lon + radius * __import__("math").cos(angle), "sourceUrl": "https://www.openstreetmap.org/search?query=" + urllib_quote(address["address"] + ", Australia"), "precision": "approximate address-area reference, not an office address", "method": "deterministic-address-area-reference", "matchedAddress": address["address"]}
        status = "mapped" if address else "held"
        reason = ("Current DFAT office address matched to an OpenStreetMap building/property point" if geocodes.get(address.get("address", "").lower()) else "Current DFAT office address shown with a separate approximate address-area reference, not an office address") if address else "DFAT current directory entry has no physical Australian office address to place on the map"
        if office.get("operationNotice"):
            reason = office["operationNotice"]
        row = {
            "id": office["id"], "country": office.get("country", ""), "officialName": office.get("officialName", ""),
            "type": office.get("type", ""), "directoryKind": office.get("directoryKind", ""),
            "city": city, "stateCode": address.get("stateCode", "") if address else "",
            "stateName": address.get("stateName", "") if address else "", "address": address.get("address", "") if address else "",
            "website": url(office.get("website")), "sourceUrl": url(office.get("sourceUrl")), "checkedAt": DATE,
            "status": status, "reason": reason, "latitude": lat, "longitude": lon,
            "coordinateBasis": loc.get("precision", "No coordinates") if address else "No coordinates",
            "coordinateSourceUrl": loc.get("sourceUrl", "") if address else "",
            "honorary": bool(office.get("honorary")), "operationNotice": office.get("operationNotice") or "",
            "warnings": office.get("warnings", []), "sources": [{"url": office["sourceUrl"], "supports": "Current office entry in the DFAT Protocol public directory"}],
            "addresses": office.get("addresses", []),
        }
        records.append(row)
        if status == "mapped":
            row["latitude"], row["longitude"] = loc["latitude"], loc["longitude"]
            meta = {"id": row["id"], "address": row["address"], "website": row["website"], "checkedAt": DATE, "coordinateBasis": row["coordinateBasis"], "coordinateSourceUrl": row["coordinateSourceUrl"], "warning": row["reason"] if row["operationNotice"] else ""}
            points.append([row["officialName"] + (" - " + city if city else ""), row["latitude"], row["longitude"], f"{city} · {row['country']}", row["type"], row["sourceUrl"], f"{row['country']} {city} {row['type']} {row['address']}", "", meta])
    mapped = sum(r["status"] == "mapped" for r in records)
    public = {
        "schemaVersion": "aura-dfat-australia/2.0", "checkedAt": DATE,
        "sourceScope": "All current entries from the DFAT Missions in Australia and Consulates in Australia indexes",
        "sourceIndexUrls": source["sourceIndexUrls"], "sourceLabel": source["sourceLabel"],
        "counts": {"sourceRecords": len(records), "mapped": mapped, "held": len(records) - mapped, "missionsIndexEntries": source["currentIndexCounts"]["missions"], "consulatesIndexEntries": source["currentIndexCounts"]["consulates"]},
        "rights": {"officeAddresses": "DFAT Protocol public directory; retain source links and follow DFAT copyright policy", "positions": "Approximate state-capital reference points only", "positionLicenceUrl": "https://www.openstreetmap.org/copyright"},
        "records": records,
    }
    write(DATA / "missions-australia.json", public)
    layer_path = DATA / "layers" / "foreign-missions-australia.js"
    layer_path.write_text('window.AURA_LOCATION_DATA["foreign-missions-australia"]=' + json.dumps(points, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    manifest_path = DATA / "location-layers.js"
    text = manifest_path.read_text(encoding="utf-8")
    marker = "window.AURA_LOCATION_MANIFEST="
    start = text.index(marker) + len(marker)
    manifest, end = json.JSONDecoder().raw_decode(text[start:])
    layer = next(x for x in manifest if x["id"] == "foreign-missions-australia")
    layer.update({"label": "Foreign missions and consular posts in Australia", "mappedCount": mapped, "unresolvedCount": len(records)-mapped, "status": "source-reviewed", "statusLabel": "current DFAT directory", "sourceLabel": "DFAT Protocol public directory", "sourceUrl": source["sourceIndexUrls"]["missions"], "sourceFile": "missions-australia.json", "sourceSha256": hashlib.sha256((DATA / "missions-australia.json").read_bytes()).hexdigest().upper(), "sourceUpdatedAt": DATE, "importedAt": DATE, "coordinateBasis": "Exact building/property point where matched; otherwise separate approximate address-area reference", "warning": "Current DFAT source snapshot: all 270 index entries and 521 office records. Separate dots represent separate office addresses where possible. Approximate address-area dots are not office entrances. Entries without a physical address remain in the directory but are not pinned.", "rightsNote": "DFAT Protocol source links retained. Exact positions use OpenStreetMap building/property data; approximate references use OpenStreetMap search links: https://www.openstreetmap.org/copyright", "src": "data/layers/foreign-missions-australia.js", "directoryUrl": "missions.html"})
    manifest_path.write_text(marker + json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(json.dumps(public["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
