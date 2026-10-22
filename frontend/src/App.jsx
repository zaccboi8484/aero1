import React,{useCallback,useEffect,useMemo,useRef,useState} from 'react';
import maplibregl from 'maplibre-gl';
import {Activity,AlertCircle,ArrowRight,BarChart3,Building2,CheckCircle2,ChevronDown,CloudLightning,Database,Download,ExternalLink,FileCheck2,FileWarning,Filter,Globe2,House,Layers3,MapPinned,Menu,Orbit,RefreshCw,Search,ShieldAlert,ShieldCheck,SlidersHorizontal,X} from 'lucide-react';

const TABS=[
 {id:'overview',label:'Command center',icon:BarChart3},
 {id:'properties',label:'Property search',icon:House},
 {id:'map',label:'Territory map',icon:MapPinned},
 {id:'permits',label:'Permit evidence',icon:FileCheck2},
 {id:'storms',label:'Storm intelligence',icon:CloudLightning},
 {id:'sources',label:'Source operations',icon:Database}
];
const fmt=n=>new Intl.NumberFormat('en-US').format(n??0);
const dollar=n=>typeof n==='number'?new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(n):'Not verified';
const date=s=>{const d=Date.parse(s||'');return Number.isFinite(d)?new Date(d).toLocaleString('en-US',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}):'Not published'};
const label=s=>String(s||'UNKNOWN').replaceAll('_',' ').toLowerCase();
const shortDate=s=>{if(!/^\d{4}-\d{2}-\d{2}$/.test(String(s||'')))return null;
 const [year,month,day]=s.split('-').map(Number);
 const d=new Date(Date.UTC(year,month-1,day));
 return Number.isFinite(d.getTime())?new Intl.DateTimeFormat('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'}).format(d):null;
};

const trusted=url=>{try{const u=new URL(url);return u.protocol==='https:'&&['tigerweb.geo.census.gov','arcgis.metc.state.mn.us','imageserver.gisdata.mn.gov','gis.cityofeagan.com','eagan.onlama.com','www.eaganmn.gov','www.ncei.noaa.gov','github.com','mn.gov'].includes(u.hostname)}catch{return false}};
function SourceLink({url,children}){return trusted(url)?<a className="source-link" href={url} target="_blank" rel="noreferrer">{children}<ExternalLink size={13}/></a>:null}
function Status({children,type='neutral'}){return <span className={'status '+type}>{children}</span>}
function Sidebar({active,onNavigate,open,onClose}){return <><div className={'scrim '+(open?'show':'')} onClick={onClose}/><aside className={'sidebar '+(open?'open':'')}>
 <div className="brand"><span className="brandmark"><Layers3 size={24}/></span><div><b>AERO<span>LEAD</span><em>AI</em></b><small>PROPERTY INTELLIGENCE</small></div><button className="close-mobile" onClick={onClose} aria-label="Close menu"><X size={18}/></button></div>
 <div className="workspace"><Building2 size={20}/><div><b>Operations workspace</b><span>Independent source network</span></div><span className="workspace-dot"/></div>
 <div className="nav-hint">INTELLIGENCE WORKSPACE</div><nav aria-label="Primary">{TABS.map(({id,label:txt,icon:Icon})=><button key={id} className={'navitem '+(active===id?'active':'')} onClick={()=>{onNavigate(id);onClose()}}><Icon size={18}/><span>{txt}</span>{id==='sources'&&<span className="navtag">LIVE</span>}</button>)}</nav>
 <div className="sidebar-bottom"><div className="side-note"><ShieldCheck size={19}/><div><b>GATEKEEPER VERIFIED PROVENANCE</b><p>Every score and source stays distinct from a physical roof inspection.</p></div></div><small>Independent React · No Base44 runtime</small></div>
 </aside></>}
