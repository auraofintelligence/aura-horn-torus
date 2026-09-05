'use strict';
(function(){
  var byId = new Map(), chunks = new Map(), bodies = new Map(), memberships = new Map();
  var rows = [], filtered = [], selectedId = '', currentPage = 0, pageSize = 30, selectionVersion = 0;
  var $ = function(id){return document.getElementById(id);};
  function node(tag,text,cls){var e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
  function link(text,url){var e=node('a',text);try{var u=new URL(url,location.href);if(!/^https?:$/.test(u.protocol))return node('span',text);e.href=u.href;e.rel='noopener';return e;}catch(_){return node('span',text);}}
  function norm(value){return String(value||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase();}
  async function getJson(url){var r=await fetch(url);if(!r.ok)throw new Error('Could not load '+url);return r.json();}
  function addOption(select,value,label){var option=node('option',label);option.value=value;select.appendChild(option);}
  function setFilters(){
    var countries=new Map(), identifiers=new Set();
    rows.forEach(function(r){(r[9]||[[r[2],r[3]]]).forEach(function(c){countries.set(c[0],c[1]||c[0]);});(r[6]||[]).forEach(function(v){identifiers.add(v);});});
    Array.from(countries).sort(function(a,b){return a[1].localeCompare(b[1]);}).forEach(function(c){addOption($('country'),c[0],c[1]);});
    Array.from(identifiers).sort().forEach(function(v){addOption($('identifier'),v,v);});
    bodies.forEach(function(b,id){addOption($('body'),id,b.name+' · evidenced members');});
  }
  function filter(){
    var q=norm($('search').value.trim()),country=$('country').value,body=$('body').value,identifier=$('identifier').value,connection=$('connection').value;
    filtered=rows.filter(function(r){
      return (!q||r.search.includes(q))&&(!country||(r[9]||[[r[2]]]).some(function(c){return c[0]===country;}))&&(!body||(memberships.get(r[0])||[]).some(function(m){return m.bodyId===body;}))
        &&(!identifier||(r[6]||[]).includes(identifier))&&(!connection||(connection==='any'?(r[7]||[]).length:(r[7]||[]).includes(connection)));
    });
    currentPage=0;renderResults();
  }
  function renderResults(){
    var result=$('results');result.replaceChildren();
    $('result-count').textContent=filtered.length.toLocaleString('en-AU')+(filtered.length===1?' institution':' institutions');
    if(!filtered.length)result.appendChild(node('p','No records match these filters. Try a wider country or remove a filter.'));
    filtered.slice(currentPage*pageSize,(currentPage+1)*pageSize).forEach(function(r){
      var button=node('button',undefined,'result');button.type='button';button.setAttribute('aria-pressed',String(r[0]===selectedId));
      button.appendChild(node('strong',r[1]));button.appendChild(node('span',[r[4],r[3]].filter(Boolean).join(', ')+(r[9]?.length>1?' · also '+r[9].filter(function(c){return c[0]!==r[2];}).map(function(c){return c[1];}).join(', '):'')));
      var memberNames=(memberships.get(r[0])||[]).map(function(m){return bodies.get(m.bodyId)?.name||m.bodyId;});
      if(memberNames.length)button.appendChild(node('span',memberNames.join(' · ')));
      button.addEventListener('click',function(){select(r[0],true);});result.appendChild(button);
    });
    var pages=Math.max(1,Math.ceil(filtered.length/pageSize));
    $('page-count').textContent='Page '+(currentPage+1)+' of '+pages;$('previous').disabled=currentPage===0;$('next').disabled=currentPage+1>=pages;$('download').disabled=!filtered.length;
  }
  async function select(id,focus){
    var row=byId.get(id);if(!row)return;selectedId=id;var version=++selectionVersion;
    var detail=$('detail');detail.replaceChildren(node('h2',row[1]),node('p','Loading institution details…'));renderResults();
    if(focus){detail.focus({preventScroll:true});if(matchMedia('(max-width:750px)').matches)detail.scrollIntoView({block:'start',behavior:'smooth'});}
    history.replaceState(null,'','#institution='+encodeURIComponent(id));
    try{
      if(!chunks.has(row[2]))chunks.set(row[2],getJson('data/education-registry/'+encodeURIComponent(row[2])+'.json'));
      var chunk=await chunks.get(row[2]);if(version!==selectionVersion)return;
      var record=chunk.organisations.find(function(r){return r.id===id;});if(!record)throw new Error('Institution record is unavailable.');
      renderDetail(record,row);
    }catch(error){chunks.delete(row[2]);if(version!==selectionVersion)return;detail.replaceChildren(node('h2',row[1]),node('p','Details could not be loaded. Select this institution again to retry.'),link('Open its ROR source',id));}
  }
  function section(title){$('detail').appendChild(node('h3',title));}
  function renderDetail(record,row){
    var detail=$('detail');detail.replaceChildren(node('h2',record.name));
    var actions=node('div',undefined,'actions');
    actions.appendChild(link('Show on Earth','index.html?institution='+encodeURIComponent(record.id)+'&layer='+encodeURIComponent(row[8]||'education-registry')));
    actions.appendChild(link('ROR record',record.id));
    if(record.websites?.length)actions.appendChild(link('Institution website',record.websites[0]));detail.appendChild(actions);
    section('Locations');var locations=node('ul');
    (record.locations||[]).forEach(function(loc){locations.appendChild(node('li',[loc.name,loc.subdivision,loc.countryName].filter(Boolean).join(', ')));});
    detail.appendChild(locations);detail.appendChild(node('p','GeoNames city/locality approximations, not campus or entrance positions.'));
    section('Peak bodies and associations');var memberList=memberships.get(record.id)||[];
    if(!memberList.length)detail.appendChild(node('p','Membership has not been assessed in this catalogue.'));
    memberList.forEach(function(m){var p=node('p');p.appendChild(link(bodies.get(m.bodyId)?.name||m.bodyId,m.sourceUrl));p.appendChild(node('span',' · checked '+m.checkedAt));detail.appendChild(p);});
    section('Shared identifiers');var ids=record.externalIds||[];
    if(!ids.length)detail.appendChild(node('p','ROR is the shared identifier currently supplied.'));
    ids.forEach(function(i){detail.appendChild(node('p',i.type+': '+(i.all||[]).join(', ')));});
    section('Recorded organisational connections');var relationships=record.relationships||[];
    if(!relationships.length)detail.appendChild(node('p','No parent, child or related organisation is recorded in this extract.'));
    var list=node('ul');relationships.forEach(function(rel){
      var li=node('li');li.appendChild(node('span',rel.type+': '));
      if(byId.has(rel.id)){var b=node('button',rel.name);b.type='button';b.addEventListener('click',function(){select(rel.id,true);});li.appendChild(b);}else li.appendChild(link(rel.name,rel.id));list.appendChild(li);
    });detail.appendChild(list);
    section('GAJRA Earth');detail.appendChild(node('p','Potential applicability is unassessed. This listing establishes neither contact nor membership. Research its programmes and the authority of any representative before treating it as an institutional connection.'));
    detail.appendChild(link('Explore the invitation and open questions','https://auraofintelligence.github.io/gajra-earth-claude-build/questions.html'));
    detail.appendChild(node('p','Organisation data: ROR v2.11, 3 August 2026. Membership evidence is dated separately.','small'));
  }
  function download(){
    function cell(value){var s=String(value??'');if(/^[=+@\-\t\r]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';}
    var data=[['ror_id','name','country_code','country','locality','evidenced_peak_bodies','shared_identifier_types','gajra_status','registry_date']];
    filtered.forEach(function(r){data.push([r[0],r[1],r[2],r[3],r[4],(memberships.get(r[0])||[]).map(function(m){return bodies.get(m.bodyId)?.name||m.bodyId;}).join(' | '),(r[6]||[]).join(' | '),'not assessed','2026-08-03']);});
    var url=URL.createObjectURL(new Blob(['\uFEFF'+data.map(function(r){return r.map(cell).join(',');}).join('\r\n')],{type:'text/csv;charset=utf-8'}));
    var a=document.createElement('a');a.href=url;a.download='education-discovery-shortlist.csv';a.click();setTimeout(function(){URL.revokeObjectURL(url);},2000);
  }
  var timer; $('search').addEventListener('input',function(){clearTimeout(timer);timer=setTimeout(filter,160);});
  ['country','body','identifier','connection'].forEach(function(id){$(id).addEventListener('change',filter);});
  $('reset').addEventListener('click',function(){['search','country','body','identifier','connection'].forEach(function(id){$(id).value='';});filter();});
  $('previous').addEventListener('click',function(){currentPage--;renderResults();});$('next').addEventListener('click',function(){currentPage++;renderResults();});$('download').addEventListener('click',download);
  Promise.all([getJson('data/education-registry-index.json'),getJson('data/university-applicability-evidence.json')]).then(function(results){
    var index=results[0],evidence=results[1];rows=index.rows;
    rows.forEach(function(r){r.search=norm([r[0],r[1],r[3],r[4]].concat(r[10]||[]).join(' '));byId.set(r[0],r);});
    (evidence.peakBodies||[]).forEach(function(b){bodies.set(b.id,b);});(evidence.institutions||[]).forEach(function(i){memberships.set(i.rorId,i.memberships||[]);});
    rows.sort(function(a,b){return a[1].localeCompare(b[1]);});setFilters();filter();
    $('coverage').textContent=rows.length.toLocaleString('en-AU')+' active education organisations · ROR snapshot: 3 August 2026 · worldwide discovery, with recognition and completeness still to be checked against national registers.';
    var id=new URLSearchParams(location.hash.slice(1)).get('institution');if(id)select(id,false);
  }).catch(function(){$('coverage').textContent='The directory could not load. Reload to retry, or open the live HTTPS site if you are viewing a downloaded file.';});
})();
