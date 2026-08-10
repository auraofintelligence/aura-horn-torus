# Aura Horn Torus

An interactive demo of a horn torus lattice: a 12 × 24 grid of addressable cells that morphs between a flat unrolled sheet and a closed torus, stacked seven shells deep inside a geosphere.

Live page: https://auraofintelligence.github.io/aura-horn-torus/

- [index.html](index.html) is the demo. One self-contained page, no build step.
- [icons.html](icons.html) is the icon library: 173 icons cut out of the original prototype screens, each named, described, and given a generation prompt. Set a style line once and every prompt comes out in that hand.
- [tables.html](tables.html) renders the register tables: the Vert and Face vector map per torus, and the shared ray directions.
- [geometry.html](geometry.html) explains the maths in plain words.
- [about.html](about.html) covers what it is, provenance and licence.

## What it shows

- Seven nested horn tori, one per chakra colour, red innermost through violet, all sharing one zero point at the centre.
- Every cell has an address: a shell, a number from 1 to 288, and a face letter. O is the exterior observer face, treated as a public permissioned register. I is the interior personal face, treated as a private encrypted register. Tap any cell to read its address, or type one in and the camera swings to it.
- An Arrange slider that moves the seven shells between two layouts: nested on a single centre, or spread up a body column, red at the base and violet at the crown.
- A geosphere around the outside carrying an Earth map, so maps of self and place sit in the one navigable space. The aura layers toggle on and off in front of it.
- The full fold: flat sheets curl into tubes, close into rings, and pinch into horn tori, live on sliders.
- A build guide that opens the page: one matrix, fold it closed, two faces, the zero point, seven layers, on the body, in the world, then free exploration.

## Running it

Open `index.html` in a browser, or use the live page above. The page loads two things from CDNs: the three.js library and the Earth texture. Everything else is inline.

## One shell of a wider design

This demo carries no claim beyond what it renders. The wider design it belongs to would map a person's own information into addressable space across nested shells, with the interior faces private to the person and the exterior faces shared on their terms.

## Provenance

The interaction pattern was sparked by Interactive Photo Cube by Amit Asulin on brik.space. The geometry, the morph and all code here are original. The horn torus mind-mapping design predates that reference by roughly a decade.

Built by Luke Hayes with Claude. Licence: [Aura of Intelligence Public Source Licence](LICENCE.md).
