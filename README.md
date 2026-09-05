# Aura Horn Torus

<!-- github-organisation:start -->

## Project links and history

- First substantive build: 3 August 2026.
- GitHub repository: [aura-horn-torus](https://github.com/auraofintelligence/aura-horn-torus).
- Public site: [visit the public site](https://auraofintelligence.github.io/aura-horn-torus/).

## Related public projects

Each link below reflects an evidenced family, lineage or direct connection. This project has 8 relevant public connections.

### Aura interface, geometry and capture architecture

- [aura-components](https://github.com/auraofintelligence/aura-components) - [public page](https://auraofintelligence.github.io/aura-components/) - later build; aura-components is earlier, ordered build lineage, shared technical architecture.
- [aura-data-mapping](https://github.com/auraofintelligence/aura-data-mapping) - [public page](https://auraofintelligence.github.io/aura-data-mapping/) - later build; aura-data-mapping is earlier, explicit cross-reference, ordered build lineage, shared technical architecture.
- [aura-of-intelligence-web-app](https://github.com/auraofintelligence/aura-of-intelligence-web-app) - explicit cross-reference, shared technical architecture.
- [aura-scan-pipeline](https://github.com/auraofintelligence/aura-scan-pipeline) - [public page](https://auraofintelligence.github.io/aura-scan-pipeline/) - explicit cross-reference, shared technical architecture.
- [aura-spatial-perception](https://github.com/auraofintelligence/aura-spatial-perception) - [public page](https://auraofintelligence.github.io/aura-spatial-perception/) - earlier build; aura-spatial-perception is later, explicit cross-reference, ordered build lineage, shared technical architecture.
- [aura-toy](https://github.com/auraofintelligence/aura-toy) - [public page](https://auraofintelligence.github.io/aura-toy/) - later build; aura-toy is earlier, ordered build lineage, shared technical architecture.
- [new-tori](https://github.com/auraofintelligence/new-tori) - [public page](https://auraofintelligence.github.io/new-tori/) - later build; new-tori is earlier, ordered build lineage, shared technical architecture.

### Direct and other supported connections

- [aura-affinity](https://github.com/auraofintelligence/aura-affinity) - [public page](https://auraofintelligence.github.io/aura-affinity/) - explicit cross-reference.

<!-- github-organisation:end -->

An interactive demo of a horn torus lattice: a 12 × 24 grid of addressable cells that morphs between a flat unrolled sheet and a closed torus, stacked seven shells deep, with a separate streamed Satellite Earth for organising places.

Live page: https://auraofintelligence.github.io/aura-horn-torus/

- [index.html](index.html) is the demo. One self-contained page, no build step.
- [universities.html](universities.html) is the worldwide education directory: find institutions, sourced peak-body memberships and shared identifiers, then show a selected institution on Earth.
- [icons.html](icons.html) is the icon library: 173 icons cut out of the original prototype screens, each named, described, and given a generation prompt. Set a style line once and every prompt comes out in that hand.
- [tables.html](tables.html) renders the register tables: the Vert and Face vector map per torus, and the shared ray directions.
- [geometry.html](geometry.html) explains the maths in plain words.
- [about.html](about.html) covers what it is, provenance and licence.
- [data/location-layers.js](data/location-layers.js) is the source-labelled catalogue for Earth overlays. The larger point sets in `data/layers/` load only when somebody switches them on.
- [tools/build_location_layers.py](tools/build_location_layers.py) rebuilds the permanent snapshots; [tools/check_location_layers.py](tools/check_location_layers.py) checks their counts, coordinates and public-safety boundaries.

## What it shows

- Seven nested horn tori, one per chakra colour, red innermost through violet, all sharing one zero point at the centre.
- Every cell has an address: a shell, a number from 1 to 288, and a face letter. O is the exterior observer face, treated as a public permissioned register. I is the interior personal face, treated as a private encrypted register. Tap any cell to read its address, or type one in and the camera swings to it.
- An Arrange slider that moves the seven shells between two layouts: nested on a single centre, or spread up a body column, red at the base and violet at the crown.
- A dedicated streamed satellite Earth beside the Horn Torus. It requests only the map tiles needed for the current view, so close zoom is no longer limited by one stretched 4K or 8K globe image.
- A borderless, flagless satellite base with independent **Streets** and **Features & names** switches. Both optional overlays begin off.
- Independent Earth location layers with colour, record count, source, age/status and coordinate-quality labels. Large layers use clustered WebGL map layers rather than thousands of separate marker objects.
- A selected-place card with locality, type, dataset status, coordinate accuracy, source and closer/regional camera controls. Places can be filtered by type, saved privately in the browser and downloaded as a CSV shortlist.
- The full fold: flat sheets curl into tubes, close into rings, and pinch into horn tori, live on sliders.
- An optional build guide: one matrix, fold it closed, two faces, the zero point, seven layers, on the body, in the world, then free exploration.

## Running it

Open `index.html` in a browser, or use the live page above. The university directory needs HTTPS or a local HTTP server because it loads JSON on demand. For local use, run `python -m http.server 8000` in this repository and open `http://localhost:8000/universities.html`. The page loads Three.js for the Horn Torus and loads MapLibre only when somebody opens Satellite Earth. Permanent location data stays in this repo, and large place layers are loaded only when switched on.

The satellite base is the 2025 [EOxCloudless](https://cloudless.eox.at/) global Sentinel-2 mosaic by EOX IT Services GmbH, containing modified Copernicus Sentinel data. Its hosted WMTS is available for non-commercial use under [CC BY-NC-SA 4.0](https://cloudless.eox.at/license-non-commercial) with visible attribution. It has a native 10 metre resolution: substantially more useful than a single world texture, but not building- or campus-level evidence. Streets and useful local labels come from [OpenFreeMap](https://openfreemap.org/) only after their switches are turned on, with OpenMapTiles and OpenStreetMap attribution. Political boundaries, country/state labels and flag icons are removed from the approved overlay style.

Opening Satellite Earth sends ordinary tile requests, including the visitor's IP address, referrer and the requested map area, to the active map providers. The site sends no browser geolocation, account details or saved-place information to them. There is no map analytics code; saved places remain in that browser unless the visitor downloads a CSV.

## Location layers

Open **Controls → Find → Earth**. The starter places are visible first; all larger or older lists begin switched off. Select a coloured point or search for a name to open its information card. **Zoom closer** can be pressed more than once for a local view; **Regional view** restores surrounding context.

The type filter works across whichever layers are visible. **Save place** creates a private shortlist in that browser only, and **Download CSV** makes the shortlist portable without uploading it anywhere.

The catalogue currently covers:

- the 34 original orientation places;
- 322 points from the legacy **1st Step to Aura Alliance** KML;
- 139 points recovered from the **North Stradbroke Island** My Maps NetworkLink, clearly marked as a legacy reference rather than current or culturally authoritative truth;
- 125 **Australian missions abroad**, checked on 19 May 2026 and shown at approximate city level;
- 44,691 **world cities** from an old, version-undated local SimpleMaps copy, with [SimpleMaps attribution](https://simplemaps.com/data/world-cities) under CC BY 4.0; and
- 5,133 university-index organisations matched to active identities in the August 2026 ROR snapshot: 64 across [UN M49 Oceania](https://unstats.un.org/unsd/methodology/m49/), 2,951 in non-Oceania countries in the 11 August 2026 [Australian free trade agreement](https://www.dfat.gov.au/trade/agreements/in-force) scope, 502 in EU member states in the [Australia-EU Framework Agreement](https://www.dfat.gov.au/geo/europe/european-union/australia-european-union-eu-framework-agreement) scope, and 1,616 across the remaining world backlog;
- another 20,970 active ROR education organisations at 21,034 recorded localities, kept in an independent wider registry layer; and
- 19,636 minimal **Aura Affinity** discovery points. Every record is unverified; copied reviews, phone numbers and other contact material are deliberately excluded. Third-party reuse terms remain **TO BE CONFIRMED**, so this stays an off-by-default reference layer rather than verified business information.

The education points use [ROR v2.11](https://zenodo.org/records/21773148), dated 3 August 2026, names and ROR links with GeoNames locality centroids. They are useful for finding an institution's city or region, but they are **not campus or building pins**. The historical layers trace accepted identities from the 2015 index. The wider registry independently includes universities, colleges and other education bodies. Neither establishes recognition, a complete list of every university on Earth, or participation in a treaty or agreement.

The release gate holds uncertain identities rather than guessing. All 9,363 historical source rows have now had an identity-matching pass: 5,141 accepted rows represent 5,133 unique organisations after eight duplicate listings are merged. Another 4,222 rows remain held for review, inactive history or no match. Timor-Leste has no row in the old list, so its historical treaty-scope layer remains empty; separate ROR education records can be explored through the directory. ROR metadata is CC0 and its GeoNames locality data is CC BY 4.0; the historical list declares no licence and is used only as a discovery index, without republishing its old website list.

The [university directory](universities.html) brings together all 26,103 registry education organisations across 224 country and territory codes. It supports country, sourced membership, identifier and organisational-relationship filters, downloadable results and direct links to the globe. The initial evidence sample has 15 memberships across 13 institutions in Universities Australia, PIURN and APRU. GAJRA Earth applicability, contact and membership remain unassessed. See the [completion report](docs/location-completion-2026-09-05.md), [applicability research](docs/university-applicability.md) and [complementary location-layer suggestions](docs/location-layer-directions.md).

The other supplied list that remains deliberately unmapped is the 141 foreign missions in Australia, because their addresses still need verified point coordinates. Its layer row explains what is missing.

### Import another list in the browser

Choose **Import CSV, KML or KMZ** in the Earth controls. The file is read in that browser tab only and is not uploaded or saved.

- CSV needs a latitude column (`lat` or `latitude`) and a longitude column (`lng`, `lon` or `longitude`). A `name`, `city`, `title`, `place`, `university` or `institution` column becomes the marker name. Recognised type, locality, address, population and website fields appear in the selected-place information.
- KML placemarks are mapped directly. Non-point geometry is represented by a centre point and labelled that way.
- KMZ is unpacked in a modern browser. A KMZ containing only a Google My Maps `NetworkLink` is reported as a pointer rather than pretending it contains locations.

KML/My Maps icon URLs are retained in the compact point records even though the first globe renderer uses one clear colour per layer.

Imported points remain temporary. Permanent public layers should be source-reviewed, dated, converted with the builder and checked before publication.

## One shell of a wider design

This demo carries no claim beyond what it renders. The wider design it belongs to would map a person's own information into addressable space across nested shells, with the interior faces private to the person and the exterior faces shared on their terms.

## Provenance

The interaction pattern was sparked by Interactive Photo Cube by Amit Asulin on brik.space. The geometry, the morph and all code here are original. The horn torus mind-mapping design predates that reference by roughly a decade.

Built by Luke Hayes with Claude. Licence: [Aura of Intelligence Public Source Licence](LICENCE.md).
