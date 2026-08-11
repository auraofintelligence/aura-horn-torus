(function (root) {
  'use strict';

  var IMAGERY_SOURCE_ID = 'aura-satellite-imagery';
  var REFERENCE_SOURCE_ID = 'aura-reference-features';
  var IMAGERY_LAYER_ID = 'aura-satellite-imagery';
  var LIBERTY_SOURCE_ID = 'openmaptiles';

  var IMAGERY_PROVIDER = {
    id: 'eoxcloudless-2025',
    name: 'EOxCloudless 2025',
    role: 'borderless satellite mosaic base',
    serviceUrl: 'https://tiles.maps.eox.at/wmts/',
    capabilitiesUrl: 'https://tiles.maps.eox.at/wmts/1.0.0/WMTSCapabilities.xml',
    tileUrl: 'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2025_3857/default/g/{z}/{y}/{x}.jpg',
    sourceInfoUrl: 'https://cloudless.eox.at/documentation/usage',
    itemUrl: 'https://cloudless.eox.at/products/viewing',
    attributionText: 'EOxCloudless https://cloudless.eox.at by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2025)',
    attribution: 'EOxCloudless <a href="https://cloudless.eox.at" target="_blank" rel="noopener noreferrer">https://cloudless.eox.at</a> by <a href="https://eox.at" target="_blank" rel="noopener noreferrer">EOX IT Services GmbH</a> (Contains modified Copernicus Sentinel data 2025)',
    source: {
      type: 'raster',
      tiles: [
        'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2025_3857/default/g/{z}/{y}/{x}.jpg'
      ],
      tileSize: 256,
      minzoom: 0,
      maxzoom: 14,
      attribution: 'EOxCloudless <a href="https://cloudless.eox.at" target="_blank" rel="noopener noreferrer">https://cloudless.eox.at</a> by <a href="https://eox.at" target="_blank" rel="noopener noreferrer">EOX IT Services GmbH</a> (Contains modified Copernicus Sentinel data 2025)'
    },
    licence: {
      name: 'Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International',
      identifier: 'CC BY-NC-SA 4.0',
      summaryUrl: 'https://cloudless.eox.at/license-non-commercial',
      termsUrl: 'https://creativecommons.org/licenses/by-nc-sa/4.0/',
      notes: [
        'The 2025 WMTS imagery is available without an API key for non-commercial use.',
        'Attribution must be legible, linked and displayed close to the imagery.',
        'Adapted material must be shared under the same licence; commercial use requires a separate EOX licence.'
      ]
    }
  };

  var REFERENCE_PROVIDER = {
    id: 'openfreemap-liberty',
    name: 'OpenFreeMap Liberty',
    role: 'optional streets and local features',
    styleUrl: 'https://tiles.openfreemap.org/styles/liberty',
    vectorSourceUrl: 'https://tiles.openfreemap.org/planet',
    glyphsUrl: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
    spriteUrl: 'https://tiles.openfreemap.org/sprites/ofm_f384/ofm',
    attribution: '<a href="https://openfreemap.org" target="_blank">OpenFreeMap</a> <a href="https://www.openmaptiles.org/" target="_blank">&copy; OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>',
    source: {
      type: 'vector',
      url: 'https://tiles.openfreemap.org/planet',
      attribution: '<a href="https://openfreemap.org" target="_blank">OpenFreeMap</a> <a href="https://www.openmaptiles.org/" target="_blank">&copy; OpenMapTiles</a> Data from <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>'
    },
    licence: {
      providerProject: 'MIT',
      mapData: 'OpenStreetMap data under ODbL',
      quickStartUrl: 'https://openfreemap.org/quick_start/',
      termsUrl: 'https://openfreemap.org/tos/',
      providerUrl: 'https://openfreemap.org/',
      openMapTilesUrl: 'https://www.openmaptiles.org/',
      openStreetMapLicenceUrl: 'https://www.openstreetmap.org/copyright',
      notes: [
        'OpenFreeMap requires attribution for its hosted map output.',
        'OpenStreetMap attribution and its ODbL link must remain visible.',
        'The public OpenFreeMap service is provided as-is and has no service-level agreement.'
      ]
    }
  };

  var GROUP_POLICY = {
    streets: {
      label: 'Streets',
      defaultVisible: false,
      allowedSourceLayers: ['transportation', 'transportation_name'],
      description: 'Road, rail, path and transport-name layers only.'
    },
    features: {
      label: 'Features',
      defaultVisible: false,
      allowedSourceLayers: [
        'place',
        'poi',
        'aerodrome',
        'aerodrome_label',
        'waterway',
        'water_name',
        'park',
        'building'
      ],
      allowedLayerTypes: ['line', 'symbol', 'circle'],
      description: 'Local names, points of interest, aerodrome labels, water lines and other restrained line, symbol or circle features. Area fills and 3D extrusions are excluded.'
    }
  };

  function hasOwn(object, key) {
    return Object.prototype.hasOwnProperty.call(object, key);
  }

  function cloneJson(value) {
    if (typeof value === 'undefined') {
      return value;
    }
    return JSON.parse(JSON.stringify(value));
  }

  function normalise(value) {
    return String(value || '').toLowerCase();
  }

  function containsFlagToken(value) {
    var key;
    var index;

    if (typeof value === 'string') {
      return /(^|[^a-z0-9])flag(?:s|pole)?([^a-z0-9]|$)/i.test(value);
    }

    if (Object.prototype.toString.call(value) === '[object Array]') {
      for (index = 0; index < value.length; index += 1) {
        if (containsFlagToken(value[index])) {
          return true;
        }
      }
      return false;
    }

    if (value && typeof value === 'object') {
      for (key in value) {
        if (hasOwn(value, key) && containsFlagToken(value[key])) {
          return true;
        }
      }
    }

    return false;
  }

  function isBoundaryId(id) {
    var value = normalise(id);
    return value.indexOf('boundary') !== -1 ||
      /(^|[-_])administrative($|[-_])/.test(value) ||
      /(^|[-_])admin[-_]?[0-9]*($|[-_])/.test(value);
  }

  function isCountryOrStateLabelId(id) {
    var value = normalise(id);
    return /(^|[-_])(?:country|state)(?:[-_]|$)/.test(value) &&
      /(?:label|name|place|capital|country|state)/.test(value);
  }

  function flagIconIsRequested(layer) {
    var layout = layer && layer.layout;
    return normalise(layer && layer.id).indexOf('flag') !== -1 ||
      Boolean(layout && containsFlagToken(layout['icon-image']));
  }

  function isFeatureSourceLayer(sourceLayer) {
    return GROUP_POLICY.features.allowedSourceLayers.indexOf(normalise(sourceLayer)) !== -1;
  }

  function isUsefulFeatureLayerType(layer) {
    return GROUP_POLICY.features.allowedLayerTypes.indexOf(normalise(layer && layer.type)) !== -1;
  }

  function isImageryObscuringFeatureFill(layer) {
    var type = normalise(layer && layer.type);
    return isFeatureSourceLayer(layer && layer['source-layer']) &&
      (type === 'fill' || type === 'fill-extrusion');
  }

  function exclusionReason(layer) {
    var sourceLayer;

    if (!layer || typeof layer !== 'object') {
      return 'invalid-layer';
    }

    sourceLayer = normalise(layer['source-layer']);
    if (sourceLayer.indexOf('boundary') !== -1) {
      return 'boundary-source-layer';
    }
    if (isBoundaryId(layer.id)) {
      return 'boundary-layer-id';
    }
    if (isCountryOrStateLabelId(layer.id)) {
      return 'country-or-state-label';
    }
    if (flagIconIsRequested(layer)) {
      return 'flag-icon';
    }
    if (isImageryObscuringFeatureFill(layer)) {
      return 'imagery-obscuring-feature-fill';
    }
    return null;
  }

  function isLocalPlaceLabel(layer) {
    var id = normalise(layer && layer.id);

    if (normalise(layer && layer['source-layer']) !== 'place') {
      return false;
    }

    if (id === 'label_other') {
      return true;
    }

    return /(^|[-_])(?:city|town|village|hamlet|suburb|neighbourhood|neighborhood|quarter|locality)(?:[-_]|$)/.test(id);
  }

  function classifyLibertyLayer(layer) {
    var sourceLayer;

    if (exclusionReason(layer)) {
      return null;
    }
    if (normalise(layer.source) !== LIBERTY_SOURCE_ID) {
      return null;
    }

    sourceLayer = normalise(layer['source-layer']);
    if (sourceLayer === 'transportation' || sourceLayer === 'transportation_name') {
      return 'streets';
    }

    if (isUsefulFeatureLayerType(layer) &&
        (isLocalPlaceLabel(layer) ||
          (sourceLayer !== 'place' && isFeatureSourceLayer(sourceLayer)))) {
      return 'features';
    }

    return null;
  }

  function applyOpacity(layer, groupName) {
    var sourceLayer = normalise(layer['source-layer']);
    var paint = layer.paint || {};

    if (groupName === 'streets') {
      if (layer.type === 'line') {
        paint['line-opacity'] = 0.46;
      } else if (layer.type === 'fill') {
        paint['fill-opacity'] = 0.12;
      } else if (layer.type === 'symbol') {
        paint['text-opacity'] = 0.78;
        paint['icon-opacity'] = 0.58;
      }
    } else if (groupName === 'features') {
      if (layer.type === 'symbol') {
        paint['text-opacity'] = 0.8;
        paint['icon-opacity'] = 0.64;
      } else if (layer.type === 'line') {
        paint['line-opacity'] = sourceLayer === 'waterway' ? 0.48 : 0.36;
      } else if (layer.type === 'circle') {
        paint['circle-opacity'] = 0.62;
        paint['circle-stroke-opacity'] = 0.72;
      }
    }

    layer.paint = paint;
    return layer;
  }

  function adaptLibertyLayer(layer, options) {
    var groupName = classifyLibertyLayer(layer);
    var adapted;
    var metadata;
    var referenceSourceId;

    if (!groupName) {
      return null;
    }

    options = options || {};
    referenceSourceId = options.referenceSourceId || REFERENCE_SOURCE_ID;
    adapted = cloneJson(layer);
    adapted.id = 'aura-' + groupName + '-' + String(layer.id || 'layer');
    adapted.source = referenceSourceId;
    adapted.layout = adapted.layout || {};
    adapted.layout.visibility = 'none';

    metadata = adapted.metadata || {};
    metadata['aura:group'] = groupName;
    metadata['aura:original-layer-id'] = String(layer.id || '');
    metadata['aura:default-visible'] = false;
    adapted.metadata = metadata;

    return applyOpacity(adapted, groupName);
  }

  function adaptLibertyStyle(style, options) {
    var layers = style && style.layers;
    var result = {
      streets: [],
      features: [],
      excluded: [],
      ignored: []
    };
    var index;
    var layer;
    var reason;
    var adapted;

    if (Object.prototype.toString.call(layers) !== '[object Array]') {
      return result;
    }

    for (index = 0; index < layers.length; index += 1) {
      layer = layers[index];
      reason = exclusionReason(layer);

      if (reason) {
        result.excluded.push({
          id: String(layer && layer.id || ''),
          reason: reason
        });
        continue;
      }

      adapted = adaptLibertyLayer(layer, options);
      if (adapted) {
        result[adapted.metadata['aura:group']].push(adapted);
      } else {
        result.ignored.push(String(layer && layer.id || ''));
      }
    }

    return result;
  }

  function createSatelliteStyle(options) {
    var sources = {};
    var imagerySourceId;

    options = options || {};
    imagerySourceId = options.imagerySourceId || IMAGERY_SOURCE_ID;
    sources[imagerySourceId] = cloneJson(IMAGERY_PROVIDER.source);

    return {
      version: 8,
      name: 'Aura borderless satellite',
      sources: sources,
      layers: [
        {
          id: IMAGERY_LAYER_ID,
          type: 'raster',
          source: imagerySourceId,
          minzoom: 0,
          maxzoom: 24
        }
      ],
      metadata: {
        'aura:borders': false,
        'aura:flags': false,
        'aura:streets-default-visible': false,
        'aura:features-default-visible': false
      }
    };
  }

  function buildStyle(libertyStyle, options) {
    var style = createSatelliteStyle(options);
    var groups = adaptLibertyStyle(libertyStyle, options);
    var referenceSourceId;
    var index;

    options = options || {};
    referenceSourceId = options.referenceSourceId || REFERENCE_SOURCE_ID;
    style.sources[referenceSourceId] = cloneJson(REFERENCE_PROVIDER.source);
    style.glyphs = REFERENCE_PROVIDER.glyphsUrl;
    style.sprite = REFERENCE_PROVIDER.spriteUrl;

    for (index = 0; index < groups.streets.length; index += 1) {
      style.layers.push(groups.streets[index]);
    }
    for (index = 0; index < groups.features.length; index += 1) {
      style.layers.push(groups.features[index]);
    }

    style.metadata['aura:excluded-liberty-layers'] = groups.excluded;
    style.metadata['aura:ignored-liberty-layer-ids'] = groups.ignored;
    return style;
  }

  function groupLayerIds(style, groupName) {
    var layers = style && style.layers;
    var ids = [];
    var index;
    var metadata;

    if (!hasOwn(GROUP_POLICY, groupName) ||
        Object.prototype.toString.call(layers) !== '[object Array]') {
      return ids;
    }

    for (index = 0; index < layers.length; index += 1) {
      metadata = layers[index].metadata || {};
      if (metadata['aura:group'] === groupName) {
        ids.push(layers[index].id);
      }
    }
    return ids;
  }

  function setGroupVisibility(map, groupName, visible) {
    var style;
    var ids;
    var index;
    var visibility = visible ? 'visible' : 'none';

    if (!map || typeof map.getStyle !== 'function' ||
        typeof map.setLayoutProperty !== 'function' ||
        !hasOwn(GROUP_POLICY, groupName)) {
      return false;
    }

    style = map.getStyle();
    ids = groupLayerIds(style, groupName);
    for (index = 0; index < ids.length; index += 1) {
      if (typeof map.getLayer !== 'function' || map.getLayer(ids[index])) {
        map.setLayoutProperty(ids[index], 'visibility', visibility);
      }
    }
    return true;
  }

  root.AURA_EARTH_MAP_CONFIG = {
    version: 1,
    engine: 'MapLibre GL JS',
    intent: 'Satellite first; no political borders, country or state labels, or flag icons.',
    sourceIds: {
      imagery: IMAGERY_SOURCE_ID,
      reference: REFERENCE_SOURCE_ID
    },
    layerIds: {
      imagery: IMAGERY_LAYER_ID
    },
    providers: {
      imagery: IMAGERY_PROVIDER,
      reference: REFERENCE_PROVIDER
    },
    groups: GROUP_POLICY,
    permanentExclusions: {
      boundarySourceLayers: true,
      boundaryLayerIds: true,
      countryAndStateLabels: true,
      flagIcons: true,
      imageryObscuringFeatureFills: true
    },
    exclusionReason: exclusionReason,
    classifyLibertyLayer: classifyLibertyLayer,
    adaptLibertyLayer: adaptLibertyLayer,
    adaptLibertyStyle: adaptLibertyStyle,
    createSatelliteStyle: createSatelliteStyle,
    buildStyle: buildStyle,
    groupLayerIds: groupLayerIds,
    setGroupVisibility: setGroupVisibility
  };
}(window));
