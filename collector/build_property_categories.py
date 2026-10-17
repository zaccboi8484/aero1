#!/usr/bin/env python3
"""AeroLeadAI property intelligence category engine: roof, tree, driveway.
Emits factual work queues from actual 60 GIS parcels; does NOT infer defects
without source imagery or professional review. Re-runnable, deterministic IDs.
"""
import csv, json, pathlib, hashlib, datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]/"evidence"/"data"
UTC=datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(name,default):
 try:return json.loads((ROOT/name).read_text(encoding="utf-8"))
 except (OSError,ValueError):return default
with (ROOT/"kingswood_parcel_candidates.csv").open(encoding="utf-8-sig",newline="") as f:
 parcels=list(csv.DictReader(f))
manifest=read("imagery_manifest.json",{})
views={str(x.get("parcel_objectid")):x for x in manifest.get("records",[])}
down=read("imagery_downloads.json",{})
downloads={str(x.get("parcel_objectid")):x for x in down.get("records",[])}
probe=read("imagery_source_probe.json",{})
remotes={str(x.get("parcel_objectid")):x for x in probe.get("records",[])}
progress=read("progressive_search_status.json",{})
audits={str(x.get("parcel_objectid")):x for x in progress.get("properties",[])}
POLICY={
 "roofing":{"label":"Roofing","aerial_can_support":["roof outline","major visible roof anomalies at sufficient resolution"],"cannot_confirm":["leaks","hail damage","roof replacement need","roof age"],"requires":["valid aerial capture","municipal permits","dated inspection or qualified review"]},
 "tree_service":{"label":"Tree service","aerial_can_support":["canopy proximity to structures","large canopy changes between dated images"],"cannot_confirm":["hazardous tree","disease","root damage","fall risk"],"requires":["valid aerial capture","dated comparative imagery","arborist assessment for hazard claims"]},
 "cracked_driveway":{"label":"Cracked driveway","aerial_can_support":["driveway footprint","apparent paving material at high resolution"],"cannot_confirm":["fine cracks","trip risk","subsurface defects"],"requires":["valid close-range photograph or inspection","reviewed condition evidence"]}
}
result=[]
for row in parcels:
 oid=str(row.get("parcel_objectid") or "")
 if not oid or not row.get("county_pin"):continue
 image=downloads.get(oid,{})
 remote=remotes.get(oid,{})
 image_ok=(image.get("status")=="DOWNLOADED" and bool(image.get("sha256")))
 remote_ok=remote.get("status")=="REMOTE_IMAGE_AVAILABLE" and bool(remote.get("sha256"))
 view=views.get(oid,{})
 checks={x.get("search_id"):x.get("status") for x in audits.get(oid,{}).get("checks",[])}
 cats={}
 for key,policy in POLICY.items():
  card={"category":key,"label":policy["label"],"evidence_status":"IMAGE_ACQUIRED_PENDING_REVIEW" if image_ok else ("REMOTE_IMAGE_AVAILABLE_PENDING_REVIEW" if remote_ok else "AWAITING_IMAGE_AND_REVIEW"),
    "finding":"UNKNOWN","opportunity_score":None,"damage_confirmed":False,
    "required_sources":policy["requires"],"aerial_observables":policy["aerial_can_support"],
    "not_provable_by_aerial":policy["cannot_confirm"],
    "image_request_url":(view.get("image_layers") or {}).get("2025-spring-leaf-off"),
    "imagery_acquisition":image.get("status","NOT_ATTEMPTED"),"remote_image_available":remote_ok,
    "remote_image_sha256":remote.get("sha256") if remote_ok else None,
    "remote_image_url":remote.get("image_link") if remote_ok else None,
    "municipal_permit_status":checks.get("permit","UNKNOWN"),
    "next_action":("Acquire authorized source image and qualified review" if key!="cracked_driveway" else "Acquire a close-up photo or inspection; overhead imagery rarely proves cracks")}
  cats[key]=card
 record={"parcel_objectid":oid,"county_pin":row["county_pin"],"address":row["address"],"identity_source":row.get("source_record_url"),
    "gatekeeper":{"identity":"OFFICIAL_GIS_SOURCE_RECORDED","conditions":"NOT_VERIFIED","review_complete":False},
    "categories":cats}
 record["integrity_sha256"]=hashlib.sha256(json.dumps(record,sort_keys=True,separators=(",",":")).encode()).hexdigest()
 result.append(record)
payload={"created_utc":UTC,"engine":"AeroLeadAI Property Categories v1","records":result,"categories":list(POLICY),
 "count":len(result),"confirmed_conditions":0,"policy":"Unknown is not no damage; source imagery URL does not mean an image was acquired."}
(ROOT/"property_category_intelligence.json").write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"cards":len(result),"categories":list(POLICY),"reviewed_findings":0}))
