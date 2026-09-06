"""Cache official DFAT office fields needed to reconcile the legacy 141 rows.

Public source HTML is cached only under ignored work/. The derived JSON excludes
staff names, personal contacts, residence addresses and postal-only addresses.
This script does not geocode, publish, contact missions or change the old source.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://protocol.dfat.gov.au"
STATES = {
    "ACT": "Australian Capital Territory", "NSW": "New South Wales",
    "NT": "Northern Territory", "QLD": "Queensland", "SA": "South Australia",
    "TAS": "Tasmania", "VIC": "Victoria", "WA": "Western Australia",
}
ALIASES = {
    "south korea": "korea republic of korea",
    "north korea": "korea democratic people s republic of korea",
    "turkey": "turkiye", "east timor": "timor leste",
    "nauru": "naoero", "united states": "united states of america",
    "vatican city": "holy see", "swaziland": "eswatini",
    "brunei": "brunei darussalam", "slovakia": "slovak republic",
}
LEGACY = re.compile(
    r"\{\s*country:\s*'(?P<country>(?:\\.|[^'])*)',\s*"
    r"city:\s*'(?P<city>(?:\\.|[^'])*)',\s*"
    r"type:\s*'(?P<type>(?:\\.|[^'])*)',"
)


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


def write_snapshot(path: Path, value: dict) -> None:
    """Make each progress snapshot an intact JSON document for parallel readers."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    parent: Node | None = None
    children: list[Node | str] = field(default_factory=list)

    def text(self) -> str:
        return clean(" ".join(c.text() if isinstance(c, Node) else c for c in self.children))

    def descendants(self):
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.descendants()

    def ancestor(self, predicate):
        node = self.parent
        while node:
            if predicate(node):
                return node
            node = node.parent
        return None


