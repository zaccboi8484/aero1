(()=>{'use strict';
const $=id=>document.getElementById(id);
const num=n=>new Intl.NumberFormat('en-US').format(n||0);
const node=(tag,value,cls)=>{const x=document.createElement(tag);x.textContent=String(value??'');if(cls)x.className=cls;return x};
const okUrl=u=>{try{const x=new URL(u);return x.protocol==='https:'&&['arcgis.metc.state.mn.us','imageserver.gisdata.mn.gov','gis.cityofeagan.com','eagan.onlama.com','cityofeaganmn.nextrequest.com','www.ncei.noaa.gov'].includes(x.hostname)}catch{return false}};
function link(title,url){if(!okUrl(url))return node('span','Official source not yet available','warning');const a=node('a',title+' ↗','link');a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a}
let rows=[],selected=null,map=null,mapReady=false,more=200,view='all',term='',cinematic=false;
function displayProperty(p){
 selected=p;
 const place=$('detail');place.replaceChildren();
 place.append(node('div',p.address,'detail-header'),node('div','PIN '+p.pin+' · '+(p.ring===0?'Original 60 research batch':'Expansion ring '+p.ring),'line'));
 const facts=[
 ['GIS check',p.parcelStatus+' · '+(p.parcelCheckedAt||'not yet checked')],
 ['Research availability',p.parcelCheckedAt?'Source search attempted':'FIRST SOURCE SEARCH NOT YET ATTEMPTED'],
 ['Research score',p.researchPriority===null?'Awaiting research (not scored)':p.researchPriority+'/100 · research only'],
 ['Roof damage','NOT VERIFIED (no certified inspection)'],
 ['Municipal permit report',p.permits.length+' imported matches · full history UNKNOWN'],
 ['City permitting portal',p.municipalPermitStatus],
 ['Regional permit query',p.regionalPermitStatus+' · '+(p.regionalPermitCount===null?'Not checked':p.regionalPermitCount+' matches')],
 ['NOAA nearby reports',p.stormReports.length+' within 15 km · '+p.stormFeedStatus],
 ['Verified government aerial',p.aerialSourceVerified?'WMS response SHA recorded (not roof condition)':'Unverified'],
 ['Municipal GIS valuation',p.valuationUsd===null?'Not source verified':'$'+num(p.valuationUsd)+' · source year not established']
 ];
 facts.forEach(([name,value])=>{const d=node('div','','line');d.append(node('b',name+': '),node('span',value));place.append(d)});
 place.append(link('Parcel source',p.parcelSource),link('Regional permit evidence',p.regionalSource),link('Official WMS aerial',p.aerialSource),
  link('Request public City permit records','https://cityofeaganmn.nextrequest.com/'));
 const panel=$('stormPanel');panel.replaceChildren();
 panel.append(node('p','CITY PERMIT: '+p.municipalPermitStatus,'warning'),node('p','An issued permit is not final inspection approval; no export match does not mean no permit. A nearby storm observation does not prove roof impact.'));
 if(p.permits.length){panel.append(node('strong','Actual imported City report rows:'));p.permits.forEach(x=>{const d=node('div',x.number+' · '+x.issuedAt+' · '+x.kind+' · ISSUER DOCUMENT PENDING','line');panel.append(d)})}
 panel.append(node('strong','Nearby NOAA storm report points:'));
 if(!p.stormReports.length)panel.append(node('div',p.stormFeedStatus==='NOAA_NOT_YET_RETRIEVED'?'NOAA feed not yet published':'No published point report within 15 km. This does not establish no storms.','line'));
 p.stormReports.forEach(x=>panel.append(node('div',x.kind+' · '+x.date+' · '+x.distanceKm+' km'+(x.hailInches===null?'':' · hail '+x.hailInches+' in')+(x.windMph===null?'':' · wind '+x.windMph+' mph'),'line')));
 panel.append(link('NOAA NCEI original database','https://www.ncei.noaa.gov/access/storm-events-database/'),
  link('NOAA mapped hail and tornado footprints','https://www.ncei.noaa.gov/products/event-footprint-catalog'));
 if(mapReady){map.flyTo({center:[p.lon,p.lat],zoom:15.8,duration:800});updateMap()}
}
function updateMap(){
 if(!mapReady)return;
 map.getSource('parcels').setData({type:'FeatureCollection',features:rows.filter(p=>Number.isFinite(p.lon)&&Number.isFinite(p.lat)).map(p=>({type:'Feature',geometry:{type:'Point',coordinates:[p.lon,p.lat]},properties:{id:p.id,ring:p.ring,selected:p.id===selected?.id}}))});
}
function makeMap(){
 if(!window.maplibregl){$('notice').textContent+=' · Map library unavailable; listing remains functional.';return}
 map=new maplibregl.Map({container:'map',style:{version:8,sources:{carto:{type:'raster',tiles:['https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'],tileSize:256,attribution:'© OSM © CARTO'}},layers:[{id:'base',type:'raster',source:'carto'}]},center:[-93.17,44.815],zoom:12.8,pitch:35,maxPitch:75});
 map.addControl(new maplibregl.NavigationControl(),'top-right');
 map.on('load',()=>{
   mapReady=true;map.addSource('parcels',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
   map.addLayer({id:'points',type:'circle',source:'parcels',paint:{
     'circle-radius':['interpolate',['linear'],['zoom'],10,3,16,9],
     'circle-color':['case',['==',['get','selected'],true],'#f4c87d',['==',['get','ring'],0],'#73e2d1','#89b9f5'],
     'circle-stroke-width':2,'circle-stroke-color':'#10212f'}});
   map.on('click','points',e=>{const id=String(e.features?.[0]?.properties?.id||'');const p=rows.find(p=>p.id===id);if(p){displayProperty(p);renderList()}});
   map.on('mouseenter','points',()=>map.getCanvas().style.cursor='pointer');
   map.on('mouseleave','points',()=>map.getCanvas().style.cursor='');
   updateMap();
 });
}
function matches(){
 return rows.filter(p=>(!term||(p.address+' '+p.pin).toLowerCase().includes(term))&&
 (view==='all'||view==='rings'&&p.ring>0||view==='original'&&p.ring===0||
 view==='permits'&&p.permits.length>0||view==='storm'&&p.stormReports.length>0));
}
function renderList(){
 const records=matches(),list=$('rows');list.replaceChildren();
 $('total').textContent=num(records.length)+' / '+num(rows.length)+' actual GIS parcels';
 records.slice(0,more).forEach((p,i)=>{
   const b=node('button','','item'+(p.id===selected?.id?' active':''));b.type='button';
   const middle=node('span','','info');
   middle.append(node('strong',p.address.split(',')[0]),node('small','PIN '+p.pin+' · '+(p.ring===0?'Seed batch':'Ring '+p.ring)));
   b.append(node('span',String(i+1),'num'),middle,node('span',p.researchPriority===null?'Research pending':p.researchPriority+'/100 data score','state pending'));
   b.addEventListener('click',()=>{displayProperty(p);renderList()});list.append(b);
 });
 if(records.length>more){const btn=node('button','Load 200 more property records','item');btn.addEventListener('click',()=>{more+=200;renderList()});list.append(btn)}
}
async function refresh(){
 $('reload').disabled=true;$('notice').textContent='Retrieving live official parcels, municipal permit evidence and NOAA report status...';
 try{
   const merged=[];let offset=0,first=null,loops=0;
   do{
     const response=await fetch('/api/property-network?limit=1000&offset='+offset,{cache:'no-store'});
     const data=await response.json();if(!response.ok)throw Error(data.detail||data.error||'HTTP '+response.status);
     if(!first)first=data;
     merged.push(...data.records);offset+=data.records.length;
     if(!data.hasMore)break;
     if(++loops>65||!data.records.length)throw Error('Network pagination incomplete');
   }while(true);
   if(merged.length!==first.counts.parcels||new Set(merged.map(p=>p.pin)).size!==merged.length)throw Error('GIS census mismatch');
   rows=merged;more=200;
   $('count').textContent=num(first.counts.parcels);$('seed').textContent=num(first.counts.initialBatch);
   $('rings').textContent=num(first.counts.expansion);$('permits').textContent=num(first.counts.municipalReportPermits);
   $('storms').textContent=first.stormRunAt?num(first.counts.historicalStormReports):'Pending';
   $('notice').textContent='LIVE OFFICIAL GIS: '+first.counts.parcels+' indexed parcels = 60 original + '+
     first.counts.expansion+' discovered. '+first.counts.parcelsAttemptedAtLeastOnce+'/'+first.counts.parcels+' parcels have a published research attempt ('+first.counts.parcelsNeverAttempted+' still waiting). Eagan issuer portal: '+
     first.counts.cityPermitPortalStatus+'. NOAA reports: '+
     (first.stormRunAt?first.counts.historicalStormReports+' historical event records from official sources':'ingestion has not yet completed')+
     '. Storm proximity, permit issue and aerial access do not establish roof damage.';
   renderList();updateMap();
   const active=rows.find(p=>p.id===selected?.id);if(active)displayProperty(active);else if(rows.length)displayProperty(rows[0]);
 }catch(e){$('notice').textContent='EVIDENCE NETWORK ERROR: '+String(e.message||e)+' · No fabricated parcels or storms.'}
 finally{$('reload').disabled=false}
}
$('query').addEventListener('input',()=>{term=$('query').value.trim().toLowerCase();more=200;renderList()});
$('view').addEventListener('change',()=>{view=$('view').value;more=200;renderList()});
$('reload').addEventListener('click',refresh);
$('tilt').addEventListener('click',()=>{cinematic=!cinematic;$('tilt').textContent=cinematic?'Return to standard map':'Cinematic orbit view';if(map)map.easeTo({pitch:cinematic?67:35,bearing:cinematic?-29:0,duration:850})});
makeMap();refresh();setInterval(()=>{if(!document.hidden)refresh()},180000);
})();