# Foreign missions in Australia review

Checked 6 September 2026. This repairs the historical 141-entry list, not every diplomatic or consular office in Australia. Australian missions abroad are a separate dataset and remain labelled with their existing city-level accuracy and source date.

## Result

All 141 identities remain traceable. Official sources provide 137 Australian office addresses. There are 124 mapped positions: 110 exact OpenStreetMap address matches and 14 ACT Government address points. Thirteen checked addresses still need coordinate review. Four other entries have specific operational or non-resident issues; they are not mapped.

Afghanistan has an official suspension notice. Venezuela has an official closure/restructure notice. Kazakhstan and Lesotho are represented by non-resident offices in Singapore and Japan respectively. An ACT heading in the DFAT directory is not proof that an office is physically in Canberra. Each record links to the evidence for its particular decision.

The 13 addresses awaiting positions are Canada (Canberra), El Salvador (Canberra), Greece (Adelaide), India (Canberra and Melbourne), Indonesia (Perth), Italy (Adelaide), Malaysia (Perth), South Africa (Canberra), Uganda (Canberra), the United Kingdom (Canberra and Sydney), and the United States (Canberra). Missing coordinates do not mean those offices are closed.

## Evidence and boundaries

The source pass retrieved all 119 relevant DFAT country pages, with no fetch errors. Main chancery or consulate addresses were separated from postal boxes, residences, honorary offices and subsidiary sections. The public files contain institutional office facts, not staff details or personal contacts.

OpenStreetMap matches require the published street number, street and postcode, an Australian location and building/property-level precision. Ambiguous positions are held. Government matches use exact number, street and suburb, with unit matches where available. The ACT source has no postcode field; no independent postcode verification is claimed. No position is presented as a verified visitor entrance.

The public catalogue is `data/missions-australia.json`. Source exceptions are recorded in `data/missions-australia-reviewed.json`; ACT coordinate decisions are in `data/missions-australia-coordinate-reviews.json`. Raw fetched pages and lookup caches remain local under ignored `work/missions-australia/`. See [source attribution and licence terms](../data/MISSIONS-LICENCE.md).

The corrected catalogue is mirrored into the [Australian World Travel missions page](https://auraofintelligence.github.io/Australian-world-travel/missions.html). That page retains its old array as historical evidence only and never uses it as a current-contact fallback.

## Rechecking and rebuilding

Public release checks do not need source fetching:

```powershell
python -B tools/check_missions_australia.py
python -B tools/check_location_layers.py
node tools/check_inline_scripts.js
node tools/check_control_tabs.js
```

With the reviewed local source cache present, regenerate the mission catalogue and layer, then replay the cached coordinate checks:

```powershell
python -B tools/build_missions_australia.py
python -B tools/check_missions_australia.py --cache
```

The address geocoder is a bounded, one-off repair tool, not a scheduled process or website lookup service. It defaults to cached results and requires an explicit usage-policy acknowledgement before fetching. New source dates and office changes need a new review, not an automatic claim that this dated snapshot remains current.

## Controls and university grouping

Facets and Earth now have separate Controls tabs. Facets contains torus cell selection, Multi select and Rays. Earth contains geographic places, layers and imports. Switching to Facets returns from the satellite view to the torus.

One Universities and education layer replaces the old geographic and treaty display categories. It retains all 26,103 active ROR education organisations and their 26,167 localities. The empty Timor-Leste display category was removed, not the six actual Timor-Leste records. Country and evidence filters remain in the university directory. Historical source groupings are archived for traceability, and older institution links still resolve to the unified layer.
