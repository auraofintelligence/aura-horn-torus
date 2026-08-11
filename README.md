# Aura Horn Torus

An interactive demo of a horn torus lattice: a 12 × 24 grid of addressable cells that morphs between a flat unrolled sheet and a closed torus, stacked seven shells deep inside a geosphere.

Live page: https://auraofintelligence.github.io/aura-horn-torus/

- [index.html](index.html) is the demo. One self-contained page, no build step.
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
- A geosphere around the outside carrying an Earth map, so maps of self and place sit in the one navigable space. The aura layers toggle on and off in front of it.
- Independent Earth location layers with colour, record count, source, age/status and coordinate-quality labels. Large layers use one WebGL point cloud each rather than thousands of separate marker objects.
- The full fold: flat sheets curl into tubes, close into rings, and pinch into horn tori, live on sliders.
- A build guide that opens the page: one matrix, fold it closed, two faces, the zero point, seven layers, on the body, in the world, then free exploration.

## Running it

Open `index.html` in a browser, or use the live page above. The page loads three.js and the Earth texture from CDNs. Permanent location data stays in this repo and large layers are loaded only on demand.

## Location layers

Open **Controls → Find → Earth**. The starter places are visible first; all larger or older lists begin switched off.

The catalogue currently covers:

- the 34 original orientation places;
- 322 points from the legacy **1st Step to Aura Alliance** KML;
- 139 points recovered from the **North Stradbroke Island** My Maps NetworkLink, clearly marked as a legacy reference rather than current or culturally authoritative truth;
- 125 **Australian missions abroad**, checked on 19 May 2026 and shown at approximate city level;
- 44,691 **world cities** from an old, version-undated local SimpleMaps copy, with [SimpleMaps attribution](https://simplemaps.com/data/world-cities) under CC BY 4.0; and
- 19,636 minimal **Aura Affinity** discovery points. Every record is unverified; copied reviews, phone numbers and other contact material are deliberately excluded. Third-party reuse terms remain **TO BE CONFIRMED before public publication**.

Two supplied lists are recorded but not faked onto the globe: `world-universities.csv` has 9,363 rows and no coordinates, while the 141 foreign missions in Australia still need verified point coordinates. Their layer rows explain what is missing.

### Import another list in the browser

Choose **Import CSV, KML or KMZ** in the Earth controls. The file is read in that browser tab only and is not uploaded or saved.

- CSV needs a latitude column (`lat` or `latitude`) and a longitude column (`lng`, `lon` or `longitude`). A `name`, `city`, `title`, `place`, `university` or `institution` column becomes the marker name.
- KML placemarks are mapped directly. Non-point geometry is represented by a centre point and labelled that way.
- KMZ is unpacked in a modern browser. A KMZ containing only a Google My Maps `NetworkLink` is reported as a pointer rather than pretending it contains locations.

KML/My Maps icon URLs are retained in the compact point records even though the first globe renderer uses one clear colour per layer.

Imported points remain temporary. Permanent public layers should be source-reviewed, dated, converted with the builder and checked before publication.

## One shell of a wider design

This demo carries no claim beyond what it renders. The wider design it belongs to would map a person's own information into addressable space across nested shells, with the interior faces private to the person and the exterior faces shared on their terms.

## Provenance

The interaction pattern was sparked by Interactive Photo Cube by Amit Asulin on brik.space. The geometry, the morph and all code here are original. The horn torus mind-mapping design predates that reference by roughly a decade.

Built by Luke Hayes with Claude. Licence: [Aura of Intelligence Public Source Licence](LICENCE.md).
