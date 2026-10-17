#!/usr/bin/env python3
"""AeroLeadAI GateKeeper roof evidence scoring v1.0.

Two DISTINCT values:
 * data_review_priority (0-100): ordered evidence-acquisition queue, NOT damage.
 * roof_condition_score (0-100 or None): only after authenticated, source-supported
   close-range observation / human review. An aerial-only observation is insufficient.

Never import Google Maps imagery into an automated image analysis or model workflow.
Original photographic reference: IBHS 'Is It Hail Damage?' photo guide.
"""
import argparse,csv,datetime as dt,hashlib,json,pathlib,re
from urllib.parse import urlparse

D=pathlib.Path(__file__).resolve().parents[1]/"evidence"/"data"
INDICATORS={
 "missing_shingles":(28,"wind / roof covering"),
 "exposed_decking":(38,"high-concern roof covering"),
 "lifted_or_creased_shingles":(20,"wind / roof covering"),
 "broken_ridge_caps":(16,"ridge covering"),
 "torn_shingle_mat":(28,"close-up damage"),
 "random_pattern_hail_bruises":(20,"close-up hail candidate"),
 "flashing_damage":(15,"metal / flashing"),
 "collateral_metal_dents":(12,"supporting hail context"),
 "isolated_granule_loss":(5,"possible normal wear"),
 "water_intrusion_observed":(22,"confirmed symptom"),
}
LOOKALIKES={"normal_granule_weathering","manufacturing_defect","blistering",
 "foot_traffic_scuff","installation_mark","tree_shadow","seasonal_vegetation"}
PROHIBITED_HOSTS={"google.com","maps.google.com","earth.google.com","googleapis.com",
 "mt0.google.com","mt1.google.com","maps.googleapis.com"}
REFERENCE={"issuer":"Insurance Institute for Business & Home Safety",
 "document":"Is It Hail Damage? (photo comparison)",
 "source_url":"https://ibhs.org/wp-content/uploads/member_docs/Is-It-Hail-Damage-Brochure_IBHS.pdf",
 "verified_guidance":"Random hail impact patterns and ridge cap damage vs weathering, blisters and mechanical marks"}

def read(name,default=None):
 try:return json.loads((D/name).read_text(encoding="utf-8"))
 except (FileNotFoundError,ValueError):return {} if default is None else default
def stamp(value):
 try:
  result=dt.datetime.fromisoformat(str(value).replace("Z","+00:00"))
  if result.tzinfo is None:return None
  if result>dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=1):return None
  return result
 except (TypeError,ValueError):return None
def permitted_source(obs):
 url=obs.get("source_url") or ""
 parsed=urlparse(url)
 if parsed.scheme!="https" or not parsed.hostname:return False
 host=parsed.hostname.lower()
 if any(host==x or host.endswith("."+x) for x in PROHIBITED_HOSTS):return False
 if obs.get("source_type")=="USER_UPLOADED":
  return bool(obs.get("consent_to_process") is True and obs.get("image_sha256"))
 return host.endswith(".mn.gov") or host in ("gisimg.co.dakota.mn.us",
      "imageserver.gisdata.mn.gov","gis.co.dakota.mn.us")
def inspect_observation(obs, trusted_hashes):
 """Independent provenance checks, not a self-declared VERIFIED string."""
 if not isinstance(obs,dict):return ["INVALID_OBSERVATION"]
 failures=[]
 sha=obs.get("image_sha256")
 if not re.fullmatch(r"[a-fA-F0-9]{64}",str(sha or "")):failures.append("IMAGE_SHA256_REQUIRED")
 if not permitted_source(obs):failures.append("SOURCE_RIGHTS_OR_DOMAIN_NOT_APPROVED")
 if sha not in trusted_hashes:
  failures.append("IMAGE_HASH_NOT_IN_COLLECTOR_LEDGER")
 if obs.get("source_type") not in ("USER_UPLOADED","MN_GOV","DAKOTA_COUNTY"):
  failures.append("SOURCE_TYPE_UNSUPPORTED")
 if not stamp(obs.get("capture_date")):failures.append("DATED_IMAGE_REQUIRED")
 if not obs.get("roof_region_reviewed"):failures.append("ROOF_BOUNDARY_REVIEW_REQUIRED")
 if not obs.get("reviewer_id") or not stamp(obs.get("reviewed_at")):
  failures.append("DATED_REVIEWER_ATTESTATION_REQUIRED")
 if obs.get("view") not in ("CLOSE_RANGE","INSPECTION","AERIAL"):
  failures.append("IMAGE_VIEW_UNSPECIFIED")
 if obs.get("source_type") in ("MN_GOV","DAKOTA_COUNTY") and obs.get("view")!="AERIAL":
  failures.append("ORTHOPHOTO_CANNOT_BE_CLOSE_RANGE")
 indicators=obs.get("indicators",[])
 if not isinstance(indicators,list) or any(x not in INDICATORS for x in indicators):
  failures.append("UNRECOGNIZED_ROOF_INDICATOR")
 if not isinstance(obs.get("lookalikes",[]),list) or any(x not in LOOKALIKES for x in obs.get("lookalikes",[])):
  failures.append("UNRECOGNIZED_LOOKALIKE")
 return failures
