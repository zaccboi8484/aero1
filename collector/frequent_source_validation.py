#!/usr/bin/env python3
"""15-minute AeroLeadAI source verification: official parcels, regional permits,
municipal public Open Data availability and MN government aerial JPEG signatures.

Each run checks a bounded rotating batch, persists a cursor and per-parcel
outcomes. This is a real network request pipeline, not a mocked completion flag.
No Eagan auth bypass and no Google imagery scraping or image analysis.
"""
import argparse,csv,datetime as dt,hashlib,json,pathlib,re,time,urllib.parse,urllib.request,urllib.error
D=pathlib.Path(__file__).resolve().parents[1]/"evidence"/"data"
GIS="https://arcgis.metc.state.mn.us/data1/rest/services/parcels/Parcels_2025/FeatureServer/2/query"
PERMITS="https://arcgis.metc.state.mn.us/server/rest/services/EnterpriseLibrary/DTATResidentialPermits/FeatureServer/0/query"
EAGAN="https://eagan.onlama.com/Dashboard.aspx"
WMS="https://imageserver.gisdata.mn.gov/cgi-bin/wmsll"
def fetch(url,limit=2_500_000):
 req=urllib.request.Request(url,headers={"User-Agent":"AeroLeadAI-GateKeeper-Research/1.1 (bounded, authorized public-source queries)","Accept":"application/json,text/html,image/jpeg,*/*"})
 with urllib.request.urlopen(req,timeout=17) as res:
  content=res.read(limit+1)
  if len(content)>limit:raise ValueError("Source response exceeded allowed size")
  return content,res.headers.get("Content-Type",""),res.status
def norm(s):
 x=re.sub(r"[^A-Z0-9 ]"," ",str(s or "").upper())
 for a,b in (("ROAD","RD"),("LANE","LN"),("COURT","CT"),("DRIVE","DR"),("AVENUE","AVE"),("STREET","ST")):x=re.sub(r"\b"+a+r"\b",b,x)
 return " ".join(x.split())
def js(url):
 payload,_,_=fetch(url)
 d=json.loads(payload)
 if "error" in d:raise ValueError("ArcGIS query error: "+str(d["error"])[:160])
 return d
def classify_regional_query(payload,address,page_size=120):
 """Fail closed: a truncated ArcGIS page cannot justify a no-match finding."""
 features=payload.get("features",[])
 if not isinstance(features,list):raise ValueError("ArcGIS features must be a list")
 valid=[x.get("attributes",{}) for x in features if norm(x.get("attributes",{}).get("ADDRESS"))==norm(address)]
 incomplete=bool(payload.get("exceededTransferLimit")) or len(features)>=page_size
 status="REGIONAL_QUERY_INCOMPLETE" if incomplete else ("PENDING_SOURCE_RECORD_REVIEW" if valid else "NO_MATCH_IN_REGIONAL_SOURCE")
 return status,valid

def load(name,default):
 try:return json.loads((D/name).read_text(encoding="utf-8"))
 except (FileNotFoundError,ValueError):return default
def jpeg(data):
 return len(data)>150 and data[:3]==b"\xff\xd8\xff" and data[-2:]==b"\xff\xd9"
def select_research_batch(rows,saved,cursor,batch):
 """Prefer never-researched official parcels, then resume the stable rotating sweep.
 No PIN can appear twice in a batch, and the prior 60 are not a global cap.
 """
 if not rows:return [],0,0
 limit=min(len(rows),max(1,batch))
 unseen=[x for x in rows if str(x["county_pin"]) not in saved]
 chosen=unseen[:limit]
 selected={str(x["county_pin"]) for x in chosen}
 start=cursor%len(rows)
 walked=0
 while len(chosen)<limit and walked<len(rows):
  candidate=rows[(start+walked)%len(rows)]
  walked+=1
  key=str(candidate["county_pin"])
  if key not in selected:
   chosen.append(candidate);selected.add(key)
 next_cursor=(start+walked)%len(rows)
 return chosen,next_cursor,len(unseen)

