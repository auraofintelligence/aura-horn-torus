'use strict';

// Dependency-free regression guard for the separate torus and Earth controls.
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert/strict');

const html = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8').replace(/\r\n/g, '\n');
const markup = html.replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, '');
const nodes = [];
const stack = [];
const voidTags = new Set('area base br col embed hr img input link meta param source track wbr'.split(' '));

// Walk actual nesting, rather than relying on where an id occurs in the file.
for (const match of markup.matchAll(/<!--[\s\S]*?-->|<\/?([a-z][\w:-]*)\b[^>]*>/gi)) {
  if (!match[1]) continue;
  const token = match[0], tag = match[1].toLowerCase();
  if (token.startsWith('</')) {
    const at = stack.map((node) => node.tag).lastIndexOf(tag);
    if (at >= 0) {
      stack[at].end = match.index;
      stack.length = at;
    }
    continue;
  }
  const attrs = {};
  for (const attr of token.matchAll(/([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')/g)) attrs[attr[1]] = attr[2] ?? attr[3];
  const node = {tag, attrs, parent:stack.at(-1), start:match.index + token.length};
  nodes.push(node);
  if (!voidTags.has(tag) && !token.endsWith('/>')) stack.push(node);
}

function one(predicate, message) {
  const found = nodes.filter(predicate);
  assert.equal(found.length, 1, message);
  return found[0];
}
function byId(id) { return one((node) => node.attrs.id === id, `expected exactly one #${id}`); }
function panelOf(node) {
  for (; node; node = node.parent) if (node.attrs['data-panel']) return node.attrs['data-panel'];
  return null;
}
const tabs = nodes.filter((node) => node.attrs['data-tab']);
const panels = nodes.filter((node) => node.attrs['data-panel']);
const keys = ['view', 'find', 'earth', 'morph', 'grid', 'drive', 'look'];
assert.deepEqual(tabs.map((node) => node.attrs['data-tab']), keys, 'seven distinct control tabs must remain');
assert.deepEqual(panels.map((node) => node.attrs['data-panel']), keys, 'each tab needs its own panel');
assert(panels.every((node) => node.parent === byId('body')), 'control panels must be siblings, not nested');
for (const [key, label] of [['find', 'Facets'], ['earth', 'Earth']]) {
  const tab = tabs.find((node) => node.attrs['data-tab'] === key);
  assert.equal(markup.slice(tab.start, tab.end).replace(/<[^>]*>/g, '').trim(), label);
}
const facetIds = ['addrshell','addrcell','sideseg','goaddr','multiBtn','clearaddr','addrnote',
  'rayseg','raysoff','rayprev','raynext','rayup','raydown','raykind','rayjump','rayjumpgo','raytrail','raynote'];
const earthIds = ['mapopen','mapstreets','mapfeatures','mapwhole','placeq','goplace','places',
  'placecategory','placefilterclear','placecard','savedpanel','savedlist','savedexport','savedclear',
  'layerlist','locationfile','layersoff','placenote','layernote'];
for (const id of facetIds) assert.equal(panelOf(byId(id)), 'find', `#${id} belongs only in Facets`);
for (const id of earthIds) assert.equal(panelOf(byId(id)), 'earth', `#${id} belongs only in Earth`);
assert.equal(byId('multiBtn').attrs['aria-pressed'], 'false');
for (const style of html.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/gi)) {
  for (const rule of style[1].matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    assert(!(/find-(?:address|places|rays)/.test(rule[1]) && /\border\s*:/.test(rule[2])),
      'CSS order must not be used to rearrange formerly mixed controls');
  }
}

// Execute the real small control functions and real click listeners. Only DOM,
// drawing and map work are stubbed; no browser or external package is needed.
function section(start, end) {
  const a = html.indexOf(start), b = html.indexOf(end, a + start.length);
  assert(a >= 0 && b > a, `missing control source boundary: ${start}`);
  return html.slice(a, b);
}
function element(node) {
  const classes = new Set((node.attrs.class || '').split(/\s+/).filter(Boolean));
  return {
    dataset:{tab:node.attrs['data-tab'], panel:node.attrs['data-panel'], side:node.attrs['data-side']},
    attrs:{...node.attrs}, listeners:{}, scrollTop:0, textContent:'',
    classList:{contains:(key) => classes.has(key), add:(key) => classes.add(key), remove:(key) => classes.delete(key),
      toggle(key, on) { if (on === undefined) on = !classes.has(key); if (on) classes.add(key); else classes.delete(key); return on; }},
    setAttribute(key, value) { this.attrs[key] = value; },
    addEventListener(event, handler) { (this.listeners[event] ||= []).push(handler); },
    click() { for (const handler of this.listeners.click || []) handler.call(this); }
  };
}
const elements = new Map(nodes.map((node) => [node, element(node)]));
const id = (name) => elements.get(byId(name));
const tabElements = tabs.map((node) => elements.get(node));
const panelElements = panels.map((node) => elements.get(node));
const sideElements = nodes.filter((node) => node.attrs['data-side']).map((node) => elements.get(node));
const sandbox = {
  document:{getElementById:id, querySelector:(selector) => {
    assert.equal(selector, '#tabs .tab.on');
    return tabElements.find((node) => node.classList.contains('on'));
  }, querySelectorAll:(selector) => {
    const options = {'#tabs .tab':tabElements, '.panel':panelElements, '#sideseg button':sideElements};
    assert(Object.hasOwn(options, selector), `unexpected selector ${selector}`);
    return options[selector];
  }},
  P:{master:1, rows:12, cols:24, shellsMode:'single', aura:true, rays:'off'},
  sphereMesh:{visible:true}, earthMapActive:false, shells:[], sel:null, selMore:[], multi:false,
  syncRail(){}, sync(){}, styleAll(){}, drawOne(){}, clearSelDraw(){}, updateSelNote(){}, rebuildRayLines(){},
  selectedPlaceContext(){ return null; }, locationName(point){ return point.name; },
  setSheetOpen(open){ sandbox.sheetOpen = open; }, setTimeout(callback){ callback(); },
  setEarthMapActive(on){ sandbox.earthMapActive = on; }
};
vm.createContext(sandbox);
const source = [
  section('function switchTab(name){', '\nvar sheet = '),
  section('function setSphere(on){', '\n/* chakra rail:'),
  section("document.getElementById('railSphere').addEventListener", '\nfunction setAura('),
  section('function setAura(on){', '\nfunction setWire('),
  section('function toggleHornTorus(){', "\ndocument.getElementById('mapstreets')"),
  section('function openPlaceControls(target){', '\nfunction focusPlace('),
  section('function sameCell(a, b){', '\nfunction updateSelNote('),
  section("document.getElementById('multiBtn').addEventListener", '\n\nrenderLocationLayerControls();')
].join('\n');
new vm.Script(source, {filename:'index.html control handlers'}).runInContext(sandbox);
function active(key) {
  assert.deepEqual(tabElements.filter((node) => node.classList.contains('on')).map((node) => node.dataset.tab), [key]);
  assert.deepEqual(panelElements.filter((node) => node.classList.contains('act')).map((node) => node.dataset.panel), [key]);
}
function clickTab(key) { tabElements.find((node) => node.dataset.tab === key).click(); }
for (const entry of ['mapopen','sphere','railSphere']) {
  sandbox.setSphere(false);
  sandbox.switchTab('view');
  id(entry).click();
  active('earth');
  assert.equal(sandbox.earthMapActive, true, `${entry} must activate Earth`);
}
id('body').scrollTop = 900;
clickTab('find');
active('find');
assert.equal(sandbox.earthMapActive, false);
assert.equal(sandbox.P.aura, true);
assert.equal(id('body').scrollTop, 0, 'changing tabs must reveal the top controls');
id('body').scrollTop = 100;
sandbox.switchTab('find');
assert.equal(id('body').scrollTop, 100, 'reselecting a facet must not reset panel scrolling');
for (const entry of ['mapback','auraBtn','railAura']) {
  clickTab('earth');
  assert.equal(sandbox.earthMapActive, true);
  id(entry).click();
  active('find');
  assert.equal(sandbox.earthMapActive, false, `${entry} must return to the torus`);
}
sandbox.openPlaceControls();
active('earth');
assert.equal(sandbox.sheetOpen, true, 'place selection must reveal Earth controls');
id('multiBtn').click();
assert.equal(sandbox.multi, true);
assert.equal(id('multiBtn').attrs['aria-pressed'], 'true');
sandbox.setSphere(true);
sandbox.setSel(3, 1, false);
active('find');
assert.equal(sandbox.earthMapActive, false, 'facet selection must return to the torus');
sandbox.setSel(3, 2, false);
assert.equal(sandbox.multiCount(), 2, 'Multi select must keep the previous facet');
sandbox.setSel(3, 2, false);
assert.equal(sandbox.multiCount(), 1, 'tapping a selected facet must remove it');
sandbox.setSel(3, 3, true);
assert.equal(sandbox.multiCount(), 2);
id('multiBtn').click();
assert.equal(sandbox.multi, false);
assert.equal(id('multiBtn').attrs['aria-pressed'], 'false');
assert.equal(sandbox.selMore.length, 0, 'turning Multi select off must clear the additional facets');
for (const key of ['view','morph','grid','drive','look']) { clickTab(key); active(key); }

console.log('CONTROL_TABS_OK tabs=7 facets=separate earth=separate multi-select=working routes=verified');
