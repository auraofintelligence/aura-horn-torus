'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const manifest = fs.readFileSync(path.join(root, 'data', 'location-layers.js'), 'utf8');

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const addStart = html.indexOf('function addEarthMapLocation(');
const addEnd = html.indexOf('\nfunction syncEarthMapLocations(', addStart);
const addSource = html.slice(addStart, addEnd);
const referenceStart = html.indexOf('function ensureEarthMapReference(');
const referenceEnd = html.indexOf('\nfunction ensureEarthMap(', referenceStart);
const referenceSource = html.slice(referenceStart, referenceEnd);

assert(addStart >= 0 && addEnd > addStart, 'location-layer map function is missing');
assert(referenceStart >= 0 && referenceEnd > referenceStart, 'reference-overlay map function is missing');
assert(addSource.indexOf('existing.dataRef === data') < addSource.indexOf('locationGeoJson(data)'),
  'unchanged datasets must be rejected before GeoJSON is rebuilt');
assert(addSource.includes('existing.filterKey === filterKey'),
  'the GeoJSON cache must include the category filter');
assert(addSource.includes('maxzoom:14'), 'large point sources need a bounded worker tile index');
assert(!referenceSource.includes('setStyle('), 'optional overlays must not replace the whole map style');
assert(!referenceSource.includes('clearEarthMapLocations('),
  'optional overlays must not delete and recluster location layers');
assert(referenceSource.includes('earthMap.setGlyphs(') && referenceSource.includes('earthMap.setSprite('),
  'optional overlay assets must be installed through the map API');
assert(!referenceSource.includes('.style.stylesheet'),
  'optional overlays must not mutate MapLibre internals');
assert(html.includes('body.earth-map #sheet') && html.includes('backdrop-filter:none'),
  'Earth mode must disable expensive panel blur');

const sandbox = {window:{}};
vm.createContext(sandbox);
new vm.Script(manifest, {filename:'data/location-layers.js'}).runInContext(sandbox);
const defaultOnLayers = (sandbox.window.AURA_LOCATION_MANIFEST || [])
  .filter((layer) => layer.defaultOn)
  .map((layer) => layer.id);
assert(defaultOnLayers.length === 1 && defaultOnLayers[0] === 'starter-world',
  'only the small starter layer may load by default');

console.log('MAP_PERFORMANCE_OK geojson-cache=on overlays=incremental blur=off default=starter-world');