def score_roof(obs,hashes):
 failures=inspect_observation(obs,hashes)
 if failures:return {"roof_condition_score":None,"status":"REVIEW_EVIDENCE_REJECTED","issues":failures,"confidence":0}
 if obs["view"]=="AERIAL":
  return {"roof_condition_score":None,"status":"AERIAL_ONLY_CONDITION_NOT_SCORABLE",
    "issues":["Aerial source can reveal gross features/change, not shingle bruising, granule loss or cracking"],"confidence":25}
 positive=set(obs.get("indicators",[]))
 lookalikes=set(obs.get("lookalikes",[]))
 raw=sum(INDICATORS[k][0] for k in positive)
 if lookalikes:raw=max(0,raw-20*len(lookalikes))
 score=min(100,raw)
 quality=90 if obs["view"]=="INSPECTION" else 75
 if lookalikes:quality=max(35,quality-15*len(lookalikes))
 if "random_pattern_hail_bruises" in positive and "collateral_metal_dents" not in positive:
  quality=min(quality,65)
 return {"roof_condition_score":score,"status":"REVIEWED_ROOF_EVIDENCE_SCORE",
   "confidence":quality,"indicators":sorted(positive),"lookalikes":sorted(lookalikes),
   "caveat":"Provisional field-condition index, not certified hail attribution, replacement directive or insurance estimate"}
def priority(parcel,progress,has_photo,has_permit,has_assessment):
 year=int(parcel.get("year_built") or 0)
 signals={"missing_usable_imagery":not has_photo,
          "municipal_permit_evidence_missing":not has_permit,
          "roof_age_unknown":True,
          "valuation_unavailable":not has_assessment,
          "building_constructed_before_2000":0<year<2000}
 weights={"missing_usable_imagery":30,"municipal_permit_evidence_missing":25,
          "roof_age_unknown":20,"valuation_unavailable":10,
          "building_constructed_before_2000":15}
 total=sum(weights[k] for k,v in signals.items() if v)
 return {"data_review_priority":min(100,total),"priority_factors":[k for k,v in signals.items() if v],
         "status":"EVIDENCE_COMPLETION_PRIORITY_ONLY","not_a_damage_score":True}
def run():
 with (D/"kingswood_parcel_candidates.csv").open(newline="",encoding="utf-8-sig") as f:parcels=list(csv.DictReader(f))
 observations=read("roof_observations.json").get("records",[])
 by_id={str(x.get("parcel_objectid")):x for x in observations if isinstance(x,dict)}
 mn=read("mngeo_aerial_evidence.json");other=read("imagery_source_probe.json")
 photo=set()
 trusted={}
 for feed,rows,status in ((mn,mn.get("records",[]),"REMOTE_IMAGE_VERIFIED"),(other,other.get("records",[]),"REMOTE_IMAGE_AVAILABLE")):
  for row in rows:
   oid=str(row.get("parcel_objectid",""))
   for element in ([row]+list((row.get("layers") or {}).values())):
    if element.get("status")==status and re.fullmatch(r"[0-9a-fA-F]{64}",str(element.get("sha256") or "")):
     photo.add(oid);trusted.setdefault(oid,set()).add(element["sha256"])
 permits=read("permit_match_review.json");permit_ids={
  str(x.get("parcel_objectid")) for x in permits.get("records",[])
  if x.get("review_status")=="REVIEWED" and x.get("source_record_id")}
 vals=read("live_property_enrichment.json")
 upload_manifest=read("trusted_uploaded_photo_ledger.json")
 for_photo=upload_manifest.get("records",[])
 for u in for_photo:
  oid=str(u.get("parcel_objectid",""))
  if u.get("file_sha256_verified") is True and re.fullmatch(r"[0-9a-fA-F]{64}",str(u.get("image_sha256") or "")):
   trusted.setdefault(oid,set()).add(u["image_sha256"])
 assessed={str(x.get("parcel_objectid")) for x in vals.get("records",[])
           if x.get("valuation",{}).get("gatekeeper")=="SOURCE_RECORDED"}
 audit=read("progressive_search_status.json")
 audit_ids={str(x.get("parcel_objectid")):x for x in audit.get("properties",[])}
 results=[]
 for p in parcels:
  oid=str(p["parcel_objectid"])
  item={"parcel_objectid":oid,"county_pin":p["county_pin"],"address":p["address"],
    "review":priority(p,audit_ids.get(oid,{}),oid in photo,oid in permit_ids,oid in assessed),
    "roof":{"roof_condition_score":None,"status":"NOT_SCORED_NO_ROOF_EVIDENCE","confidence":0}}
  if oid in by_id:item["roof"]=score_roof(by_id[oid],trusted.get(oid,set()))
  results.append(item)
 result={"generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
   "count":len(results),"priority_scored":len(results),
   "reviewed_roof_condition_scores":sum(x["roof"]["status"]=="REVIEWED_ROOF_EVIDENCE_SCORE" for x in results),
   "reference":REFERENCE,"no_legacy_leads_merged":True,
   "note":"The 0-100 DATA REVIEW PRIORITY reflects missing evidence, not roof damage or Mindex.",
   "records":results}
 (D/"roof_evidence_scores.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({k:result[k] for k in ("count","priority_scored","reviewed_roof_condition_scores")}))
 return result
if __name__=="__main__":run()