class Tree(HTMLParser):
    VOID = {"br", "hr", "img", "input", "link", "meta", "wbr", "source", "area", "base", "embed", "param", "track", "col"}

    def __init__(self, html: str):
        super().__init__(convert_charrefs=True)
        self.root = Node("document", {})
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs), self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack[-1].tag == tag and tag not in self.VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        for idx in range(len(self.stack) - 1, 0, -1):
            if self.stack[idx].tag == tag:
                del self.stack[idx:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def read_legacy(path: Path) -> list[dict]:
    records = []
    for number, match in enumerate(LEGACY.finditer(path.read_text(encoding="utf-8-sig")), 1):
        row = {k: v.replace("\\'", "'").replace("\\\\", "\\") for k, v in match.groupdict().items()}
        records.append({"legacyRowNumber": number, **row})
    if not records:
        raise ValueError("No legacy mission records found")
    return records


class Cache:
    def __init__(self, path: Path, delay: float, offline: bool):
        self.path, self.delay, self.offline = path, delay, offline
        self.path.mkdir(parents=True, exist_ok=True)
        self.last_request = 0.0

    def get(self, url: str) -> tuple[str, str]:
        if urlparse(url).hostname != "protocol.dfat.gov.au":
            raise ValueError("Only public DFAT Protocol pages are in scope")
        file = self.path / (urlparse(url).path.strip("/").replace("/", "-") + ".html")
        if file.exists():
            return file.read_text(encoding="utf-8"), "cache"
        if self.offline:
            raise FileNotFoundError(f"No cached public page: {url}")
        for attempt in range(3):
            pause = self.delay - (time.monotonic() - self.last_request)
            if pause > 0:
                time.sleep(pause)
            request = Request(url, headers={
                "User-Agent": "AuraLocationSourceReview/1.0 (+https://auraofintelligence.github.io/aura-horn-torus/)",
                "Accept": "text/html",
            })
            self.last_request = time.monotonic()
            try:
                with urlopen(request, timeout=30) as response:
                    html = response.read().decode(response.headers.get_content_charset() or "utf-8")
                if "address_Formatted" not in html and "card-title" not in html and "MissionsInAustralia" not in html:
                    raise ValueError("Response did not resemble the expected public directory HTML")
                file.write_text(html, encoding="utf-8")
                return html, "network"
            except (HTTPError, URLError, TimeoutError):
                if attempt == 2:
                    raise
                time.sleep(1 + attempt)
        raise RuntimeError("Unreachable fetch state")


def country_index(html: str, mode: str) -> dict[str, dict]:
    pattern = re.compile(r"^/Public/Missions/(\d+)$" if mode == "missions" else r"^/Public/Consulates/(\d+)/State$")
    result = {}
    for node in Tree(html).root.descendants():
        if node.tag != "a":
            continue
        path = node.attrs.get("href", "")
        match = pattern.match(path)
        if match:
            country = node.text()
            result[key(country)] = {"country": country, "countryId": match.group(1), "url": urljoin(BASE, path)}
    if not result:
        raise ValueError(f"Could not identify {mode} country links")
    return result


def address_parts(address: str) -> dict:
    match = re.search(r",\s*([^,]+),\s*(ACT|NSW|NT|QLD|SA|TAS|VIC|WA)\s+(\d{4})\s*$", address, re.I)
    if match:
        return {"locality": match[1].strip(), "stateCode": match[2].upper(), "postcode": match[3]}
    match = re.search(r"\b(ACT|NSW|NT|QLD|SA|TAS|VIC|WA)\s+(\d{4})\s*$", address, re.I)
    return {"locality": None, "stateCode": match[1].upper() if match else None, "postcode": match[2] if match else None}


def classify_type(name: str, mode: str) -> str:
    lower = name.casefold()
    for needle, result in [("consulate-general", "Consulate-General"), ("consulate general", "Consulate-General"), ("consulate", "Consulate"), ("high commission", "High Commission"), ("embassy", "Embassy")]:
        if needle in lower:
            return result
    return "Diplomatic mission" if mode == "missions" else "Consular office"


def parse_offices(html: str, source: dict, mode: str, checked_at: str) -> list[dict]:
    markers = list(re.finditer(r"<h([34])\b[^>]*>.*?</h\1>", html, re.I | re.S))
    state_code, state_name = None, None
    offices = []
    for index, marker in enumerate(markers):
        heading = Tree(marker[0]).root
        header = next(heading.descendants())
        if marker[1] == "3":
            state_name = header.text()
            state_code = header.attrs.get("id") or next((k for k, v in STATES.items() if v == state_name), None)
            continue
        if not state_name:
            continue
        end = markers[index + 1].start() if index + 1 < len(markers) else len(html)
        segment = html[marker.end():end]
        tree = Tree(segment)
        nodes = list(tree.root.descendants())
        name = header.text()
        addresses, excluded, warnings = [], [], []
        current_label = None
        section_fields = {}
        for node in nodes:
            if node.tag == "p" and "h5" in node.attrs.get("class", "").split():
                current_label = node.text()
            if node.tag == "label" and node.attrs.get("for") == "address_Formatted":
                parent = node.ancestor(lambda x: x.tag == "p")
                address = clean(parent.text().removeprefix("Details")) if parent else ""
                label = current_label or "Unlabelled address"
                if re.search(r"residen|postal|mailing|private", label, re.I):
                    excluded.append(label)
                elif re.search(r"\b(?:PO|P\.?\s*O\.?)\s*Box\b|GPO\s*Box|Locked Bag", address, re.I):
                    excluded.append("Postal-only address")
                elif label == "Unlabelled address":
                    excluded.append(label)
                    warnings.append("Unlabelled address excluded pending review")
                elif re.search(r"chancery|office|consula|embassy|high commission|commission|delegation", label, re.I):
                    addresses.append({"kind": "office", "sourceLabel": label, "address": address, **address_parts(address)})
                else:
                    excluded.append(label)
                    warnings.append("Other address label excluded pending review")
            if node.tag == "div" and "form-group" in node.attrs.get("class", "").split():
                children = [c for c in node.children if isinstance(c, Node)]
                label_node = next((c for c in children if "col-sm-4" in c.attrs.get("class", "").split()), None)
                value_node = next((c for c in children if "col-sm-8" in c.attrs.get("class", "").split()), None)
                if not label_node or not value_node:
                    continue
                label = label_node.text()
                fields = section_fields.setdefault(current_label, {})
                if label == "Web Site Url":
                    links = [c.attrs.get("href", "") for c in value_node.descendants() if c.tag == "a"]
                    listed_url = next((url for url in links if urlparse(url).scheme in {"http", "https"}), None)
                    if listed_url:
                        fields.setdefault("website", listed_url)
                elif label == "Hours of Business":
                    if value_node.text():
                        fields.setdefault("hours", value_node.text())
        # A page can list trade/education/defence sections after the main office.
        # Do not attribute their website or opening hours to the chancery/consulate.
        main_label = next((label for label in section_fields if label and re.match(r"^(?:Chancery|Consulat|Embassy|High Commission|Office$)", label, re.I)), None)
        if main_label is None:
            main_label = next((item["sourceLabel"] for item in addresses if item["sourceLabel"] in section_fields), None)
        fields = section_fields.get(main_label, {})
        website_source_value = fields.get("website")
        website = website_source_value
        if website and (not urlparse(website).hostname or "." not in urlparse(website).hostname or urlparse(website).username):
            website = None
            warnings.append("Main office website link is malformed in official source; excluded pending review")
        hours = fields.get("hours")
        honorary = bool(re.search(r"\bHonorary\s+Consul", tree.root.text(), re.I))
        operation_notice = hours if hours and re.search(r"suspend|permanently\s+closed|ceased\s+operat|no\s+longer\s+operat", hours, re.I) else None
        if operation_notice:
            warnings.append("Official source reports an operational suspension or closure; do not treat as active")
        if honorary:
            warnings.append("Honorary consular post: public office/residential character needs review before precise publication")
        if not addresses:
            warnings.append("No labelled non-postal public office address extracted")
        if addresses and any(not item["stateCode"] for item in addresses):
            warnings.append("Address lacks a recognised Australian state/postcode pattern; may be non-resident representation")
        identity_material = f"{mode}|{source['countryId']}|{state_code}|{key(name)}"
        local_id = f"dfat-protocol-{mode}-{source['countryId']}-{sha256(identity_material.encode()).hexdigest()[:12]}"
        offices.append({
            "id": local_id, "sourceCountryId": source["countryId"], "sourceOfficeId": None,
            "sourceUrl": source["url"], "checkedAt": checked_at, "country": source["country"],
            "officialName": name, "type": classify_type(name, mode), "directoryKind": mode,
            "stateCode": state_code, "stateName": state_name, "addresses": addresses,
            "website": website, "hours": hours, "honorary": honorary,
            "websiteSourceValue": website_source_value,
            "websiteSourceLabel": main_label if website_source_value else None,
            "hoursSourceLabel": main_label if hours else None,
            "operationNotice": operation_notice,
            "excludedAddressKinds": sorted(set(excluded)), "warnings": warnings,
            "coordinateSource": None, "coordinates": None,
        })
    duplicates = Counter(row["id"] for row in offices)
    occurrence = Counter()
    for row in offices:
        if duplicates[row["id"]] > 1:
            occurrence[row["id"]] += 1
            row["id"] += f"-occurrence-{occurrence[row['id']]}"
            row["warnings"].append("Duplicate office heading within state: local occurrence suffix requires reconciliation")
    return offices


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy", type=Path, default=ROOT.parent / "Australian-world-travel" / "missions.html")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--checked-at", default="2026-09-06")
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--limit-pages", type=int, default=None, help="Smoke-test a bounded number of needed country pages")
    parser.add_argument(
        "--all-current", action="store_true",
        help="Fetch every current mission and consulate page from both official index pages into a separate snapshot"
    )
    args = parser.parse_args()
    if args.output is None:
        args.output = ROOT / "work" / "missions-australia" / (
            "dfat-all-current.json" if args.all_current else "dfat-offices.json"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cache = Cache(args.output.parent / "html" / args.checked_at, max(args.delay, 0.5), args.offline)
    legacy = [] if args.all_current else read_legacy(args.legacy)
    indices = {}
    index_urls = {"missions": BASE + "/Public/MissionsInAustralia", "consulates": BASE + "/Public/ConsulatesInAustralia"}
    for mode, url in index_urls.items():
        text, _ = cache.get(url)
        indices[mode] = country_index(text, mode)
    requests, unmatched = {}, []
    if args.all_current:
        # The complete current snapshot is deliberately independent of the old
        # 141-row list. Keep the directory mode in the request key because a
        # country can have both a diplomatic and a consular index entry.
        work = [
            {"source": source, "mode": mode, "legacyRows": []}
            for mode in ("missions", "consulates")
            for source in sorted(indices[mode].values(), key=lambda item: (item["country"].casefold(), item["countryId"]))
        ]
    else:
        for row in legacy:
            mode = "consulates" if "consul" in row["type"].casefold() else "missions"
            country_key = ALIASES.get(key(row["country"]), key(row["country"]))
            source = indices[mode].get(country_key)
            if not source:
                unmatched.append({**row, "reason": f"Country not found in current official {mode} index"})
                continue
            request_key = (mode, source["countryId"])
            if request_key not in requests:
                requests[request_key] = {"source": source, "mode": mode, "legacyRows": []}
            requests[request_key]["legacyRows"].append(row["legacyRowNumber"])
        work = list(requests.values())
    if args.limit_pages:
        work = work[:args.limit_pages]
    result = {
        "schemaVersion": "aura-dfat-office-source/1.0", "checkedAt": args.checked_at,
        "retrievedAt": datetime.now(timezone.utc).isoformat(), "sourceIndexUrls": index_urls,
        "sourceLabel": "Department of Foreign Affairs and Trade Protocol public directory",
        "sourceLicenceUrl": "https://www.dfat.gov.au/about-us/about-this-website/copyright",
        "licenceNote": "DFAT website copyright policy states CC BY 4.0 except otherwise noted; retain Protocol source links and check any source-specific exceptions before release.",
        "identityNote": "sourceCountryId is the official URL identifier; office id is locally derived, not a DFAT-issued identifier.",
        "snapshotScope": "all current entries from both DFAT index pages" if args.all_current else "pages needed to reconcile the historical list",
        "currentIndexCounts": {mode: len(indices[mode]) for mode in ("missions", "consulates")},
        "oldRecordCount": len(legacy), "neededCountryPages": len(work), "limitedRun": bool(args.limit_pages),
        "allCurrent": args.all_current,
        "complete": False,
        "legacyRecords": legacy, "offices": [], "pageResults": [], "unmatchedCountries": unmatched, "fetchErrors": [],
    }
    for idx, item in enumerate(work, 1):
        source, mode = item["source"], item["mode"]
        try:
            text, cache_status = cache.get(source["url"])
            offices = parse_offices(text, source, mode, args.checked_at)
            result["offices"].extend(offices)
            result["pageResults"].append({"url": source["url"], "country": source["country"], "mode": mode, "officeCount": len(offices), "legacyRows": item["legacyRows"], "cache": cache_status, "sha256": sha256(text.encode()).hexdigest()})
            print(f"{idx}/{len(work)} {mode} {source['country']}: {len(offices)} offices", flush=True)
        except Exception as error:
            result["fetchErrors"].append({"url": source["url"], "country": source["country"], "mode": mode, "legacyRows": item["legacyRows"], "error": str(error)})
            print(f"{idx}/{len(work)} failed {mode} {source['country']}: {type(error).__name__}", flush=True)
        # A partial file remains useful if a later network request is interrupted.
        result["counts"] = {"offices": len(result["offices"]), "pagesFetched": len(result["pageResults"]), "fetchErrors": len(result["fetchErrors"]), "unmatchedLegacyRows": len(unmatched)}
        result["complete"] = idx == len(work) and len(result["pageResults"]) == len(work) and not result["fetchErrors"]
        write_snapshot(args.output, result)
    print(json.dumps(result["counts"]), flush=True)


if __name__ == "__main__":
    main()