def execute(no_network=False,batch=8,deadline_seconds=480):
 with (D/"kingswood_parcel_candidates.csv").open(newline="",encoding="utf-8-sig") as f:seed=list(csv.DictReader(f))
 ring=load("outward_ring_candidates.json",{}).get("ring_candidates",[])
 allrows=seed+[{"parcel_objectid":str(p.get("parcel_objectid")),"county_pin":p.get("county_pin"),
     "address":p.get("address"),"origin":"NEW_GIS_RING"} for p in ring]
 allrows=[x for x in allrows if x.get("county_pin") and x.get("address")]
 # Deduplicate by PIN, with original 60 taking precedence.
 dedup={};[dedup.setdefault(str(r["county_pin"]),r) for r in allrows]
 rows=list(dedup.values())
 state=load("fast_validation_cursor.json",{"cursor":0})
 old_cursor=int(state.get("cursor") or 0)%max(1,len(rows))
 now=dt.datetime.now(dt.timezone.utc).isoformat()
 history=load("fast_validation_report.json",{}).get("records",[])
 active_pins={str(x["county_pin"]) for x in rows}
 # Preserve prior verified records even if yesterday's search ring moved or shrank.
 # Only the currently indexed PINs contribute to active coverage statistics.
 saved={str(x.get("county_pin")):x for x in history if x.get("county_pin")}
 active_saved={pin:x for pin,x in saved.items() if pin in active_pins}
 batchrows,next_cursor,initial_unchecked=select_research_batch(rows,active_saved,old_cursor,batch)
 started=time.monotonic()
 attempted=0
 manifest=load("imagery_manifest.json",{}).get("records",[])
 boxes={str(x.get("parcel_objectid")):x.get("bbox_4326") for x in manifest}
 # Expanded official GIS polygon-envelope windows. Not inferred roofs or parcel damage.
 for x in ring:
  bbox=x.get("bbox_4326")
  if (isinstance(bbox,list) and len(bbox)==4 and all(isinstance(v,(int,float)) for v in bbox)
      and bbox[0]<bbox[2] and bbox[1]<bbox[3]):
   boxes[str(x.get("parcel_objectid"))]=bbox
 region={} # new official GIS ring envelopes can also request permitted government WMS sources
 errors=[]
 if no_network:errors.append("Offline mode: no source requests executed")
 if not no_network:
  for r in batchrows:
   if attempted>0 and time.monotonic()-started>=deadline_seconds:
    errors.append("Research time budget reached; unattempted parcels remain queued")
    break
   attempted+=1
   oid=str(r.get("parcel_objectid"));pin=str(r["county_pin"])
   response={"parcel_objectid":oid,"county_pin":pin,"address":r["address"],
    "last_checked_utc":now,"parcel_validation":"NOT_QUERIED","municipal_permits":"NOT_QUERIED",
    "regional_permits":"NOT_QUERIED","imagery":"NOT_QUERIED"}
   try:
    uri=GIS+"?"+urllib.parse.urlencode({"f":"json","where":"COUNTY_PIN='"+pin.replace("'","''")+"'",
      "outFields":"OBJECTID,COUNTY_PIN,ANUMBER,ST_NAME,ST_POS_TYP,CTU_NAME","returnGeometry":"false","resultRecordCount":6})
    features=js(uri).get("features",[])
    confirmed=[x.get("attributes",{}) for x in features if str(x.get("attributes",{}).get("COUNTY_PIN"))==pin]
    response["parcel_validation"]="OFFICIAL_PIN_CONFIRMED" if len(confirmed)==1 else ("GIS_NO_MATCH" if not confirmed else "GIS_AMBIGUOUS_PIN")
    response["parcel_source_url"]=uri
   except Exception as e:response["parcel_validation"]="GIS_SOURCE_ERROR";response["parcel_error"]=str(e)[:160]
   try:
    addr=r["address"].split(",")[0]
    house=addr.split(" ",1)[0];street=addr.split(" ",1)[1] if " " in addr else ""
    prefix=street.split(" ")[0]
    # Official regional permit layer queried for the CURRENT parcel's house number and street.
    # It may cover new construction only; lack of a result never certifies zero Eagan roof permits.
    clauses=["UPPER(CTU_NAME)='EAGAN'","UPPER(ADDRESS) LIKE '%"+house.replace("'","''")+"%'",
             "UPPER(ADDRESS) LIKE '%"+prefix.replace("'","''")+"%'"]
    uri=PERMITS+"?"+urllib.parse.urlencode({"f":"json","where":" AND ".join(clauses),
      "outFields":"OBJECTID,ADDRESS,YEAR,RES_PERMIT_TYPE,PERMIT_VALUE","returnGeometry":"false",
      "resultRecordCount":120})
    response["regional_permits"],valid=classify_regional_query(js(uri),addr)
    response["regional_permit_count"]=len(valid)
    response["regional_query_complete"]=response["regional_permits"]!="REGIONAL_QUERY_INCOMPLETE"
    response["regional_source_url"]=uri
    response["regional_record_ids"]=[str(x.get("OBJECTID")) for x in valid][:30]
   except Exception as e:response["regional_permits"]="REGIONAL_QUERY_ERROR";response["regional_error"]=str(e)[:160]
   box=boxes.get(oid)
   if box and len(box)==4:
    image_errors=[]
    # Prefer the newest published high-resolution metro flight (2025). The
    # 2023 Dakota 6-inch service is a documented fallback, never a fake 2025.
    for layer,year in (("met25",2025),("dak23",2023)):
     try:
      url=WMS+"?"+urllib.parse.urlencode({"SERVICE":"WMS","VERSION":"1.1.1","REQUEST":"GetMap","LAYERS":layer,"STYLES":"","SRS":"EPSG:4326","BBOX":",".join(map(str,box)),"WIDTH":800,"HEIGHT":620,"FORMAT":"image/jpeg"})
      body,mime,_=fetch(url)
      if not jpeg(body):
       image_errors.append(layer+": response was not a valid JPEG");continue
      response["imagery"]="GOVERNMENT_REMOTE_JPEG_VERIFIED"
      response["imagery_sha256"]=hashlib.sha256(body).hexdigest()
      response["imagery_source_url"]=url
      response["imagery_content_type"]=mime
      response["imagery_layer"]=layer
      response["imagery_year"]=year
      response["imagery_verified_bytes"]=len(body)
      break
     except Exception as e:image_errors.append(layer+": "+str(e)[:120])
    if response["imagery"]!="GOVERNMENT_REMOTE_JPEG_VERIFIED":
     response["imagery"]="IMAGE_SOURCE_ERROR"
    if image_errors:response["imagery_attempts_failed"]=image_errors
   else:response["imagery"]="NO_BOUNDING_BOX_YET"
   saved[pin]=response
  try:
   body,mime,status=fetch(EAGAN,limit=250000)
   text=body.decode("utf-8","ignore")
   municipal={"status":"PUBLIC_OPEN_DATA_PAGE_REACHABLE" if "Open Data" in text else "PUBLIC_REPORT_PAGE_UNEXPECTED",
      "source_url":EAGAN,"http_status":status,"checked_utc":now,
      "note":"This only establishes report portal availability; no per-address municipal permit history was retrieved"}
  except Exception as e:
   municipal={"status":"PUBLIC_SOURCE_UNAVAILABLE","source_url":EAGAN,"checked_utc":now,
      "error":str(e)[:160],"note":"Do not bypass access restrictions"}
 else:
  municipal={"status":"NOT_QUERIED_OFFLINE","source_url":EAGAN}
 checked_total=sum(pin in saved for pin in active_pins)
 out={"run_utc":now,"interval_target_minutes":15,"total_indexed":len(rows),
   "batch_requested":len(batchrows),"batch_attempted":0 if no_network else attempted,
   "checked_total":checked_total,"remaining_unchecked":max(0,len(rows)-checked_total),
   "archived_pins_outside_active_geographic_discovery":max(0,len(saved)-checked_total),
   "unseen_at_run_start":initial_unchecked,
   "research_deadline_seconds":deadline_seconds,
   "next_cursor":next_cursor if not no_network else old_cursor,
   "records":[saved[x] for x in sorted(saved)],"municipal_permit_source":municipal,
   "errors":errors,"source_checks_not_property_damage_certification":True}
 D.mkdir(parents=True,exist_ok=True)
 (D/"fast_validation_report.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
 (D/"fast_validation_cursor.json").write_text(json.dumps({"cursor":out["next_cursor"],"updated_at_utc":now},indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"indexed":out["total_indexed"],"checked_this_run":out["batch_attempted"],"unique_checked":len(saved),
     "images_verified":sum(x.get("imagery")=="GOVERNMENT_REMOTE_JPEG_VERIFIED" for x in saved.values()),
     "municipal_portal":municipal["status"],"next_cursor":out["next_cursor"]}))
 return out
if __name__=="__main__":
 a=argparse.ArgumentParser()
 a.add_argument("--no-network",action="store_true")
 a.add_argument("--batch",type=int,default=24)
 a.add_argument("--deadline-seconds",type=int,default=480)
 x=a.parse_args()
 execute(x.no_network,max(1,min(x.batch,24)),max(60,min(x.deadline_seconds,570)))
