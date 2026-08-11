'use strict';

var fs = require('fs');
var path = require('path');
var vm = require('vm');

var repositoryRoot = path.resolve(__dirname, '..');
var configPath = path.join(repositoryRoot, 'data', 'map-style.js');

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

function loadConfig(source) {
  var sandbox = { window: {} };
  vm.createContext(sandbox);
  new vm.Script(source, { filename: configPath }).runInContext(sandbox);
  return sandbox.window.AURA_EARTH_MAP_CONFIG;
}

function originalLayerIds(layers) {
  return layers.map(function (layer) {
    return layer.metadata && layer.metadata['aura:original-layer-id'];
  });
}

function allHidden(layers) {
  return layers.every(function (layer) {
    return layer.layout && layer.layout.visibility === 'none';
  });
}

function run() {
  var source = fs.readFileSync(configPath, 'utf8');
  var config = loadConfig(source);
  var fixture = {
    version: 8,
    sources: {
      openmaptiles: {
        type: 'vector',
        url: 'https://fixture.invalid/tiles.json'
      }
    },
    layers: [
      {
        id: 'road_fixture',
        type: 'line',
        source: 'openmaptiles',
        'source-layer': 'transportation'
      },
      {
        id: 'road_name_fixture',
        type: 'symbol',
        source: 'openmaptiles',
        'source-layer': 'transportation_name',
        layout: { 'text-field': ['get', 'name'] }
      },
      {
        id: 'label_city',
        type: 'symbol',
        source: 'openmaptiles',
        'source-layer': 'place',
        layout: { 'text-field': ['get', 'name'] }
      },
      {
        id: 'label_village',
        type: 'symbol',
        source: 'openmaptiles',
        'source-layer': 'place',
        layout: { 'text-field': ['get', 'name'] }
      },
      {
        id: 'poi_fixture',
        type: 'symbol',
        source: 'openmaptiles',
        'source-layer': 'poi',
        layout: { 'icon-image': 'museum_11' }
      },
      {
        id: 'airport_fixture',
        type: 'symbol',
        source: 'openmaptiles',
        'source-layer': 'aerodrome_label',
        layout: { 'icon-image': 'airport_11' }
      },
      {
        id: 'waterway_fixture',
        type: 'line',
        source: 'openmaptiles',
        'source-layer': 'waterway'
      },
      {
        id: 'water_name_fixture',
        type: 'symbol',
        source: 'openmaptiles',
        'source-layer': 'water_name',
        layout: { 'text-field': ['get', 'name'] }
      },
      {
        id: 'park_outline_fixture',
        type: 'line',
        source: 'openmaptiles',
        'source-layer': 'park'
      },
      {
        id: 'poi_circle_fixture',
        type: 'circle',
        source: 'openmaptiles',
        'source-layer': 'poi'
      },
      {
        id: 'park_fill_fixture',
        type: 'fill',
        source: 'openmaptiles',
        'source-layer': 'park'
      },
      {
        id: 'building_fill_fixture',
        type: 'fill',
        source: 'openmaptiles',
        'source-layer': 'building'
      },
      {
        id: 'building_extrusion_fixture',
        type: 'fill-extrusion',
        source: 'openmaptiles',
        'source-layer': 'building'
      },
      {
        id: 'boundary_source_fixture',
        type: 'line',
        source: 'openmaptiles',
        'source-layer': 'boundary'
      },
      {
        id: 'boundary_id_fixture',
        type: 'line',
        source: 'openmaptiles',
        'source-layer': 'waterway'
      },
      {
        id: 'label_country_fixture',
        type: 'symbol',
        source: 'openmaptiles',
        'source-layer': 'place',
        layout: { 'text-field': ['get', 'name'] }
      },
      {
        id: 'label_state_fixture',
        type: 'symbol',
        source: 'openmaptiles',
        'source-layer': 'place',
        layout: { 'text-field': ['get', 'name'] }
      },
      {
        id: 'flag_icon_fixture',
        type: 'symbol',
        source: 'openmaptiles',
        'source-layer': 'poi',
        layout: { 'icon-image': 'flag_11' }
      }
    ]
  };
  var satellite;
  var built;
  var imagery;
  var streets;
  var features;
  var includedOriginalIds;
  var prohibitedIds;
  var provider;
  var licence;

  assert(config && typeof config === 'object', 'AURA_EARTH_MAP_CONFIG was not exposed');

  satellite = config.createSatelliteStyle();
  assert(Object.keys(satellite.sources).length === 1, 'satellite style must have exactly one source');
  assert(hasOwn(satellite.sources, config.sourceIds.imagery), 'satellite style is missing imagery');
  assert(!hasOwn(satellite.sources, config.sourceIds.reference), 'satellite style must not contain the reference source');
  assert(!hasOwn(satellite, 'glyphs'), 'satellite style must not contain glyphs');
  assert(!hasOwn(satellite, 'sprite'), 'satellite style must not contain a sprite');
  assert(satellite.layers.length === 1 && satellite.layers[0].type === 'raster', 'satellite style must contain only its raster layer');

  built = config.buildStyle(fixture);
  assert(Object.keys(built.sources).length === 2, 'built style must have imagery and reference sources');
  assert(hasOwn(built.sources, config.sourceIds.imagery), 'built style is missing imagery');
  assert(hasOwn(built.sources, config.sourceIds.reference), 'built style is missing its reference source');
  assert(built.glyphs === config.providers.reference.glyphsUrl, 'built style has the wrong glyph source');
  assert(built.sprite === config.providers.reference.spriteUrl, 'built style has the wrong sprite source');

  streets = built.layers.filter(function (layer) {
    return layer.metadata && layer.metadata['aura:group'] === 'streets';
  });
  features = built.layers.filter(function (layer) {
    return layer.metadata && layer.metadata['aura:group'] === 'features';
  });
  assert(streets.length === 2, 'expected two allowed street layers');
  assert(features.length === 8, 'expected eight allowed feature layers');
  assert(allHidden(streets), 'street layers must be hidden by default');
  assert(allHidden(features), 'feature layers must be hidden by default');
  assert(features.every(function (layer) {
    return layer.type === 'line' || layer.type === 'symbol' || layer.type === 'circle';
  }), 'features must contain only line, symbol or circle layers');

  includedOriginalIds = originalLayerIds(streets.concat(features));
  prohibitedIds = [
    'boundary_source_fixture',
    'boundary_id_fixture',
    'label_country_fixture',
    'label_state_fixture',
    'flag_icon_fixture',
    'park_fill_fixture',
    'building_fill_fixture',
    'building_extrusion_fixture'
  ];
  prohibitedIds.forEach(function (id) {
    assert(includedOriginalIds.indexOf(id) === -1, 'prohibited fixture was included: ' + id);
  });
  assert(built.metadata['aura:excluded-liberty-layers'].length === prohibitedIds.length, 'not every prohibited fixture was recorded as excluded');

  provider = config.providers.imagery;
  licence = provider.licence || {};
  imagery = satellite.sources[config.sourceIds.imagery];
  assert(provider.id === 'eoxcloudless-2025', 'imagery provider must be EOxCloudless 2025');
  assert(/^https:\/\/tiles\.maps\.eox\.at\//.test(provider.tileUrl), 'EOxCloudless tile template must use HTTPS');
  assert(provider.tileUrl.indexOf('s2cloudless-2025_3857') !== -1, 'tile template must use the 2025 Web Mercator layer');
  assert(imagery.tiles.length === 1 && imagery.tiles[0] === provider.tileUrl, 'raster source must use the declared EOxCloudless tile template');
  assert(licence.identifier === 'CC BY-NC-SA 4.0', 'imagery licence identifier is missing or incorrect');
  assert(/^https:\/\//.test(licence.summaryUrl) && /^https:\/\//.test(licence.termsUrl), 'imagery licence links must use HTTPS');
  assert(provider.attributionText.indexOf('EOxCloudless https://cloudless.eox.at') !== -1, 'required EOxCloudless attribution is missing');
  assert(provider.attributionText.indexOf('modified Copernicus Sentinel data 2025') !== -1, '2025 Copernicus attribution is missing');
  assert(!/esri|arcgis/i.test(source), 'Esri or ArcGIS remnant found in map-style.js');

  console.log(
    'MAP_STYLE_OK satellite=imagery-only streets=' + streets.length +
    ' features=' + features.length + ' prohibited=' + prohibitedIds.length +
    ' provider=' + provider.id + ' licence=' + licence.identifier
  );
}

try {
  run();
} catch (error) {
  console.error('MAP_STYLE_FAIL ' + error.message);
  process.exitCode = 1;
}
