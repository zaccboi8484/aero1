#!/usr/bin/env python3
"""GateKeeper: source-directed, fail-closed certification gap search planner.

This is a *real* evidence JOIN and an actionable research queue, not a simulator,
not an inspection and not an independent permit-document verification. Existing
official-source crawler outputs remain the evidence of record; search pathways
are permission-aware and never bypass the Eagan 403 portal restriction.

Produces three nonsecret machine-readable files under evidence/data:
  certification_gap_summary.json   compact source coverage / release blockers
  certification_gap_queue.json     original-60, parcel-keyed tasks
  permit_issuer_review_queue.csv   real issuer-document requests for 25 matches

A change in input identity, contradictory permit ownership or duplicate issuer
record fails before any "complete" status can be published.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import io
import json
import pathlib
import re
from urllib.parse import urlsplit

ROOT = pathlib.Path(__file__).resolve().parents[1]
D = ROOT / "evidence" / "data"
REVIEW_STATES = {"OPEN", "SOURCE_BLOCKED", "EVIDENCE_ATTACHED_PENDING_HUMAN_REVIEW",
                 "AWAITING_AUTHORIZED_PROVIDER", "AWAITING_HUMAN_EVIDENCE"}
SOURCE_CATALOG = (
  {"key":"eagan_open_data", "authority":"City of Eagan", "category":"municipal_report",
   "url":"https://eagan.onlama.com/Dashboard.aspx", "mode":"AUTHORIZED_PUBLIC_EXPORT",
   "capability":"Monthly, prior-year, open and 90-day building permit reports; portal search supports batches of up to 200 CSV rows",
   "public_csv_export_limit":200, "full_history_guaranteed":False,
   "documentation":"https://eagan.onlama.com/Help.aspx"},
  {"key":"eagan_issuer_documents", "authority":"City of Eagan", "category":"original_issuer_permit",
   "url":"https://eagan.onlama.com/Search.aspx", "mode":"HUMAN_OR_AUTHORIZED_SERVICE",
   "capability":"Permit number and situs address lookup; logged-in permit holder can view attachments and inspection results",
   "full_history_guaranteed":False,
   "documentation":"https://www.eaganmn.gov/permithandouts"},
  {"key":"eagan_government_data", "authority":"City of Eagan", "category":"formal_public_data_request",
   "url":"https://www.eaganmn.gov/buildinginspections", "mode":"FORMAL_REQUEST",
   "capability":"Existing public permit, scope, issue, inspection and closure records under Minnesota Statutes Chapter 13",
   "full_history_guaranteed":False,
   "documentation":"https://mn.gov/admin/data-practices/data/requests/"},
  {"key":"eagan_official_gis", "authority":"City of Eagan", "category":"assessment",
   "url":"https://gis.cityofeagan.com/arcgis/rest/services/EA_PropertyInformation/MapServer/19",
   "mode":"AUTHORIZED_PUBLIC_ARCGIS", "capability":"Tax PIN, house number, value and year-built source attributes; assessment year is not in current published result",
   "full_history_guaranteed":False},
  {"key":"mn_address_points", "authority":"Metropolitan Council / MN GIS", "category":"address",
   "url":"https://arcgis.metc.state.mn.us/server/rest/services/GISLibrary/VWAddressPointsCommons/FeatureServer/0",
   "mode":"AUTHORIZED_PUBLIC_ARCGIS", "capability":"Published GIS addresses, distinct from USPS deliverability",
   "full_history_guaranteed":False},
  {"key":"mngeo_2025_wms", "authority":"Minnesota Geospatial Information Office", "category":"imagery",
   "url":"https://imageserver.gisdata.mn.gov/cgi-bin/wmsll",
   "mode":"REMOTE_VIEW_RIGHTS_REVIEW", "capability":"2025 7-county aerial JPEG GetMap; view-only source observation is not a condition report or redistribution grant",
   "full_history_guaranteed":False,
   "documentation":"https://mn.gov/mngeo/gis-data-and-maps/web-map-services/mngeo-image-service/technical.jsp"},
  {"key":"regional_residential_permits", "authority":"Metropolitan Council", "category":"regional_context",
   "url":"https://arcgis.metc.state.mn.us/server/rest/services/EnterpriseLibrary/DTATResidentialPermits/FeatureServer/0",
   "mode":"AUTHORIZED_PUBLIC_ARCGIS", "capability":"Regional residential permit dataset, not Eagan roofing permit history",
   "full_history_guaranteed":False}
)

def read_json(d, name, *, required=False):
    path=d/name
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data,dict): raise ValueError("JSON root must be object")
        return data
    except (OSError, ValueError) as exc:
        if required:raise ValueError(f"Required evidence {name} unavailable or invalid: {exc}") from exc
        return {}

def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def normal(value):
    return re.sub(r"\s+"," ",re.sub(r"[^A-Z0-9 ]"," ",str(value or "").upper())).strip()

def id_for(kind,oid,source_record_id=""):
    return "GK-"+hashlib.sha256((kind+"\x1f"+oid+"\x1f"+source_record_id).encode()).hexdigest()[:18]

def safe_source(value):
    try:
        u=urlsplit(str(value or ""))
        return u.scheme=="https" and not u.username and not u.password and u.hostname in {
            "eagan.onlama.com","www.eaganmn.gov","eaganmn.gov",
            "gis.cityofeagan.com","arcgis.metc.state.mn.us",
            "imageserver.gisdata.mn.gov","mn.gov"}
    except ValueError:
        return False

def task(tasks, *, kind, parcel, status, authority, source_url, priority, action,
         requirements, source_record_id="", automatable=False, evidence_stage="NOT_VERIFIED"):
    assert status in REVIEW_STATES, f"Invalid research state {status}"
    assert safe_source(source_url), f"Not an approved public source: {source_url!r}"
    oid=str(parcel["parcel_objectid"])
    key=id_for(kind,oid,source_record_id)
    tasks.append({
        "task_id":key,
        "kind":kind, "priority":int(priority), "parcel_objectid":oid,
        "county_pin":str(parcel["county_pin"]), "address":parcel["address"],
        "authority":authority, "source_record_id":source_record_id or None,
        "official_source_url":source_url,"status":status, "evidence_stage":evidence_stage,
        "next_action":action, "requirements":requirements, "automatable_from_authorized_public_sources":bool(automatable),
        "human_issuer_or_professional_signoff_required":not bool(automatable),
        "completed":False, "source_evidence_sha256":None,
        "certification_approved":False
    })

def compile_gap_index(directory=D):
    with (directory/"kingswood_parcel_candidates.csv").open(encoding="utf-8-sig",newline="") as f:
        parcels=list(csv.DictReader(f))
    if len(parcels)!=60:raise ValueError("GateKeeper original residential inventory must remain exactly 60")
    by_oid={}
    by_pin={}
    for p in parcels:
        oid=str(p.get("parcel_objectid") or "")
        pin=str(p.get("county_pin") or "")
        if not oid or not pin or not p.get("address") or oid in by_oid or pin in by_pin:
            raise ValueError("Missing, ambiguous or duplicate canonical property identity")
        by_oid[oid]=p;by_pin[pin]=p
    exports=read_json(directory,"municipal_permit_export_audit.json",required=True)
    address=read_json(directory,"mn_address_validation.json",required=True)
    valuation=read_json(directory,"live_property_enrichment.json",required=True)
    imagery=read_json(directory,"imagery_source_availability.json",required=True)
    crawl=read_json(directory,"fast_validation_report.json",required=True)
    release=read_json(directory,"gatekeeper_release_truth.json",required=True)
    permit_rows=exports.get("records")
    if not isinstance(permit_rows,list):raise ValueError("Permit report rows must be a list")
    if len(permit_rows)!=int(exports.get("matched_permit_events",-1)):
        raise ValueError("Imported municipal permit event count is inconsistent")
    permit_keys=set()
    permits=collections.defaultdict(list)
    for row in permit_rows:
        if not isinstance(row,dict):raise ValueError("Invalid permit evidence row")
        oid=str(row.get("parcel_objectid") or "")
        number=str(row.get("permit_number") or "")
        if not number or oid not in by_oid or number in permit_keys:
            raise ValueError("Missing, conflicting or duplicate city permit identity")
        permit_keys.add(number);permits[oid].append(row)
    if len(permits)!=int(exports.get("properties_with_matches",-1)):
        raise ValueError("Imported municipal matching-property count is inconsistent")
    def mapping(rows,label):
        if not isinstance(rows,list):raise ValueError(label+" must be list")
        result={}
        for row in rows:
            if not isinstance(row,dict):raise ValueError(label+" contains invalid row")
            oid=str(row.get("parcel_objectid") or "")
            if oid in result:raise ValueError("Duplicate "+label+" parcel ID "+oid)
            if oid in by_oid:
                if row.get("county_pin") is not None and str(row.get("county_pin"))!=str(by_oid[oid]["county_pin"]):
                    raise ValueError("Contradictory "+label+" county PIN for "+oid)
                result[oid]=row
        return result
    address_by=mapping(address.get("records",[]),"address")
    value_by=mapping(valuation.get("records",[]),"valuation")
    image_by=mapping(imagery.get("records",[]),"imagery")
    portal=crawl.get("municipal_permit_source") or {}
    portal_blocked=isinstance(portal,dict) and portal.get("status")=="PUBLIC_SOURCE_UNAVAILABLE"
    tasks=[]
    parcel_evidence=[]
    for p in parcels:
        oid=str(p["parcel_objectid"])
        matches=sorted(permits.get(oid,[]), key=lambda v:str(v.get("permit_number")))
        address_ok=address_by.get(oid,{}).get("status")=="STATE_GIS_ADDRESS_MATCH"
        v=value_by.get(oid,{}).get("valuation") or {}
        value_ok=(v.get("gatekeeper")=="SOURCE_RECORDED" and
                  isinstance(v.get("amount_usd"),(int,float)) and v["amount_usd"]>=0 and
                  safe_source(v.get("source_url")))
        assessment_year=v.get("assessment_year") if value_ok else None
        year_proven=isinstance(assessment_year,int) and 1900<=assessment_year<=2100
        im=image_by.get(oid,{})
        image_ok=(im.get("source_status")=="REMOTE_GOVERNMENT_JPEG_LAST_VERIFIED"
                  and safe_source(im.get("source_url"))
                  and re.fullmatch("[a-f0-9]{64}",str(im.get("source_sha256") or ""),re.I) is not None)
        flags={
            "parcel_identity":"OFFICIAL_GIS_MATCH_IN_EXISTING_INDEX",
            "municipal_export_matches":len(matches),
            "permit_history_completeness":"UNKNOWN_NOT_INDEPENDENTLY_RECHECKED",
            "original_permit_issuer_documents_reviewed":0,
            "address_source_matched":bool(address_ok),
            "valuation_source_recorded":bool(value_ok),
            "valuation_assessment_year_verified":bool(year_proven),
            "government_image_response_hash_recorded":bool(image_ok),
            "imagery_commercial_redistribution_rights_verified":False,
            "roof_condition_human_reviewed":False,
            "mindex_certified":False
        }
        parcel_evidence.append({"parcel_objectid":oid, "county_pin":p["county_pin"],
                                "address":p["address"],"gates":flags})
        task(tasks,kind="MUNICIPAL_FULL_PERMIT_HISTORY",parcel=p,
             status="SOURCE_BLOCKED" if portal_blocked else "AWAITING_AUTHORIZED_PROVIDER",
             authority="City of Eagan",source_url="https://eagan.onlama.com/Search.aspx",priority=22 if matches else 37,
             action="Obtain and inspect issuer-maintained complete address/parcel permit history, not only monthly/public export subsets",
             requirements=["issuer-provided address/PIN history","searched date span and authoritative completeness/coverage","document record references","human reviewer approval"])
        for x in matches:
            number=str(x["permit_number"])
            priority=1 if x.get("permit_kind")=="ROOF_CANDIDATE_PENDING_DOCUMENT_REVIEW" else 12
            task(tasks,kind="ORIGINAL_ISSUER_PERMIT_DOCUMENT",parcel=p,
                 status="SOURCE_BLOCKED" if portal_blocked else "AWAITING_AUTHORIZED_PROVIDER",
                 authority="City of Eagan",source_url="https://eagan.onlama.com/Search.aspx",priority=priority,
                 source_record_id=number,evidence_stage="OWNER_PROVIDED_REPORT_MATCH_NOT_CITY_DOCUMENT_VERIFIED",
                 action="Request issuer-issued permit PDF, work scope, inspection events and final result for permit "+number,
                 requirements=["city-issued document or official permit detail URL","permit number matches issuer",
                               "parcel address/PIN reconciled","scope as issued","dated inspection results",
                               "independent named reviewer","source capture SHA-256"])
        if not address_ok:
            task(tasks,kind="ADDRESS_GIS_RECONCILIATION",parcel=p,
                 status="OPEN",authority="Metropolitan Council / City of Eagan",
                 source_url="https://arcgis.metc.state.mn.us/server/rest/services/GISLibrary/VWAddressPointsCommons/FeatureServer/0/query",
                 priority=15,automatable=True,
                 action="Re-query exact municipal street number/name; reconcile missing GIS point without inventing USPS deliverability",
                 requirements=["official point ID or documented nonmatch","exact house/street normalization","county PIN cross-check"])
        if not value_ok:
            task(tasks,kind="OFFICIAL_ASSESSMENT_RECORD",parcel=p,status="OPEN",priority=19,
                 authority="City of Eagan",automatable=True,
                 source_url="https://gis.cityofeagan.com/arcgis/rest/services/EA_PropertyInformation/MapServer/19/query",
                 action="Re-query Eagan public parcel GIS for the exact county PIN and source-backed valuation",
                 requirements=["original municipal GIS parcel","exact county PIN","source record ID","recorded amount"])
        if not year_proven:
            task(tasks,kind="ASSESSMENT_YEAR_PROVENANCE",parcel=p,status="AWAITING_AUTHORIZED_PROVIDER",
                 authority="City of Eagan / Dakota County Assessor",priority=28,
                 source_url="https://www.eaganmn.gov/buildinginspections",
                 action="Obtain authoritative valuation assessment year; the current map layer does not publish it",
                 requirements=["assessor valuation effective/tax year","source document or schema field","human reconciliation"])
        if not image_ok:
            task(tasks,kind="GOVERNMENT_AERIAL_SOURCE_RECHECK",parcel=p,status="OPEN",priority=24,
                 authority="Minnesota Geospatial Information Office",automatable=True,
                 source_url="https://imageserver.gisdata.mn.gov/cgi-bin/wmsll",
                 action="Fetch verified official WMS JPEG from parcel bounding box; retain SHA-256 and acquisition date",
                 requirements=["valid JPEG markers","byte length","SHA-256","layer/date","parcel bounding box"])
        task(tasks,kind="AERIAL_COMMERCIAL_RIGHTS_REVIEW",parcel=p,status="AWAITING_HUMAN_EVIDENCE",priority=36,
             authority="MnGeo / underlying image rights holder",
             source_url="https://mn.gov/mngeo/gis-data-and-maps/web-map-services/mngeo-image-service/",
             action="Review rights for commercial processing, screenshots, redistribution and customer-facing reuse of the exact aerial layer",
             requirements=["layer-specific license/source metadata","permitted commercial uses","attribution","reviewer and written permission if necessary"])
        task(tasks,kind="PHYSICAL_ROOF_CONDITION_REVIEW",parcel=p,status="AWAITING_HUMAN_EVIDENCE",priority=45,
             authority="Qualified human property-condition reviewer",
             source_url="https://www.eaganmn.gov/buildinginspections",
             action="Obtain dated, authorized roof evidence/inspection; distinguish image visibility from actual roof condition",
             requirements=["specific dated image or site inspection","location/parcel attribution","condition observations",
                           "reviewer credential/identity","reviewer timestamp","limitations and uncertainty"])
        task(tasks,kind="EVIDENCE_SUPPORTED_MINDEX",parcel=p,status="AWAITING_HUMAN_EVIDENCE",priority=55,
             authority="AeroLeadAI GateKeeper release authority",
             source_url="https://www.eaganmn.gov/buildinginspections",
             action="Score only after reviewer-approved condition and permit coverage; current Mindex must remain NULL",
             requirements=["named verified source references","documented scoring rubric/version","reviewer-approved inputs",
                           "no contradictory evidence","audit trail and human release decision"])
    ids=[x["task_id"] for x in tasks]
    if len(ids)!=len(set(ids)):raise ValueError("Duplicate certification task IDs")
    tasks.sort(key=lambda x:(x["priority"],x["county_pin"],x["kind"],x["source_record_id"] or ""))
    counts=dict(collections.Counter(x["kind"] for x in tasks))
    source_status={c["key"]:("SOURCE_BLOCKED" if portal_blocked and c["key"] in ("eagan_open_data","eagan_issuer_documents")
                             else "PUBLIC_SOURCE_CONFIGURED" if c["mode"].startswith("AUTHORIZED_PUBLIC_ARCGIS")
                             else "HUMAN_OR_RIGHTS_GATE_REQUIRED") for c in SOURCE_CATALOG}
    now=utc()
    summary={
        "generated_at_utc":now,"version":"GATEKEEPER_CERTIFICATION_GAP_V1",
        "territory":"kings-wood-001","original_residential_parcels":len(parcels),
        "export_report_matches_pending_document_review":len(permit_rows),
        "properties_with_export_matches":len(permits),
        "priority_roof_2025_candidates":sum(x.get("permit_kind")=="ROOF_CANDIDATE_PENDING_DOCUMENT_REVIEW" for x in permit_rows),
        "gis_address_matched":sum(x["gates"]["address_source_matched"] for x in parcel_evidence),
        "valuation_source_matched":sum(x["gates"]["valuation_source_recorded"] for x in parcel_evidence),
        "assessment_year_proven":sum(x["gates"]["valuation_assessment_year_verified"] for x in parcel_evidence),
        "remote_wms_image_hashes":sum(x["gates"]["government_image_response_hash_recorded"] for x in parcel_evidence),
        "original_issuer_permit_documents_reviewed":0,"human_reviewed_roof_conditions":0,
        "certified_mindex_scores":0,"full_property_certifications":0,
        "public_eagan_portal_403_observed":portal_blocked,
        "portal_source_run_at_utc":crawl.get("run_utc"),
        "release_certified":False,
        "task_count":len(tasks),"open_tasks_by_kind":dict(sorted(counts.items())),
        "source_catalog":[{**s,"current_operational_state":source_status[s["key"]]} for s in SOURCE_CATALOG],
        "data_not_found_means_unknown":True,
        "note":"City export matches are candidates, not final roof inspections; a remote JPEG is not a roof-condition finding. This queue plans authorized searches, not 1:1 human-complete investigations.",
        "next_actions":[
          "Obtain issuer permit documents/inspection outcomes for 25 export matches, starting with the single explicit 2025 roofing candidate",
          "Ask City for complete permit histories of the original 60 and covered date ranges under the Minnesota Government Data Practices Act",
          "Reconcile 4 missing GIS address matches and 4 missing valuations; request assessment-year provenance",
          "Acquire authorized dated roof-specific review evidence and explicit image licensing before Mindex certification"
        ]
    }
    rows=[]
    for t in tasks:
        if t["kind"]=="ORIGINAL_ISSUER_PERMIT_DOCUMENT":
            rows.append({k:t[k] for k in ("task_id","priority","parcel_objectid","county_pin","address","source_record_id","status","official_source_url","next_action")})
    result={"generated_at_utc":now,"version":summary["version"],
            "territory":summary["territory"],
            "tasks":tasks,"per_property_truth":parcel_evidence,
            "certificate_count":0,"warning":"All tasks are actionable UNKNOWN/BLOCKED work; none is automatically certified."}
    return summary,result,rows

def publish(directory=D):
    summary,index,rows=compile_gap_index(directory)
    directory.mkdir(parents=True,exist_ok=True)
    (directory/"certification_gap_summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    (directory/"certification_gap_queue.json").write_text(json.dumps(index,indent=2)+"\n",encoding="utf-8")
    buff=io.StringIO()
    columns=["task_id","priority","parcel_objectid","county_pin","address","source_record_id","status","official_source_url","next_action"]
    writer=csv.DictWriter(buff,fieldnames=columns)
    writer.writeheader();writer.writerows(rows)
    (directory/"permit_issuer_review_queue.csv").write_text(buff.getvalue(),encoding="utf-8")
    print(json.dumps({"properties":summary["original_residential_parcels"],
         "source_backed_export_matches":summary["export_report_matches_pending_document_review"],
         "tasks":summary["task_count"],"certificates":0,
         "priority_2025_roof_cases":summary["priority_roof_2025_candidates"],
         "eagan_portal_blocked":summary["public_eagan_portal_403_observed"]}))
    return summary,index,rows

if __name__=="__main__":
    a=argparse.ArgumentParser()
    a.add_argument("--data-dir",type=pathlib.Path,default=D)
    args=a.parse_args()
    publish(args.data_dir)