function Stat({icon:Icon,title,value,detail,variation,onClick}){return <button className="statcard" onClick={onClick}><div className="stathead"><span>{title}</span><Icon size={19} className="teal"/></div><strong>{value}</strong><div className="statnote">{detail}</div>{variation&&<span className="statvariation">{variation}</span>}</button>}
function SourceMeter({name,count,total,detail}){const percent=total?Math.max(0,Math.min(100,Math.round(count/total*100))):0;return <div className="meter"><div className="meter-top"><b>{name}</b><strong>{fmt(count)} / {fmt(total)}</strong></div><div className="track"><span style={{width:percent+'%'}}/></div><small>{detail}</small></div>}
function GeoMap({properties,selected,onSelect,cinematic=false,large=false}){
 const element=useRef(null),map=useRef(null),ready=useRef(false),latest=useRef(onSelect),[failure,setFailure]=useState('');
 latest.current=onSelect;
 useEffect(()=>{if(!element.current)return;
  try{
   const instance=new maplibregl.Map({container:element.current,center:[-93.171,44.816],zoom:13.5,pitch:32,bearing:0,maxPitch:75,
     style:{version:8,sources:{carto:{type:'raster',tiles:['https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'],tileSize:256,attribution:'© OpenStreetMap contributors © CARTO'}},
       layers:[{id:'base',type:'raster',source:'carto'}]}});
   map.current=instance;instance.addControl(new maplibregl.NavigationControl(),'top-right');
   instance.on('load',()=>{ready.current=true;instance.addSource('parcels',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
     instance.addLayer({id:'halo',type:'circle',source:'parcels',paint:{'circle-radius':10,'circle-color':'#46cabe','circle-opacity':0.15}});
     instance.addLayer({id:'parcel-points',type:'circle',source:'parcels',paint:{
       'circle-radius':['interpolate',['linear'],['zoom'],11,3.8,17,9],
       'circle-color':['case',['==',['get','selected'],true],'#f2c57d',['==',['get','ring'],0],'#4ad4c8','#82aef3'],
       'circle-stroke-width':2,'circle-stroke-color':'#071725'}});
     instance.on('click','parcel-points',e=>{const id=String(e.features?.[0]?.properties?.id||'');if(id)latest.current(id)});
     instance.on('mouseenter','parcel-points',()=>instance.getCanvas().style.cursor='pointer');
     instance.on('mouseleave','parcel-points',()=>instance.getCanvas().style.cursor='');
     instance.fire('aero-data-ready');
   });
   instance.on('error',()=>{if(!ready.current)setFailure('Map tiles unavailable; source records still accessible')});
   return()=>{ready.current=false;instance.remove();map.current=null};
  }catch(e){setFailure(String(e.message||e))}
 },[]);
 useEffect(()=>{
  const refresh=()=>{const instance=map.current,src=instance?.getSource('parcels');if(!src)return;
   src.setData({type:'FeatureCollection',features:properties.filter(p=>Number.isFinite(p.lon)&&Number.isFinite(p.lat)).map(p=>({
     type:'Feature',geometry:{type:'Point',coordinates:[p.lon,p.lat]},
     properties:{id:p.id,selected:p.id===selected,ring:p.ring}}))});
  };
  const instance=map.current;
  if(ready.current)refresh();else if(instance)instance.once('aero-data-ready',refresh);
  return()=>{if(instance)instance.off('aero-data-ready',refresh)};
 },[properties,selected]);
 useEffect(()=>{map.current?.easeTo({pitch:cinematic?67:32,bearing:cinematic?-30:0,duration:750})},[cinematic]);
 useEffect(()=>{const p=properties.find(x=>x.id===selected);if(p&&map.current&&Number.isFinite(p.lon))map.current.flyTo({center:[p.lon,p.lat],zoom:Math.max(map.current.getZoom(),14),duration:600})},[selected,properties]);
 useEffect(()=>{const id=setTimeout(()=>map.current?.resize(),220);return()=>clearTimeout(id)},[large]);
 return <div className={'mapbox '+(large?'map-large':'')}><div ref={element} className="mapinner"/><span className="mapbadge"><span className="smallpulse"/>{fmt(properties.length)} SOURCE-LOCATED PARCELS</span><span className="mapdisclaimer">GIS centroids · Camera tilt is a visual effect, not 3D roof imagery</span>{failure&&<div className="maperror">{failure}</div>}</div>
}

function PropertyIndexCards({records,onPick,pageSize=30}){
 const [take,setTake]=useState(pageSize);
 useEffect(()=>setTake(pageSize),[records,pageSize]);
 if(!records.length)return <div className="empty"><Search size={26}/>No matching GIS records. Adjust the address or evidence filters.</div>;
 return <>
 <div className="property-index-grid" aria-label="Dated property evidence index cards">
 {records.slice(0,take).map(p=>{
  const permit=p.permitFacts||{},storm=p.stormFacts||{},roof=p.roofNeeds||{};
  const permitDate=shortDate(permit.latestDate),stormDate=shortDate(storm.latestDate);
  return <button type="button" className="property-index-card" key={p.pin} onClick={()=>onPick(p.id)}
    aria-label={'Open source evidence for '+p.address}>
   <div className="index-head"><div className="index-property-icon"><House size={19}/></div><div className="index-title"><b>{p.address.split(',')[0]}</b><small>PIN {p.pin}</small></div><ArrowRight size={16} className="index-arrow"/></div>
   <div className="index-meta"><span>{p.ring===0?'Original research batch':'Discovery ring '+p.ring}</span><span>{p.researchPriority==null?'Unscored':'Research priority '+p.researchPriority+'/100'}</span></div>
   <div className="index-evidence-grid">
    <div className="index-evidence-item"><div className="index-evidence-label"><FileCheck2 size={15}/>PERMIT ACTIVITY</div>
     <strong>{permitDate|| (permit.count?'Date missing in report':'No export match')}</strong>
     <span>{permit.count?
      (permit.latestNumber?permit.latestNumber+' · ':'')+(permit.roofPermitCandidateCount?'Roofing candidate · document unreviewed':'Issuer document unreviewed'):
      'Full municipal history unknown'}</span>
     <small>{permit.count?permit.count+' report match'+(permit.count===1?'':'es')+' · not final approval':'Search of full permit history needed'}</small>
    </div>
    <div className="index-evidence-item"><div className="index-evidence-label"><CloudLightning size={15}/>NEARBY NOAA STORM</div>
     <strong>{stormDate||'No dated nearby report'}</strong>
     <span>{stormDate?storm.latestType+' · '+storm.latestDistanceKm+' km away':
        p.stormFeedStatus==='NOAA_NOT_YET_RETRIEVED'?'NOAA feed pending':'No report within 15 km in loaded data'}</span>
     <small>{stormDate?
       (storm.latestHailInches==null?'':storm.latestHailInches+' in hail · ')+
       (storm.latestWindMph==null?'':storm.latestWindMph+' mph wind · ')+
       'Not a confirmed property hit':'No report is not proof of no storm'}</small>
    </div>
   </div>
   <div className="zip-source-band"><div>
    <span className="zip-source-label"><CloudLightning size={14}/>NOAA REPORTED POINT IN ZIP-AREA</span>
    <strong>{p.censusZcta?'Census ZCTA '+p.censusZcta:'ZIP area pending official mapping'}</strong>
   </div><div><b>{p.latestZipStorm?shortDate(p.latestZipStorm.date)||p.latestZipStorm.date:
     p.zipAreaStormStatus==='ZIP_AREA_INDEX_STALE'?'ZIP overlay source stale':
     p.zipAreaStormStatus==='ZIP_AREA_INDEX_PENDING'?'Census ZIP overlay pending':
     'No sourced NOAA point in ZIP-area'}</b>
    <small>{p.latestZipStorm?p.latestZipStorm.kind+' · point reported inside ZIP-area':
      '2020 Census ZIP approximation · not verified roof impact'}</small>
   </div></div>
   <div className="roof-needs-card"><div className="roof-needs-top"><span><ShieldAlert size={15}/>ROOF REVIEW NEEDS</span><span className="roof-status">UNVERIFIED</span></div>
    <strong>{roof.headline||'Roof inspection and records required'}</strong>
    <div className="roof-need-tags">{(roof.needs||[]).slice(0,3).map(item=><span key={item.code}>{item.label}</span>)}</div>
    <small>No damage, reroof completion, or replacement requirement certified.</small>
   </div>
   <div className="index-card-foot"><span><span className="card-source-dot"/>Official GIS parcel candidate</span><span>View complete evidence <ArrowRight size={14}/></span></div>
  </button>
 })}
 </div>
 {take<records.length&&<button className="load-more" onClick={()=>setTake(v=>v+48)}>Load 48 more of {fmt(records.length)} index cards <ChevronDown size={15}/></button>}
 </>;
}

function ParcelTable({records,onPick,pageSize=75}){const [take,setTake]=useState(pageSize);useEffect(()=>setTake(pageSize),[records,pageSize]);
 if(!records.length)return <div className="empty"><Search size={26}/>No matching source records.</div>;
 return <div className="table-wrap"><table><thead><tr><th>PROPERTY</th><th>RESEARCH SCOPE</th><th>PRIORITY</th><th>PERMITS</th><th>ROOF CONDITION</th><th></th></tr></thead>
 <tbody>{records.slice(0,take).map(p=><tr key={p.pin} tabIndex={0} onClick={()=>onPick(p.id)} onKeyDown={e=>{if(e.key==='Enter')onPick(p.id)}}>
 <td><div className="address"><span><House size={17}/></span><div><b>{p.address.split(',')[0]}</b><small>PIN {p.pin}</small></div></div></td>
 <td><b>{p.ring===0?'Original research batch':'GIS discovery ring '+p.ring}</b><small>{label(p.parcelStatus)}</small></td>
 <td><span className="priority">{p.researchPriority==null?'—':p.researchPriority}</span><small>Data review only</small></td>
 <td>{p.permits.length?<Status type="pending">{p.permits.length} export match(es)</Status>:<Status>History unknown</Status>}</td>
 <td><Status type="warning">Not inspected</Status></td>
 <td><ArrowRight size={16}/></td></tr>)}</tbody></table>
 {take<records.length&&<button className="load-more" onClick={()=>setTake(v=>v+75)}>Show 75 more of {fmt(records.length)} parcels <ChevronDown size={15}/></button>}
 </div>
}
function EvidenceDrawer({p,onClose}){useEffect(()=>{const fn=e=>{if(e.key==='Escape')onClose()};document.addEventListener('keydown',fn);return()=>document.removeEventListener('keydown',fn)},[onClose]);if(!p)return null;
 const facts=[['County PIN',p.pin],['Parcel GIS identity',label(p.parcelStatus)],['GIS construction year',p.yearBuilt||'Unknown'],
 ['Recorded municipal assessment',dollar(p.valuationUsd)+' · assessment year unverified'],['Data-research priority',p.researchPriority==null?'Not calculated':p.researchPriority+' / 100 · NOT DAMAGE'],
 ['Roof condition','Not inspected / not certified'],
 ['Latest permit report',p.permitFacts?.latestDate?(shortDate(p.permitFacts.latestDate)+' · '+p.permitFacts.latestNumber):'None dated in imported exports'],
 ['Latest nearby NOAA report',p.stormFacts?.latestDate?(shortDate(p.stormFacts.latestDate)+' · '+p.stormFacts.latestType+' · '+p.stormFacts.latestDistanceKm+' km'):'No dated point report in loaded years'],
 ['Roof review needs',p.roofNeeds?.headline||'Condition inspection / roofing history needed'],
 ['2020 Census ZIP area (not postal-certified)',p.censusZcta||'Not mapped'],
 ['Reported NOAA storm point inside ZIP-area',label(p.zipAreaStormStatus)],
 ['City permit portal',label(p.municipalPermitStatus)],['Municipal historic completeness','Unknown'],['Regional permit query',label(p.regionalPermitStatus)],['Imagery',p.aerialSourceVerified?'Official JPEG checksum verified; usage rights need review':'No verified JPEG source'] ];
 return <div className="drawer-screen" onClick={onClose}><aside role="dialog" aria-modal="true" aria-label={'Evidence for '+p.address} className="drawer" onClick={e=>e.stopPropagation()}>
 <div className="drawer-top"><span className="eyebrow">PROPERTY EVIDENCE · GATEKEEPER</span><button onClick={onClose} aria-label="Close details"><X size={19}/></button></div>
 <h2>{p.address.split(',')[0]}</h2><p>{p.address.split(',').slice(1).join(',')} · {p.ring===0?'Original 60 research batch':'Discovered GIS ring '+p.ring}</p>
 <div className="drawer-alert"><ShieldAlert size={18}/>Prioritization and weather proximity do not constitute verified roof damage.</div>
 <div className="factlist">{facts.map(([k,v])=><div key={k}><small>{k}</small><b>{v}</b></div>)}</div>
 <h3>Municipal permit candidate records</h3>{p.permits.length?<div className="stack">{p.permits.map(x=><div className="evidence-entry" key={x.number}><b>{x.number}</b><small>{x.kind} · Issued {x.issuedAt||'unknown'}</small><Status type="warning">Original issuer document pending</Status></div>)}</div>:<p className="subtle">No report match in the current exports. Complete municipal permit history has NOT been established.</p>}
 <h3>Roof assessment tasks · not a damage verdict</h3>
 <div className="roof-action-list">{(p.roofNeeds?.needs||[]).map(item=><div key={item.code}><CheckCircle2 size={14}/>{item.label}</div>)}</div>
 <h3>Nearby reported storm points</h3>{p.stormReports.length?<div className="stack">{p.stormReports.slice(0,8).map(x=><div className="evidence-entry" key={x.id}><b>{x.kind} · {x.distanceKm} km</b><small>{shortDate(x.sortKey?.slice(0,10))||x.date} {x.hailInches==null?'':'· '+x.hailInches+' in hail'} {x.windMph==null?'':'· '+x.windMph+' mph wind'}</small><small>Source observation only. No verified parcel impact.</small></div>)}</div>:<p className="subtle">No nearby point records in the currently imported NOAA dataset. This does not establish an absence of storms.</p>}
 <h3>Dated NOAA storm reports inside Census ZIP-area</h3>
 <p className="subtle">Census ZCTA areas approximate USPS ZIP Codes. A genuine NOAA point in the ZCTA confirms a reported event location there, not that the entire ZIP or this specific roof was struck.</p>
 {(p.zipAreaStormReports||[]).length?
  <div className="stack">{p.zipAreaStormReports.map(e=><div key={e.id} className="evidence-entry">
   <b>{e.kind} · {shortDate(e.date)||e.date}</b>
   <small>{e.hailInches===null?'':e.hailInches+' in reported hail · '}{e.windMph===null?'':e.windMph+' mph reported wind · '} NOAA point in Census ZIP-area</small>
   <SourceLink url={e.sourceUrl}>NOAA original archive</SourceLink>
  </div>)}</div>:
  <p className="subtle">No dated NOAA point currently assigned to this Census ZIP-area, or the official overlay is pending.</p>}
 <div className="drawer-links"><SourceLink url={p.parcelSource}>Official parcel record</SourceLink><SourceLink url={p.regionalSource}>Regional permit source</SourceLink><SourceLink url={p.aerialSource}>Government WMS image</SourceLink><SourceLink url="https://eagan.onlama.com/Search.aspx">Search City permit portal</SourceLink></div>
 </aside></div>
}
function StormPanel({properties,stormCount,stormUpdated}){const [hailOnly,setHailOnly]=useState(false);
 const reports=useMemo(()=>{const events=new Map();for(const p of properties)for(const r of p.stormReports){const existing=events.get(r.id);if(!existing||r.distanceKm<existing.distanceKm)events.set(r.id,{...r,address:p.address});}
 return [...events.values()].sort((a,b)=>String(b.sortKey||'').localeCompare(String(a.sortKey||'')))},[properties]);
 const filtered=reports.filter(x=>!hailOnly||(x.kind==='HAIL'&&typeof x.hailInches==='number'&&x.hailInches>=1.5));
 return <section className="panel"><div className="panel-head"><div><span className="eyebrow">NATIONAL WEATHER SERVICE · NCEI</span><h2>Historical reported storm events</h2><p>{fmt(stormCount)} regional source events; {fmt(reports.length)} unique reported points near indexed properties.</p></div><Status type={stormUpdated?'good':'warning'}>{stormUpdated?'NOAA SOURCE LOADED':'PENDING SOURCE'}</Status></div>
 <div className="inline-toolbar"><label className="toggle"><input type="checkbox" checked={hailOnly} onChange={e=>setHailOnly(e.target.checked)}/>Hail reports at least 1.5 inches</label><small>Published source run {date(stormUpdated)}</small></div>
 <div className="storm-list">{filtered.slice(0,80).map(e=><article key={e.id}><span className="weathericon"><CloudLightning size={19}/></span><div><b>{e.kind} · {e.distanceKm} km from nearby parcel</b><small>{shortDate(e.sortKey?.slice(0,10))||e.date} · {e.address.split(',')[0]}</small><p>{e.hailInches==null?'':e.hailInches+' in reported hail · '}{e.windMph==null?'':e.windMph+' mph reported wind · '}Not a verified property impact</p></div></article>)}{!filtered.length&&<p className="subtle">No qualifying nearby NOAA point records in the current published years. This does not rule out storms.</p>}</div>
 <SourceLink url="https://www.ncei.noaa.gov/access/storm-events-database/">NOAA Storm Events Database</SourceLink>
 </section>
}
function PermitPanel({properties,portal}){const p=properties.filter(x=>x.permits.length);
 return <section className="panel"><div className="panel-head"><div><span className="eyebrow">CITY ISSUER / RECONCILIATION</span><h2>Real permit evidence and search gaps</h2><p>{fmt(p.reduce((a,x)=>a+x.permits.length,0))} imported issuer-report candidate rows across {fmt(p.length)} properties.</p></div><Status type="warning">{label(portal)}</Status></div>
 <div className="warningbox"><AlertCircle size={18}/><p>The City's public portal cannot currently be searched unattended by this collector. Regional construction permits are not a complete roofing history. Issued permit ≠ final inspection.</p></div>
 <div className="two-actions"><SourceLink url="https://eagan.onlama.com/Search.aspx">Search by address or permit number</SourceLink><SourceLink url="https://eagan.onlama.com/Dashboard.aspx">Download public City reports</SourceLink><SourceLink url="https://www.revisor.mn.gov/statutes/cite/13.03">Minnesota public-data rights</SourceLink></div>
 <div className="permitgrid">{p.map(property=><article key={property.pin}><span className="eyebrow">PIN {property.pin}</span><h3>{property.address.split(',')[0]}</h3>{property.permits.map(item=><div key={item.number} className="permitline"><b>{item.number}</b><small>{item.kind} · Issued {shortDate(item.issuedAt)||'date unavailable in export'}</small></div>)}<Status type="pending">Issuer document / inspection pending</Status></article>)}</div>
 </section>
}
function Operations({network,ops}){const d=network?.counts||{},sources=ops?.sources||[];
 return <section className="panel"><div className="panel-head"><div><span className="eyebrow">OPERATIONS · VERIFIED VS PENDING</span><h2>Pipeline health and source provenance</h2><p>Operational source checks do not certify condition or completeness of City permits.</p></div><Status type="warning">NOT FULLY CERTIFIED</Status></div>
 <div className="healthgrid"><SourceMeter name="GIS parcel identity" count={d.bulkPinVerified||d.checkedPins||0} total={d.parcels||1} detail="Official PIN match; no structural inference"/>
 <SourceMeter name="Aerial JPEG source" count={d.sourceValidatedImagery||0} total={d.parcels||1} detail="Verified remote response; no resale rights implied"/>
 <SourceMeter name="Municipal history certified" count={0} total={d.parcels||1} detail="Source access/issuer documents still outstanding"/>
 <SourceMeter name="Roof conditions reviewed" count={0} total={d.parcels||1} detail="No physical inspection or issuer final-status certification"/></div>
 <div className="sourcegrid">{sources.map(s=><article key={s.id}><div className="source-top"><Globe2 size={19}/><Status type={s.state==='CURRENT'?'good':s.state==='BLOCKED'?'warning':'neutral'}>{s.state}</Status></div><b>{s.name}</b><p>{s.message}</p><small>Last check: {date(s.lastChecked)}</small>{s.url&&<SourceLink url={s.url}>Original authority</SourceLink>}</article>)}</div>
 <div className="warningbox"><FileWarning size={19}/><p>Full operational readiness requires a licensed image-use policy, authorized original permit/inspection access, a persistent audit database, and proven automatic code deployments. A successful CI run alone cannot satisfy those gates.</p></div>
 </section>
}
export default function App(){
 const [tab,setTab]=useState('overview'),[menu,setMenu]=useState(false),[records,setRecords]=useState([]),
 [network,setNetwork]=useState(null),[ops,setOps]=useState(null),[state,setState]=useState('CONNECTING'),[error,setError]=useState(''),
 [text,setText]=useState(''),[scope,setScope]=useState('all'),[chosen,setChosen]=useState(null),[cinematic,setCinematic]=useState(false);
 const reload=useCallback(async()=>{
  setState('CHECKING');setError('');
  try{
   let offset=0,doc=null,list=[],loops=0;
   do{
    const r=await fetch('/api/property-network?limit=1000&offset='+offset,{cache:'no-store',signal:AbortSignal.timeout(16000)});
    const j=await r.json();if(!r.ok)throw Error(j.detail||j.error||('API HTTP '+r.status));
    if(!doc)doc=j;
    list.push(...j.records);offset+=j.records.length;
    if(!j.hasMore)break;
    if(++loops>=60||!j.records.length)throw Error('Pagination incomplete');
   }while(true);
   if(!doc||list.length!==doc.counts.parcels||new Set(list.map(p=>p.pin)).size!==list.length)
    throw Error('GIS registry incomplete or duplicated. No invented fallback data.');
   setNetwork(doc);setRecords(list);setState('LIVE');
   try{const h=await fetch('/api/operations-health',{cache:'no-store',signal:AbortSignal.timeout(12000)});
    if(h.ok)setOps(await h.json());else setOps(null)}catch{setOps(null)}
  }catch(e){setError(String(e.message||e));setState('STALE_ERROR')}
 },[]);
 useEffect(()=>{reload();const timer=setInterval(()=>{if(!document.hidden)reload()},180000);return()=>clearInterval(timer)},[reload]);
 const filtered=useMemo(()=>records.filter(p=>{
  if(text&&!((p.address+' '+p.pin).toLowerCase().includes(text.toLowerCase())))return false;
  return scope==='all'||scope==='original'&&p.ring===0||scope==='rings'&&p.ring>0||scope==='permits'&&p.permits.length>0||
   scope==='storms'&&p.stormReports.length>0||scope==='zipstorm'&&p.zipAreaStormReports?.length>0;
 }),[records,text,scope]);
 const select=useCallback(id=>setChosen(id),[]);
 const selected=records.find(p=>p.id===chosen)||null;
 const counts=network?.counts||{},total=counts.parcels||0;
 const metrics=<div className="statgrid"><Stat icon={Building2} title="INDEXED GIS PROPERTIES" value={fmt(total)} detail={fmt(counts.initialBatch||0)+' original / '+fmt(counts.expansion||0)+' expanded'} onClick={()=>setTab('properties')}/>
 <Stat icon={ShieldCheck} title="VERIFIED GIS IDENTITIES" value={fmt(counts.bulkPinVerified??counts.checkedPins??0)} detail="Official record identities, not roofs" onClick={()=>setTab('sources')}/>
 <Stat icon={FileCheck2} title="PERMIT EXPORT MATCHES" value={fmt(counts.municipalReportPermits||0)} detail={fmt(counts.municipalReportProperties||0)+' properties · issuer review pending'} onClick={()=>setTab('permits')}/>
 <Stat icon={CloudLightning} title="NOAA HISTORICAL EVENTS" value={network?.stormRunAt?fmt(counts.historicalStormReports||0):'Pending'} detail="Storm reports, not parcel damage" onClick={()=>setTab('storms')}/></div>;
 const searchBar=<div className="tools"><label className="search"><Search size={17}/><input value={text} onChange={e=>setText(e.target.value)} placeholder="Search all addresses and county PINs" aria-label="Search property addresses and county PINs"/></label>
 <label className="filter"><Filter size={16}/><select value={scope} onChange={e=>setScope(e.target.value)} aria-label="Filter property records"><option value="all">All discovered</option><option value="original">First research batch</option><option value="rings">Expansion rings</option><option value="permits">Permit candidates</option><option value="storms">Nearby NOAA reports</option><option value="zipstorm">NOAA report within ZIP-area</option></select></label></div>;
 return <div className="app"><Sidebar active={tab} onNavigate={setTab} open={menu} onClose={()=>setMenu(false)}/><main className="main">
 <header className="topbar"><div className="breadcrumb"><button className="menubutton" onClick={()=>setMenu(true)} aria-label="Open menu"><Menu size={19}/></button><span>OPERATIONS</span><span className="breadslash">/</span><b>{TABS.find(x=>x.id===tab)?.label}</b></div><div className="top-actions"><span className={'top-connection '+(state==='LIVE'?'connected':'')}><span/>{state==='LIVE'?'SOURCE DATA LIVE':state==='STALE_ERROR'?'SOURCE ERROR':'CHECKING SOURCES'}</span><button onClick={reload} className="refresh" aria-label="Refresh evidence sources"><RefreshCw size={16}/> Refresh</button></div></header>
 <div className="content"><div className="hero"><div><span className="eyebrow"><span className="smallpulse"/> AEROLEADAI · INDEPENDENT GATEKEEPER</span><h1>{tab==='overview'?'Property intelligence command center':TABS.find(x=>x.id===tab)?.label}</h1><p>Autonomous discovery. Real source provenance. No Base44 dependence. Unknown findings stay unknown.</p></div><div className="hero-tag"><Activity size={17}/>{date(network?.sourceRunAt)}</div></div>
 {error&&<div className="errorbar"><AlertCircle size={18}/><div><b>Source refresh failed.</b> Last verified records remain visible, not silently replaced. {error}</div></div>}
 {!error&&state==='LIVE'&&counts.cityPermitPortalStatus!=='PUBLIC_OPEN_DATA_PAGE_REACHABLE'&&<div className="infobar"><AlertCircle size={16}/><span>Eagan issuer portal: {label(counts.cityPermitPortalStatus)}. GIS discovery and NOAA reports are separate functioning sources; complete permit history remains unavailable.</span></div>}
 {metrics}
 {tab==='overview'&&<><div className="overviewgrid"><section className="panel map-panel"><div className="panel-head"><div><span className="eyebrow">LIVE TERRITORY INTELLIGENCE</span><h2>Geographic property network</h2><p>{fmt(total)} real indexed parcels. Interactive map and documented GIS centroids.</p></div><button className="ghost" onClick={()=>setCinematic(x=>!x)}><Orbit size={17}/>{cinematic?'Standard view':'Cinematic view'}</button></div><GeoMap properties={records} selected={chosen} onSelect={select} cinematic={cinematic}/></section>
 <section className="panel coverage-panel"><div className="panel-head"><div><span className="eyebrow">SOURCE COVERAGE</span><h2>Evidence completeness</h2><p>Completed searches vs outstanding work</p></div></div><div className="padding"><SourceMeter name="GIS identity" count={counts.bulkPinVerified??counts.checkedPins??0} total={total} detail="Government-reported object and county PIN"/><SourceMeter name="Government JPEG source" count={counts.sourceValidatedImagery??0} total={total} detail="Image response checksum; licensing pending"/><SourceMeter name="Original issuer permits verified" count={0} total={total} detail="Public report matches are not final inspections"/><SourceMeter name="Certified physical conditions" count={0} total={total} detail="No unsupported damage labels"/></div><div className="coverage-foot"><ShieldAlert size={17}/><span>GateKeeper: this is a research inventory, not a certified damage list.</span></div></section></div>
 <section className="panel board-panel"><div className="panel-head"><div><span className="eyebrow">ALL SOURCED PROPERTIES</span><h2>Searchable property board</h2><p>Initial 60 remain the first research batch, never a display limit.</p></div><button className="ghost" onClick={()=>setTab('properties')}>Full property search <ArrowRight size={16}/></button></div><div className="padding">{searchBar}<PropertyIndexCards records={filtered} onPick={select} pageSize={24}/></div></section></>}
 {tab==='properties'&&<section className="panel"><div className="panel-head"><div><span className="eyebrow">GIS PROPERTY INDEX</span><h2>{fmt(filtered.length)} searchable official-source parcel records</h2><p>Addresses, PINs, permitted-report evidence and research priority where available.</p></div><Status>DATA-RESEARCH SCORES ONLY</Status></div><div className="padding">{searchBar}<PropertyIndexCards records={filtered} onPick={select} pageSize={48}/></div></section>}
 {tab==='map'&&<section className="panel"><div className="panel-head"><div><span className="eyebrow">REAL OFFICIAL GIS COORDINATES</span><h2>Interactive Eagan property map</h2><p>Map is a presentation layer. Parcel polygons and inspection findings are not asserted.</p></div><button className="ghost" onClick={()=>setCinematic(x=>!x)}><Orbit size={17}/>{cinematic?'Reset camera':'Cinematic camera'}</button></div><GeoMap properties={filtered} selected={chosen} onSelect={select} cinematic={cinematic} large/><div className="padding">{searchBar}</div></section>}
 {tab==='permits'&&<PermitPanel properties={records} portal={counts.cityPermitPortalStatus}/>}
 {tab==='storms'&&<StormPanel properties={records} stormCount={counts.historicalStormReports||0} stormUpdated={network?.stormRunAt}/>}
 {tab==='sources'&&<Operations network={network} ops={ops}/>}
 <footer>Independent React · Official GIS / NCEI / City-source reports · No Base44 SDK · No simulated approvals · <a href="/classic.html">Legacy cinematic desk</a> · <a href="/certification-gaps.html">Certification queue</a></footer>
 </div></main><EvidenceDrawer p={selected} onClose={()=>setChosen(null)}/></div>
}
