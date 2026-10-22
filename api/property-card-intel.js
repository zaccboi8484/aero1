/** Pure GateKeeper property-card facts from existing issuer and NOAA evidence.
 * This module must not invent reroof dates, damage, storm footprints, or inspections.
 * All dates are source-local calendar labels; NOAA archived time zone is not assumed.
 */
const MONTHS=['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
export function calendarDate(source){
 if(typeof source!=='string')return null;
 const date=source.trim();
 let y,m,d;
 if(/^\d{4}-\d{2}-\d{2}(?:T.*)?$/.test(date)){[y,m,d]=date.slice(0,10).split('-').map(Number);}
 else{
  const match=/^(\d{1,2})-([A-Z]{3})-(\d{2,4})(?:\s+.*)?$/i.exec(date);
  if(!match)return null;
  d=Number(match[1]);m=MONTHS.indexOf(match[2].toUpperCase())+1;y=Number(match[3]);
  if(y<100)y=y<=79?2000+y:1900+y;
 }
 if(!Number.isInteger(y)||!Number.isInteger(m)||!Number.isInteger(d)||m<1||m>12||d<1||d>31)return null;
 const check=new Date(Date.UTC(y,m-1,d));
 if(check.getUTCFullYear()!==y||check.getUTCMonth()+1!==m||check.getUTCDate()!==d)return null;
 return String(y).padStart(4,'0')+'-'+String(m).padStart(2,'0')+'-'+String(d).padStart(2,'0');
}
const newest=(a,b)=>String(b?.dateISO||'').localeCompare(String(a?.dateISO||''));
const permitIsRoof=x=>x.kind==='ROOF_CANDIDATE_PENDING_DOCUMENT_REVIEW';
export function permitCardFacts(permits){
 const rows=Array.isArray(permits)?permits:[];
 const known=rows.map(p=>({...p,dateISO:calendarDate(p.issuedAt)}));
 known.sort((a,b)=>newest(a,b)||String(a.number).localeCompare(String(b.number)));
 const latest=known.find(x=>x.dateISO)||null;
 const roof=known.filter(permitIsRoof);
 const latestRoof=roof.find(x=>x.dateISO)||null;
 return {
  count:known.length,
  latestDate:latest?.dateISO||null,
  latestNumber:latest?.number||null,
  latestKind:latest?.kind||null,
  reroofCandidateDate:latestRoof?.dateISO||null,
  reroofCandidateNumber:latestRoof?.number||null,
  roofPermitCandidateCount:roof.length,
  sourceLevel:known.length?'CITY_REPORT_EXPORT_NOT_ORIGINAL_DOCUMENT':'NO_MATCH_IN_PARTIAL_EXPORTS',
  fullHistoryVerified:false,finalInspectionVerified:false,
  verifiedRoofReplacementDate:null,
  note:known.length?'City public-report candidate; source document and final inspection not reviewed':'No match in imported report windows; complete City history unknown'
 };
}
export function stormCardFacts(storms,sourceReady=false){
 const source=Array.isArray(storms)?storms:[];
 const known=source.map(s=>({...s,dateISO:calendarDate(s.sortKey||s.date)}))
  .filter(x=>x.dateISO&&Number.isFinite(x.distanceKm)&&x.distanceKm>=0);
 known.sort((a,b)=>newest(a,b)||a.distanceKm-b.distanceKm);
 const latest=known[0]||null;
 const strongestHail=known.filter(x=>x.kind==='HAIL'&&Number.isFinite(x.hailInches))
  .sort((a,b)=>b.hailInches-a.hailInches||newest(a,b))[0]||null;
 const strongestWind=known.filter(x=>Number.isFinite(x.windMph))
  .sort((a,b)=>b.windMph-a.windMph||newest(a,b))[0]||null;
 return {
  nearbyCount:known.length,
  latestDate:latest?.dateISO||null,latestType:latest?.kind||null,
  latestDistanceKm:latest?.distanceKm??null,
  latestHailInches:latest?.hailInches??null,
  latestWindMph:latest?.windMph??null,
  latestEventId:latest?.id||null,
  maxNearbyHailInches:strongestHail?.hailInches??null,
  maxNearbyHailDate:strongestHail?.dateISO||null,
  maxNearbyWindMph:strongestWind?.windMph??null,
  sourceLevel:sourceReady?'NOAA_REPORTED_POINT_NEARBY_NOT_PROPERTY_IMPACT':'NOAA_FEED_NOT_PUBLISHED',
  propertyImpactVerified:false,
  note:known.length?'NOAA observation reported near this parcel, not a verified storm track or roof strike':
    sourceReady?'No nearby point report in imported years; storms are not ruled out':'Storm archive unavailable'
 };
}
export function roofReviewNeeds({yearBuilt,permitFacts,stormFacts,sourceImageryVerified=false}){
 const needs=[];
 // These are actionable research needs, not observed damage, roof age, or repairs.
 if(permitFacts?.roofPermitCandidateCount>0)needs.push({code:'ISSUER_FINAL',label:'Verify reroof scope and final inspection',type:'permit'});
 else needs.push({code:'PERMIT_HISTORY',label:'Find complete roofing permit history',type:'permit'});
 needs.push({code:'ROOF_AGE',label:'Verify actual roof installation/replacement date',type:'records'});
 if(stormFacts?.nearbyCount>0)needs.push({code:'STORM_PROXIMITY',label:'Review dated nearby storm reports for applicability',type:'weather'});
 needs.push({code:'INSPECTION',label:'Obtain dated roof-condition inspection',type:'inspection'});
 if(!sourceImageryVerified)needs.push({code:'IMAGERY_SOURCE',label:'Verify authorized current roof imagery',type:'imagery'});
 const constructionYear=Number.isInteger(yearBuilt)&&yearBuilt>=1800&&yearBuilt<=2100?yearBuilt:null;
 return {
  status:'ROOF_CONDITION_UNKNOWN_NEEDS_REVIEW',
  headline:permitFacts?.roofPermitCandidateCount>0?'Review reported reroof permit and inspection':
    stormFacts?.nearbyCount>0?'Review storm proximity and inspect roof':'Document roof age and condition',
  needs,yearBuilt:constructionYear,roofInstallYear:null,
  roofAgeYears:null,roofReplacementRequired:null,
  roofRepairRequired:null,damageDetected:false,conditionCertified:false,
  note:'Construction year is not roof age. Reported storms and permits cannot establish physical damage, repair or replacement.'
 };
}
