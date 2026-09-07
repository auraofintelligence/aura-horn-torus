'use strict';
(function () {
  var rows = [], filtered = [], byId = new Map(), selectedId = '', currentPage = 0;
  var pageSize = 20, checkedAt = '', filterTimer, loading = false;
  var $ = function (id) { return document.getElementById(id); };

  function node(tag, text, className) {
    var element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  }
  function normalise(value) {
    return String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('en-AU');
  }
  function safeUrl(value) {
    if (typeof value !== 'string' || !/^https?:\/\//i.test(value.trim())) return null;
    try {
      var url = new URL(value);
      if (!/^https?:$/.test(url.protocol) || url.username || url.password) return null;
      return url.href;
    } catch (_) { return null; }
  }
  function sourceLink(label, value) {
    var url = safeUrl(value);
    if (!url) return null;
    var anchor = node('a', label);
    anchor.href = url;
    anchor.rel = 'noopener noreferrer';
    return anchor;
  }
  function dateLabel(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return 'Date not supplied';
    var date = new Date(value + 'T00:00:00Z');
    if (!Number.isFinite(date.getTime())) return 'Date not supplied';
    return date.toLocaleDateString('en-AU', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
  }
  function validPosition(record) {
    return typeof record.latitude === 'number' && Number.isFinite(record.latitude) && Math.abs(record.latitude) <= 90
      && typeof record.longitude === 'number' && Number.isFinite(record.longitude) && Math.abs(record.longitude) <= 180;
  }
  function statusLabel(record) { return record.status === 'mapped' ? 'On Earth' : 'Not mapped'; }
  function badge(record) { return node('span', statusLabel(record), 'badge' + (record.status === 'held' ? ' held' : '')); }
  function honoraryBadge(record) { return record.honorary ? node('span', 'Honorary', 'badge honorary') : null; }
  function setSelectionUrl(id) {
    var url = new URL(location.href);
    url.searchParams.delete('mission');
    url.hash = id ? 'mission=' + encodeURIComponent(id) : '';
    history.replaceState(null, '', url);
  }
  function emptyDetail() {
    var title = node('h2', 'Select a mission'); title.id = 'detail-title';
    $('detail').replaceChildren(title, node('p', 'See its office address, review date, sources and map status.'),
      node('p', 'Only source-backed office positions can be opened on Earth. A listing does not guarantee public access or available services.'));
  }
  function addOptions(id, field) {
    var select = $(id);
    while (select.options.length > 1) select.remove(1);
    Array.from(new Set(rows.map(function (record) { return record[field]; }).filter(Boolean)))
      .sort(function (a, b) { return a.localeCompare(b, 'en-AU'); })
      .forEach(function (value) { var option = node('option', value); option.value = value; select.appendChild(option); });
  }
  function applyFilters() {
    clearTimeout(filterTimer);
    var terms = normalise($('search').value.trim()).split(/\s+/).filter(Boolean);
    filtered = rows.filter(function (record) {
      return terms.every(function (term) { return record.searchText.includes(term); })
        && (!$('country').value || record.country === $('country').value)
        && (!$('city').value || record.city === $('city').value)
        && (!$('type').value || record.type === $('type').value)
        && (!$('honorary').value || (record.honorary ? 'yes' : 'no') === $('honorary').value)
        && (!$('status').value || record.status === $('status').value);
    });
    currentPage = 0;
    if (selectedId && !filtered.some(function (record) { return record.id === selectedId; })) {
      selectedId = ''; emptyDetail(); setSelectionUrl('');
    }
    renderResults();
  }
  function renderResults() {
    var result = $('results'); result.replaceChildren(); result.setAttribute('aria-busy', 'false');
    $('result-count').textContent = filtered.length.toLocaleString('en-AU') + (filtered.length === 1 ? ' mission' : ' missions');
    if (!filtered.length) result.appendChild(node('p', 'No records match these filters. Try another city or clear a filter.', 'empty'));
    filtered.slice(currentPage * pageSize, (currentPage + 1) * pageSize).forEach(function (record) {
      var button = node('button', undefined, 'result'); button.type = 'button';
      button.setAttribute('aria-pressed', String(record.id === selectedId));
      button.setAttribute('aria-controls', 'detail');
      button.appendChild(node('strong', record.name || record.country + ' ' + record.type));
      button.appendChild(node('span', [record.country, record.city, record.type].filter(Boolean).join(' · '), 'context'));
      button.appendChild(badge(record));
      if (record.honorary) button.appendChild(honoraryBadge(record));
      button.addEventListener('click', function () { select(record.id, true); });
      result.appendChild(button);
    });
    var pages = Math.max(1, Math.ceil(filtered.length / pageSize));
    $('page-count').textContent = filtered.length ? 'Page ' + (currentPage + 1) + ' of ' + pages : 'No results';
    $('previous').disabled = currentPage === 0;
    $('next').disabled = currentPage + 1 >= pages;
  }
  function select(id, focus) {
    var record = byId.get(id); if (!record) return;
    selectedId = id; renderResults(); renderDetail(record); setSelectionUrl(id);
    if (focus) {
      $('detail').focus({ preventScroll: true });
      if (matchMedia('(max-width:750px)').matches) $('detail').scrollIntoView({ block: 'start', behavior: matchMedia('(prefers-reduced-motion:reduce)').matches ? 'auto' : 'smooth' });
    }
  }
  function renderDetail(record) {
    var detail = $('detail'), title = node('h2', record.name || record.country + ' ' + record.type);
    title.id = 'detail-title'; detail.replaceChildren(title, badge(record));
    if (record.honorary) detail.appendChild(honoraryBadge(record));
    detail.appendChild(node('p', [record.country, record.city, record.type].filter(Boolean).join(' · ')));
    detail.appendChild(node('h3', 'Office address'));
    detail.appendChild(node('p', record.address || 'No current public office address is confirmed in this review.', 'address'));
      detail.appendChild(node('p', 'Checked ' + dateLabel(record.checkedAt || checkedAt) + '. Current DFAT directory record.', 'small'));
    if (record.reason) detail.appendChild(node('p', record.reason, 'review-reason'));
    if (record.reviewNote && record.reviewNote !== record.reason) detail.appendChild(node('p', record.reviewNote, 'small'));

    detail.appendChild(node('h3', 'Map position'));
    if (record.status === 'mapped' && validPosition(record)) {
      detail.appendChild(node('p', record.coordinateBasis || 'A source-backed office position. Check the coordinate source for its limitations.'));
      detail.appendChild(node('p', 'Latitude ' + record.latitude.toFixed(6) + ', longitude ' + record.longitude.toFixed(6) + '.', 'small'));
    } else {
      detail.appendChild(node('p', 'No verified point is shown on Earth for this record. A city-centre location has not been substituted.'));
      if (record.coordinateBasis) detail.appendChild(node('p', record.coordinateBasis, 'small'));
    }
    var actions = node('div', undefined, 'actions');
    if (record.status === 'mapped' && validPosition(record)) {
      var mapLink = node('a', 'Show on Earth', 'primary'); mapLink.href = 'index.html?mission=' + encodeURIComponent(record.id); actions.appendChild(mapLink);
    }
    var website = sourceLink('Mission website', record.website); if (website) actions.appendChild(website);
    if (actions.childElementCount) detail.appendChild(actions);

    detail.appendChild(node('h3', 'Sources'));
    var sources = node('ul', undefined, 'source-links');
    var officialSource = sourceLink('Official directory or mission source', record.sourceUrl);
    if (officialSource) {
      if (new URL(officialSource.href).hostname === 'protocol.dfat.gov.au') officialSource.textContent = 'DFAT directory source';
      var sourceItem = node('li'); sourceItem.appendChild(officialSource); sources.appendChild(sourceItem);
    }
    var sourceUrls = new Set(officialSource ? [officialSource.href] : []);
    (Array.isArray(record.sources) ? record.sources : []).forEach(function (evidence) {
      var evidenceLink = sourceLink('Additional office evidence', evidence.url);
      if (!evidenceLink || sourceUrls.has(evidenceLink.href)) return;
      sourceUrls.add(evidenceLink.href);
      var evidenceItem = node('li'); evidenceItem.appendChild(evidenceLink);
      if (evidence.supports) evidenceItem.appendChild(node('span', ': ' + evidence.supports));
      sources.appendChild(evidenceItem);
    });
    var coordinateSource = sourceLink('Coordinate source', record.coordinateSourceUrl);
    if (coordinateSource) { var coordinateItem = node('li'); coordinateItem.appendChild(coordinateSource); sources.appendChild(coordinateItem); }
    if (sources.childElementCount) detail.appendChild(sources);
    else detail.appendChild(node('p', 'A current official source link is not available in this record.'));
    detail.appendChild(node('p', 'Confirm appointments and services with the mission before visiting. This directory contains office information, not personal contact details.', 'small'));
  }
  function changePage(step) {
    var nextPage = currentPage + step, pages = Math.max(1, Math.ceil(filtered.length / pageSize));
    if (nextPage < 0 || nextPage >= pages) return;
    currentPage = nextPage; renderResults(); $('result-count').focus({ preventScroll: true });
    $('result-count').scrollIntoView({ block: 'start', behavior: 'auto' });
  }
  async function load() {
    if (loading) return; loading = true;
    $('retry').hidden = true; $('filters').disabled = true; $('coverage').classList.remove('error');
    $('coverage').textContent = 'Loading the missions directory...'; $('results').setAttribute('aria-busy', 'true');
    try {
      var response = await fetch('data/missions-australia.json?v=20260906');
      if (!response.ok) throw new Error('Directory request failed.');
      var data = await response.json();
      if (!Array.isArray(data.records) || !data.counts || data.counts.sourceRecords !== data.records.length) throw new Error('Invalid directory data.');
      var ids = new Set(), mapped = 0, held = 0;
      data.records.forEach(function (record) {
        if (!/^dfat-protocol-(missions|consulates)-[A-Za-z0-9-]+$/.test(record.id) || ids.has(record.id) || typeof record.country !== 'string'
          || typeof record.city !== 'string' || typeof record.type !== 'string' || typeof record.directoryKind !== 'string'
          || !['mapped', 'held'].includes(record.status)) throw new Error('Invalid mission record.');
        if (record.status === 'mapped' && (!validPosition(record) || !safeUrl(record.coordinateSourceUrl))) throw new Error('Missing coordinate evidence.');
        ids.add(record.id); if (record.status === 'mapped') mapped++; else held++;
        record.searchText = normalise([record.id, record.country, record.city, record.type, record.name, record.address].filter(Boolean).join(' '));
      });
      if (mapped !== data.counts.mapped || held !== data.counts.held) throw new Error('Directory count mismatch.');
      rows = data.records.slice().sort(function (a, b) {
        return a.country.localeCompare(b.country, 'en-AU') || a.city.localeCompare(b.city, 'en-AU') || a.type.localeCompare(b.type, 'en-AU') || a.id.localeCompare(b.id);
      });
      checkedAt = data.checkedAt; byId.clear(); rows.forEach(function (record) { byId.set(record.id, record); });
      addOptions('country', 'country'); addOptions('city', 'city'); addOptions('type', 'type');
      $('filters').disabled = false; applyFilters();
      $('coverage').textContent = data.counts.sourceRecords.toLocaleString('en-AU') + ' current DFAT office records. '
        + mapped.toLocaleString('en-AU') + ' approximate office positions on Earth; ' + held.toLocaleString('en-AU') + ' directory-only records. Checked ' + dateLabel(checkedAt) + '.';
      var selected = new URLSearchParams(location.hash.slice(1)).get('mission') || new URLSearchParams(location.search).get('mission');
      if (selected && byId.has(selected)) select(selected, false);
    } catch (_) {
      $('coverage').classList.add('error');
      $('coverage').textContent = 'The missions directory could not load. Try again, or open the live website if you are viewing a downloaded file. The official DFAT directory remains available below.';
      $('retry').hidden = false; $('results').setAttribute('aria-busy', 'false');
    } finally { loading = false; }
  }
  $('search').addEventListener('input', function () { clearTimeout(filterTimer); filterTimer = setTimeout(applyFilters, 160); });
  ['country', 'city', 'type', 'honorary', 'status'].forEach(function (id) { $(id).addEventListener('change', applyFilters); });
  $('reset').addEventListener('click', function () { ['search', 'country', 'city', 'type', 'honorary', 'status'].forEach(function (id) { $(id).value = ''; }); applyFilters(); });
  $('previous').addEventListener('click', function () { changePage(-1); });
  $('next').addEventListener('click', function () { changePage(1); });
  $('retry').addEventListener('click', load);
  window.addEventListener('hashchange', function () {
    var id = new URLSearchParams(location.hash.slice(1)).get('mission');
    if (id && byId.has(id)) select(id, false);
    else if (!id) { selectedId = ''; emptyDetail(); renderResults(); }
  });
  load();
})();
