# University coverage and connections

5 September 2026. The purpose is to discover education institutions and networks that could contribute to the [Global Association for Joyful Responsible Abundance on Earth](https://auraofintelligence.github.io/gajra-earth-claude-build/).

## What is available

The [university directory](../universities.html) contains **26,103 active education organisations across 224 country and territory codes** from the [ROR v2.11 snapshot](https://zenodo.org/records/21773148), dated 3 August 2026. All 26,167 registry locality entries are preserved. Forty-five organisations have multiple localities.

ROR describes research organisations. Its education category includes universities, colleges and other education bodies. This is a broad discovery foundation, not proof of accreditation or a completed inventory of all universities on Earth. Neither the registry's education classification nor an organisation's name establishes that it awards recognised university degrees.

The directory supports name and multilingual alias search, country, evidenced peak-body membership, shared identifiers and recorded organisational relationships. Country and locality search include additional locations. A selected institution opens its own details and can be shown on the globe. Results can be downloaded as a CSV for further investigation.

Thirteen institutions have 15 initial, sourced peak-body membership entries: eight from [Universities Australia](https://universitiesaustralia.edu.au/our-universities/), four from the [Pacific Islands Universities Regional Network (PIURN)](https://piurn.org/member-universities/) and three from the [Association of Pacific Rim Universities (APRU)](https://www.apru.org/members/). ANU and UQ each have two checked memberships. The international sample includes the University of the South Pacific, Fiji National University, the University of Papua New Guinea, the National University of Samoa and the University of Auckland. This is a starter sample only. Absence of an entry means not yet assessed.

## Completing the historical university list

All **9,363 rows** in the supplied 2015 list have now had an identity-matching pass. The untouched first audit remains available as a baseline; the effective catalogue combines it with the newly audited world backlog and explicit reviews.

| Result | Historical rows |
| --- | ---: |
| Accepted active identity in the pinned registry | 5,141 |
| Further identity review needed | 1,995 |
| No acceptable match found | 2,121 |
| Inactive historical identity | 106 |
| Total | 9,363 |

The 5,141 accepted source rows represent **5,133 unique organisations**, after eight duplicate listings are merged. That is **1,624 more mapped institutions** than the previous release: 1,616 from the previously unchecked world backlog and eight Oceania identity reviews. Oceania rises from 56 to 64 mapped institutions, with 13 historical rows still held.

The eight reviewed additions are Avondale, James Cook, RMIT, Federation/Ballarat, Newcastle Australia, Notre Dame Australia, Sydney and Western Sydney. Their official identity evidence is in [the review ledger](../data/university-reviewed-matches.json). Locations remain city/locality approximations.

The independent wider ROR layer adds **20,970 organisations at 21,034 localities**, excluding the 5,133 organisations already in the historical layers. Together the layers cover the 26,103 registry organisations without duplicating an institution across those layers. A current registry organisation can be shown independently even while an ambiguous old name remains unresolved; that does not assert they are the same entity.

## Applicability and interoperability

Use separate evidence for national recognition, subjects or programmes, peak-body membership, public participation, and specific collaboration opportunities. [The applicability research](university-applicability.md) proposes six filters and an enrichment sequence through Universities Australia, PIURN and APRU, followed by IAU and ACU.

ROR, ISNI, Wikidata and funder identifiers help records from different systems refer to the same institution. Parent/child/related links describe only the relationship recorded by ROR. They do not establish participation in a treaty, a research partnership or an ability to exchange data automatically.

GAJRA status starts as **not assessed**. A person signing GAJRA's invitation does not establish the membership of their employer. There has been no outreach through this work.

Suggested complementary place layers include repair and sharing, community food/seed projects, libraries and makerspaces, citizen science, habitat care, community energy, co-operatives, arts/play/gathering, and public amenities. These are [suggestions with directory leads](location-layer-directions.md), not imported organisations or assessed GAJRA members.

## Remaining work

1. Establish country-by-country university coverage against national regulators and registers; use WHED's recognition criteria and identifiers where access and reuse permit. Preserve recognised universities, colleges, vocational providers and research organisations as distinct evidence-based classes.
2. Enrich membership and programme evidence, starting with the peak bodies above. Each claim needs a source and checked date. Add public community participation and specific research capabilities from institution pages.
3. Resolve the 4,222 held historical rows and add actual campus locations from official sources. Some current organisations already appear in the wider registry even where their historical identity is still uncertain.
4. The 141 foreign missions in Australia still need verified address coordinates. The historical business, island and city snapshots retain their original age and caveats.

## Reproducing this update

The source university CSV and pinned ROR JSON are inputs, not altered by these commands. Use an HTTP server for the directory; browsers usually block its local JSON requests when opened with `file://`.

```powershell
python -B tools/audit_university_backlog.py
python -B tools/complete_university_catalogue.py
python -B tools/build_location_layers.py --universities-only
python -B tools/build_education_registry.py
python -B tools/build_location_layers.py --universities-only
python -B tools/check_location_layers.py
python -B tools/check_education_registry.py
```

The two university-only passes first create the historical map targets, then register the independently generated wider registry. They preserve all unrelated data snapshots. The original input hashes, review evidence and effective ledger hash are recorded in [the completion summary](../data/university-completion-summary.json). The ROR snapshot bytes are checked before regeneration.

The globe still loads large layers on demand. The directory loads its search index and small membership file first, then the selected country's details. Its 22 MB full registry export is a separate download and is not fetched for ordinary browsing.

ROR metadata is CC0; embedded GeoNames locality data is CC BY 4.0. The historical list's compilation licence is unknown; its old website list has not been republished. The satellite provider and imagery configuration are unchanged by this data update.
