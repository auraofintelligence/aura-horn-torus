#!/usr/bin/env python3
"""One-off, cached address checks for this mission repair, never a website API.

Read https://operations.osmfoundation.org/policies/nominatim/ before --fetch.
Only public, non-honorary office addresses selected in the candidate file are
sent. One process, one request at a time, at most one per 1.2 seconds. Do not
schedule this tool or expose it as a generic geocoding service.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work" / "missions-australia"
ENDPOINT = "https://nominatim.openstreetmap.org/search"
POLICY = "https://operations.osmfoundation.org/policies/nominatim/"
USER_AGENT = "AuraEarthMissionAddressReview/1.0 (+https://github.com/auraofintelligence/aura-horn-torus)"


def normalise(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).lower().replace("’", "'")
    value = re.sub(r"[^a-z0-9 ]", " ", value)
    aliases = {"st": "street", "rd": "road", "ave": "avenue", "av": "avenue",
               "cres": "crescent", "cct": "circuit", "ct": "court", "pl": "place",
               "tce": "terrace", "hwy": "highway", "dr": "drive", "pde": "parade"}
    return " ".join(aliases.get(word, word) for word in value.split())


def query_for(address: str) -> str:
    # Remove floor/suite information, never change the street number or locality.
    text = re.sub(r"\b(?:suite|suit|level|floor|unit)\s+\d+[A-Za-z]?(?:\.\d+)?\s*,?\s*", "", address, flags=re.I)
    text = re.sub(r"\b\d+(?:st|nd|rd|th)\s+floor\s*,?\s*", "", text, flags=re.I)
    text = re.sub(r"\b(?:[LU])?\d+/\s*(?=\d+\s+[A-Za-z])", "", text, flags=re.I)
    # Start at the street-number phrase, skipping an optional building name.
    street = re.search(r"\b\d+[A-Za-z]?(?:\s*-\s*\d+[A-Za-z]?)?\s+(?:[A-Za-z'’.]+\s+){1,5}(?:street|st|road|rd|circuit|cct|crescent|cres|avenue|ave|av|place|pl|close|drive|dr|terrace|tce|way|court|ct|highway|hwy|parade|pde)\b", text, re.I)
    if street:
        text = text[street.start():]
    return text.rstrip(", ") + ("" if re.search(r"\bAustralia\b", text, re.I) else ", Australia")


def cache_path(query: str) -> Path:
    return WORK / "nominatim-cache" / (hashlib.sha256(query.encode()).hexdigest() + ".json")


def fetch(query: str) -> list[dict]:
    url = ENDPOINT + "?" + urllib.parse.urlencode({"q": query, "format": "jsonv2",
        "addressdetails": 1, "countrycodes": "au", "limit": 5})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-AU,en"})
    with urllib.request.urlopen(req, timeout=30) as response:
        results = json.load(response)
    if not isinstance(results, list):
        raise ValueError("Unexpected geocoder response")
    path = cache_path(query)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"query": query, "url": url, "checkedAt": "2026-09-06",
        "licence": "ODbL 1.0", "results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return results


def strict_match(office: dict, results: list[dict]) -> tuple[dict | None, str]:
    source = office["address"]
    norm_source = " " + normalise(source) + " "
    postcodes = re.findall(r"\b(?:ACT|NSW|VIC|QLD|SA|WA|NT|TAS)\s+(\d{4})\b", source, re.I)
    accepted = []
    for result in results:
        parts = result.get("address", {})
        if parts.get("country_code") != "au" or int(result.get("place_rank", 0)) < 28:
            continue
        road = parts.get("road", "")
        number = parts.get("house_number", "")
        if not road or not number:
            continue
        # Exact full street/number in the published address. No similarity score.
        street = normalise(number + " " + road)
        if " " + street + " " not in norm_source:
            continue
        if not postcodes or parts.get("postcode") not in postcodes:
            continue
        lat, lon = float(result["lat"]), float(result["lon"])
        if not (-44 <= lat <= -9 and 112 <= lon <= 154):
            continue
        accepted.append(result)
    if not accepted:
        return None, "No exact building/property address match with the published street number, street and postcode"
    first = accepted[0]
    country = normalise(office.get("country", ""))
    aliases = {"united states of america": "united states", "norway": "norwegian", "ireland": "irish"}
    names = [country, aliases.get(country, country)]
    named = [r for r in accepted if any(name and (" " + name + " ") in (" " + normalise(r.get("name", "")) + " ") for name in names)]
    method = "exact-street-number-road-postcode"
    if len(named) == 1:
        first = named[0]
        accepted = named
        method += "+unique-country-office-name"
    # Separate OSM point/polygon representations within about 25 metres are okay.
    if any(abs(float(r["lat"]) - float(first["lat"])) > .0002 or
           abs(float(r["lon"]) - float(first["lon"])) > .0002 for r in accepted[1:]):
        return None, "Multiple distinct address positions need review"
    return {"latitude": float(first["lat"]), "longitude": float(first["lon"]),
        "sourceUrl": f"https://www.openstreetmap.org/{first['osm_type']}/{first['osm_id']}",
        "precision": "address-matched building/property point, not an entrance",
        "checkedAt": "2026-09-06", "method": method,
        "matchedAddress": first["display_name"], "licence": "ODbL 1.0"}, "Exact address match"


def run(args: argparse.Namespace) -> None:
    source = json.loads(args.input.read_text(encoding="utf-8"))
    offices = source["offices"]
    if len(offices) > 141:
        raise ValueError("This one-off repair is limited to the historical 141 records")
    if args.fetch and not args.accept_usage_policy:
        raise ValueError(f"Read {POLICY} and explicitly pass --accept-usage-policy for this one-off run")
    records, last_request, requests = [], 0.0, 0
    for index, office in enumerate(offices):
        if office.get("honorary") or office.get("addressStatus") != "official-office":
            raise ValueError("Only explicitly selected public non-honorary office addresses may be queried")
        query = query_for(office["address"])
        path = cache_path(query)
        results = None
        if path.exists():
            cached = json.loads(path.read_text(encoding="utf-8"))
            if cached["query"] != query:
                raise ValueError("Cache query mismatch")
            results = cached["results"]
        elif args.fetch:
            time.sleep(max(0, 1.2 - (time.monotonic() - last_request)))
            last_request = time.monotonic()
            try:
                results = fetch(query)
                requests += 1
            except urllib.error.HTTPError as exc:
                # Never retry access denials/rate limits or change identity to get through.
                raise SystemExit(f"Geocoder returned HTTP {exc.code}; stopped. Cached results are preserved.") from exc
        location, reason = strict_match(office, results or [])
        if results is None:
            reason = "Address lookup not yet cached"
        records.append({"id": office["id"], "query": query, "location": location, "reason": reason})
        if (index + 1) % 10 == 0:
            print(f"Checked {index + 1}/{len(offices)} office addresses", flush=True)
    result = {"checkedAt": "2026-09-06", "source": "OpenStreetMap contributors via Nominatim",
        "sourceUrl": "https://www.openstreetmap.org/copyright", "licence": "ODbL 1.0",
        "usagePolicy": POLICY, "records": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"offices": len(records), "addressMatched": sum(bool(r["location"]) for r in records),
        "newRequests": requests, "output": str(args.output)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=WORK / "office-candidates.json")
    parser.add_argument("--output", type=Path, default=WORK / "address-matches.json")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--accept-usage-policy", action="store_true")
    run(parser.parse_args())
