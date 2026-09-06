#!/usr/bin/env python3
"""Reconcile the historical 141 missions with sourced offices and cached geocodes."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

if __package__:
    from .build_location_layers import write_layer, write_manifest
    from .geocode_missions_australia import query_for
else:
    from build_location_layers import write_layer, write_manifest
    from geocode_missions_australia import query_for

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work" / "missions-australia"
DATA = ROOT / "data"
DATE = "2026-09-06"
SOURCE = "https://auraofintelligence.github.io/Australian-world-travel/missions.html"
CITY_STATES = {"Canberra": "ACT", "Sydney": "NSW", "Melbourne": "VIC",
               "Brisbane": "QLD", "Perth": "WA", "Adelaide": "SA"}
POSTCODE_BOUNDS = {"Canberra": (2600, 2620), "Sydney": (2000, 2234),
    "Melbourne": (3000, 3207), "Brisbane": (4000, 4179),
    "Perth": (6000, 6199), "Adelaide": (5000, 5199)}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_url(value) -> str:
    return value if isinstance(value, str) and re.match(r"^https?://[^\s]+$", value) else ""


def local_address(address: dict) -> bool:
    return (address.get("kind") == "office" and address.get("stateCode") in CITY_STATES.values()
        and re.fullmatch(r"\d{4}", str(address.get("postcode", ""))) is not None
        and not re.search(r"\b(?:P\.?\s*O\.?\s*Box|GPO|Locked Bag|Private Bag)\b", address["address"], re.I))


def city_for(address: dict) -> str:
    state, postcode = address.get("stateCode"), int(address.get("postcode") or 0)
    for city, (low, high) in POSTCODE_BOUNDS.items():
        if state == CITY_STATES[city] and low <= postcode <= high:
            return city
    return address.get("locality") or state or "Australia"


def primary_addresses(office: dict) -> list[dict]:
    addresses = [a for a in office["addresses"] if local_address(a)]
    for pattern in (r"^chancery$", r"^consulate(?:[- ]general)?(?:$| of )", r"^office$"):
        primary = [a for a in addresses if re.match(pattern, a.get("sourceLabel", ""), re.I)]
        if primary:
            return primary
    return addresses


def reconcile(source: dict, evidence: dict) -> tuple[list[dict], list[dict]]:
    if source["oldRecordCount"] != 141 or source.get("limitedRun"):
        raise ValueError("A complete attempted source pass over all 141 old records is required")
    if len(source["pageResults"]) + len(source["fetchErrors"]) != source["neededCountryPages"]:
        raise ValueError("The official source fetch has not finished")
    reviews = {r["sourceRowNumber"]: r for r in evidence["reviews"]}
    pages = {row: page["url"] for page in source["pageResults"] for row in page["legacyRows"]}
    records, candidates = [], []
    for old in source["legacyRecords"]:
        number = old["legacyRowNumber"]
        record = {"id": f"mission-au-{number:03d}", "legacyRowNumber": number,
            "country": old["country"], "city": old["city"], "type": old["type"],
            "name": f"{old['country']} {old['type']} - {old['city']}", "address": "", "website": "",
            "sourceUrl": pages.get(number, "https://protocol.dfat.gov.au/Public/MissionsInAustralia"),
            "checkedAt": DATE, "status": "held", "reason": "No unambiguous current Australian office found for the historical listing",
            "coordinateBasis": "No verified coordinates", "latitude": None, "longitude": None,
            "coordinateSourceUrl": "", "historicalSourceUrl": SOURCE,
            "historicalCity": old["city"], "historicalType": old["type"], "sources": []}
        review = reviews.get(number)
        if review and (review["country"], review["sourceCity"], review["missionType"]) != (old["country"], old["city"], old["type"]):
            raise ValueError(f"Review identity differs for row {number}")
        offices = [office for office in source["offices"] if office["sourceUrl"] == pages.get(number)]
        if review and review["decision"] == "hold":
            record.update(reason=review["reason"], sources=review["sources"], sourceUrl=review["sources"][0]["url"])
            records.append(record)
            continue
        active = [office for office in offices if not office.get("operationNotice")]
        if offices and not active:
            record["reason"] = "Official source reports: " + "; ".join(dict.fromkeys(o["operationNotice"] for o in offices))
            records.append(record)
            continue
        pairs = [(office, address) for office in active if not office.get("honorary")
                 for address in primary_addresses(office)]
        if "consul" in old["type"].lower():
            pairs = [(office, address) for office, address in pairs if city_for(address) == old["city"]]
        selected = pairs[0] if len(pairs) == 1 else None
        if selected:
            office, address = selected
            record.update(name=office["officialName"] + " - " + city_for(address), city=city_for(address),
                type=office["type"], address=address["address"], website=safe_url(office["website"]),
                sourceUrl=office["sourceUrl"], officeSourceId=office["id"],
                sources=[{"url": office["sourceUrl"], "supports": "Published institutional office address in the DFAT Protocol directory"}])
        if review and review["decision"] == "address-verified":
            if review.get("officialPhysicalCountryCode") != "AU":
                raise ValueError("Only explicitly Australian reviewed offices may be mapped")
            record.update(name=review["officialName"] + " - " + review["officialCity"],
                city=review["officialCity"], address=review["officialAddress"],
                sourceUrl=review["sources"][0]["url"], sources=review["sources"], reviewNote=review["reason"])
            record["type"] = review.get("officialType", record["type"])
        if record["address"]:
            record["reason"] = "Office address checked; building/property position still needs an exact address match"
            candidates.append({"id": record["id"], "address": record["address"], "addressStatus": "official-office",
                "honorary": False, "name": record["name"], "country": record["country"], "sourceUrl": record["sourceUrl"]})
        elif active and not pairs:
            record["reason"] = "No suitable Australian physical office address: non-resident, postal-only or honorary office requires separate review"
        elif len(pairs) > 1:
            record["reason"] = "More than one current office/address matches this historical entry; identity review needed"
        records.append(record)
    if {r["legacyRowNumber"] for r in records} != set(range(1, 142)):
        raise ValueError("Historical record coverage is incomplete")
    return records, candidates


def build(args: argparse.Namespace) -> None:
    source = json.loads((WORK / "dfat-offices.json").read_text(encoding="utf-8"))
    evidence = json.loads((DATA / "missions-australia-reviewed.json").read_text(encoding="utf-8"))
    records, candidates = reconcile(source, evidence)
    write_json(WORK / "office-candidates.json", {"checkedAt": DATE, "offices": candidates})
    if args.candidates_only:
        print(json.dumps({"officeCandidates": len(candidates), "held": len(records) - len(candidates),
            "reasons": dict(Counter(r["reason"] for r in records if not r["address"]))}, indent=2))
        return
    geocodes = json.loads((WORK / "address-matches.json").read_text(encoding="utf-8"))
    matches = {r["id"]: r for r in geocodes["records"]}
    coordinate_reviews = json.loads((DATA / "missions-australia-coordinate-reviews.json").read_text(encoding="utf-8"))
    accepted = {r["id"]: r for r in coordinate_reviews["reviews"] if r["decision"] == "accept"}
    by_id = {r["id"]: r for r in records}
    for mid, review in accepted.items():
        if mid not in by_id or not by_id[mid]["address"] or review["expectedAddress"] != by_id[mid]["address"]:
            raise ValueError(f"Reviewed coordinate address has changed: {mid}")
    points = []
    for record in records:
        result = matches.get(record["id"])
        review = accepted.get(record["id"])
        if not record["address"] or not (result or review):
            continue
        if review:
            location = {**review, "matchedAddress": review["sourceAddress"], "checkedAt": coordinate_reviews["checkedAt"]}
            position_label = "ACT Government address point"
        elif result["query"] != query_for(record["address"]):
            record["reason"] = "The cached position belongs to an earlier address query; a new exact address match is required"
            continue
        elif not result["location"]:
            record["reason"] = "Office address checked. " + result["reason"]
            continue
        else:
            location = result["location"]
            position_label = "OpenStreetMap building/property position"
        coordinate_evidence = {"matchedAddress": location["matchedAddress"], "method": location["method"], "checkedAt": DATE}
        if review:
            coordinate_evidence.update({key: review[key] for key in ("sourceFeatureId", "licence", "licenceUrl", "sourceLabel", "attribution", "sourceMetadataUrl", "postcodeVerified", "reason")})
        record.update(status="mapped", reason="Published office address matched to an " + position_label,
            latitude=location["latitude"], longitude=location["longitude"],
            coordinateBasis=location["precision"], coordinateSourceUrl=location["sourceUrl"],
            coordinateEvidence=coordinate_evidence)
        metadata = {"id": record["id"], "address": record["address"], "website": record["website"],
            "checkedAt": DATE, "coordinateBasis": record["coordinateBasis"],
            "coordinateSourceUrl": record["coordinateSourceUrl"],
            "warning": record.get("reviewNote", "")}
        points.append([record["name"],record["latitude"],record["longitude"],
            record["city"] + " · " + record["country"],record["type"],record["sourceUrl"],
            " ".join([record["country"],record["city"],record["type"],record["address"]]),"",metadata])
    public = {"schemaVersion": "aura-missions-australia/1.0", "checkedAt": DATE,
        "historicalSourceUrl": SOURCE, "historicalSourceSha256": evidence["source"]["sha256"],
        "counts": {"sourceRecords": 141, "mapped": len(points), "held": 141 - len(points)},
        "sourceScope": "Repair of the historical 141-entry list, not a complete current diplomatic directory",
        "rights": {"officeAddresses": "DFAT and linked official sources; DFAT CC BY 4.0 except otherwise noted",
            "positions": "OpenStreetMap contributors, ODbL 1.0; ACTGOV ADDRESSES from ACTmapi, © Australian Capital Territory, CC BY 4.0",
            "positionLicenceUrl": "https://www.openstreetmap.org/copyright",
            "actSourceUrl": "https://www.arcgis.com/home/item.html?id=13427dc77da340a29dd6601af4d7484d",
            "actLicenceUrl": "https://creativecommons.org/licenses/by/4.0/"},
        "records": records}
    write_json(DATA / "missions-australia.json", public)
    write_layer("foreign-missions-australia", points)
    manifest_text = (DATA / "location-layers.js").read_text(encoding="utf-8")
    marker = "window.AURA_LOCATION_MANIFEST="
    manifest = json.JSONDecoder().raw_decode(manifest_text.split(marker, 1)[1])[0]
    apply_layer(manifest, public)
    write_manifest(manifest)
    print(json.dumps(public["counts"]))


def apply_layer(manifest: list[dict], public: dict | None = None) -> None:
    if public is None:
        path = DATA / "missions-australia.json"
        if not path.exists():
            return
        public = json.loads(path.read_text(encoding="utf-8"))
    layer = next(r for r in manifest if r["id"] == "foreign-missions-australia")
    counts = public["counts"]
    layer.update(label="Foreign missions in Australia", mappedCount=counts["mapped"], unresolvedCount=counts["held"],
        defaultOn=False, status="source-reviewed", statusLabel="office addresses checked 6 September 2026",
        sourceLabel="DFAT Protocol and official mission sources", sourceUrl="https://protocol.dfat.gov.au/Public/MissionsInAustralia",
        sourceFile="missions-australia.json", sourceSha256=hashlib.sha256((DATA / "missions-australia.json").read_bytes().replace(b"\r\n", b"\n")).hexdigest().upper(),
        sourceUpdatedAt=DATE, importedAt=DATE, coordinateBasis="Exact OSM or ACT Government address-matched property point, not an entrance",
        warning="A repair of the historical 141 records, not a complete current diplomatic directory. Only matched public offices are pinned. Held, suspended, non-resident and ambiguous records are explained in the missions directory. Check current services and appointments with the office before visiting.",
        rightsNote="Office addresses: DFAT and linked official sources; DFAT CC BY 4.0. Position data © OpenStreetMap contributors, ODbL 1.0: https://www.openstreetmap.org/copyright; ACTGOV ADDRESSES © Australian Capital Territory, CC BY 4.0: https://www.arcgis.com/home/item.html?id=13427dc77da340a29dd6601af4d7484d",
        src="data/layers/foreign-missions-australia.js", directoryUrl="missions.html")
    layer.pop("unavailableReason", None)
    if not counts["mapped"]:
        layer["unavailableReason"] = "Office addresses have been reviewed; no building/property positions have passed the address matching gate"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates-only", action="store_true")
    build(parser.parse_args())
